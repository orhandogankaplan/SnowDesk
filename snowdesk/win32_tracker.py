"""
Win32 Window, Multi-Monitor Taskbar, and Dynamic Click-Through tracker for SnowDesk.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
from dataclasses import dataclass
from typing import List, Optional, Tuple


user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14

SKIP_CLASSES = {
    "Progman",
    "WorkerW",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "Windows.UI.Core.CoreWindow",
    "ApplicationFrameInputSinkWindow",
    "ForegroundStaging",
    "MultitaskingViewFrame",
    "Xaml_WindowedPopupClass",
    "EdgeUiInputTopWndClass",
    "EdgeUiInputWndClass",
    "SysShadow",
}


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


@dataclass
class SurfaceRect:
    hwnd: int
    left: float
    top: float
    right: float
    bottom: float
    is_taskbar: bool = False
    visible_spans: Optional[List[Tuple[float, float]]] = None


def enable_dpi_awareness() -> None:
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def get_virtual_screen_bounds() -> Tuple[int, int, int, int]:
    """Return (x, y, width, height) covering all connected monitors."""
    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    if vw <= 0 or vh <= 0:
        return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    return vx, vy, vw, vh


def make_overlay_click_through(hwnd: int) -> None:
    try:
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    except Exception:
        pass


def set_overlay_interactive(hwnd: int, interactive: bool) -> None:
    try:
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if interactive:
            new_style = (style | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE) & ~WS_EX_TRANSPARENT
        else:
            new_style = style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        if new_style != style:
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
    except Exception:
        pass


def _get_window_rect_dwm(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    rect = RECT()
    hr = dwmapi.DwmGetWindowAttribute(
        wt.HWND(hwnd),
        wt.DWORD(DWMWA_EXTENDED_FRAME_BOUNDS),
        ctypes.byref(rect),
        ctypes.sizeof(rect),
    )
    if hr == 0:
        return rect.left, rect.top, rect.right, rect.bottom
    if user32.GetWindowRect(wt.HWND(hwnd), ctypes.byref(rect)):
        return rect.left, rect.top, rect.right, rect.bottom
    return None


def _is_window_cloaked(hwnd: int) -> bool:
    cloaked = ctypes.c_int(0)
    hr = dwmapi.DwmGetWindowAttribute(
        wt.HWND(hwnd),
        wt.DWORD(DWMWA_CLOAKED),
        ctypes.byref(cloaked),
        ctypes.sizeof(cloaked),
    )
    return hr == 0 and cloaked.value != 0


def _get_class_name(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(128)
    user32.GetClassNameW(wt.HWND(hwnd), buf, 128)
    return buf.value


def _subtract_occluders(
    x1: float, x2: float, y: float, occluders: List[Tuple[float, float, float, float]]
) -> List[Tuple[float, float]]:
    spans = [(x1, x2)]
    for ox1, oy1, ox2, oy2 in occluders:
        if oy1 <= y + 2 and oy2 >= y - 2:
            new_spans: List[tuple[float, float]] = []
            for sx1, sx2 in spans:
                if ox2 <= sx1 or ox1 >= sx2:
                    new_spans.append((sx1, sx2))
                else:
                    if ox1 > sx1:
                        new_spans.append((sx1, ox1))
                    if ox2 < sx2:
                        new_spans.append((ox2, sx2))
            spans = new_spans
            if not spans:
                break
    return [(a, b) for a, b in spans if (b - a) >= 16]


def get_visible_surfaces(
    own_hwnd: int,
    virt_x: float,
    virt_y: float,
    screen_w: float,
    screen_h: float,
    dpr: float = 1.0,
) -> Tuple[List[SurfaceRect], List[Tuple[float, float, float, float]]]:
    surfaces: List[SurfaceRect] = []
    occluders: List[Tuple[float, float, float, float]] = []

    # Primary taskbar (and secondary monitor taskbar if present)
    for cls_name in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
        tb_hwnd = user32.FindWindowW(cls_name, None)
        if tb_hwnd and user32.IsWindowVisible(tb_hwnd):
            r = _get_window_rect_dwm(tb_hwnd)
            if r:
                lx1 = r[0] / dpr - virt_x
                ly1 = r[1] / dpr - virt_y
                lx2 = r[2] / dpr - virt_x
                ly2 = r[3] / dpr - virt_y
                if (lx2 - lx1) > 100 and ly1 > 40:
                    surfaces.append(
                        SurfaceRect(
                            hwnd=int(tb_hwnd),
                            left=max(0.0, lx1),
                            top=ly1,
                            right=min(screen_w, lx2),
                            bottom=ly2,
                            is_taskbar=True,
                            visible_spans=[(max(0.0, lx1), min(screen_w, lx2))],
                        )
                    )

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def _callback(hwnd, _lparam):
        ihwnd = int(hwnd)
        if ihwnd == own_hwnd:
            return True
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        if _is_window_cloaked(ihwnd):
            return True

        exstyle = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if exstyle & (WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE):
            return True
        if user32.GetWindowTextLengthW(hwnd) <= 0:
            return True

        cls = _get_class_name(ihwnd)
        if cls in SKIP_CLASSES:
            return True

        r = _get_window_rect_dwm(ihwnd)
        if not r:
            return True

        lx1 = r[0] / dpr - virt_x
        ly1 = r[1] / dpr - virt_y
        lx2 = r[2] / dpr - virt_x
        ly2 = r[3] / dpr - virt_y
        w = lx2 - lx1
        h = ly2 - ly1
        if w < 140 or h < 80:
            return True
        if lx2 <= 0 or lx1 >= screen_w or ly2 <= 0 or ly1 >= screen_h:
            return True

        cx1 = max(0.0, lx1)
        cx2 = min(screen_w, lx2)

        if ly1 >= 14 and (cx2 - cx1) >= 40:
            spans = _subtract_occluders(cx1, cx2, ly1, occluders)
            if spans:
                surfaces.append(
                    SurfaceRect(
                        hwnd=ihwnd,
                        left=cx1,
                        top=ly1,
                        right=cx2,
                        bottom=ly2,
                        is_taskbar=False,
                        visible_spans=spans,
                    )
                )

        occluders.append((cx1, max(0.0, ly1), cx2, min(screen_h, ly2)))
        return True

    user32.EnumWindows(EnumWindowsProc(_callback), 0)
    return surfaces, occluders
