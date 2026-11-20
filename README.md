# SnowDesk ❄️

A zero-dependency, 60 FPS interactive winter desktop overlay for Windows 10/11. Built purely with Python's standard library (`tkinter` + `ctypes` Win32/GDI+ + `winmm` + `winsound`) so it runs smoothly without `pip install` or unsigned `.pyd` extensions.

## Features

- **Real-Time Tech & Environment Sensors:**
  - **Microphone Blow Detection:** Blow or speak near your mic to splash snowdrifts and gust snowflakes away from your cursor!
  - **CPU/RAM-Reactive Corner Frost:** Corner ice crystals melt when system load rises and refreeze when idle.
  - **Thermal Cursor Melting:** Holding your cursor over snow melts it into dripping water droplets and steam.
  - **Live Weather & Battery Sync:** Pulls real-time local wind speed (Open-Meteo) and turns the taskbar streetlamp red-amber when laptop battery drops below 25%.
  - **Fullscreen Auto-Pause:** Automatically hides during fullscreen games or movies.
- **Illustrated Santa Claus & Reindeer Sleigh:** Flies across the sky periodically (or anytime with **`F5`**), leaving golden stardust.
- **Aurora Borealis & 4 Themes (`F1` / `F3`):** Switch between `Classic`, `Aurora`, `Cyber-Snow (Neon)`, and `Gold` themes, with a glassmorphism Tech HUD (`F2`).
- **True Zero-Glue Window Physics:** Dragging windows detaches snow naturally; icicles grow on corners and break off when shaken; snowmen track your cursor with their eyes and shatter on high-speed throws; rolling & stacking two snowballs builds a new snowman!

## Quick Start

1. Make sure **Python 3.10+** is installed on Windows.
2. Double-click **`SnowDesk.vbs`** (or run `start "" pyw main.py`).

## Hotkeys

| Action | Shortcut |
| :--- | :--- |
| Cycle Theme (`Classic` / `Aurora` / `Cyber` / `Gold`) | **`F1`** |
| Toggle Glassmorphism Tech HUD | **`F2`** |
| Toggle Aurora Borealis | **`F3`** |
| Toggle Winter Sound Effects | **`F4`** |
| Summon Illustrated Santa & Reindeer Sleigh | **`F5`** |
| Cycle Snow Density (`Gentle` / `Cozy` / `Blizzard`) | **`F6`** |
| Toggle Window Fairy Lights | **`F7`** |
| Sweep Snow with Yellow Snowplow | **`F8`** or **`Ctrl + Shift + C`** |
| Pause / Resume | **`F9`** |
| Exit SnowDesk | **`F10`** |
| Reels Demo Mode (9s showcase) | **`F11`** |
| Toggle Windows Auto-Startup | **`F12`** |

## License

[MIT](LICENSE)
