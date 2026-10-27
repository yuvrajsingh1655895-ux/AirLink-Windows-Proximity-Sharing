# AirLink — Wallpaper-Adaptive Acrylic Glass UI

AirLink is a Windows desktop UI prototype for an AirDrop-like sharing flow. The normal dashboard remains available when the app is opened. When a drag gesture starts anywhere on the desktop, a floating device dock appears at the right edge; it accepts file drops from File Explorer.

## What this version changes

- **Glass UI:** frameless rounded windows, translucent surfaces, glass-style device cards, soft outlines, and a floating dock.
- **Native Windows material:** on Windows, AirLink requests the Acrylic composition/backdrop effect through Windows composition APIs. The exact blur strength depends on Windows build, graphics settings, and accessibility settings. If the native effect cannot be applied, the UI falls back to translucent Qt surfaces.
- **Wallpaper-matched colors:** AirLink samples the current wallpaper and chooses a dominant accent hue. It polls every five seconds, so blue, green, purple, warm, and neutral wallpapers can shift the accent automatically.
- **Two modes:** opening AirLink shows the full Nearby / Activity / Settings dashboard. Starting in background mode leaves it in the system tray; dragging a file reveals the floating right-side panel.
- **System tray:** use “Open AirLink”, “Show drop panel”, or “Quit AirLink”. Closing the dashboard hides it to the tray rather than stopping background monitoring.

## Quick start on Windows

1. Extract the entire ZIP into a normal folder (do not run from the ZIP preview).
2. Double-click `setup_and_run.bat`. It installs dependencies and opens the main dashboard.
3. To run only in the background, use `start_background.bat` after the first setup.
4. To run automatically after Windows sign-in, use `install_startup.bat` once. Undo with `remove_startup.bat`.
5. Right-click the AirLink tray icon and choose `Quit AirLink` to fully stop it.

### Dependencies

- PySide6 for the glass-style desktop UI
- pynput for global mouse-drag gesture detection
- Pillow for reading the wallpaper and choosing an accent palette

## Important honest limitations

- **Global drag detection is a heuristic.** Windows does not expose a universal file-only “drag started” event to ordinary desktop applications. The panel can briefly appear for other left-button drag gestures too; it accepts local file drops from Explorer.
- **Device names and signal levels are sample data.** AirLink does not yet discover laptops over Bluetooth or Wi-Fi, pair with them, or establish a secure connection.
- **Actual file transmission is not implemented.** A successful drop records a local UI demo event only; it does not send file bytes to another device.
- **The 5-metre rule is illustrative.** RSSI can vary with walls, interference, antenna design, and hardware; it cannot prove an exact physical distance.
- Wallpaper adaptation requires Windows to expose a readable wallpaper image path. Otherwise the default blue palette is used.

## Checks

```powershell
python -m pip install -r requirements.txt
python -m unittest -v
python app.py
python app.py --background
```

The automated tests cover the conservative demo proximity policy and wallpaper palette generation. The Windows Acrylic effect and global drag/drop behavior still need to be verified on the target Windows laptop.

## Updating an existing GitHub repo

Copy the source files from this folder into the cloned repository folder (preserve the hidden `.git` folder). Commit the changes with a message such as `Redesign AirLink with acrylic glass UI`, then push to origin.
