"""
Hardware, System Audio Peak (Core Audio COM ctypes), Mic Blow, Media Title, Weather & Startup Sensors.
100% built-in Windows ctypes + Python stdlib (zero external packages).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import math
import os
import struct
import threading
import time
import urllib.request


kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32
winmm = ctypes.windll.winmm
shell32 = ctypes.windll.shell32
ole32 = ctypes.windll.ole32


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wt.DWORD),
        ("Data2", wt.WORD),
        ("Data3", wt.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_str(cls, s: str) -> "GUID":
        s = s.strip("{}")
        p = s.split("-")
        d4 = bytes.fromhex(p[3] + p[4])
        return cls(int(p[0], 16), int(p[1], 16), int(p[2], 16), (ctypes.c_ubyte * 8)(*d4))


CLSID_MMDeviceEnumerator = GUID.from_str("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
IID_IMMDeviceEnumerator = GUID.from_str("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
IID_IAudioMeterInformation = GUID.from_str("{C02216F6-8C67-4B5B-9D00-D008E73E0064}")


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wt.DWORD), ("dwHighDateTime", wt.DWORD)]


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wt.DWORD),
        ("dwMemoryLoad", wt.DWORD),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_ubyte),
        ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte),
        ("SystemStatusFlag", ctypes.c_ubyte),
        ("BatteryLifeTime", wt.DWORD),
        ("BatteryFullLifeTime", wt.DWORD),
    ]


class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [
        ("wFormatTag", wt.WORD),
        ("nChannels", wt.WORD),
        ("nSamplesPerSec", wt.DWORD),
        ("nAvgBytesPerSec", wt.DWORD),
        ("nBlockAlign", wt.WORD),
        ("wBitsPerSample", wt.WORD),
        ("cbSize", wt.WORD),
    ]


class WAVEHDR(ctypes.Structure):
    _fields_ = [
        ("lpData", ctypes.c_void_p),
        ("dwBufferLength", wt.DWORD),
        ("dwBytesRecorded", wt.DWORD),
        ("dwUser", ctypes.c_size_t),
        ("dwFlags", wt.DWORD),
        ("dwLoops", wt.DWORD),
        ("lpNext", ctypes.c_void_p),
        ("reserved", ctypes.c_size_t),
    ]


kernel32.GetSystemTimes.argtypes = [ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME)]
kernel32.GetSystemTimes.restype = wt.BOOL
kernel32.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(MEMORYSTATUSEX)]
kernel32.GlobalMemoryStatusEx.restype = wt.BOOL
kernel32.GetSystemPowerStatus.argtypes = [ctypes.POINTER(SYSTEM_POWER_STATUS)]
kernel32.GetSystemPowerStatus.restype = wt.BOOL
shell32.SHQueryUserNotificationState.argtypes = [ctypes.POINTER(ctypes.c_int)]
shell32.SHQueryUserNotificationState.restype = ctypes.c_long

ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wt.DWORD]
ole32.CoInitializeEx.restype = ctypes.c_long
ole32.CoUninitialize.argtypes = []
ole32.CoCreateInstance.argtypes = [ctypes.POINTER(GUID), ctypes.c_void_p, wt.DWORD, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
ole32.CoCreateInstance.restype = ctypes.c_long

winmm.waveInOpen.argtypes = [ctypes.POINTER(ctypes.c_void_p), wt.UINT, ctypes.POINTER(WAVEFORMATEX), ctypes.c_size_t, ctypes.c_size_t, wt.DWORD]
winmm.waveInOpen.restype = wt.UINT
winmm.waveInStart.argtypes = [ctypes.c_void_p]
winmm.waveInStop.argtypes = [ctypes.c_void_p]
winmm.waveInClose.argtypes = [ctypes.c_void_p]
winmm.waveInPrepareHeader.argtypes = [ctypes.c_void_p, ctypes.POINTER(WAVEHDR), wt.UINT]
winmm.waveInUnprepareHeader.argtypes = [ctypes.c_void_p, ctypes.POINTER(WAVEHDR), wt.UINT]
winmm.waveInAddBuffer.argtypes = [ctypes.c_void_p, ctypes.POINTER(WAVEHDR), wt.UINT]


def _com_vtable(obj_ptr: ctypes.c_void_p, index: int, restype, *argtypes):
    vtbl = ctypes.cast(obj_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    fn_type = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    return fn_type(vtbl[index])


def _ft_to_int(ft: FILETIME) -> int:
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


def _detect_now_playing() -> str:
    """Detect active music/media title from Spotify, YouTube, VLC, or Music window titles."""
    found: list[str] = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def _cb(hwnd, _lp):
        if not user32.IsWindowVisible(hwnd):
            return True
        ln = user32.GetWindowTextLengthW(hwnd)
        if ln <= 2 or ln > 160:
            return True
        buf = ctypes.create_unicode_buffer(ln + 1)
        user32.GetWindowTextW(hwnd, buf, ln + 1)
        title = buf.value.strip()
        if not title:
            return True

        # YouTube / YouTube Music in browser
        for suffix in (" - YouTube Music", " - YouTube - Google Chrome", " - YouTube - Microsoft Edge", " - YouTube"):
            if suffix in title:
                clean = title.split(suffix)[0].strip()
                if clean and clean.lower() not in ("youtube", "youtube music"):
                    found.append(clean[:44])
                    return False

        # VLC Media Player
        if title.endswith(" - VLC media player"):
            clean = title[:-19].strip()
            if clean:
                found.append(clean[:44])
                return False

        # Spotify (when playing, window title is "Artist - Song" with Chrome_WidgetWin_0/1)
        cls_buf = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, cls_buf, 64)
        if "Chrome_WidgetWin" in cls_buf.value and " - " in title:
            low = title.lower()
            if not any(b in low for b in ("google chrome", "microsoft edge", "visual studio", "discord", "mozilla")):
                found.append(title[:44])
                return False

        return True

    user32.EnumWindows(EnumWindowsProc(_cb), 0)
    return found[0] if found else ""


class SystemSensors:
    def __init__(self) -> None:
        self.cpu_pct: float = 12.0
        self.ram_pct: float = 40.0
        self.battery_pct: int = 100
        self.ac_online: bool = True
        self.is_fullscreen: bool = False
        self.mic_level: float = 0.0
        self.mic_available: bool = False
        self.audio_peak: float = 0.0  # 0.0..1.0 system audio output peak
        self.now_playing: str = ""
        self.weather_wind_kmh: float = 10.0
        self.weather_label: str = "Açık"

        self._prev_idle = 0
        self._prev_total = 0
        self._running = True

        threading.Thread(target=self._poll_system_loop, daemon=True).start()
        threading.Thread(target=self._audio_meter_loop, daemon=True).start()
        threading.Thread(target=self._mic_loop, daemon=True).start()
        threading.Thread(target=self._media_loop, daemon=True).start()
        threading.Thread(target=self._weather_loop, daemon=True).start()

    def stop(self) -> None:
        self._running = False

    def _poll_system_loop(self) -> None:
        while self._running:
            try:
                idle, kernel, user = FILETIME(), FILETIME(), FILETIME()
                if kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
                    i_val = _ft_to_int(idle)
                    t_val = _ft_to_int(kernel) + _ft_to_int(user)
                    if self._prev_total > 0:
                        dt_total = t_val - self._prev_total
                        dt_idle = i_val - self._prev_idle
                        if dt_total > 0:
                            self.cpu_pct = max(0.0, min(100.0, 100.0 * (1.0 - dt_idle / dt_total)))
                    self._prev_idle = i_val
                    self._prev_total = t_val

                mem = MEMORYSTATUSEX()
                mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):
                    self.ram_pct = float(mem.dwMemoryLoad)

                pwr = SYSTEM_POWER_STATUS()
                if kernel32.GetSystemPowerStatus(ctypes.byref(pwr)):
                    self.ac_online = (pwr.ACLineStatus == 1)
                    if pwr.BatteryLifePercent <= 100:
                        self.battery_pct = int(pwr.BatteryLifePercent)

                state = ctypes.c_int(0)
                if shell32.SHQueryUserNotificationState(ctypes.byref(state)) == 0:
                    self.is_fullscreen = state.value in (2, 3, 4)
            except Exception:
                pass
            time.sleep(1.0)

    def _media_loop(self) -> None:
        while self._running:
            try:
                self.now_playing = _detect_now_playing()
            except Exception:
                self.now_playing = ""
            time.sleep(1.5)

    def _audio_meter_loop(self) -> None:
        """Read real-time system audio output peak via Windows Core Audio IAudioMeterInformation."""
        try:
            ole32.CoInitializeEx(None, 0)  # COINIT_MULTITHREADED = 0
            p_enum = ctypes.c_void_p(0)
            hr = ole32.CoCreateInstance(
                ctypes.byref(CLSID_MMDeviceEnumerator),
                None,
                23,  # CLSCTX_ALL
                ctypes.byref(IID_IMMDeviceEnumerator),
                ctypes.byref(p_enum),
            )
            if hr != 0 or not p_enum.value:
                return

            get_default = _com_vtable(p_enum, 4, ctypes.c_long, wt.INT, wt.INT, ctypes.POINTER(ctypes.c_void_p))
            p_dev = ctypes.c_void_p(0)
            if get_default(p_enum, 0, 0, ctypes.byref(p_dev)) != 0 or not p_dev.value:
                return

            activate = _com_vtable(p_dev, 3, ctypes.c_long, ctypes.POINTER(GUID), wt.DWORD, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
            p_meter = ctypes.c_void_p(0)
            if activate(p_dev, ctypes.byref(IID_IAudioMeterInformation), 23, None, ctypes.byref(p_meter)) != 0 or not p_meter.value:
                return

            get_peak = _com_vtable(p_meter, 3, ctypes.c_long, ctypes.POINTER(ctypes.c_float))
            peak = ctypes.c_float(0.0)
            while self._running:
                if get_peak(p_meter, ctypes.byref(peak)) == 0:
                    self.audio_peak = max(0.0, min(1.0, float(peak.value)))
                time.sleep(0.02)

            release_m = _com_vtable(p_meter, 2, ctypes.c_ulong)
            release_d = _com_vtable(p_dev, 2, ctypes.c_ulong)
            release_e = _com_vtable(p_enum, 2, ctypes.c_ulong)
            release_m(p_meter)
            release_d(p_dev)
            release_e(p_enum)
            ole32.CoUninitialize()
        except Exception:
            pass

    def _mic_loop(self) -> None:
        try:
            hwi = ctypes.c_void_p(0)
            wfx = WAVEFORMATEX(1, 1, 8000, 16000, 2, 16, 0)
            res = winmm.waveInOpen(ctypes.byref(hwi), 0xFFFFFFFF, ctypes.byref(wfx), 0, 0, 0)
            if res != 0 or not hwi.value:
                return
            self.mic_available = True
            winmm.waveInStart(hwi)

            buf_samples = 512
            buf_bytes = buf_samples * 2
            buf = (ctypes.c_char * buf_bytes)()
            hdr = WAVEHDR()
            hdr.lpData = ctypes.cast(buf, ctypes.c_void_p).value
            hdr.dwBufferLength = buf_bytes

            while self._running:
                hdr.dwFlags = 0
                hdr.dwBytesRecorded = 0
                winmm.waveInPrepareHeader(hwi, ctypes.byref(hdr), ctypes.sizeof(hdr))
                winmm.waveInAddBuffer(hwi, ctypes.byref(hdr), ctypes.sizeof(hdr))
                t0 = time.perf_counter()
                while self._running and not (hdr.dwFlags & 1):
                    if time.perf_counter() - t0 > 0.25:
                        break
                    time.sleep(0.015)
                winmm.waveInUnprepareHeader(hwi, ctypes.byref(hdr), ctypes.sizeof(hdr))
                if hdr.dwBytesRecorded >= 4:
                    n_s = hdr.dwBytesRecorded // 2
                    samples = struct.unpack(f"<{n_s}h", bytes(buf[: n_s * 2]))
                    rms = math.sqrt(sum(s * s for s in samples) / max(1, n_s)) / 32768.0
                    level = min(1.0, rms * 5.5)
                    self.mic_level = max(level, self.mic_level * 0.72)

            winmm.waveInStop(hwi)
            winmm.waveInClose(hwi)
        except Exception:
            self.mic_available = False

    def _weather_loop(self) -> None:
        while self._running:
            try:
                url = "https://api.open-meteo.com/v1/forecast?latitude=37.84&longitude=27.84&current=wind_speed_10m,weather_code"
                req = urllib.request.Request(url, headers={"User-Agent": "SnowDesk/1.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    cur = data.get("current", {})
                    self.weather_wind_kmh = float(cur.get("wind_speed_10m", 10.0))
                    code = int(cur.get("weather_code", 0))
                    if code >= 71:
                        self.weather_label = "Karlı"
                    elif code >= 51:
                        self.weather_label = "Yağmurlu"
                    elif code >= 1:
                        self.weather_label = "Bulutlu"
                    else:
                        self.weather_label = "Açık"
            except Exception:
                pass
            time.sleep(900)


def toggle_windows_startup(project_dir: str) -> bool:
    startup_dir = os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft",
        "Windows",
        "Start Menu",
        "Programs",
        "Startup",
    )
    if not os.path.isdir(startup_dir):
        return False
    bat_path = os.path.join(startup_dir, "SnowDeskStartup.vbs")
    if os.path.exists(bat_path):
        os.remove(bat_path)
        return False
    main_py = os.path.join(project_dir, "main.py").replace('"', '""')
    content = (
        'Set objShell = CreateObject("WScript.Shell")\n'
        f'objShell.CurrentDirectory = "{project_dir}"\n'
        f'objShell.Run "pyw ""{main_py}""", 0, False\n'
    )
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(content)
    return True
