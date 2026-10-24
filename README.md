# AirLink — Windows Drag-to-Share Panel Prototype

This updated prototype keeps the existing **Nearby / Activity / Settings** dashboard, and adds a Windows background mode that reveals a vertical AirLink device panel when a global left-button drag gesture is detected. The panel is a file drop target: drag a file from File Explorer and drop it onto one of the sample device cards.

## Quick start

1. Extract the entire ZIP to a normal folder (for example, `Downloads\AirLink_Windows_5m_Demo`). Do not run the app from inside the ZIP preview.
2. Double-click `setup_and_run.bat`. This installs the dependencies, then opens the familiar dashboard.
3. The AirLink icon should appear in the Windows system tray. Closing the dashboard window hides it to the tray; choose **Open AirLink** from the tray icon to reopen it.
4. Double-click `start_background.bat` to start AirLink hidden in the tray. You do not need to keep the dashboard open.
5. To start AirLink automatically when you sign into Windows, run `install_startup.bat` once. To undo this, run `remove_startup.bat`.

## How to test the panel

1. Start AirLink with `start_background.bat`.
2. Open File Explorer and drag a file. Once a drag gesture is detected, a right-side panel should appear.
3. Drop the file directly on one of the device cards. The panel will show that a file drop was detected and remember the selected file/receiver in the dashboard.
4. Use the AirLink tray menu to reopen the old dashboard.

## Honest current limitations

- The three device names and RSSI values are sample data, not nearby computers discovered over Bluetooth or Wi-Fi.
- The current app detects global mouse drag gestures. Since a low-level mouse hook cannot reliably tell whether every drag originates from a file object, the panel may also appear during some non-file left-button drags; the panel only processes supported file drops.
- The 5 m rule is an illustrative RSSI policy, not reliable physical-distance measurement.
- This prototype does **not transmit file bytes to another computer yet**. It detects a local file drop and previews the selected recipient. Real pairing, discovery, secure socket transfer, receiver approval, and transfer-progress handling remain to be implemented.

## Commands

```powershell
python -m pip install -r requirements.txt
python -m unittest -v test_proximity_policy.py
python app.py
python app.py --background
```

Windows only. If Windows prompts about Python or security software, review the prompt before allowing anything. The app does not need administrator privileges for its normal operation.
