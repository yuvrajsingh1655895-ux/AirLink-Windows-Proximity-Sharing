# AirLink — Wallpaper-Adaptive Windows Drag-to-Share Prototype

AirLink is a Windows desktop UI prototype exploring an AirDrop-like drag-to-share workflow. The normal Nearby / Activity / Settings dashboard stays available; when a global mouse drag is detected, a compact receiver panel can appear along the right edge of the desktop.

## Wallpaper-adaptive theme

- At launch, AirLink samples the current Windows desktop wallpaper and derives a dominant accent hue.
- The dashboard and sharing panel use a dark tinted palette based on that hue, so blue, green, purple, and other colorful wallpapers produce different accent and surface tints.
- AirLink checks the wallpaper periodically and updates the palette when the wallpaper changes.
- This is a **wallpaper-colour-matched theme**, not a true Windows Acrylic/Mica blur effect. The UI uses Tkinter, which does not provide native Windows backdrop blur by itself.

## Quick start

1. Extract the complete ZIP into a normal folder; do not run the project from inside ZIP preview.
2. Double-click `setup_and_run.bat`. It installs the Python dependencies and opens the dashboard.
3. Closing the dashboard hides it to the system tray. Choose **Open AirLink** from the tray menu to reopen it.
4. To start it hidden, double-click `start_background.bat`.
5. To start AirLink automatically when you sign into Windows, run `install_startup.bat` once. Use `remove_startup.bat` to undo this.

## Test the drag panel

1. Start AirLink in the background with `start_background.bat`.
2. Drag a file from File Explorer. The global mouse-drag detector should show the right-side receiver panel.
3. Drop the file onto a sample device card. AirLink remembers the selected file/receiver and displays a demo status.
4. Open the dashboard from the system tray to see the selected file and receiver.

## Run checks

```powershell
python -m pip install -r requirements.txt
python -m unittest -v
python app.py
python app.py --background
```

## Important limitations

- Device names and RSSI values are sample data, not computers discovered through Bluetooth or Wi-Fi.
- The global mouse hook detects general drag gestures; it cannot guarantee that every gesture comes from a file in Explorer, so the panel may briefly appear during some non-file drags.
- The approximate 5 m rule is a demonstration policy based on illustrative RSSI values. Wi-Fi/Bluetooth signal strength cannot guarantee a physical 5 m boundary.
- **Actual laptop-to-laptop file transfer is not implemented.** Pairing, real device discovery, secure networking, receiver approval, and byte transfer still need to be developed.
- Dynamic palette sampling works when Windows exposes a readable wallpaper image path. If it cannot read the wallpaper, AirLink falls back to the default blue palette.

## Project structure

- `app.py` — dashboard, tray, and drag panel
- `wallpaper_theme.py` — wallpaper sampling, palette generation, and widget recoloring
- `proximity_policy.py` — demo proximity gate
- `test_proximity_policy.py` — proximity policy unit tests
- `test_wallpaper_theme.py` — adaptive palette tests

Windows only. If Windows prompts about Python or security software, review the prompt before allowing it. AirLink does not require administrator privileges for normal use.
