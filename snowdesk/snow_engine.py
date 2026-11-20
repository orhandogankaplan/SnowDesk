"""
60 FPS Full-Featured Realistic & Tech Snow Engine for SnowDesk:
- Zero-glue window snow detachment + falling icicles + keystroke micro-quake
- Window shake snowglobe vortex + mini window skier/sledder
- Subwoofer bass-reactive jumping snow granules (accumulated pile stays grounded, snow hops to the beat!)
- Thermal cursor heat (melting snow into water droplets & steam)
- Microphone blow detection (splashes snowdrifts & gusts flakes)
- Snowman snowball fight (deflect incoming snowballs with fast cursor!)
- Night shooting stars, New Year fireworks, Santa Sleigh Now-Playing banner, Reels Demo Mode (F11)
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

from .win32_tracker import SurfaceRect


PRESETS = {
    "gentle": {"count": 190, "speed": 1.0, "accum_gain": 1.15, "wind_scale": 0.7},
    "cozy": {"count": 330, "speed": 1.18, "accum_gain": 1.6, "wind_scale": 1.0},
    "blizzard": {"count": 540, "speed": 1.5, "accum_gain": 2.3, "wind_scale": 2.1},
}
PRESET_ORDER = ["gentle", "cozy", "blizzard"]
THEMES = ["classic", "aurora", "cyber", "gold"]


@dataclass
class Flake:
    x: float
    y: float
    vx: float
    vy: float
    radius: float
    alpha: int
    layer: int
    phase: float
    sway_amp: float
    sway_speed: float
    angle: float = 0.0
    spin: float = 0.0
    is_shed: bool = False
    mass: float = 1.4


@dataclass
class BassHopParticle:
    """Snow granule launched straight up from an accumulated snowdrift by music bass."""
    x: float
    y: float
    floor_y: float
    vx: float
    vy: float
    radius: float
    life: float = 1.1


@dataclass
class SoftParticle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    size: float
    kind: str  # "spark" | "smoke" | "breath" | "mist" | "gold" | "droplet" | "steam" | "fw"
    color_idx: int = 0


@dataclass
class ShootingStar:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float


@dataclass
class FireworkRocket:
    x: float
    y: float
    vx: float
    vy: float
    target_y: float
    color_idx: int


@dataclass
class Skier:
    x: float
    y: float
    vx: float
    vy: float
    dir_x: float
    resting_hwnd: Optional[int] = None


@dataclass
class Icicle:
    hwnd: int
    offset_x: float
    x: float
    y: float
    length: float
    vy: float = 0.0
    falling: bool = False


@dataclass
class PineTree:
    x: float
    scale: float
    snow_cover: float = 0.65
    sway: float = 0.0


@dataclass
class Snowman:
    id: int
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    scarf_red: bool = True
    held: bool = False
    resting_hwnd: Optional[int] = None
    hat_tilt: float = 0.0
    breath_cd: float = 2.0
    throw_cd: float = 9.0


@dataclass
class Snowball:
    id: int
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    radius: float = 7.0
    held: bool = True
    resting_hwnd: Optional[int] = None
    from_snowman: bool = False


class SurfaceDrift:
    BIN_W = 5.0
    MAX_DEPTH = 26.0

    def __init__(self, hwnd: int, left: float, top: float, right: float, is_taskbar: bool):
        self.hwnd = hwnd
        self.left = left
        self.top = top
        self.right = right
        self.is_taskbar = is_taskbar
        n_bins = max(4, int(math.ceil((right - left) / self.BIN_W)))
        self.bins: List[float] = [0.0] * n_bins
        self.hop_y: List[float] = [0.0] * n_bins
        self.hop_vy: List[float] = [0.0] * n_bins
        self.visible_spans: List[Tuple[float, float]] = [(left, right)]
        p1 = random.uniform(0.0, math.tau)
        p2 = random.uniform(0.0, math.tau)
        for i in range(2, max(2, n_bins - 2)):
            wave = 4.2 + 3.2 * math.sin(i * 0.14 + p1) + 1.8 * math.cos(i * 0.31 + p2)
            self.bins[i] = max(1.5, wave)

    def resize_or_move(
        self, new_left: float, new_top: float, new_right: float, spans: List[Tuple[float, float]]
    ) -> Tuple[float, float, float, float, List[Tuple[float, float, float]]]:
        old_left = self.left
        old_top = self.top
        old_right = self.right
        dx = new_left - old_left
        dy = new_top - old_top
        trimmed_clumps: List[Tuple[float, float, float]] = []
        new_n = max(4, int(math.ceil((new_right - new_left) / self.BIN_W)))
        if new_n != len(self.bins):
            old = self.bins
            old_n = len(old)
            # If window shrunk, shed the overhanging snow bins instead of compressing them away
            for i in range(0, old_n, 2):
                bx = old_left + i * self.BIN_W
                if (bx < new_left - 2.0 or bx > new_right + 2.0) and old[i] > 0.6:
                    trimmed_clumps.append((bx, old_top - old[i] * 0.5, old[i]))
            new_bins = [0.0] * new_n
            for i in range(new_n):
                wx = new_left + i * self.BIN_W
                oi = int((wx - old_left) / self.BIN_W)
                if 0 <= oi < old_n:
                    new_bins[i] = old[oi]
            self.bins = new_bins
            self.hop_y = [0.0] * new_n
            self.hop_vy = [0.0] * new_n
        self.left = new_left
        self.top = new_top
        self.right = new_right
        self.visible_spans = spans
        return dx, dy, old_left, old_top, trimmed_clumps

    def is_x_visible(self, x: float) -> bool:
        for s1, s2 in self.visible_spans:
            if s1 <= x <= s2:
                return True
        return False

    def depth_at(self, x: float) -> float:
        idx = int((x - self.left) / self.BIN_W)
        if 0 <= idx < len(self.bins):
            return self.bins[idx]
        return 0.0

    def deposit(self, x: float, amount: float) -> None:
        idx = int((x - self.left) / self.BIN_W)
        if not (0 <= idx < len(self.bins)):
            return
        self.bins[idx] = min(self.MAX_DEPTH, self.bins[idx] + amount)
        for off, w in ((-1, 0.58), (1, 0.58), (-2, 0.28), (2, 0.28), (-3, 0.12), (3, 0.12)):
            ni = idx + off
            if 0 <= ni < len(self.bins):
                self.bins[ni] = min(self.MAX_DEPTH, self.bins[ni] + amount * w)

    def melt_at(self, x: float, amount: float) -> bool:
        idx = int((x - self.left) / self.BIN_W)
        melted = False
        for off in (-2, -1, 0, 1, 2):
            ni = idx + off
            if 0 <= ni < len(self.bins) and self.bins[ni] > 0.3:
                self.bins[ni] = max(0.0, self.bins[ni] - amount * (1.0 - abs(off) * 0.25))
                melted = True
        return melted

    def scoop_at(self, x: float, radius_px: float = 22.0) -> float:
        center_idx = int((x - self.left) / self.BIN_W)
        span = max(1, int(radius_px / self.BIN_W))
        scooped = 0.0
        for i in range(max(0, center_idx - span), min(len(self.bins), center_idx + span + 1)):
            if self.bins[i] > 0.2:
                take = self.bins[i] * 0.72
                self.bins[i] -= take
                if self.bins[i] < 0.4:
                    self.bins[i] = 0.0
                scooped += take
        return scooped

    def clear_range(self, x1: float, x2: float) -> List[Tuple[float, float]]:
        sprayed: List[Tuple[float, float]] = []
        i1 = max(0, int((x1 - self.left) / self.BIN_W))
        i2 = min(len(self.bins) - 1, int((x2 - self.left) / self.BIN_W))
        for i in range(i1, i2 + 1):
            if self.bins[i] > 1.0:
                if i % 2 == 0:
                    sprayed.append((self.left + i * self.BIN_W, self.top - self.bins[i]))
                self.bins[i] = 0.0
        return sprayed

    def relax(self) -> List[Tuple[float, float, float]]:
        spills: List[Tuple[float, float, float]] = []
        n = len(self.bins)
        if n < 3:
            return spills
        for i in range(1, n - 1):
            avg = (self.bins[i - 1] + self.bins[i] * 2.0 + self.bins[i + 1]) * 0.25
            self.bins[i] = self.bins[i] * 0.88 + avg * 0.12

        if not self.is_taskbar:
            if self.bins[0] > 3.2 and random.random() < 0.28:
                self.bins[0] -= 1.2
                spills.append((self.left - 3.0, self.top - self.bins[0], -1.0))
            if self.bins[-1] > 3.2 and random.random() < 0.28:
                self.bins[-1] -= 1.2
                spills.append((self.right + 3.0, self.top - self.bins[-1], 1.0))

        self.bins[0] *= 0.90
        self.bins[-1] *= 0.90
        return spills

    def impulse_bass(self, strength: float, time_acc: float) -> None:
        n = len(self.bins)
        for i in range(1, n - 1):
            if self.bins[i] > 0.8:
                wave = 0.55 + 0.45 * abs(math.sin(i * 0.28 + time_acc * 12.0))
                self.hop_vy[i] += strength * 135.0 * wave

    def step_hop(self, dt: float) -> None:
        n = len(self.bins)
        k = 190.0
        damp = max(0.0, 1.0 - dt * 8.5)
        for i in range(n):
            if self.hop_y[i] != 0.0 or self.hop_vy[i] != 0.0:
                self.hop_vy[i] -= self.hop_y[i] * k * dt
                self.hop_vy[i] *= damp
                self.hop_y[i] += self.hop_vy[i] * dt
                if self.hop_y[i] < 0.0:
                    self.hop_y[i] = 0.0
                    self.hop_vy[i] = max(0.0, -self.hop_vy[i] * 0.25)
                if abs(self.hop_y[i]) < 0.05 and abs(self.hop_vy[i]) < 0.5:
                    self.hop_y[i] = 0.0
                    self.hop_vy[i] = 0.0

    def has_snow(self) -> bool:
        return any(b > 0.5 for b in self.bins)


class SnowEngine:
    def __init__(
        self,
        width: float,
        height: float,
        preset: str = "cozy",
        on_sound: Optional[Callable[[str], None]] = None,
    ):
        self.width = max(100.0, width)
        self.height = max(100.0, height)
        self.preset_name = preset if preset in PRESETS else "cozy"
        self.theme = "classic"
        self.paused = False
        self.mouse_breeze = True
        self.fairy_lights = True
        self.show_hud = False
        self.show_aurora = True
        self.fullscreen_pause = False
        self.sound_enabled = True
        self.on_sound = on_sound
        self.global_wind = 0.0
        self.time_acc = 0.0

        # Live sensor telemetry
        self.cpu_pct = 12.0
        self.ram_pct = 40.0
        self.battery_pct = 100
        self.ac_online = True
        self.mic_level = 0.0
        self.audio_peak = 0.0
        self._audio_avg = 0.04
        self.bass_pulse = 0.0  # 0..1 subwoofer glow/vibration pulse under snowdrifts
        self._beat_cd = 0.0
        self.now_playing = ""
        self.weather_wind_kmh = 10.0
        self.weather_label = "Açık"
        self.fps = 60.0
        self._mic_gust_cd = 0.0

        # Demo Mode (F11)
        self.demo_active = False
        self.demo_timer = 0.0

        hr = datetime.now().hour
        self.is_evening = (hr >= 17 or hr < 7)

        self.plow_auto = False
        self.plow_x = 28.0
        self.taskbar_top = height - 48.0

        self.santa_active = False
        self.santa_x = -460.0
        self.santa_y = 110.0
        self.santa_timer = 14.0

        self.lamp_x = 84.0
        self.cabin_x = max(360.0, width - 135.0)
        self._smoke_timer = 0.0
        self._droplet_timer = 0.0
        self._star_timer = 4.0
        self._skier_timer = 11.0
        self._newyear_fired_year: Optional[int] = None
        self.score = 0

        self.flakes: List[Flake] = []
        self.bass_hops: List[BassHopParticle] = []
        self.particles: List[SoftParticle] = []
        self.shooting_stars: List[ShootingStar] = []
        self.rockets: List[FireworkRocket] = []
        self.skiers: List[Skier] = []
        self.icicles: List[Icicle] = []
        self.drifts: Dict[int, SurfaceDrift] = {}
        self.occluders: List[Tuple[float, float, float, float]] = []
        self.snowmen: List[Snowman] = []
        self.snowballs: List[Snowball] = []
        self.trees: List[PineTree] = [
            PineTree(x=115.0, scale=0.92, snow_cover=0.7),
            PineTree(x=152.0, scale=0.75, snow_cover=0.65),
            PineTree(x=max(260.0, width - 225.0), scale=1.0, snow_cover=0.75),
            PineTree(x=max(300.0, width - 185.0), scale=0.80, snow_cover=0.7),
        ]
        self._next_id = 1
        self._spawned_hwnds: set[int] = set()
        self._shake_state: Dict[int, Tuple[int, int, float]] = {}  # hwnd -> (last_sign, count, expire_t)

        self.mouse_x = width * 0.5
        self.mouse_y = height * 0.5
        self._last_mouse: Tuple[float, float] | None = None
        self._mouse_vx = 0.0
        self._mouse_vy = 0.0
        self._drag_target: Optional[Tuple[str, int]] = None

        self._sync_flake_count(scatter_y=True)

    def _play_sfx(self, name: str) -> None:
        if self.sound_enabled and self.on_sound is not None:
            self.on_sound(name)

    def set_screen_size(self, width: float, height: float) -> None:
        self.width = max(100.0, width)
        self.height = max(100.0, height)
        self.cabin_x = max(360.0, width - 135.0)

    def cycle_preset(self) -> str:
        idx = (PRESET_ORDER.index(self.preset_name) + 1) % len(PRESET_ORDER)
        self.preset_name = PRESET_ORDER[idx]
        self._sync_flake_count(scatter_y=False)
        return self.preset_name

    def cycle_theme(self) -> str:
        idx = (THEMES.index(self.theme) + 1) % len(THEMES)
        self.theme = THEMES[idx]
        if self.theme == "aurora":
            self.show_aurora = True
        return self.theme

    def trigger_santa(self) -> None:
        self.santa_active = True
        self.santa_x = -460.0
        self.santa_y = random.uniform(75.0, min(210.0, self.height * 0.22))
        self._play_sfx("bells")

    def trigger_fireworks(self, count: int = 4) -> None:
        for i in range(count):
            rx = random.uniform(self.width * 0.15, self.width * 0.85)
            self.rockets.append(
                FireworkRocket(
                    x=rx,
                    y=self.taskbar_top - 4.0,
                    vx=random.uniform(-45.0, 45.0),
                    vy=random.uniform(-520.0, -420.0),
                    target_y=random.uniform(self.height * 0.14, self.height * 0.38),
                    color_idx=i % 4,
                )
            )
        self._play_sfx("bells")

    def trigger_keystroke_quake(self, fg_hwnd: Optional[int] = None) -> None:
        """Shake a few tiny snow clumps off the active foreground window when typing."""
        target = None
        if fg_hwnd and fg_hwnd in self.drifts and not self.drifts[fg_hwnd].is_taskbar:
            target = self.drifts[fg_hwnd]
        else:
            for d in self.drifts.values():
                if not d.is_taskbar and d.has_snow():
                    target = d
                    break
        if target is None or not target.has_snow():
            return
        for _ in range(2):
            idx = random.randint(0, len(target.bins) - 1)
            if target.bins[idx] > 1.2:
                target.bins[idx] = max(0.0, target.bins[idx] - 0.55)
                fx = target.left + idx * target.BIN_W
                if target.is_x_visible(fx):
                    self._spawn_falling_clump(fx, target.top - target.bins[idx], random.uniform(-18.0, 18.0), 15.0)

    def trigger_demo_mode(self) -> None:
        self.demo_active = True
        self.demo_timer = 0.0
        self.show_aurora = True
        self.fairy_lights = True
        self.trigger_santa()
        self.trigger_fireworks(3)

    def _make_flake(self, scatter_y: bool = False) -> Flake:
        cfg = PRESETS[self.preset_name]
        layer = random.choices([0, 1, 2], weights=[0.45, 0.37, 0.18])[0]
        if layer == 0:
            radius = random.uniform(1.0, 1.6)
            vy = random.uniform(42.0, 68.0) * cfg["speed"]
            alpha = random.randint(120, 175)
        elif layer == 1:
            radius = random.uniform(1.7, 2.5)
            vy = random.uniform(70.0, 105.0) * cfg["speed"]
            alpha = random.randint(175, 220)
        else:
            radius = random.uniform(2.8, 4.2)
            vy = random.uniform(95.0, 138.0) * cfg["speed"]
            alpha = random.randint(215, 250)

        return Flake(
            x=random.uniform(-20.0, self.width + 20.0),
            y=random.uniform(-20.0, self.height) if scatter_y else random.uniform(-45.0, -5.0),
            vx=random.uniform(-8.0, 8.0),
            vy=vy,
            radius=radius,
            alpha=alpha,
            layer=layer,
            phase=random.uniform(0.0, math.tau),
            sway_amp=random.uniform(12.0, 28.0),
            sway_speed=random.uniform(1.0, 2.2),
            angle=random.uniform(0.0, math.tau),
            spin=random.uniform(-1.8, 1.8) if layer == 2 else 0.0,
        )

    def _sync_flake_count(self, scatter_y: bool) -> None:
        target = PRESETS[self.preset_name]["count"]
        base_flakes = [f for f in self.flakes if not f.is_shed]
        shed_flakes = [f for f in self.flakes if f.is_shed]
        while len(base_flakes) < target:
            base_flakes.append(self._make_flake(scatter_y=scatter_y))
        if len(base_flakes) > target:
            base_flakes = base_flakes[:target]
        self.flakes = base_flakes + shed_flakes

    def _spawn_snow_burst(self, x: float, y: float, count: int = 10, vx_bias: float = 0.0, vy_bias: float = -40.0) -> None:
        for _ in range(count):
            if len(self.flakes) > 950:
                return
            self.flakes.append(
                Flake(
                    x=x + random.uniform(-8, 8),
                    y=y + random.uniform(-6, 4),
                    vx=vx_bias + random.uniform(-90.0, 90.0),
                    vy=vy_bias + random.uniform(-50.0, 80.0),
                    radius=random.uniform(1.5, 2.9),
                    alpha=random.randint(190, 245),
                    layer=1,
                    phase=random.uniform(0.0, math.tau),
                    sway_amp=12.0,
                    sway_speed=2.0,
                    is_shed=True,
                )
            )

    def _trigger_window_vortex(self, drift: SurfaceDrift) -> None:
        """Snowglobe shake vortex around a rapidly shaken window."""
        cx = (drift.left + drift.right) * 0.5
        cy = drift.top + 80.0
        w = max(80.0, drift.right - drift.left)
        for _ in range(42):
            if len(self.flakes) > 950:
                break
            ang = random.uniform(0.0, math.tau)
            rx = cx + math.cos(ang) * (w * 0.45 * random.uniform(0.5, 1.1))
            ry = cy + math.sin(ang) * random.uniform(40.0, 140.0)
            # Tangential swirl velocity
            vx = -math.sin(ang) * random.uniform(180.0, 340.0)
            vy = math.cos(ang) * random.uniform(120.0, 240.0) - 90.0
            self.flakes.append(
                Flake(
                    x=rx,
                    y=ry,
                    vx=vx,
                    vy=vy,
                    radius=random.uniform(1.8, 3.4),
                    alpha=random.randint(205, 250),
                    layer=1,
                    phase=random.uniform(0.0, math.tau),
                    sway_amp=16.0,
                    sway_speed=2.4,
                    is_shed=True,
                )
            )
        self._play_sfx("bells")

    def update_surfaces(
        self,
        surfaces: List[SurfaceRect],
        occluders: List[Tuple[float, float, float, float]] | None = None,
    ) -> None:
        if occluders is not None:
            self.occluders = occluders

        seen_hwnds = set()
        for surf in surfaces:
            seen_hwnds.add(surf.hwnd)
            if surf.is_taskbar:
                self.taskbar_top = surf.top

            spans = surf.visible_spans or [(surf.left, surf.right)]
            if surf.hwnd in self.drifts:
                drift = self.drifts[surf.hwnd]
                dx, dy, old_left, old_top, trimmed = drift.resize_or_move(surf.left, surf.top, surf.right, spans)
                for tx, ty, tval in trimmed:
                    self._spawn_falling_clump(tx, ty, random.uniform(-25.0, 25.0), 30.0, mass=tval * 0.85)

                # Detect rapid left-right window shake -> Snowglobe Vortex!
                if not surf.is_taskbar and abs(dx) > 14.0:
                    sign = 1 if dx > 0 else -1
                    last_sign, cnt, exp_t = self._shake_state.get(surf.hwnd, (0, 0, 0.0))
                    if self.time_acc > exp_t:
                        cnt = 0
                    if sign != last_sign:
                        cnt += 1
                        self._shake_state[surf.hwnd] = (sign, cnt, self.time_acc + 0.40)
                        if cnt >= 3:
                            self._shake_state[surf.hwnd] = (sign, 0, 0.0)
                            self._trigger_window_vortex(drift)

                if dy > 1.5 and drift.has_snow():
                    for i in range(0, len(drift.bins), 2):
                        val = drift.bins[i]
                        if val > 0.6:
                            self._spawn_falling_clump(old_left + i * drift.BIN_W, old_top - val * 0.5, -dx * 0.5, 35.0, mass=val * 0.75)
                    drift.bins = [0.0] * len(drift.bins)
                elif dy < -2.0 and drift.has_snow():
                    for i in range(0, len(drift.bins), 2):
                        val = drift.bins[i]
                        if val > 0.6 and random.random() < 0.7:
                            drift.bins[i] *= 0.35
                            self._spawn_falling_clump(old_left + i * drift.BIN_W, old_top - val, -dx * 0.8, -80.0, mass=val * 0.6)
                elif abs(dx) > 1.5 and drift.has_snow():
                    n_bins = len(drift.bins)
                    bin_shift = int(round(dx / drift.BIN_W))
                    new_bins = [0.0] * n_bins
                    keep_ratio = max(0.20, 0.78 - abs(dx) * 0.035)
                    for i in range(n_bins):
                        val = drift.bins[i]
                        if val <= 0.4:
                            continue
                        dest = i - bin_shift
                        if 0 <= dest < n_bins:
                            kept = val * keep_ratio
                            new_bins[dest] = kept
                            if (val - kept) > 0.4 and i % 2 == 0:
                                bx = old_left + i * drift.BIN_W
                                # Pour sideways toward neighboring windows or downward
                                self._spawn_falling_clump(bx, old_top - val * 0.5, -dx * 1.6, 20.0, mass=(val - kept) * 1.1)
                        else:
                            bx = old_left + i * drift.BIN_W
                            self._spawn_falling_clump(bx, old_top - val * 0.5, -dx * 1.8, 25.0, mass=val * 0.9)
                    drift.bins = new_bins

                    # Direct window-to-window snow flow when sliding near/next to another window
                    edge_x = drift.right if dx > 0 else drift.left
                    for other in self.drifts.values():
                        if other.hwnd == drift.hwnd:
                            continue
                        if abs(other.top - drift.top) < 42.0:
                            if (other.left - 35.0) <= edge_x <= (other.right + 35.0):
                                pour_x = max(other.left + 6.0, min(other.right - 6.0, edge_x))
                                other.deposit(pour_x, min(3.5, abs(dx) * 0.25))
                                self._spawn_falling_clump(pour_x, min(drift.top, other.top) - 6.0, dx * 2.2, 10.0, mass=2.5)

                move_mag = abs(dx) + abs(dy)
                for ic in self.icicles:
                    if not ic.falling and ic.hwnd == surf.hwnd:
                        ic.x = surf.left + ic.offset_x
                        ic.y = surf.top + 1.0
                        if move_mag > 10.0:
                            ic.falling = True
                            self._play_sfx("crunch")

                if abs(dx) > 1.5 or abs(dy) > 1.5:
                    for sm in self.snowmen:
                        if not sm.held and sm.resting_hwnd == surf.hwnd:
                            if dy > 2.5 or abs(dx) > 9.0:
                                sm.resting_hwnd = None
                                sm.vx = -dx * 1.8
                            else:
                                sm.x += dx * 0.2
                                sm.vx -= dx * 2.5
                                sm.y = surf.top - drift.depth_at(sm.x) * 0.55
                    for sb in self.snowballs:
                        if not sb.held and sb.resting_hwnd == surf.hwnd:
                            if dy > 2.5 or abs(dx) > 8.0:
                                sb.resting_hwnd = None
                                sb.vx = -dx * 1.8
                            else:
                                sb.x += dx * 0.2
                                sb.vx -= dx * 2.5
                                sb.y = surf.top - sb.radius * 0.65
            else:
                self.drifts[surf.hwnd] = SurfaceDrift(
                    surf.hwnd, surf.left, surf.top, surf.right, surf.is_taskbar
                )
                self.drifts[surf.hwnd].visible_spans = spans
                if not surf.is_taskbar and surf.hwnd not in self._spawned_hwnds and (surf.right - surf.left) > 240:
                    self._spawned_hwnds.add(surf.hwnd)
                    w_len = surf.right - surf.left
                    for off in (18.0, 34.0, w_len - 34.0, w_len - 18.0):
                        if 8.0 < off < w_len - 8.0 and len(self.icicles) < 28:
                            self.icicles.append(
                                Icicle(
                                    hwnd=surf.hwnd,
                                    offset_x=off,
                                    x=surf.left + off,
                                    y=surf.top + 1.0,
                                    length=random.uniform(9.0, 18.0),
                                )
                            )
                    if len(self.snowmen) < 6:
                        s1, s2 = spans[0]
                        if (s2 - s1) > 180:
                            self.snowmen.append(
                                Snowman(
                                    id=self._next_id,
                                    x=s1 + (s2 - s1) * 0.62,
                                    y=surf.top - 4.0,
                                    scarf_red=True,
                                    resting_hwnd=surf.hwnd,
                                    throw_cd=random.uniform(7.0, 14.0),
                                )
                            )
                            self._next_id += 1

        gone = [h for h in self.drifts if h not in seen_hwnds]
        for h in gone:
            drift = self.drifts.pop(h)
            self._shake_state.pop(h, None)
            if drift.has_snow():
                self._shed_drift_as_flakes(drift)
            for ic in self.icicles:
                if ic.hwnd == h:
                    ic.falling = True
            for sm in self.snowmen:
                if sm.resting_hwnd == h:
                    sm.resting_hwnd = None
            for sb in self.snowballs:
                if sb.resting_hwnd == h:
                    sb.resting_hwnd = None
            for sk in self.skiers:
                if sk.resting_hwnd == h:
                    sk.resting_hwnd = None

    def _spawn_falling_clump(self, x: float, y: float, vx: float, vy_init: float, mass: float = 2.2) -> None:
        if len(self.flakes) > 950:
            return
        self.flakes.append(
            Flake(
                x=x + random.uniform(-4, 4),
                y=y + random.uniform(-3, 3),
                vx=max(-220.0, min(220.0, vx + random.uniform(-24.0, 24.0))),
                vy=vy_init + random.uniform(35.0, 95.0),
                radius=random.uniform(1.8, 3.4),
                alpha=random.randint(205, 250),
                layer=1,
                phase=random.uniform(0.0, math.tau),
                sway_amp=8.0,
                sway_speed=2.0,
                is_shed=True,
                mass=max(1.2, min(6.5, mass)),
            )
        )

    def _shed_drift_as_flakes(self, drift: SurfaceDrift) -> None:
        for i in range(0, len(drift.bins)):
            depth = drift.bins[i]
            if depth < 0.7:
                continue
            fx = drift.left + i * drift.BIN_W
            self._spawn_falling_clump(fx, drift.top - random.uniform(1, depth), random.uniform(-18.0, 18.0), 30.0, mass=depth * 0.85)

    def clear_all_snow(self) -> None:
        self.plow_auto = True
        self.plow_x = -80.0
        for ic in self.icicles:
            ic.falling = True
        self._play_sfx("crunch")

    def is_point_interactive(self, mx: float, my: float) -> bool:
        if self._drag_target is not None:
            return True
        for sm in self.snowmen:
            if abs(mx - sm.x) <= 22.0 and (sm.y - 52.0) <= my <= (sm.y + 6.0):
                return True
        for sb in self.snowballs:
            if math.hypot(mx - sb.x, my - sb.y) <= sb.radius + 8.0:
                return True
        if (self.plow_x - 8.0) <= mx <= (self.plow_x + 62.0) and (self.taskbar_top - 40.0) <= my <= (self.taskbar_top + 6.0):
            return True
        for drift in self.drifts.values():
            if drift.left <= mx <= drift.right and drift.is_x_visible(mx):
                d = drift.depth_at(mx)
                if d > 1.5 and (drift.top - d - 8.0) <= my <= (drift.top + 3.0):
                    return True
        return False

    def handle_mouse(self, mx: float, my: float, lbutton_down: bool) -> None:
        if lbutton_down and self._drag_target is None:
            for sm in reversed(self.snowmen):
                if abs(mx - sm.x) <= 24.0 and (sm.y - 52.0) <= my <= (sm.y + 8.0):
                    sm.held = True
                    sm.resting_hwnd = None
                    self._drag_target = ("snowman", sm.id)
                    return
            for sb in reversed(self.snowballs):
                if math.hypot(mx - sb.x, my - sb.y) <= sb.radius + 9.0:
                    sb.held = True
                    sb.resting_hwnd = None
                    sb.from_snowman = False
                    self._drag_target = ("snowball", sb.id)
                    return
            if (self.plow_x - 10.0) <= mx <= (self.plow_x + 64.0) and (self.taskbar_top - 42.0) <= my <= (self.taskbar_top + 8.0):
                self.plow_held = True
                self.plow_auto = False
                self._drag_target = ("plow", 0)
                return
            for drift in self.drifts.values():
                if drift.left <= mx <= drift.right and drift.is_x_visible(mx):
                    d = drift.depth_at(mx)
                    if d > 1.2 and (drift.top - d - 10.0) <= my <= (drift.top + 5.0):
                        drift.scoop_at(mx, 22.0)
                        sb_id = self._next_id
                        self._next_id += 1
                        self.snowballs.append(Snowball(id=sb_id, x=mx, y=my, radius=7.5, held=True))
                        self._drag_target = ("snowball", sb_id)
                        return

        elif lbutton_down and self._drag_target is not None:
            kind, tid = self._drag_target
            if kind == "snowman":
                for sm in self.snowmen:
                    if sm.id == tid:
                        sm.x = mx
                        sm.y = my + 16.0
                        sm.vx = max(-750.0, min(750.0, self._mouse_vx * 0.6))
                        sm.vy = max(-750.0, min(750.0, self._mouse_vy * 0.6))
                        break
            elif kind == "plow":
                old_px = self.plow_x
                self.plow_x = max(0.0, min(self.width - 58.0, mx - 28.0))
                x_min = min(old_px, self.plow_x) - 4.0
                x_max = max(old_px, self.plow_x) + 58.0
                for drift in self.drifts.values():
                    if drift.is_taskbar:
                        sprayed = drift.clear_range(x_min, x_max)
                        for sx, sy in sprayed:
                            self._spawn_snow_burst(sx, sy, count=2, vx_bias=self._mouse_vx * 0.35, vy_bias=-65.0)
                for tr in self.trees:
                    if x_min <= tr.x <= x_max and tr.snow_cover > 0.1:
                        tr.snow_cover = 0.0
                        self._spawn_snow_burst(tr.x, self.taskbar_top - 26.0, count=6, vx_bias=self._mouse_vx * 0.3, vy_bias=-60.0)
            elif kind == "snowball":
                for sb in self.snowballs:
                    if sb.id == tid:
                        sb.x = mx
                        sb.y = my
                        sb.vx = max(-950.0, min(950.0, self._mouse_vx * 0.72))
                        sb.vy = max(-950.0, min(950.0, self._mouse_vy * 0.72))
                        for drift in self.drifts.values():
                            if drift.left <= mx <= drift.right and abs(my - drift.top) < 28.0:
                                vol = drift.scoop_at(mx, 20.0)
                                if vol > 0.2:
                                    sb.radius = min(17.0, sb.radius + vol * 0.12)
                        break

        elif not lbutton_down and self._drag_target is not None:
            kind, tid = self._drag_target
            if kind == "snowman":
                for sm in self.snowmen:
                    if sm.id == tid:
                        sm.held = False
                        break
            elif kind == "plow":
                self.plow_held = False
            elif kind == "snowball":
                for sb in self.snowballs:
                    if sb.id == tid:
                        sb.held = False
                        break
            self._drag_target = None

        elif not lbutton_down:
            speed_sq = self._mouse_vx * self._mouse_vx + self._mouse_vy * self._mouse_vy
            if speed_sq > 22000.0:
                for drift in self.drifts.values():
                    if drift.left <= mx <= drift.right and drift.is_x_visible(mx):
                        d = drift.depth_at(mx)
                        if d > 1.2 and (drift.top - d - 8.0) <= my <= (drift.top + 4.0):
                            vol = drift.scoop_at(mx, 18.0)
                            if vol > 0.5:
                                self._spawn_snow_burst(mx, drift.top - d * 0.5, count=3, vx_bias=self._mouse_vx * 0.25, vy_bias=-55.0)

    def _find_landing_surface(self, x: float, prev_y: float, new_y: float) -> Optional[SurfaceDrift]:
        best: Optional[SurfaceDrift] = None
        for drift in self.drifts.values():
            if drift.left <= x <= drift.right and drift.is_x_visible(x):
                land_y = drift.top - drift.depth_at(x) * 0.55
                if prev_y <= land_y + 10.0 and new_y >= land_y - 2.0:
                    if best is None or drift.top < best.top:
                        best = drift
        return best

    def _apply_mic_blow(self, level: float) -> None:
        """Splash snow upward & sideways on the side of the cursor when user blows/speaks into mic!"""
        cx = self.mouse_x
        self._play_sfx("crunch")
        for drift in self.drifts.values():
            for i in range(0, len(drift.bins), 3):
                bx = drift.left + i * drift.BIN_W
                if abs(bx - cx) < 420.0 * level and drift.bins[i] > 1.5:
                    take = drift.bins[i] * min(0.7, level * 0.8)
                    drift.bins[i] -= take
                    dir_x = 1.0 if bx >= cx else -1.0
                    self._spawn_snow_burst(bx, drift.top - drift.bins[i], count=2, vx_bias=dir_x * (180.0 * level), vy_bias=-160.0 * level)
        for f in self.flakes:
            dx = f.x - cx
            if abs(dx) < 550.0:
                dir_x = 1.0 if dx >= 0 else -1.0
                f.vx += dir_x * (260.0 * level)
                f.vy -= 110.0 * level

    def _spawn_bass_hops(self, strength: float) -> None:
        """Ripple accumulated snowdrifts with spring physics AND launch visible snow granules upward."""
        for drift in self.drifts.values():
            if not drift.has_snow():
                continue
            drift.impulse_bass(strength, self.time_acc)
            step_i = max(3, len(drift.bins) // 14)
            for i in range(1, len(drift.bins) - 1, step_i):
                depth = drift.bins[i]
                if depth > 1.0 and len(self.bass_hops) < 320:
                    bx = drift.left + i * drift.BIN_W + random.uniform(-2.0, 2.0)
                    if not drift.is_x_visible(bx):
                        continue
                    floor_y = drift.top - depth * 0.72
                    self.bass_hops.append(
                        BassHopParticle(
                            x=bx,
                            y=floor_y - 1.5,
                            floor_y=floor_y,
                            vx=random.uniform(-26.0, 26.0),
                            vy=-random.uniform(165.0, 315.0) * (0.55 + 0.65 * strength),
                            radius=random.uniform(2.0, 4.1),
                            life=1.2,
                        )
                    )

    def step(self, dt: float, mouse_pos: Tuple[float, float] | None, lbutton_down: bool = False) -> None:
        if self.paused:
            return
        dt = min(dt, 0.05)
        self.time_acc += dt
        if dt > 0:
            self.fps = self.fps * 0.9 + (1.0 / dt) * 0.1

        # New Year midnight auto-fireworks
        now_dt = datetime.now()
        if now_dt.month == 1 and now_dt.day == 1 and now_dt.hour == 0 and now_dt.minute == 0:
            if self._newyear_fired_year != now_dt.year:
                self._newyear_fired_year = now_dt.year
                self.trigger_fireworks(6)

        # Reels Demo Mode timeline
        if self.demo_active:
            prev_t = self.demo_timer
            self.demo_timer += dt
            if prev_t < 3.0 <= self.demo_timer:
                self.preset_name = "blizzard"
                self._sync_flake_count(scatter_y=False)
            elif prev_t < 6.0 <= self.demo_timer:
                self.clear_all_snow()
            elif self.demo_timer >= 9.0:
                self.demo_active = False
                self.preset_name = "cozy"
                self._sync_flake_count(scatter_y=False)

        # Music Bass / Beat Reaction: keep snowdrift grounded, launch visible snow granules upward!
        if self._beat_cd > 0.0:
            self._beat_cd -= dt
        self.bass_pulse *= max(0.0, 1.0 - dt * 9.0)
        self._audio_avg = self._audio_avg * 0.90 + self.audio_peak * 0.10
        beat_delta = self.audio_peak - self._audio_avg
        if (self.audio_peak > 0.08 and beat_delta > 0.028 or self.audio_peak > 0.42) and self._beat_cd <= 0.0:
            self._beat_cd = 0.11
            strength = min(1.0, max(0.35, beat_delta * 5.0 + self.audio_peak * 0.7))
            self.bass_pulse = max(self.bass_pulse, strength)
            self._spawn_bass_hops(strength)

        # Update bass-hopping snow granules (arc up with gravity, land back on snowdrift)
        next_hops: List[BassHopParticle] = []
        for hp in self.bass_hops:
            hp.life -= dt
            hp.vy += 840.0 * dt
            hp.x += hp.vx * dt
            hp.y += hp.vy * dt
            if hp.y < hp.floor_y and hp.life > 0.0:
                next_hops.append(hp)
        self.bass_hops = next_hops

        # Microphone blow reaction
        if self._mic_gust_cd > 0.0:
            self._mic_gust_cd -= dt
        if self.mic_level > 0.24 and self._mic_gust_cd <= 0.0:
            self._mic_gust_cd = 0.25
            self._apply_mic_blow(self.mic_level)

        if mouse_pos is not None:
            mx, my = mouse_pos
            self.mouse_x = mx
            self.mouse_y = my
            if self._last_mouse is not None:
                mvx = (mx - self._last_mouse[0]) / max(dt, 0.008)
                mvy = (my - self._last_mouse[1]) / max(dt, 0.008)
                self._mouse_vx = self._mouse_vx * 0.55 + max(-1100.0, min(1100.0, mvx)) * 0.45
                self._mouse_vy = self._mouse_vy * 0.55 + max(-1100.0, min(1100.0, mvy)) * 0.45
            self._last_mouse = (mx, my)
            self.handle_mouse(mx, my, lbutton_down)

            speed_sq = self._mouse_vx * self._mouse_vx + self._mouse_vy * self._mouse_vy
            if speed_sq > 95000.0 and len(self.particles) < 200 and random.random() < 0.65:
                self.particles.append(
                    SoftParticle(
                        x=mx + random.uniform(-6, 6),
                        y=my + random.uniform(-6, 6),
                        vx=-self._mouse_vx * 0.08 + random.uniform(-25, 25),
                        vy=-self._mouse_vy * 0.08 + random.uniform(-10, 30),
                        life=0.45,
                        max_life=0.45,
                        size=random.uniform(2.0, 3.8),
                        kind="spark",
                    )
                )

            # Thermal cursor heat: resting cursor slowly melts snow into water droplets & steam!
            if not lbutton_down and speed_sq < 2500.0:
                self._droplet_timer += dt
                if self._droplet_timer >= 0.14:
                    self._droplet_timer = 0.0
                    for drift in self.drifts.values():
                        if drift.left <= mx <= drift.right and abs(my - drift.top) < 20.0:
                            if drift.melt_at(mx, 0.85):
                                self.particles.append(
                                    SoftParticle(
                                        x=mx + random.uniform(-4, 4),
                                        y=drift.top + 2.0,
                                        vx=0.0,
                                        vy=random.uniform(75.0, 125.0),
                                        life=1.2,
                                        max_life=1.2,
                                        size=2.4,
                                        kind="droplet",
                                    )
                                )
                                self.particles.append(
                                    SoftParticle(
                                        x=mx + random.uniform(-5, 5),
                                        y=drift.top - 4.0,
                                        vx=random.uniform(-8, 8),
                                        vy=-24.0,
                                        life=0.65,
                                        max_life=0.65,
                                        size=3.0,
                                        kind="steam",
                                    )
                                )
                                break
        else:
            mx, my = -9999.0, -9999.0
            self._mouse_vx *= 0.8
            self._mouse_vy *= 0.8

        # Night shooting stars
        self._star_timer -= dt
        if self._star_timer <= 0.0:
            self._star_timer = random.uniform(5.5, 11.5)
            if self.is_evening or self.show_aurora:
                dir_x = 1.0 if random.random() < 0.6 else -1.0
                self.shooting_stars.append(
                    ShootingStar(
                        x=random.uniform(self.width * 0.1, self.width * 0.9),
                        y=random.uniform(18.0, min(170.0, self.height * 0.22)),
                        vx=dir_x * random.uniform(420.0, 650.0),
                        vy=random.uniform(140.0, 240.0),
                        life=0.65,
                        max_life=0.65,
                    )
                )

        next_stars: List[ShootingStar] = []
        for st in self.shooting_stars:
            st.life -= dt
            st.x += st.vx * dt
            st.y += st.vy * dt
            if st.life > 0.0:
                next_stars.append(st)
        self.shooting_stars = next_stars

        # Fireworks rockets
        next_rockets: List[FireworkRocket] = []
        for rk in self.rockets:
            rk.vy += 260.0 * dt
            rk.x += rk.vx * dt
            rk.y += rk.vy * dt
            if rk.y <= rk.target_y or rk.vy >= -40.0:
                for k in range(28):
                    ang = (k / 28.0) * math.tau + random.uniform(-0.1, 0.1)
                    spd = random.uniform(80.0, 220.0)
                    self.particles.append(
                        SoftParticle(
                            x=rk.x,
                            y=rk.y,
                            vx=math.cos(ang) * spd,
                            vy=math.sin(ang) * spd,
                            life=random.uniform(0.75, 1.25),
                            max_life=1.25,
                            size=random.uniform(2.2, 4.0),
                            kind="fw",
                            color_idx=rk.color_idx,
                        )
                    )
                self._play_sfx("crunch")
            else:
                next_rockets.append(rk)
        self.rockets = next_rockets

        # Mini Window Skier
        self._skier_timer -= dt
        if self._skier_timer <= 0.0 and len(self.skiers) == 0:
            self._skier_timer = random.uniform(18.0, 28.0)
            cands = [d for d in self.drifts.values() if not d.is_taskbar and d.has_snow() and d.visible_spans]
            if cands:
                d = random.choice(cands)
                s1, s2 = d.visible_spans[0]
                if (s2 - s1) > 150.0:
                    self.skiers.append(
                        Skier(
                            x=s1 + 10.0,
                            y=d.top - d.depth_at(s1 + 10.0) * 0.55,
                            vx=135.0,
                            vy=0.0,
                            dir_x=1.0,
                            resting_hwnd=d.hwnd,
                        )
                    )

        next_skiers: List[Skier] = []
        for sk in self.skiers:
            if sk.resting_hwnd is not None and sk.resting_hwnd in self.drifts:
                d = self.drifts[sk.resting_hwnd]
                if d.left <= sk.x <= d.right and d.is_x_visible(sk.x):
                    sk.x += sk.vx * dt
                    sk.y = d.top - d.depth_at(sk.x) * 0.6
                    if random.random() < 0.45 and len(self.particles) < 210:
                        self.particles.append(
                            SoftParticle(
                                x=sk.x - sk.dir_x * 8.0,
                                y=sk.y - 2.0,
                                vx=-sk.dir_x * random.uniform(20.0, 50.0),
                                vy=random.uniform(-35.0, -10.0),
                                life=0.35,
                                max_life=0.35,
                                size=2.2,
                                kind="spark",
                            )
                        )
                    next_skiers.append(sk)
                    continue
                else:
                    sk.resting_hwnd = None
                    sk.vy = -110.0  # Jump off window edge!

            prev_sy = sk.y
            sk.vy += 680.0 * dt
            sk.x += sk.vx * dt
            sk.y += sk.vy * dt
            if sk.vy >= 0:
                landed = self._find_landing_surface(sk.x, prev_sy, sk.y)
                if landed is not None:
                    sk.resting_hwnd = landed.hwnd
                    sk.y = landed.top - landed.depth_at(sk.x) * 0.6
                    sk.vy = 0.0
            if -30.0 <= sk.x <= self.width + 30.0 and sk.y <= self.height + 20.0:
                next_skiers.append(sk)
        self.skiers = next_skiers

        self._smoke_timer += dt
        if self._smoke_timer >= 0.42:
            self._smoke_timer = 0.0
            if len(self.particles) < 200:
                self.particles.append(
                    SoftParticle(
                        x=self.cabin_x + 42.0,
                        y=self.taskbar_top - 48.0,
                        vx=self.global_wind * 0.4 + random.uniform(-5, 8),
                        vy=random.uniform(-34.0, -22.0),
                        life=1.9,
                        max_life=1.9,
                        size=random.uniform(4.0, 6.5),
                        kind="smoke",
                    )
                )

        if abs(self.global_wind) > 10.0 and len(self.particles) < 200 and random.random() < 0.14:
            self.particles.append(
                SoftParticle(
                    x=random.uniform(0.0, self.width),
                    y=self.taskbar_top - random.uniform(2.0, 12.0),
                    vx=self.global_wind * 2.2 + random.uniform(15, 45),
                    vy=random.uniform(-8.0, 2.0),
                    life=1.1,
                    max_life=1.1,
                    size=random.uniform(8.0, 15.0),
                    kind="mist",
                )
            )

        if not self.santa_active:
            self.santa_timer -= dt
            if self.santa_timer <= 0.0:
                self.santa_timer = 28.0
                self.trigger_santa()
        else:
            self.santa_x += 235.0 * dt
            if len(self.particles) < 210 and random.random() < 0.75:
                self.particles.append(
                    SoftParticle(
                        x=self.santa_x + random.uniform(10.0, 80.0),
                        y=self.santa_y + random.uniform(40.0, 110.0),
                        vx=random.uniform(-45.0, -10.0),
                        vy=random.uniform(15.0, 45.0),
                        life=0.85,
                        max_life=0.85,
                        size=random.uniform(2.0, 4.2),
                        kind="gold",
                    )
                )
            if self.santa_x > self.width + 420.0:
                self.santa_active = False

        next_parts: List[SoftParticle] = []
        for p in self.particles:
            p.life -= dt
            if p.life > 0:
                if p.kind == "droplet":
                    p.vy += 280.0 * dt
                elif p.kind == "fw":
                    p.vy += 170.0 * dt
                    p.vx *= 0.98
                p.x += p.vx * dt
                p.y += p.vy * dt
                if p.kind in ("smoke", "breath", "steam"):
                    p.size += dt * 3.5
                    p.vx += self.global_wind * 0.25 * dt
                next_parts.append(p)
        self.particles = next_parts

        next_icicles: List[Icicle] = []
        for ic in self.icicles:
            if ic.falling:
                ic.vy += 680.0 * dt
                ic.y += ic.vy * dt
                if ic.y < self.height + 20.0:
                    next_icicles.append(ic)
            else:
                if ic.length < 22.0:
                    ic.length += dt * 0.15
                next_icicles.append(ic)
        self.icicles = next_icicles

        if self.plow_auto:
            self.plow_x += 920.0 * dt
            for drift in self.drifts.values():
                sprayed = drift.clear_range(self.plow_x - 10.0, self.plow_x + 56.0)
                for sx, sy in sprayed:
                    self._spawn_snow_burst(sx + 10.0, sy, count=2, vx_bias=240.0, vy_bias=-75.0)
            for tr in self.trees:
                if self.plow_x - 10.0 <= tr.x <= self.plow_x + 56.0 and tr.snow_cover > 0.1:
                    tr.snow_cover = 0.0
                    self._spawn_snow_burst(tr.x, self.taskbar_top - 26.0, count=7, vx_bias=220.0, vy_bias=-65.0)
            if self.plow_x > self.width + 90.0:
                self.plow_auto = False
                self.plow_x = 28.0

        for tr in self.trees:
            if tr.snow_cover < 1.0:
                tr.snow_cover = min(1.0, tr.snow_cover + dt * 0.035)
            tr.sway = math.sin(self.time_acc * 2.1 + tr.x * 0.05) * (0.04 + abs(self.global_wind) * 0.0025)

        surviving_snowmen: List[Snowman] = []
        for sm in self.snowmen:
            sm.hat_tilt *= max(0.0, 1.0 - dt * 1.5)
            sm.breath_cd -= dt
            if sm.breath_cd <= 0.0:
                sm.breath_cd = random.uniform(3.2, 6.0)
                if len(self.particles) < 200:
                    self.particles.append(
                        SoftParticle(
                            x=sm.x + 6.0,
                            y=sm.y - 28.0,
                            vx=16.0 + self.global_wind * 0.3,
                            vy=-10.0,
                            life=0.9,
                            max_life=0.9,
                            size=2.5,
                            kind="breath",
                        )
                    )

            # Snowman snowball fight: occasionally toss a snowball toward cursor
            if not sm.held and sm.resting_hwnd is not None and mouse_pos is not None:
                sm.throw_cd -= dt
                if sm.throw_cd <= 0.0:
                    sm.throw_cd = random.uniform(9.0, 17.0)
                    dx_m = mx - sm.x
                    dy_m = my - (sm.y - 24.0)
                    if 60.0 < math.hypot(dx_m, dy_m) < 520.0 and len(self.snowballs) < 12:
                        flight_t = max(0.45, min(0.95, math.hypot(dx_m, dy_m) / 480.0))
                        vx_t = dx_m / flight_t
                        vy_t = (dy_m - 0.5 * 640.0 * flight_t * flight_t) / flight_t
                        sb_id = self._next_id
                        self._next_id += 1
                        self.snowballs.append(
                            Snowball(
                                id=sb_id,
                                x=sm.x + (10.0 if dx_m >= 0 else -10.0),
                                y=sm.y - 24.0,
                                vx=vx_t,
                                vy=vy_t,
                                radius=6.5,
                                held=False,
                                from_snowman=True,
                            )
                        )

            if sm.held:
                surviving_snowmen.append(sm)
                continue
            prev_y = sm.y
            if sm.resting_hwnd is not None and sm.resting_hwnd in self.drifts:
                drift = self.drifts[sm.resting_hwnd]
                if drift.left + 8 <= sm.x <= drift.right - 8 and drift.is_x_visible(sm.x):
                    sm.x += sm.vx * dt
                    sm.vx *= 0.85
                    sm.y = drift.top - drift.depth_at(sm.x) * 0.55
                    sm.vy = 0.0
                    surviving_snowmen.append(sm)
                    continue
                else:
                    sm.resting_hwnd = None

            sm.vy += 760.0 * dt
            sm.x += sm.vx * dt
            sm.y += sm.vy * dt
            sm.vx *= 0.98

            if sm.x < 20.0:
                sm.x = 20.0
                sm.vx = abs(sm.vx) * 0.4
            elif sm.x > self.width - 20.0:
                sm.x = self.width - 20.0
                sm.vx = -abs(sm.vx) * 0.4

            shattered = False
            if sm.vy >= 0:
                landed_drift = self._find_landing_surface(sm.x, prev_y, sm.y)
                impact = math.hypot(sm.vx, sm.vy)
                if landed_drift is not None:
                    if impact >= 520.0:
                        self._spawn_snow_burst(sm.x, landed_drift.top - 12.0, count=24, vx_bias=sm.vx * 0.2, vy_bias=-130.0)
                        self._play_sfx("crunch")
                        shattered = True
                    else:
                        sm.y = landed_drift.top - landed_drift.depth_at(sm.x) * 0.55
                        sm.vy = 0.0
                        sm.vx *= 0.4
                        sm.resting_hwnd = landed_drift.hwnd
                elif sm.y >= self.taskbar_top:
                    if impact >= 520.0:
                        self._spawn_snow_burst(sm.x, self.taskbar_top - 12.0, count=24, vx_bias=sm.vx * 0.2, vy_bias=-130.0)
                        self._play_sfx("crunch")
                        shattered = True
                    else:
                        sm.y = self.taskbar_top
                        sm.vy = 0.0
                        sm.vx *= 0.4

            if not shattered:
                surviving_snowmen.append(sm)
        self.snowmen = surviving_snowmen

        mouse_speed_sq = self._mouse_vx * self._mouse_vx + self._mouse_vy * self._mouse_vy
        active_balls: List[Snowball] = []
        consumed_ids: set[int] = set()
        for sb in self.snowballs:
            if sb.id in consumed_ids:
                continue
            if sb.held:
                active_balls.append(sb)
                continue

            if sb.resting_hwnd is not None and sb.resting_hwnd in self.drifts:
                drift = self.drifts[sb.resting_hwnd]
                if drift.left + 6 <= sb.x <= drift.right - 6 and drift.is_x_visible(sb.x):
                    sb.x += sb.vx * dt
                    sb.vx *= 0.82
                    sb.y = drift.top - drift.depth_at(sb.x) * 0.45 - sb.radius * 0.65
                    sb.vy = 0.0
                    active_balls.append(sb)
                    continue
                else:
                    sb.resting_hwnd = None

            prev_y = sb.y
            sb.vy += 640.0 * dt
            sb.x += sb.vx * dt
            sb.y += sb.vy * dt

            # Deflect incoming snowman snowball with fast cursor swipe!
            if sb.from_snowman and mouse_speed_sq > 45000.0:
                if math.hypot(sb.x - mx, sb.y - my) < 34.0:
                    sb.from_snowman = False
                    sb.vx = self._mouse_vx * 0.9
                    sb.vy = min(-160.0, self._mouse_vy * 0.8)
                    self.score += 2
                    self._spawn_snow_burst(sb.x, sb.y, count=10, vx_bias=sb.vx * 0.2, vy_bias=-90.0)
                    self._play_sfx("crunch")
                    if self.score % 5 == 0:
                        self.trigger_fireworks(3)

            hit_target = False
            if not sb.from_snowman and math.hypot(sb.vx, sb.vy) > 160.0:
                for sm in self.snowmen:
                    if abs(sb.x - sm.x) < 18.0 and (sm.y - 50.0) <= sb.y <= sm.y:
                        sm.hat_tilt = 0.55 if sb.vx >= 0 else -0.55
                        self.score += 1
                        self._spawn_snow_burst(sb.x, sb.y, count=14, vx_bias=sb.vx * 0.2, vy_bias=-90.0)
                        self._play_sfx("crunch")
                        if self.score % 5 == 0:
                            self.trigger_fireworks(3)
                        hit_target = True
                        break
                if not hit_target:
                    for tr in self.trees:
                        if abs(sb.x - tr.x) < 18.0 * tr.scale and (self.taskbar_top - 48.0 * tr.scale) <= sb.y <= self.taskbar_top:
                            tr.snow_cover = max(0.0, tr.snow_cover - 0.5)
                            self.score += 1
                            self._spawn_snow_burst(sb.x, sb.y, count=14, vx_bias=sb.vx * 0.2, vy_bias=-90.0)
                            self._play_sfx("crunch")
                            if self.score % 5 == 0:
                                self.trigger_fireworks(3)
                            hit_target = True
                            break
            if hit_target:
                continue

            merged = False
            if not sb.from_snowman:
                for other in self.snowballs:
                    if other.id == sb.id or other.id in consumed_ids or other.held or other.from_snowman:
                        continue
                    if abs(sb.x - other.x) <= (sb.radius + other.radius) * 0.95 and abs(sb.y - (other.y - other.radius)) <= 16.0:
                        if math.hypot(sb.vx, sb.vy) < 380.0:
                            consumed_ids.add(other.id)
                            consumed_ids.add(sb.id)
                            self.snowmen.append(
                                Snowman(
                                    id=self._next_id,
                                    x=other.x,
                                    y=other.y + other.radius * 0.65,
                                    scarf_red=(self._next_id % 2 == 1),
                                    resting_hwnd=other.resting_hwnd,
                                    throw_cd=random.uniform(8.0, 15.0),
                                )
                            )
                            self._next_id += 1
                            self._spawn_snow_burst(other.x, other.y - 12.0, count=8, vy_bias=-50.0)
                            merged = True
                            break
            if merged:
                continue

            if sb.vy >= 0:
                hit = self._find_landing_surface(sb.x, prev_y + sb.radius, sb.y + sb.radius)
                if hit is not None:
                    impact_speed = math.hypot(sb.vx, sb.vy)
                    if impact_speed >= 420.0 or sb.from_snowman:
                        hit.deposit(sb.x, sb.radius * 0.75)
                        self._spawn_snow_burst(sb.x, hit.top - 4.0, count=18, vx_bias=sb.vx * 0.25, vy_bias=-120.0)
                        self._play_sfx("crunch")
                        continue
                    else:
                        sb.resting_hwnd = hit.hwnd
                        sb.y = hit.top - hit.depth_at(sb.x) * 0.45 - sb.radius * 0.65
                        sb.vx *= 0.25
                        sb.vy = 0.0
                        active_balls.append(sb)
                        continue

            if sb.y >= self.height - 10.0 or sb.x < -40.0 or sb.x > self.width + 40.0:
                self._spawn_snow_burst(sb.x, min(sb.y, self.height - 12.0), count=12, vy_bias=-110.0)
                continue
            active_balls.append(sb)

        self.snowballs = [b for b in active_balls if b.id not in consumed_ids]

        cfg = PRESETS[self.preset_name]
        wx_wind = (self.weather_wind_kmh - 10.0) * 1.4
        target_wind = (math.sin(self.time_acc * 0.45) * 18.0 + math.cos(self.time_acc * 0.19) * 10.0 + wx_wind) * cfg["wind_scale"]
        self.global_wind += (target_wind - self.global_wind) * min(1.0, dt * 4.0)

        accum_gain = cfg["accum_gain"]
        next_flakes: List[Flake] = []

        for f in self.flakes:
            sway = math.sin(self.time_acc * f.sway_speed + f.phase) * f.sway_amp
            layer_wind = self.global_wind * (0.45 + 0.3 * f.layer)

            if self.mouse_breeze and mouse_speed_sq > 14000.0:
                dx = f.x - mx
                dy = f.y - my
                dist_sq = dx * dx + dy * dy
                if dist_sq < 130.0 * 130.0:
                    force = 1.0 - (dist_sq / (130.0 * 130.0))
                    f.vx += self._mouse_vx * 0.14 * force
                    f.vy += self._mouse_vy * 0.08 * force

            prev_fy = f.y
            if f.is_shed:
                f.vy = min(380.0, f.vy + 460.0 * dt)
                f.vx *= 0.97
                f.x += f.vx * dt
            else:
                f.vx *= 0.95
                f.x += (f.vx + sway + layer_wind) * dt
            f.y += f.vy * dt
            f.angle += f.spin * dt

            if f.x < -25.0:
                f.x = self.width + 20.0
            elif f.x > self.width + 25.0:
                f.x = -20.0

            landed = False
            if not self.plow_auto and f.vy > 0:
                for drift in self.drifts.values():
                    if drift.left <= f.x <= drift.right and drift.is_x_visible(f.x):
                        cur_depth = drift.depth_at(f.x)
                        surface_y = drift.top - cur_depth * 0.55
                        if prev_fy <= drift.top + 8.0 and f.y >= surface_y - 3.0:
                            if cur_depth < drift.MAX_DEPTH:
                                dep = f.mass if f.is_shed else accum_gain * (0.55 + 0.25 * f.layer)
                                drift.deposit(f.x, dep)
                            landed = True
                            break

            if landed:
                if not f.is_shed:
                    next_flakes.append(self._make_flake(scatter_y=False))
                continue

            if f.y > self.height + 15.0:
                if not f.is_shed:
                    next_flakes.append(self._make_flake(scatter_y=False))
                continue

            next_flakes.append(f)

        self.flakes = next_flakes

        for drift in self.drifts.values():
            drift.step_hop(dt)
            spills = drift.relax()
            for sx, sy, vx_dir in spills:
                self._spawn_falling_clump(sx, sy + 2.0, vx_dir * random.uniform(18.0, 42.0), 10.0)
