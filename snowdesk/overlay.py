"""
Native Windows GDI+ + UpdateLayeredWindow (32-bit ARGB) Ultra-Realistic 60 FPS Overlay for SnowDesk.
Features:
- True 60 FPS dynamic frame pacing & layered 3D-shaded GDI+ graphics (no flat cartoon shapes)
- Spring-wave bass-bouncing snowdrifts + jumping snow granules + subwoofer glow
- 6-branch dendritic crystal snowflakes, volumetric streetlamp light cones, 4-pane glowing cabin
- Twinkling night starfield, crescent moon, shooting stars, & gradient-curtain Aurora Borealis (F3)
- Real illustrated Santa & Reindeer Sleigh sprite (assets/santa_sleigh.png) + Now-Playing song banner
- Keystroke micro-quake, Window shake snowglobe vortex, Mini window skier, Snowman snowball fight, Fireworks
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import io
import math
import os
import struct
import time
import tkinter as tk
import wave
import winsound
from datetime import datetime
from typing import Dict, List, Tuple

from .sensors import SystemSensors, toggle_windows_startup
from .snow_engine import Icicle, PineTree, Skier, SnowEngine, Snowman, SurfaceDrift
from .win32_tracker import (
    enable_dpi_awareness,
    get_visible_surfaces,
    make_overlay_click_through,
    set_overlay_interactive,
)

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
gdiplus = ctypes.windll.gdiplus

VK_LBUTTON = 0x01
VK_F1 = 0x70
VK_F2 = 0x71
VK_F3 = 0x72
VK_F4 = 0x73
VK_F5 = 0x74
VK_F6 = 0x75
VK_F7 = 0x76
VK_F8 = 0x77
VK_F9 = 0x78
VK_F10 = 0x79
VK_F11 = 0x7A
VK_F12 = 0x7B
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_C = 0x43
VK_F = 0x46

TYPING_VKS = (0x20, 0x0D, 0x08, 0x41, 0x45, 0x49, 0x4F, 0x55, 0x53, 0x54, 0x4E, 0x52, 0x4C, 0x4B, 0x4D)

ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
SmoothingModeAntiAlias = 4
CombineModeExclude = 4
FillModeAlternate = 0
WrapModeTileFlipX = 1


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_ubyte),
        ("BlendFlags", ctypes.c_ubyte),
        ("SourceConstantAlpha", ctypes.c_ubyte),
        ("AlphaFormat", ctypes.c_ubyte),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wt.WORD),
        ("biBitCount", wt.WORD),
        ("biCompression", wt.DWORD),
        ("biSizeImage", wt.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wt.DWORD),
        ("biClrImportant", wt.DWORD),
    ]


class GdiplusStartupInput(ctypes.Structure):
    _fields_ = [
        ("GdiplusVersion", ctypes.c_uint32),
        ("DebugEventCallback", ctypes.c_void_p),
        ("SuppressBackgroundThread", ctypes.c_int),
        ("SuppressExternalCodecs", ctypes.c_int),
    ]


class PointF(ctypes.Structure):
    _fields_ = [("X", ctypes.c_float), ("Y", ctypes.c_float)]


class RectF(ctypes.Structure):
    _fields_ = [("X", ctypes.c_float), ("Y", ctypes.c_float), ("Width", ctypes.c_float), ("Height", ctypes.c_float)]


gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateDIBSection.argtypes = [wt.HDC, ctypes.c_void_p, wt.UINT, ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD]
gdi32.CreateDIBSection.restype = wt.HBITMAP
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wt.HDC]

user32.GetDC.argtypes = [wt.HWND]
user32.GetDC.restype = wt.HDC
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wt.HWND
user32.UpdateLayeredWindow.argtypes = [
    wt.HWND, wt.HDC, ctypes.POINTER(POINT), ctypes.POINTER(SIZE),
    wt.HDC, ctypes.POINTER(POINT), wt.COLORREF, ctypes.POINTER(BLENDFUNCTION), wt.DWORD,
]
user32.UpdateLayeredWindow.restype = wt.BOOL

gdiplus.GdiplusStartup.argtypes = [ctypes.POINTER(ctypes.c_ulonglong), ctypes.POINTER(GdiplusStartupInput), ctypes.c_void_p]
gdiplus.GdiplusShutdown.argtypes = [ctypes.c_ulonglong]
gdiplus.GdipCreateFromHDC.argtypes = [wt.HDC, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipDeleteGraphics.argtypes = [ctypes.c_void_p]
gdiplus.GdipSetSmoothingMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
gdiplus.GdipSetClipRect.argtypes = [ctypes.c_void_p, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_int]
gdiplus.GdipResetClip.argtypes = [ctypes.c_void_p]
gdiplus.GdipCreateSolidFill.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipCreateLineBrush.argtypes = [
    ctypes.POINTER(PointF), ctypes.POINTER(PointF), ctypes.c_uint32, ctypes.c_uint32, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)
]
gdiplus.GdipDeleteBrush.argtypes = [ctypes.c_void_p]
gdiplus.GdipCreatePen1.argtypes = [ctypes.c_uint32, ctypes.c_float, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipDeletePen.argtypes = [ctypes.c_void_p]
gdiplus.GdipFillEllipse.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float]
gdiplus.GdipFillRectangle.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float]
gdiplus.GdipDrawRectangle.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float]
gdiplus.GdipFillPolygon.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(PointF), ctypes.c_int, ctypes.c_int]
gdiplus.GdipDrawPolygon.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(PointF), ctypes.c_int]
gdiplus.GdipDrawLine.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float]
gdiplus.GdipLoadImageFromFile.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipDisposeImage.argtypes = [ctypes.c_void_p]
gdiplus.GdipDrawImageRect.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float]
gdiplus.GdipCreateFontFamilyFromName.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipDeleteFontFamily.argtypes = [ctypes.c_void_p]
gdiplus.GdipCreateFont.argtypes = [ctypes.c_void_p, ctypes.c_float, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipDeleteFont.argtypes = [ctypes.c_void_p]
gdiplus.GdipCreateStringFormat.argtypes = [ctypes.c_int, wt.LANGID, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipDeleteStringFormat.argtypes = [ctypes.c_void_p]
gdiplus.GdipDrawString.argtypes = [
    ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(RectF), ctypes.c_void_p, ctypes.c_void_p
]


def _argb(a: int, r: int, g: int, b: int) -> int:
    return ((a & 0xFF) << 24) | ((r & 0xFF) << 16) | ((g & 0xFF) << 8) | (b & 0xFF)


def _key_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def _build_wav_bytes() -> Dict[str, bytes]:
    sr = 22050
    sounds: Dict[str, bytes] = {}

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        n = int(sr * 0.45)
        for i in range(n):
            t = i / sr
            env = math.exp(-t * 7.5)
            val = (math.sin(2 * math.pi * 1567.98 * t) + 0.6 * math.sin(2 * math.pi * 2093.0 * t)) * 0.14 * env
            frames.extend(struct.pack("<h", int(max(-1.0, min(1.0, val)) * 32767)))
        wf.writeframes(bytes(frames))
    sounds["bells"] = buf.getvalue()

    import random
    buf2 = io.BytesIO()
    with wave.open(buf2, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames2 = bytearray()
        n2 = int(sr * 0.14)
        for i in range(n2):
            t = i / sr
            env = math.exp(-t * 22.0)
            val = random.uniform(-1.0, 1.0) * 0.12 * env
            frames2.extend(struct.pack("<h", int(val * 32767)))
        wf.writeframes(bytes(frames2))
    sounds["crunch"] = buf2.getvalue()
    return sounds


class SnowDeskApp:
    def __init__(self) -> None:
        enable_dpi_awareness()

        self.gdip_token = ctypes.c_ulonglong(0)
        si = GdiplusStartupInput(1, None, 0, 0)
        gdiplus.GdiplusStartup(ctypes.byref(self.gdip_token), ctypes.byref(si), None)

        self.vx, self.vy = 0, 0
        self.sw = 0
        self.sh = 0
        self.project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.root = tk.Tk()
        self.root.title("SnowDesk")
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()
        self.root.geometry(f"{self.sw}x{self.sh}+0+0")
        self.root.update_idletasks()

        try:
            frame_hwnd = int(self.root.wm_frame(), 16)
        except Exception:
            frame_hwnd = 0
        self.own_hwnd = frame_hwnd if frame_hwnd else (user32.GetParent(self.root.winfo_id()) or self.root.winfo_id())
        make_overlay_click_through(self.own_hwnd)

        self.screen_dc = user32.GetDC(None)
        self.mem_dc = gdi32.CreateCompatibleDC(self.screen_dc)
        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = self.sw
        bmi.biHeight = -self.sh
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0

        self.bits_ptr = ctypes.c_void_p(0)
        self.hbmp = gdi32.CreateDIBSection(
            self.mem_dc, ctypes.byref(bmi), 0, ctypes.byref(self.bits_ptr), None, 0
        )
        self.old_bmp = gdi32.SelectObject(self.mem_dc, self.hbmp)
        self.buf_bytes = self.sw * self.sh * 4

        self.sounds = _build_wav_bytes()

        self.santa_img = ctypes.c_void_p(0)
        santa_path = os.path.join(self.project_dir, "assets", "santa_sleigh.png")
        if os.path.exists(santa_path):
            st = gdiplus.GdipLoadImageFromFile(santa_path, ctypes.byref(self.santa_img))
            if st != 0:
                self.santa_img = ctypes.c_void_p(0)

        self.font_family = ctypes.c_void_p(0)
        self.hud_font = ctypes.c_void_p(0)
        self.small_font = ctypes.c_void_p(0)
        self.str_fmt = ctypes.c_void_p(0)
        if gdiplus.GdipCreateFontFamilyFromName("Segoe UI", None, ctypes.byref(self.font_family)) == 0 and self.font_family.value:
            gdiplus.GdipCreateFont(self.font_family, 12.0, 1, 2, ctypes.byref(self.hud_font))
            gdiplus.GdipCreateFont(self.font_family, 10.5, 1, 2, ctypes.byref(self.small_font))
            gdiplus.GdipCreateStringFormat(0, 0, ctypes.byref(self.str_fmt))

        self.flake_brushes: Dict[str, List[ctypes.c_void_p]] = {"classic": [], "cyber": [], "gold": []}
        self.halo_brushes: Dict[str, List[ctypes.c_void_p]] = {"classic": [], "cyber": [], "gold": []}
        for alpha in (110, 145, 180, 215, 245):
            for tname, rgb, hrgb in (
                ("classic", (250, 253, 255), (210, 236, 255)),
                ("cyber", (103, 232, 249), (168, 85, 247)),
                ("gold", (254, 240, 138), (251, 191, 36)),
            ):
                b = ctypes.c_void_p(0)
                gdiplus.GdipCreateSolidFill(_argb(alpha, *rgb), ctypes.byref(b))
                self.flake_brushes[tname].append(b)
                hb = ctypes.c_void_p(0)
                gdiplus.GdipCreateSolidFill(_argb(int(alpha * 0.30), *hrgb), ctypes.byref(hb))
                self.halo_brushes[tname].append(hb)

        def _solid(a, r, g, b):
            br = ctypes.c_void_p(0)
            gdiplus.GdipCreateSolidFill(_argb(a, r, g, b), ctypes.byref(br))
            return br

        def _pen(a, r, g, b, w):
            p = ctypes.c_void_p(0)
            gdiplus.GdipCreatePen1(_argb(a, r, g, b), w, 2, ctypes.byref(p))
            return p

        self.br_white = _solid(254, 255, 255, 255)
        self.br_snow_mid = _solid(246, 236, 245, 255)
        self.br_snow_shade = _solid(242, 192, 218, 246)
        self.br_shadow = _solid(78, 15, 23, 42)
        self.br_icicle = _solid(180, 196, 234, 255)
        self.br_frost = _solid(42, 224, 242, 254)
        self.br_droplet = _solid(215, 125, 211, 252)
        self.br_blush = _solid(180, 244, 114, 182)
        self.br_black = _solid(255, 24, 28, 36)
        self.br_carrot = _solid(255, 249, 115, 22)
        self.br_scarf_red = _solid(255, 220, 38, 38)
        self.br_scarf_blue = _solid(255, 37, 99, 235)
        self.br_yellow = _solid(255, 250, 204, 21)
        self.br_amber = _solid(255, 245, 158, 11)
        self.br_gold = _solid(245, 253, 224, 71)
        self.br_gold_glow = _solid(52, 253, 224, 71)
        self.br_light_cone = _solid(26, 254, 240, 138)
        self.br_red_glow = _solid(75, 239, 68, 68)
        self.br_bass_glow = _solid(95, 56, 189, 248)
        self.br_glass = _solid(235, 56, 189, 248)
        self.br_silver = _solid(255, 203, 213, 225)
        self.br_gray = _solid(255, 100, 116, 139)
        self.br_pine_deep = _solid(255, 14, 68, 42)
        self.br_pine_dark = _solid(255, 21, 94, 56)
        self.br_pine_light = _solid(255, 34, 139, 82)
        self.br_trunk = _solid(255, 110, 65, 32)
        self.br_cabin = _solid(255, 134, 76, 38)
        self.br_cabin_dark = _solid(255, 98, 52, 24)
        self.br_roof = _solid(255, 127, 29, 29)
        self.br_banner_bg = _solid(220, 127, 29, 29)
        self.br_spark = _solid(220, 186, 230, 253)
        self.br_mist = _solid(65, 241, 245, 249)
        self.br_smoke = _solid(90, 226, 232, 240)
        self.br_hud_bg = _solid(185, 15, 23, 42)
        self.br_hud_text = _solid(245, 241, 245, 249)
        self.br_moon = _solid(225, 254, 249, 195)
        self.br_moon_glow = _solid(38, 254, 249, 195)
        self.br_moon_cut = _solid(210, 15, 23, 42)
        self.fw_brushes = [
            _solid(240, 251, 113, 133),
            _solid(240, 56, 189, 248),
            _solid(240, 250, 204, 21),
            _solid(240, 168, 85, 247),
        ]

        self.light_bulbs = [
            (_solid(245, 253, 224, 71), _solid(75, 253, 224, 71)),
            (_solid(245, 125, 211, 252), _solid(75, 125, 211, 252)),
            (_solid(245, 251, 113, 133), _solid(75, 251, 113, 133)),
            (_solid(245, 110, 231, 183), _solid(75, 110, 231, 183)),
        ]

        self.drift_pen = _pen(230, 255, 255, 255, 1.5)
        self.twig_pen = _pen(255, 110, 70, 40, 2.0)
        self.wire_pen = _pen(170, 51, 65, 85, 1.4)
        self.crystal_pen = _pen(230, 248, 252, 255, 1.15)
        self.cyber_pen = _pen(235, 56, 189, 248, 1.25)
        self.gold_pen = _pen(235, 250, 204, 21, 1.25)
        self.hud_pen = _pen(190, 56, 189, 248, 1.4)
        self.star_pen = _pen(235, 254, 249, 195, 2.0)
        self.ice_spec_pen = _pen(230, 255, 255, 255, 1.1)

        # Deterministic twinkling night stars
        self._bg_stars = [
            ((i * 173 + 47) % max(200, self.sw), (i * 89 + 23) % max(100, int(self.sh * 0.36)), 0.8 + (i % 3) * 0.5, i * 0.9)
            for i in range(28)
        ]

        self.sensors = SystemSensors()
        self.engine = SnowEngine(float(self.sw), float(self.sh), preset="cozy", on_sound=self._play_sound)
        self._last_time = time.perf_counter()
        self._last_hk = 0.0
        self._prev_typing_state = 0
        self._startup_msg = ""
        self._startup_msg_until = 0.0

        self._scan_surfaces()
        self._render(time.perf_counter())
        user32.ShowWindow(self.own_hwnd, 4)
        self._tick()

    def _play_sound(self, name: str) -> None:
        buf = self.sounds.get(name)
        if buf:
            try:
                winsound.PlaySound(buf, winsound.SND_MEMORY | winsound.SND_ASYNC)
            except Exception:
                pass

    def _scan_surfaces(self) -> None:
        surfaces, occluders = get_visible_surfaces(
            own_hwnd=self.own_hwnd,
            virt_x=float(self.vx),
            virt_y=float(self.vy),
            screen_w=float(self.sw),
            screen_h=float(self.sh),
            dpr=1.0,
        )
        self.engine.update_surfaces(surfaces, occluders)

    def _check_typing_activity(self) -> None:
        mask = 0
        for idx, vk in enumerate(TYPING_VKS):
            if _key_down(vk):
                mask |= (1 << idx)
        if (mask & ~self._prev_typing_state) != 0:
            fg = user32.GetForegroundWindow()
            self.engine.trigger_keystroke_quake(int(fg) if fg else None)
        self._prev_typing_state = mask

    def _check_hotkeys(self, now: float) -> None:
        if now - self._last_hk < 0.35:
            return
        if _key_down(VK_F1):
            self._last_hk = now
            self.engine.cycle_theme()
        elif _key_down(VK_F2):
            self._last_hk = now
            self.engine.show_hud = not self.engine.show_hud
        elif _key_down(VK_F3):
            self._last_hk = now
            self.engine.show_aurora = not self.engine.show_aurora
        elif _key_down(VK_F4):
            self._last_hk = now
            self.engine.sound_enabled = not self.engine.sound_enabled
        elif _key_down(VK_F5):
            self._last_hk = now
            self.engine.trigger_santa()
        elif _key_down(VK_F6):
            self._last_hk = now
            self.engine.cycle_preset()
        elif _key_down(VK_F7):
            self._last_hk = now
            self.engine.fairy_lights = not self.engine.fairy_lights
        elif _key_down(VK_F8) or (_key_down(VK_CONTROL) and _key_down(VK_SHIFT) and _key_down(VK_C)):
            self._last_hk = now
            self.engine.clear_all_snow()
        elif _key_down(VK_CONTROL) and _key_down(VK_SHIFT) and _key_down(VK_F):
            self._last_hk = now
            self.engine.trigger_fireworks(5)
        elif _key_down(VK_F9):
            self._last_hk = now
            self.engine.paused = not self.engine.paused
        elif _key_down(VK_F10):
            self._last_hk = now
            self._cleanup()
            self.root.destroy()
        elif _key_down(VK_F11):
            self._last_hk = now
            self.engine.trigger_demo_mode()
        elif _key_down(VK_F12):
            self._last_hk = now
            enabled = toggle_windows_startup(self.project_dir)
            self._startup_msg = "Başlangıç: Açık" if enabled else "Başlangıç: Kapalı"
            self._startup_msg_until = now + 2.0

    def _brush_for_alpha(self, alpha: int) -> Tuple[ctypes.c_void_p, ctypes.c_void_p]:
        idx = min(4, max(0, (alpha - 100) // 35))
        tkey = self.engine.theme if self.engine.theme in self.flake_brushes else "classic"
        return self.flake_brushes[tkey][idx], self.halo_brushes[tkey][idx]

    def _draw_crystal_flake(self, gfx: ctypes.c_void_p, x: float, y: float, r: float, angle: float) -> None:
        """True 6-branch dendritic crystal snowflake with side-twigs and soft halo."""
        pen = self.cyber_pen if self.engine.theme == "cyber" else (self.gold_pen if self.engine.theme == "gold" else self.crystal_pen)
        gdiplus.GdipFillEllipse(gfx, self.br_frost, float(x - r * 1.4), float(y - r * 1.4), float(r * 2.8), float(r * 2.8))
        for k in range(3):
            a = angle + k * (math.pi / 3.0)
            ca, sa = math.cos(a), math.sin(a)
            dx, dy = ca * r, sa * r
            gdiplus.GdipDrawLine(gfx, pen, float(x - dx), float(y - dy), float(x + dx), float(y + dy))
            # Dendritic V-branches on both ends
            for sign in (1.0, -1.0):
                bx, by = x + sign * dx * 0.58, y + sign * dy * 0.58
                for side in (-0.55, 0.55):
                    ba = a + (0.0 if sign > 0 else math.pi) + side
                    gdiplus.GdipDrawLine(
                        gfx, pen, float(bx), float(by),
                        float(bx + math.cos(ba) * r * 0.36), float(by + math.sin(ba) * r * 0.36),
                    )

    def _draw_aurora(self, gfx: ctypes.c_void_p) -> None:
        """Vertical gradient-curtain Aurora Borealis."""
        if not self.engine.show_aurora:
            return
        t = self.engine.time_acc
        step = max(60, self.sw // 16)
        for band, base_y, c_top, c_bot in (
            (0, 82.0, _argb(0, 16, 185, 129), _argb(46, 52, 211, 153)),
            (1, 112.0, _argb(0, 139, 92, 246), _argb(36, 168, 85, 247)),
        ):
            pts: List[PointF] = [PointF(0.0, 0.0)]
            for x in range(0, self.sw + step, step):
                y = base_y + 28.0 * math.sin(x * 0.004 + t * (0.7 - band * 0.15)) + 14.0 * math.cos(x * 0.009 - t * 0.4)
                pts.append(PointF(float(x), float(y)))
            pts.append(PointF(float(self.sw), 0.0))
            arr = (PointF * len(pts))(*pts)
            p1, p2 = PointF(0.0, 0.0), PointF(0.0, base_y + 42.0)
            grad = ctypes.c_void_p(0)
            gdiplus.GdipCreateLineBrush(ctypes.byref(p1), ctypes.byref(p2), c_top, c_bot, WrapModeTileFlipX, ctypes.byref(grad))
            gdiplus.GdipFillPolygon(gfx, grad, arr, len(pts), FillModeAlternate)
            gdiplus.GdipDeleteBrush(grad)

    def _draw_night_sky(self, gfx: ctypes.c_void_p) -> None:
        if self.engine.is_evening:
            t = self.engine.time_acc
            for sx, sy, sr, ph in self._bg_stars:
                if 0.65 + 0.35 * math.sin(t * 2.4 + ph) > 0.45:
                    gdiplus.GdipFillEllipse(gfx, self.br_white, float(sx), float(sy), float(sr * 2), float(sr * 2))

            mx = float(self.sw) - 115.0
            my = 66.0
            gdiplus.GdipFillEllipse(gfx, self.br_moon_glow, float(mx - 34.0), float(my - 34.0), 68.0, 68.0)
            gdiplus.GdipFillEllipse(gfx, self.br_moon, float(mx - 18.0), float(my - 18.0), 36.0, 36.0)
            gdiplus.GdipFillEllipse(gfx, self.br_moon_cut, float(mx - 9.0), float(my - 21.0), 30.0, 30.0)

        for st in self.engine.shooting_stars:
            tail_x = st.x - st.vx * 0.09
            tail_y = st.y - st.vy * 0.09
            gdiplus.GdipDrawLine(gfx, self.star_pen, float(tail_x), float(tail_y), float(st.x), float(st.y))
            gdiplus.GdipFillEllipse(gfx, self.br_white, float(st.x - 2.5), float(st.y - 2.5), 5.0, 5.0)

    def _draw_corner_frost(self, gfx: ctypes.c_void_p) -> None:
        cpu_cool = max(0.0, 1.0 - max(0.0, self.engine.cpu_pct - 25.0) / 55.0)
        intensity = (1.0 if self.engine.preset_name == "blizzard" else (0.55 if self.engine.preset_name == "cozy" else 0.25)) * cpu_cool
        corners = [(0.0, 0.0, 1, 1), (float(self.sw), 0.0, -1, 1), (0.0, float(self.sh), 1, -1), (float(self.sw), float(self.sh), -1, -1)]
        high_load = (self.engine.cpu_pct >= 68.0) or (self.engine.ram_pct >= 78.0)
        crack_pen = self.cyber_pen if self.engine.theme == "cyber" else self.crystal_pen

        for cx, cy, sx, sy in corners:
            dist = math.hypot(self.engine.mouse_x - cx, self.engine.mouse_y - cy)
            if cpu_cool > 0.05 and dist >= 130.0:
                fade = min(1.0, (dist - 130.0) / 80.0) * intensity
                for k in range(5):
                    r = (18.0 + k * 14.0) * fade
                    ox = cx + sx * (k * 10.0)
                    oy = cy + sy * (k * 8.0)
                    gdiplus.GdipFillEllipse(gfx, self.br_frost, float(ox - r), float(oy - r), float(r * 2), float(r * 2))

            if high_load:
                reach = 48.0 + min(60.0, max(0.0, self.engine.cpu_pct - 50.0) * 1.1)
                x1, y1 = cx + sx * (reach * 0.45), cy + sy * (reach * 0.35)
                x2, y2 = cx + sx * reach, cy + sy * (reach * 0.55)
                x3, y3 = cx + sx * (reach * 0.6), cy + sy * (reach * 0.95)
                gdiplus.GdipDrawLine(gfx, crack_pen, float(cx), float(cy), float(x1), float(y1))
                gdiplus.GdipDrawLine(gfx, crack_pen, float(x1), float(y1), float(x2), float(y2))
                gdiplus.GdipDrawLine(gfx, crack_pen, float(x1), float(y1), float(x3), float(y3))

    def _draw_santa_sleigh(self, gfx: ctypes.c_void_p) -> None:
        if not self.engine.santa_active:
            return
        sx = self.engine.santa_x
        bob = math.sin(self.engine.time_acc * 3.8) * 6.0
        sy = self.engine.santa_y + bob

        # Soft warm magic headlight cone in front of lead reindeer
        cone = (PointF * 3)(
            PointF(sx + 340.0, sy + 56.0),
            PointF(sx + 470.0, sy + 20.0),
            PointF(sx + 470.0, sy + 96.0),
        )
        gdiplus.GdipFillPolygon(gfx, self.br_light_cone, cone, 3, FillModeAlternate)

        if self.santa_img and self.santa_img.value:
            gdiplus.GdipDrawImageRect(gfx, self.santa_img, float(sx), float(sy), 360.0, 154.0)

        song = self.engine.now_playing
        if song and self.small_font.value and self.str_fmt.value:
            txt = f"♫ {song}"
            bw = min(290.0, max(120.0, 28.0 + len(txt) * 6.8))
            bh = 26.0
            bx = sx - bw - 18.0
            by = sy + 64.0
            gdiplus.GdipDrawLine(gfx, self.gold_pen, float(bx + bw), float(by + 6), float(sx + 18.0), float(sy + 72.0))
            gdiplus.GdipDrawLine(gfx, self.gold_pen, float(bx + bw), float(by + bh - 6), float(sx + 18.0), float(sy + 86.0))
            gdiplus.GdipFillRectangle(gfx, self.br_banner_bg, float(bx), float(by), float(bw), float(bh))
            gdiplus.GdipDrawRectangle(gfx, self.gold_pen, float(bx), float(by), float(bw), float(bh))
            rf = RectF(bx + 8.0, by + 4.0, bw - 14.0, bh - 6.0)
            gdiplus.GdipDrawString(gfx, txt, len(txt), self.small_font, ctypes.byref(rf), self.str_fmt, self.br_gold)

    def _draw_streetlamp_and_cabin(self, gfx: ctypes.c_void_p, base_y: float) -> None:
        lx = self.engine.lamp_x
        low_bat = (not self.engine.ac_online) and self.engine.battery_pct < 25

        # Volumetric light cone casting onto snowdrift
        if not low_bat:
            cone = (PointF * 3)(PointF(lx, base_y - 46.0), PointF(lx - 34.0, base_y), PointF(lx + 34.0, base_y))
            gdiplus.GdipFillPolygon(gfx, self.br_light_cone, cone, 3, FillModeAlternate)

        gdiplus.GdipFillEllipse(gfx, self.br_shadow, float(lx - 9), float(base_y - 3), 18.0, 5.0)
        gdiplus.GdipFillRectangle(gfx, self.br_black, float(lx - 2.5), float(base_y - 6), 5.0, 6.0)
        gdiplus.GdipFillRectangle(gfx, self.br_black, float(lx - 1.5), float(base_y - 46), 3.0, 42.0)
        gdiplus.GdipFillRectangle(gfx, self.br_black, float(lx - 6), float(base_y - 54), 12.0, 3.0)

        glow_r = 24.0 if self.engine.is_evening else 15.0
        glow_br = self.br_red_glow if low_bat else self.br_gold_glow
        bulb_br = self.br_carrot if low_bat else self.br_gold
        gdiplus.GdipFillEllipse(gfx, glow_br, float(lx - glow_r), float(base_y - 49 - glow_r), float(glow_r * 2), float(glow_r * 2))
        gdiplus.GdipFillEllipse(gfx, bulb_br, float(lx - 4.5), float(base_y - 52), 9.0, 9.0)

        cx = self.engine.cabin_x
        gdiplus.GdipFillEllipse(gfx, self.br_shadow, float(cx - 4), float(base_y - 3), 68.0, 6.0)
        # Warm window glow spilling onto snow
        gdiplus.GdipFillEllipse(gfx, self.br_light_cone, float(cx + 6), float(base_y - 6), 48.0, 10.0)
        gdiplus.GdipFillRectangle(gfx, self.br_gray, float(cx + 38), float(base_y - 50), 8.0, 20.0)
        gdiplus.GdipFillRectangle(gfx, self.br_cabin, float(cx + 6), float(base_y - 28), 48.0, 28.0)
        # Log plank lines
        for ly in (base_y - 22, base_y - 15, base_y - 8):
            gdiplus.GdipFillRectangle(gfx, self.br_cabin_dark, float(cx + 6), float(ly), 48.0, 1.5)

        roof = (PointF * 3)(PointF(cx + 30, base_y - 47), PointF(cx + 61, base_y - 26), PointF(cx - 1, base_y - 26))
        gdiplus.GdipFillPolygon(gfx, self.br_roof, roof, 3, FillModeAlternate)
        snow_roof = (PointF * 3)(PointF(cx + 30, base_y - 49), PointF(cx + 59, base_y - 30), PointF(cx + 1, base_y - 30))
        gdiplus.GdipFillPolygon(gfx, self.br_white, snow_roof, 3, FillModeAlternate)
        gdiplus.GdipFillRectangle(gfx, self.br_trunk, float(cx + 25), float(base_y - 16), 10.0, 16.0)

        # 4-pane glowing windows
        for wx in (cx + 11, cx + 39):
            gdiplus.GdipFillRectangle(gfx, self.br_gold, float(wx), float(base_y - 21), 10.0, 10.0)
            gdiplus.GdipDrawLine(gfx, self.twig_pen, float(wx + 5), float(base_y - 21), float(wx + 5), float(base_y - 11))
            gdiplus.GdipDrawLine(gfx, self.twig_pen, float(wx), float(base_y - 16), float(wx + 10), float(base_y - 16))

        if self.small_font.value and self.str_fmt.value:
            now_dt = datetime.now()
            ny = datetime(now_dt.year + 1, 1, 1)
            rem = ny - now_dt
            days = rem.days
            label = f"{days}G" if days > 0 else f"{rem.seconds // 3600:02d}:{(rem.seconds % 3600) // 60:02d}"
            sx, sy, sw, sh = cx + 10.0, base_y - 68.0, 42.0, 17.0
            gdiplus.GdipFillRectangle(gfx, self.br_hud_bg, float(sx), float(sy), float(sw), float(sh))
            gdiplus.GdipDrawRectangle(gfx, self.gold_pen, float(sx), float(sy), float(sw), float(sh))
            rf = RectF(sx + 4.0, sy + 1.0, sw - 4.0, sh)
            gdiplus.GdipDrawString(gfx, label, len(label), self.small_font, ctypes.byref(rf), self.str_fmt, self.br_gold)

    def _draw_pine_tree(self, gfx: ctypes.c_void_p, tr: PineTree, base_y: float) -> None:
        cx = tr.x
        s = tr.scale
        gdiplus.GdipFillEllipse(gfx, self.br_shadow, float(cx - 15 * s), float(base_y - 3), float(30 * s), 6.0)
        gdiplus.GdipFillRectangle(gfx, self.br_trunk, float(cx - 3.5 * s), float(base_y - 10 * s), float(7 * s), float(10 * s))
        tiers = [
            (base_y - 7 * s, base_y - 25 * s, 19 * s, 0.30),
            (base_y - 17 * s, base_y - 35 * s, 15 * s, 0.55),
            (base_y - 27 * s, base_y - 44 * s, 11 * s, 0.80),
            (base_y - 36 * s, base_y - 51 * s, 7.5 * s, 1.0),
        ]
        for idx, (by, ty, hw, sw_mul) in enumerate(tiers):
            tip_x = cx + tr.sway * 35.0 * sw_mul
            br = self.br_pine_deep if idx == 0 else (self.br_pine_dark if idx == 1 else self.br_pine_light)
            tri = (PointF * 3)(PointF(tip_x, ty), PointF(cx + hw, by), PointF(cx - hw, by))
            gdiplus.GdipFillPolygon(gfx, br, tri, 3, FillModeAlternate)
            if tr.snow_cover > 0.15:
                sw = hw * (0.42 + 0.35 * tr.snow_cover)
                sh = (by - ty) * (0.32 + 0.24 * tr.snow_cover)
                cap = (PointF * 3)(PointF(tip_x, ty), PointF(tip_x + sw, ty + sh), PointF(tip_x - sw, ty + sh))
                gdiplus.GdipFillPolygon(gfx, self.br_white, cap, 3, FillModeAlternate)

        # Tiny twinkling tree ornaments
        if self.engine.fairy_lights:
            t = self.engine.time_acc
            for oi, (ox_off, oy_off) in enumerate(((-6.0, -16.0), (5.0, -23.0), (-3.0, -32.0))):
                if math.sin(t * 3.5 + tr.x + oi * 2.1) > -0.2:
                    bulb_br, _ = self.light_bulbs[(oi + int(tr.x)) % len(self.light_bulbs)]
                    gdiplus.GdipFillEllipse(gfx, bulb_br, float(cx + ox_off * s), float(base_y + oy_off * s), 3.4, 3.4)

    def _draw_skier(self, gfx: ctypes.c_void_p, sk: Skier) -> None:
        cx, by = sk.x, sk.y
        gdiplus.GdipDrawLine(gfx, self.twig_pen, float(cx - 10), float(by), float(cx + 11), float(by))
        gdiplus.GdipDrawLine(gfx, self.twig_pen, float(cx + 9), float(by), float(cx + 13), float(by - 4))
        gdiplus.GdipFillRectangle(gfx, self.br_scarf_blue, float(cx - 4), float(by - 12), 8.0, 10.0)
        gdiplus.GdipFillEllipse(gfx, self.br_white, float(cx - 3.5), float(by - 18), 7.0, 7.0)
        gdiplus.GdipFillEllipse(gfx, self.br_scarf_red, float(cx - 4), float(by - 20), 8.0, 4.5)
        gdiplus.GdipDrawLine(gfx, self.twig_pen, float(cx - 4), float(by - 12), float(cx - 13), float(by - 14))

    def _draw_icicle(self, gfx: ctypes.c_void_p, ic: Icicle) -> None:
        pts = (PointF * 3)(
            PointF(ic.x - 3.2, ic.y),
            PointF(ic.x + 3.2, ic.y),
            PointF(ic.x, ic.y + ic.length),
        )
        gdiplus.GdipFillPolygon(gfx, self.br_icicle, pts, 3, FillModeAlternate)
        # Left specular highlight + glistening tip bead
        gdiplus.GdipDrawLine(gfx, self.ice_spec_pen, float(ic.x - 1.5), float(ic.y + 1.0), float(ic.x), float(ic.y + ic.length - 1.5))
        gdiplus.GdipFillEllipse(gfx, self.br_white, float(ic.x - 1.2), float(ic.y + ic.length - 2.0), 2.4, 2.4)

    def _draw_fairy_lights(self, gfx: ctypes.c_void_p, drift: SurfaceDrift) -> None:
        if drift.is_taskbar or not self.engine.fairy_lights:
            return
        t = self.engine.time_acc
        for s1, s2 in drift.visible_spans:
            if (s2 - s1) < 120:
                continue
            step = 34.0
            x = s1 + 18.0
            idx = 0
            prev_x = s1 + 6.0
            prev_y = drift.top + 1.0
            while x <= s2 - 18.0:
                sag = 5.0 + 2.5 * math.sin(idx * 1.1)
                ly = drift.top + sag
                gdiplus.GdipDrawLine(gfx, self.wire_pen, float(prev_x), float(prev_y), float(x), float(ly))
                prev_x, prev_y = x, ly

                bulb_br, glow_br = self.light_bulbs[idx % len(self.light_bulbs)]
                twinkle = 0.55 + 0.45 * math.sin(t * 3.2 + idx * 1.7)
                if twinkle > 0.4:
                    gr = 8.5 * twinkle if self.engine.is_evening else 6.5 * twinkle
                    gdiplus.GdipFillEllipse(gfx, glow_br, float(x - gr), float(ly - gr), float(gr * 2), float(gr * 2))
                gdiplus.GdipFillEllipse(gfx, bulb_br, float(x - 2.6), float(ly - 2.6), 5.2, 5.2)
                x += step
                idx += 1

    def _draw_snowman(self, gfx: ctypes.c_void_p, sm: Snowman) -> None:
        hop_y = 0.0
        if sm.resting_hwnd is not None and sm.resting_hwnd in self.engine.drifts:
            d_obj = self.engine.drifts[sm.resting_hwnd]
            idx = int((sm.x - d_obj.left) / d_obj.BIN_W)
            if 0 <= idx < len(d_obj.hop_y):
                hop_y = d_obj.hop_y[idx]
        cx, base_y = sm.x, sm.y - hop_y
        gdiplus.GdipFillEllipse(gfx, self.br_shadow, float(cx - 14), float(base_y - 3), 28.0, 6.0)

        gdiplus.GdipDrawLine(gfx, self.twig_pen, float(cx - 9), float(base_y - 19), float(cx - 20), float(base_y - 25))
        gdiplus.GdipDrawLine(gfx, self.twig_pen, float(cx + 9), float(base_y - 19), float(cx + 20), float(base_y - 25))

        gdiplus.GdipFillEllipse(gfx, self.br_snow_shade, float(cx - 12.5), float(base_y - 24.5), 25.0, 25.0)
        gdiplus.GdipFillEllipse(gfx, self.br_snow_mid, float(cx - 12.0), float(base_y - 24.5), 23.0, 23.0)
        gdiplus.GdipFillEllipse(gfx, self.br_white, float(cx - 10.5), float(base_y - 23.5), 18.0, 17.0)

        gdiplus.GdipFillEllipse(gfx, self.br_snow_shade, float(cx - 9.0), float(base_y - 38.5), 18.0, 18.0)
        gdiplus.GdipFillEllipse(gfx, self.br_snow_mid, float(cx - 8.5), float(base_y - 38.5), 16.5, 16.5)
        gdiplus.GdipFillEllipse(gfx, self.br_white, float(cx - 7.5), float(base_y - 37.5), 13.0, 12.0)

        scarf = self.br_scarf_red if sm.scarf_red else self.br_scarf_blue
        flutter = math.sin(self.engine.time_acc * 4.0 + sm.id) * 1.5 + self.engine.global_wind * 0.05
        gdiplus.GdipFillRectangle(gfx, scarf, float(cx - 7.5), float(base_y - 24), 15.0, 4.0)
        gdiplus.GdipFillRectangle(gfx, scarf, float(cx + 2.0 + flutter), float(base_y - 21), 4.0, 7.0)

        dx = self.engine.mouse_x - cx
        dy = self.engine.mouse_y - (base_y - 32.5)
        dist = math.hypot(dx, dy) or 1.0
        ex = (dx / dist) * 1.4
        ey = (dy / dist) * 1.1

        gdiplus.GdipFillEllipse(gfx, self.br_blush, float(cx - 6.0), float(base_y - 30), 3.5, 2.5)
        gdiplus.GdipFillEllipse(gfx, self.br_blush, float(cx + 2.5), float(base_y - 30), 3.5, 2.5)
        gdiplus.GdipFillEllipse(gfx, self.br_black, float(cx - 4.0 + ex), float(base_y - 33.5 + ey), 2.6, 2.6)
        gdiplus.GdipFillEllipse(gfx, self.br_black, float(cx + 1.5 + ex), float(base_y - 33.5 + ey), 2.6, 2.6)
        gdiplus.GdipFillEllipse(gfx, self.br_black, float(cx - 1.2), float(base_y - 17), 2.4, 2.4)
        gdiplus.GdipFillEllipse(gfx, self.br_black, float(cx - 1.2), float(base_y - 12), 2.4, 2.4)

        nose = (PointF * 3)(
            PointF(cx, base_y - 31.0),
            PointF(cx + 8.0, base_y - 29.5),
            PointF(cx, base_y - 28.0),
        )
        gdiplus.GdipFillPolygon(gfx, self.br_carrot, nose, 3, FillModeAlternate)

        ht_x = cx + sm.hat_tilt * 8.0
        gdiplus.GdipFillRectangle(gfx, self.br_black, float(ht_x - 10.0), float(base_y - 39.5), 20.0, 3.0)
        gdiplus.GdipFillRectangle(gfx, self.br_black, float(ht_x - 6.5), float(base_y - 49.0), 13.0, 10.0)
        gdiplus.GdipFillRectangle(gfx, scarf, float(ht_x - 6.5), float(base_y - 41.5), 13.0, 2.0)

    def _draw_snowplow(self, gfx: ctypes.c_void_p, px: float, base_y: float) -> None:
        gdiplus.GdipFillEllipse(gfx, self.br_shadow, float(px + 2), float(base_y - 3), 50.0, 6.0)
        gdiplus.GdipFillRectangle(gfx, self.br_amber, float(px), float(base_y - 20), 42.0, 14.0)
        gdiplus.GdipFillRectangle(gfx, self.br_yellow, float(px + 8), float(base_y - 32), 24.0, 14.0)
        gdiplus.GdipFillRectangle(gfx, self.br_glass, float(px + 18), float(base_y - 29), 11.0, 9.0)
        gdiplus.GdipFillEllipse(gfx, self.br_carrot, float(px + 15), float(base_y - 37), 7.0, 6.0)
        blade = (PointF * 4)(
            PointF(px + 42, base_y - 18),
            PointF(px + 54, base_y - 14),
            PointF(px + 56, base_y - 2),
            PointF(px + 42, base_y - 2),
        )
        gdiplus.GdipFillPolygon(gfx, self.br_silver, blade, 4, FillModeAlternate)
        for wx in (px + 6, px + 26):
            gdiplus.GdipFillEllipse(gfx, self.br_black, float(wx), float(base_y - 10), 12.0, 12.0)
            gdiplus.GdipFillEllipse(gfx, self.br_gray, float(wx + 3), float(base_y - 7), 6.0, 6.0)

    def _draw_drift(self, gfx: ctypes.c_void_p, drift: SurfaceDrift) -> None:
        if not drift.has_snow():
            return
        n = len(drift.bins)
        t = self.engine.time_acc
        for s1, s2 in drift.visible_spans:
            i_start = max(0, int((s1 - drift.left) / drift.BIN_W))
            i_end = min(n - 1, int((s2 - drift.left) / drift.BIN_W))
            if i_end - i_start < 2:
                continue

            if self.engine.bass_pulse > 0.08:
                ph = 2.0 + 3.8 * self.engine.bass_pulse
                gdiplus.GdipFillRectangle(gfx, self.br_bass_glow, float(s1), float(drift.top - ph * 0.5), float(s2 - s1), float(ph))

            pts_list: List[PointF] = []
            x0 = drift.left + i_start * drift.BIN_W
            pts_list.append(PointF(x0, drift.top + 1.5))
            step = max(1, (i_end - i_start) // 72)
            max_d = 2.0
            for i in range(i_start, i_end + 1, step):
                px = min(s2, drift.left + i * drift.BIN_W)
                d = drift.bins[i] + drift.hop_y[i]
                if d > max_d:
                    max_d = d
                pts_list.append(PointF(px, drift.top - d))
            x_end = min(s2, drift.left + i_end * drift.BIN_W)
            pts_list.append(PointF(x_end, drift.top - (drift.bins[i_end] + drift.hop_y[i_end])))
            pts_list.append(PointF(x_end, drift.top + 1.5))

            count = len(pts_list)
            arr = (PointF * count)(*pts_list)

            p1 = PointF(x0, drift.top - max_d - 2.0)
            p2 = PointF(x0, drift.top + 2.0)
            grad = ctypes.c_void_p(0)
            gdiplus.GdipCreateLineBrush(
                ctypes.byref(p1),
                ctypes.byref(p2),
                _argb(252, 255, 255, 255),
                _argb(242, 194, 224, 252),
                WrapModeTileFlipX,
                ctypes.byref(grad),
            )
            gdiplus.GdipFillPolygon(gfx, grad, arr, count, FillModeAlternate)
            gdiplus.GdipDrawPolygon(gfx, self.drift_pen, arr, count)
            gdiplus.GdipDeleteBrush(grad)

            # Glistening snow-crystal glints along the top of the drift
            glint_step = max(12, (i_end - i_start) // 7)
            for gi in range(i_start + 3, i_end - 2, glint_step):
                if drift.bins[gi] > 2.5 and math.sin(t * 4.5 + gi * 1.3) > 0.72:
                    gx = drift.left + gi * drift.BIN_W
                    gy = drift.top - (drift.bins[gi] + drift.hop_y[gi]) + 1.5
                    gdiplus.GdipFillEllipse(gfx, self.br_white, float(gx - 1.6), float(gy - 1.6), 3.2, 3.2)

    def _draw_tech_hud(self, gfx: ctypes.c_void_p, now: float) -> None:
        if not self.engine.show_hud:
            return
        hx, hy, hw, hh = 16.0, 16.0, 335.0, 68.0
        gdiplus.GdipFillRectangle(gfx, self.br_hud_bg, hx, hy, hw, hh)
        gdiplus.GdipDrawRectangle(gfx, self.hud_pen, hx, hy, hw, hh)

        mic_txt = f"Mic:{int(self.engine.mic_level * 100)}%" if self.sensors.mic_available else "Mic:N/A"
        extra = f" | {self._startup_msg}" if (self._startup_msg and now < self._startup_msg_until) else ""
        line1 = f"SnowDesk  |  {int(self.engine.fps)} FPS  |  CPU {int(self.engine.cpu_pct)}%  RAM {int(self.engine.ram_pct)}%"
        line2 = f"{self.engine.theme.upper()}  •  {self.engine.preset_name.upper()}  •  {self.engine.weather_label} {int(self.engine.weather_wind_kmh)}km/h  •  {mic_txt}{extra}"
        line3 = f"F1:Tema F2:HUD F5:NoelBaba Ctrl+Shift+F:HavaiFişek  Skor:{self.engine.score}"

        r1 = RectF(hx + 10.0, hy + 6.0, hw - 16.0, 20.0)
        r2 = RectF(hx + 10.0, hy + 25.0, hw - 16.0, 20.0)
        r3 = RectF(hx + 10.0, hy + 44.0, hw - 16.0, 20.0)
        if not self.hud_font.value or not self.str_fmt.value:
            return
        gdiplus.GdipDrawString(gfx, line1, len(line1), self.hud_font, ctypes.byref(r1), self.str_fmt, self.br_hud_text)
        gdiplus.GdipDrawString(gfx, line2, len(line2), self.hud_font, ctypes.byref(r2), self.str_fmt, self.br_spark)
        gdiplus.GdipDrawString(gfx, line3, len(line3), self.hud_font, ctypes.byref(r3), self.str_fmt, self.br_hud_text)

    def _render(self, now: float) -> None:
        ctypes.memset(self.bits_ptr, 0, self.buf_bytes)

        gfx = ctypes.c_void_p(0)
        gdiplus.GdipCreateFromHDC(self.mem_dc, ctypes.byref(gfx))
        gdiplus.GdipSetSmoothingMode(gfx, SmoothingModeAntiAlias)

        if self.engine.fullscreen_pause and self.sensors.is_fullscreen:
            gdiplus.GdipDeleteGraphics(gfx)
        else:
            self._draw_aurora(gfx)

            for ox1, oy1, ox2, oy2 in self.engine.occluders:
                w = ox2 - ox1
                h = oy2 - oy1
                if w > 4 and h > 4 and not (w >= self.sw * 0.98 and h >= self.sh * 0.98):
                    gdiplus.GdipSetClipRect(
                        gfx,
                        float(ox1 + 1.0),
                        float(oy1 + 1.0),
                        float(w - 2.0),
                        float(h - 2.0),
                        CombineModeExclude,
                    )

            self._draw_night_sky(gfx)

            for f in self.engine.flakes:
                if f.layer == 2:
                    self._draw_crystal_flake(gfx, f.x, f.y, f.radius, f.angle)
                else:
                    brush, halo = self._brush_for_alpha(f.alpha)
                    d = f.radius * 2.0
                    if f.layer == 1:
                        hd = f.radius * 3.0
                        gdiplus.GdipFillEllipse(gfx, halo, float(f.x - hd * 0.5), float(f.y - hd * 0.5), float(hd), float(hd))
                    gdiplus.GdipFillEllipse(gfx, brush, float(f.x - f.radius), float(f.y - f.radius), float(d), float(d))

            gdiplus.GdipResetClip(gfx)

            self._draw_corner_frost(gfx)
            self._draw_santa_sleigh(gfx)

            for rk in self.engine.rockets:
                gdiplus.GdipFillEllipse(gfx, self.fw_brushes[rk.color_idx % len(self.fw_brushes)], float(rk.x - 3.0), float(rk.y - 5.0), 6.0, 10.0)

            for p in self.engine.particles:
                sz = p.size * (p.life / p.max_life if p.kind in ("spark", "gold", "fw") else 1.0)
                if sz <= 0.3:
                    continue
                if p.kind == "spark":
                    gdiplus.GdipFillEllipse(gfx, self.br_spark, float(p.x - sz), float(p.y - sz), float(sz * 2), float(sz * 2))
                elif p.kind == "gold":
                    gdiplus.GdipFillEllipse(gfx, self.br_gold, float(p.x - sz), float(p.y - sz), float(sz * 2), float(sz * 2))
                elif p.kind == "fw":
                    br = self.fw_brushes[p.color_idx % len(self.fw_brushes)]
                    gdiplus.GdipFillEllipse(gfx, br, float(p.x - sz), float(p.y - sz), float(sz * 2), float(sz * 2))
                elif p.kind == "droplet":
                    gdiplus.GdipFillEllipse(gfx, self.br_droplet, float(p.x - sz * 0.8), float(p.y - sz * 1.2), float(sz * 1.6), float(sz * 2.4))
                elif p.kind in ("smoke", "steam"):
                    gdiplus.GdipFillEllipse(gfx, self.br_smoke, float(p.x - sz), float(p.y - sz), float(sz * 2), float(sz * 2))
                elif p.kind == "breath":
                    gdiplus.GdipFillEllipse(gfx, self.br_frost, float(p.x - sz), float(p.y - sz), float(sz * 2), float(sz * 2))
                elif p.kind == "mist":
                    gdiplus.GdipFillEllipse(gfx, self.br_mist, float(p.x - sz * 1.8), float(p.y - sz * 0.5), float(sz * 3.6), float(sz))

            for ic in self.engine.icicles:
                self._draw_icicle(gfx, ic)

            for drift in self.engine.drifts.values():
                self._draw_fairy_lights(gfx, drift)
                self._draw_drift(gfx, drift)

            for hp in self.engine.bass_hops:
                r = hp.radius
                gdiplus.GdipFillEllipse(gfx, self.br_bass_glow, float(hp.x - r * 1.4), float(hp.y - r * 1.4), float(r * 2.8), float(r * 2.8))
                gdiplus.GdipFillEllipse(gfx, self.br_white, float(hp.x - r), float(hp.y - r), float(r * 2.0), float(r * 2.0))

            for sk in self.engine.skiers:
                self._draw_skier(gfx, sk)

            self._draw_streetlamp_and_cabin(gfx, self.engine.taskbar_top)

            for tr in self.engine.trees:
                self._draw_pine_tree(gfx, tr, self.engine.taskbar_top)

            for sm in self.engine.snowmen:
                self._draw_snowman(gfx, sm)

            for sb in self.engine.snowballs:
                r = sb.radius
                if sb.resting_hwnd is not None:
                    gdiplus.GdipFillEllipse(gfx, self.br_shadow, float(sb.x - r), float(sb.y + r * 0.55), float(r * 2.0), 5.0)
                gdiplus.GdipFillEllipse(gfx, self.br_snow_shade, float(sb.x - r), float(sb.y - r), float(r * 2.0), float(r * 2.0))
                gdiplus.GdipFillEllipse(gfx, self.br_snow_mid, float(sb.x - r * 0.95), float(sb.y - r * 0.95), float(r * 1.85), float(r * 1.85))
                gdiplus.GdipFillEllipse(gfx, self.br_white, float(sb.x - r * 0.78), float(sb.y - r * 0.85), float(r * 1.35), float(r * 1.25))

            self._draw_snowplow(gfx, self.engine.plow_x, self.engine.taskbar_top)
            self._draw_tech_hud(gfx, now)
            gdiplus.GdipDeleteGraphics(gfx)

        pt_dst = POINT(self.vx, self.vy)
        pt_src = POINT(0, 0)
        sz = SIZE(self.sw, self.sh)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        ok = user32.UpdateLayeredWindow(
            self.own_hwnd,
            self.screen_dc,
            ctypes.byref(pt_dst),
            ctypes.byref(sz),
            self.mem_dc,
            ctypes.byref(pt_src),
            0,
            ctypes.byref(blend),
            ULW_ALPHA,
        )
        if not ok and self.own_hwnd != self.root.winfo_id():
            self.own_hwnd = self.root.winfo_id()
            make_overlay_click_through(self.own_hwnd)
            user32.UpdateLayeredWindow(
                self.own_hwnd, self.screen_dc, ctypes.byref(pt_dst), ctypes.byref(sz),
                self.mem_dc, ctypes.byref(pt_src), 0, ctypes.byref(blend), ULW_ALPHA,
            )

    def _tick(self) -> None:
        now = time.perf_counter()
        dt = now - self._last_time
        self._last_time = now

        self._check_hotkeys(now)
        if not self.root.winfo_exists():
            return

        self.engine.cpu_pct = self.sensors.cpu_pct
        self.engine.ram_pct = self.sensors.ram_pct
        self.engine.battery_pct = self.sensors.battery_pct
        self.engine.ac_online = self.sensors.ac_online
        self.engine.mic_level = self.sensors.mic_level
        self.engine.audio_peak = self.sensors.audio_peak
        self.engine.now_playing = self.sensors.now_playing
        self.engine.weather_wind_kmh = self.sensors.weather_wind_kmh
        self.engine.weather_label = self.sensors.weather_label

        if not (self.engine.fullscreen_pause and self.sensors.is_fullscreen):
            self._scan_surfaces()
            self._check_typing_activity()

            pt = POINT()
            mouse_pos = (float(pt.x - self.vx), float(pt.y - self.vy)) if user32.GetCursorPos(ctypes.byref(pt)) else None
            lbutton = _key_down(VK_LBUTTON)

            if mouse_pos is not None:
                interactive = self.engine.is_point_interactive(mouse_pos[0], mouse_pos[1])
                set_overlay_interactive(self.own_hwnd, interactive)

            self.engine.step(dt, mouse_pos, lbutton_down=lbutton)

        self._render(now)
        elapsed = time.perf_counter() - now
        delay_ms = max(1, int((1.0 / 60.0 - elapsed) * 1000.0))
        self.root.after(delay_ms, self._tick)

    def _cleanup(self) -> None:
        self.sensors.stop()
        try:
            if self.santa_img:
                gdiplus.GdipDisposeImage(self.santa_img)
            gdiplus.GdipDeleteFont(self.hud_font)
            gdiplus.GdipDeleteFont(self.small_font)
            gdiplus.GdipDeleteFontFamily(self.font_family)
            gdiplus.GdipDeleteStringFormat(self.str_fmt)
            for b, gb in self.light_bulbs:
                gdiplus.GdipDeleteBrush(b)
                gdiplus.GdipDeleteBrush(gb)
            for b in self.fw_brushes:
                gdiplus.GdipDeleteBrush(b)
            for tkey in self.flake_brushes:
                for b in self.flake_brushes[tkey] + self.halo_brushes[tkey]:
                    gdiplus.GdipDeleteBrush(b)
            for b in [
                self.br_white, self.br_snow_mid, self.br_snow_shade, self.br_shadow,
                self.br_icicle, self.br_frost, self.br_droplet, self.br_blush, self.br_black,
                self.br_carrot, self.br_scarf_red, self.br_scarf_blue, self.br_yellow,
                self.br_amber, self.br_gold, self.br_gold_glow, self.br_light_cone,
                self.br_red_glow, self.br_bass_glow, self.br_glass, self.br_silver,
                self.br_gray, self.br_pine_deep, self.br_pine_dark, self.br_pine_light,
                self.br_trunk, self.br_cabin, self.br_cabin_dark, self.br_roof,
                self.br_banner_bg, self.br_spark, self.br_mist, self.br_smoke,
                self.br_hud_bg, self.br_hud_text, self.br_moon, self.br_moon_glow, self.br_moon_cut,
            ]:
                gdiplus.GdipDeleteBrush(b)
            gdiplus.GdipDeletePen(self.drift_pen)
            gdiplus.GdipDeletePen(self.twig_pen)
            gdiplus.GdipDeletePen(self.wire_pen)
            gdiplus.GdipDeletePen(self.crystal_pen)
            gdiplus.GdipDeletePen(self.cyber_pen)
            gdiplus.GdipDeletePen(self.gold_pen)
            gdiplus.GdipDeletePen(self.hud_pen)
            gdiplus.GdipDeletePen(self.star_pen)
            gdiplus.GdipDeletePen(self.ice_spec_pen)
            gdi32.SelectObject(self.mem_dc, self.old_bmp)
            gdi32.DeleteObject(self.hbmp)
            gdi32.DeleteDC(self.mem_dc)
            user32.ReleaseDC(None, self.screen_dc)
            gdiplus.GdiplusShutdown(self.gdip_token)
        except Exception:
            pass

    def run(self) -> int:
        self.root.mainloop()
        return 0


def run_app() -> int:
    app = SnowDeskApp()
    return app.run()
