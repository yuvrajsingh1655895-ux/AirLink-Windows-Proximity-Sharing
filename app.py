"""AirLink: Windows drag-to-share panel prototype.

The mouse hook only detects drag gestures. tkinterdnd2 receives actual file drops.
Device discovery, RSSI values, and the transfer action remain demo-only.
"""
from __future__ import annotations

import argparse
import queue
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError as exc:  # Explain setup clearly instead of failing with a cryptic traceback.
    raise SystemExit(
        "AirLink needs its Windows drag-and-drop dependencies.\n"
        "Run setup_and_run.bat once, or run: python -m pip install -r requirements.txt"
    ) from exc

from proximity_policy import ProximityPolicy

BG = "#0b1020"
PANEL = "#121a2e"
PANEL2 = "#17223a"
BORDER = "#263450"
TEXT = "#edf3ff"
MUTED = "#9aa9c4"
BLUE = "#6aa8ff"
CYAN = "#61e6dc"
GREEN = "#69e0a3"
ORANGE = "#ffca78"


class AirLink:
    """The familiar full dashboard; it can be hidden to the system tray."""

    def __init__(self, root):
        self.root = root
        root.title("AirLink — Windows proximity sharing")
        root.geometry("1050x720")
        root.minsize(900, 620)
        root.configure(bg=BG)
        self.policy = ProximityPolicy(target_metres=5)
        self.device = None
        self.file = None
        self.history = []
        # These names and signal values are deliberately sample data.
        self.devices = [
            ("DESKTOP-STUDIO", "Windows laptop", -48),
            ("Study Laptop", "Windows laptop", -62),
            ("Room PC", "Windows laptop", -75),
        ]
        self.page = "Nearby"
        self.build()
        self.nearby()

    def label(self, p, t, size=10, color=TEXT, bold=False, **kw):
        return tk.Label(
            p,
            text=t,
            bg=kw.pop("bg", p.cget("bg")),
            fg=color,
            font=("Segoe UI", size, "bold" if bold else "normal"),
            **kw,
        )

    def btn(self, p, t, cmd, primary=False):
        return tk.Button(
            p,
            text=t,
            command=cmd,
            bg=BLUE if primary else PANEL2,
            fg="#07101f" if primary else TEXT,
            activebackground=CYAN,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            padx=14,
            pady=9,
        )

    def build(self):
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=26, pady=20)
        self.label(top, "◉", 28, CYAN, True).pack(side="left", padx=(0, 12))
        title = tk.Frame(top, bg=BG)
        title.pack(side="left")
        self.label(title, "AirLink", 22, TEXT, True).pack(anchor="w")
        self.label(title, "WINDOWS ONLY  ·  APPROX. 5 METRE POLICY", 8, MUTED, True).pack(anchor="w")
        self.label(top, "● BACKGROUND READY", 9, GREEN, True, bg="#112b2a").pack(side="right", pady=10, padx=10)

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=26, pady=(0, 18))
        side = tk.Frame(body, bg=PANEL, width=190, highlightbackground=BORDER, highlightthickness=1)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        self.label(side, "WORKSPACE", 9, MUTED, True).pack(anchor="w", padx=16, pady=(22, 10))
        self.nav = {}
        for name in ("Nearby", "Activity", "Settings"):
            b = tk.Button(
                side,
                text="  " + name,
                anchor="w",
                command=lambda n=name: self.show(n),
                bg=PANEL,
                fg=TEXT,
                activebackground=PANEL2,
                relief="flat",
                bd=0,
                font=("Segoe UI", 11),
                padx=14,
                pady=12,
            )
            b.pack(fill="x", padx=8)
            self.nav[name] = b
        self.label(
            side,
            "Drag a file anywhere on the desktop.\nAirLink's receiver panel appears while dragging.",
            9,
            MUTED,
            justify="left",
            wraplength=155,
        ).pack(side="bottom", anchor="w", padx=16, pady=18)
        self.content = tk.Frame(body, bg=BG)
        self.content.pack(side="left", fill="both", expand=True, padx=(20, 0))
        self.label(
            self.root,
            "SAMPLE DEVICES · NO REAL DISCOVERY OR FILE TRANSFER YET",
            8,
            "#657693",
            True,
        ).pack(anchor="w", padx=26, pady=(0, 10))

    def show(self, name):
        self.page = name
        for w in self.content.winfo_children():
            w.destroy()
        for n, b in self.nav.items():
            b.configure(bg=PANEL2 if n == name else PANEL, fg=CYAN if n == name else TEXT)
        {"Nearby": self.nearby, "Activity": self.activity, "Settings": self.settings}[name]()

    def nearby(self):
        head = tk.Frame(self.content, bg=BG)
        head.pack(fill="x", pady=(0, 16))
        self.label(head, "Nearby Windows laptops", 24, TEXT, True).pack(anchor="w")
        self.label(head, "Select a sample device to preview the 5 m policy gate.", 10, MUTED).pack(anchor="w", pady=(5, 0))
        hero = tk.Frame(self.content, bg="#13223a", highlightbackground="#2a4770", highlightthickness=1)
        hero.pack(fill="x", pady=(0, 16))
        self.label(hero, "PROXIMITY GATE · THREE STABLE SAMPLES · FAIL CLOSED", 10, CYAN, True, bg="#13223a").pack(anchor="w", padx=18, pady=(16, 6))
        self.label(hero, "Pairing + connection + fresh signal are required.", 13, TEXT, True, bg="#13223a").pack(anchor="w", padx=18, pady=(0, 16))
        self.btn(hero, "＋ Choose file", self.choose, True).pack(anchor="e", padx=16, pady=(0, 14))

        grid = tk.Frame(self.content, bg=BG)
        grid.pack(fill="x")
        for i, (name, kind, rssi) in enumerate(self.devices):
            d = self.policy.evaluate(rssi, True, True, [rssi - 1, rssi, rssi + 1])
            card = tk.Frame(
                grid,
                bg=PANEL,
                highlightbackground=BLUE if self.device == name else BORDER,
                highlightthickness=2 if self.device == name else 1,
            )
            card.grid(row=i // 2, column=i % 2, sticky="nsew", padx=6, pady=6)
            grid.grid_columnconfigure(i % 2, weight=1)
            card.bind("<Button-1>", lambda e, n=name: self.select(n))
            self.label(card, "▣", 25, CYAN if d.allowed else ORANGE, True, bg=PANEL).pack(anchor="w", padx=14, pady=(12, 0))
            self.label(card, name, 12, TEXT, True).pack(anchor="w", padx=14, pady=(6, 2))
            self.label(card, kind, 9, MUTED).pack(anchor="w", padx=14)
            self.label(card, f"RSSI {rssi} dBm · rough estimate {d.estimated_metres:.1f} m", 9, MUTED).pack(anchor="w", padx=14, pady=(10, 3))
            self.label(card, "ELIGIBLE (DEMO)" if d.allowed else "BLOCKED BY THRESHOLD", 8, GREEN if d.allowed else ORANGE, True).pack(anchor="w", padx=14, pady=(0, 14))
            for w in card.winfo_children():
                w.bind("<Button-1>", lambda e, n=name: self.select(n))

        action = tk.Frame(self.content, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        action.pack(fill="x", pady=(14, 0))
        self.label(action, "RECIPIENT  ·  " + (self.device or "none selected"), 9, CYAN if self.device else MUTED, True).pack(anchor="w", padx=16, pady=(13, 4))
        self.label(action, "FILE  ·  " + (Path(self.file).name if self.file else "No file selected"), 10, TEXT, True).pack(anchor="w", padx=16, pady=(0, 10))
        self.btn(action, "Send file →", self.send, True).pack(anchor="e", padx=14, pady=(0, 12))

    def select(self, name):
        self.device = name
        self.show("Nearby")

    def choose(self):
        f = filedialog.askopenfilename(parent=self.root)
        if f:
            self.file = f
            self.show("Nearby")

    def send(self):
        if not self.device:
            messagebox.showwarning("Choose device", "Select a sample laptop first.", parent=self.root)
            return
        rssi = next(r for n, _, r in self.devices if n == self.device)
        decision = self.policy.evaluate(rssi, True, True, [rssi - 1, rssi, rssi + 1])
        if not decision.allowed:
            messagebox.showwarning("Blocked by proximity policy", f"Sample RSSI {rssi} dBm is below the illustrative threshold.\nNo send allowed.", parent=self.root)
            return
        if not self.file:
            self.choose()
        if not self.file:
            return
        win = tk.Toplevel(self.root)
        win.title("Transfer preview")
        win.configure(bg=BG)
        win.geometry("460x250")
        self.label(win, "DEMO TRANSFER PREVIEW", 10, CYAN, True).pack(anchor="w", padx=24, pady=(24, 8))
        self.label(win, Path(self.file).name, 13, TEXT, True, wraplength=400).pack(anchor="w", padx=24)
        self.label(win, f"Target: {self.device}", 9, MUTED).pack(anchor="w", padx=24, pady=8)
        self.label(win, "No file data is transmitted. Real networking is not implemented yet.", 10, ORANGE, wraplength=410, justify="left").pack(anchor="w", padx=24, pady=12)

    def accept_drop(self, file_path: str, device_name: str, status_callback):
        """Record selection from the overlay without claiming a transfer occurred."""
        p = Path(file_path)
        if not p.exists() or not p.is_file():
            status_callback("That drop was not a regular file.", ORANGE)
            return
        rssi = next(r for n, _, r in self.devices if n == device_name)
        d = self.policy.evaluate(rssi, True, True, [rssi - 1, rssi, rssi + 1])
        self.file = str(p)
        self.device = device_name
        if self.page == "Nearby":
            self.show("Nearby")
        if not d.allowed:
            status_callback(f"{p.name}: blocked by demo range threshold.", ORANGE)
        else:
            status_callback(f"{p.name} → {device_name}\nDrop detected; actual transfer is not implemented.", CYAN)

    def activity(self):
        self.label(self.content, "Activity", 24, TEXT, True).pack(anchor="w", pady=(0, 15))
        self.label(self.content, "No real transfers recorded. This prototype does not transmit file data.", 11, MUTED, wraplength=660, justify="left").pack(anchor="w")

    def settings(self):
        self.label(self.content, "Range & security policy", 24, TEXT, True).pack(anchor="w", pady=(0, 8))
        self.label(self.content, "Target: approximately 5 m, not a guaranteed boundary.", 11, ORANGE).pack(anchor="w", pady=(0, 18))
        rows = [
            ("Gate", "Fail closed", "Reject unpaired, disconnected, stale or unstable signals"),
            ("Stability", "3 recent samples", "Reject readings that fluctuate too much"),
            ("Signal threshold", "-65 dBm example", "Must be calibrated per hardware and environment"),
            ("Connection loss", "Pause / reject", "A real transfer must re-check policy while sending"),
            ("Physical distance", "Not guaranteed", "RSSI cannot accurately prove a 5 m radius"),
            ("Network transfer", "Not implemented", "This remains a visual UI prototype"),
        ]
        for a, b, c in rows:
            box = tk.Frame(self.content, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
            box.pack(fill="x", pady=5)
            self.label(box, a, 11, TEXT, True).pack(anchor="w", padx=14, pady=(10, 2))
            self.label(box, b, 9, CYAN, True).pack(anchor="w", padx=14)
            self.label(box, c, 9, MUTED, wraplength=620, justify="left").pack(anchor="w", padx=14, pady=(3, 10))


class DragOverlay:
    """A right-edge drop panel revealed by a global left-button drag gesture."""

    def __init__(self, root, dashboard: AirLink, event_queue: queue.Queue):
        self.root = root
        self.dashboard = dashboard
        self.events = event_queue
        self.window = None
        self.status_label = None
        self.device_widgets = {}
        self.last_drop_at = 0.0

    def show(self):
        if self.window is None or not self.window.winfo_exists():
            self._build()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        height = min(510, max(430, sh - 80))
        width = 286
        x = max(0, sw - width - 16)
        y = max(0, (sh - height) // 2)
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        self.window.deiconify()
        self.window.lift()
        self.window.attributes("-topmost", True)
        self.window.update_idletasks()

    def _build(self):
        w = tk.Toplevel(self.root)
        self.window = w
        w.title("AirLink drop panel")
        w.configure(bg=BG)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        try:
            w.attributes("-alpha", 0.98)
        except tk.TclError:
            pass
        w.protocol("WM_DELETE_WINDOW", self.hide)
        w.bind("<Escape>", lambda _e: self.hide())
        w.drop_target_register(DND_FILES)
        w.dnd_bind("<<DropEnter>>", self._drop_enter)
        w.dnd_bind("<<DropPosition>>", self._drop_position)
        w.dnd_bind("<<DropLeave>>", self._drop_leave)
        w.dnd_bind("<<Drop>>", self._drop)

        head = tk.Frame(w, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        head.pack(fill="x", padx=8, pady=(8, 6))
        line = tk.Frame(head, bg=PANEL)
        line.pack(fill="x", padx=12, pady=(10, 2))
        tk.Label(line, text="◉ AirLink", bg=PANEL, fg=CYAN, font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Button(line, text="×", command=self.hide, bg=PANEL2, fg=TEXT, relief="flat", bd=0, padx=8, cursor="hand2").pack(side="right")
        tk.Label(head, text="DROP A FILE ON A DEVICE", bg=PANEL, fg=TEXT, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(2, 3))
        tk.Label(head, text="Drag-and-drop preview · sample devices", bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", padx=12, pady=(0, 10))

        devices_box = tk.Frame(w, bg=BG)
        devices_box.pack(fill="both", expand=True, padx=8)
        for name, _kind, rssi in self.dashboard.devices:
            decision = self.dashboard.policy.evaluate(rssi, True, True, [rssi - 1, rssi, rssi + 1])
            card = tk.Frame(devices_box, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
            card.pack(fill="x", pady=4)
            self.device_widgets[name] = card
            row = tk.Frame(card, bg=PANEL)
            row.pack(fill="x", padx=10, pady=(9, 2))
            tk.Label(row, text="▢", bg=PANEL, fg=CYAN if decision.allowed else ORANGE, font=("Segoe UI", 19, "bold")).pack(side="left", padx=(0, 8))
            labels = tk.Frame(row, bg=PANEL)
            labels.pack(side="left", fill="x", expand=True)
            tk.Label(labels, text=name, bg=PANEL, fg=TEXT, font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")
            tk.Label(labels, text=f"RSSI {rssi} dBm · DEMO", bg=PANEL, fg=MUTED, font=("Segoe UI", 8), anchor="w").pack(fill="x", pady=(2, 0))
            tk.Label(card, text="DROP HERE" if decision.allowed else "BLOCKED BY DEMO THRESHOLD", bg=PANEL, fg=GREEN if decision.allowed else ORANGE, font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", padx=12, pady=(0, 8))

        footer = tk.Frame(w, bg="#13223a", highlightbackground="#2a4770", highlightthickness=1)
        footer.pack(fill="x", padx=8, pady=8)
        self.status_label = tk.Label(footer, text="Waiting for file drop…", bg="#13223a", fg=MUTED, font=("Segoe UI", 9), wraplength=245, justify="left", anchor="w")
        self.status_label.pack(fill="x", padx=11, pady=10)
        # Panel is a target; target handler decides the receiver from screen coordinates.

    def hide(self):
        if self.window is not None and self.window.winfo_exists():
            self.window.withdraw()

    def status(self, text, color=MUTED):
        if self.status_label is not None and self.status_label.winfo_exists():
            self.status_label.configure(text=text, fg=color)

    def _drop_enter(self, event):
        self.status("Drop on a laptop card to select the receiver.", CYAN)
        return event.action

    def _drop_position(self, event):
        return event.action

    def _drop_leave(self, _event):
        pass

    def _drop(self, event):
        self.last_drop_at = time.monotonic()
        try:
            paths = list(self.root.tk.splitlist(event.data))
        except tk.TclError:
            paths = [event.data.strip("{}")]
        paths = [p for p in paths if p]
        chosen = None
        for name, widget in self.device_widgets.items():
            top = widget.winfo_rooty()
            bottom = top + widget.winfo_height()
            pointer_y = getattr(event, "y_root", widget.winfo_rooty() + getattr(event, "y", 0))
            if top <= pointer_y <= bottom:
                chosen = name
                break
        if not paths:
            self.status("No file path received. Try dragging a file from File Explorer.", ORANGE)
        elif chosen is None:
            self.status("File drag detected. Drop directly on one of the laptop cards.", ORANGE)
        else:
            self.dashboard.accept_drop(paths[0], chosen, self.status)
            if len(paths) > 1:
                self.status(f"{len(paths)} files dropped; preview stores the first file only.\nActual transfer is not implemented.", ORANGE)
        self.root.after(3500, self.hide)
        return getattr(event, "action", "copy")


class AirLinkHost:
    """Tray, global mouse listener, and the event bridge to Tk's UI thread."""

    def __init__(self, root, dashboard, background=False):
        self.root = root
        self.dashboard = dashboard
        self.background = background
        self.events = queue.Queue()
        self.overlay = DragOverlay(root, dashboard, self.events)
        self.listener = None
        self.tray = None
        self.alive = True
        self._pressed = False
        self._start_xy = None
        self._dragging = False
        self._mouse_lock = threading.Lock()
        self._setup_tray()
        self._setup_mouse_listener()
        self.root.protocol("WM_DELETE_WINDOW", self.hide_dashboard)
        if background:
            self.root.withdraw()
        self.root.after(60, self._poll_events)

    def _setup_mouse_listener(self):
        try:
            from pynput import mouse
        except ImportError:
            self.events.put(("status", "pynput is missing; rerun setup_and_run.bat.", None))
            return

        def on_click(x, y, button, pressed):
            if button != mouse.Button.left:
                return
            with self._mouse_lock:
                if pressed:
                    self._pressed = True
                    self._start_xy = (x, y)
                    self._dragging = False
                else:
                    was_dragging = self._dragging
                    self._pressed = False
                    self._start_xy = None
                    self._dragging = False
                    if was_dragging:
                        self.events.put(("drag_end", None, None))

        def on_move(x, y):
            start_drag = False
            with self._mouse_lock:
                if self._pressed and self._start_xy and not self._dragging:
                    sx, sy = self._start_xy
                    if abs(x - sx) + abs(y - sy) >= 10:
                        self._dragging = True
                        start_drag = True
            if start_drag:
                self.events.put(("drag_start", None, None))

        try:
            from pynput import mouse
            self.listener = mouse.Listener(on_move=on_move, on_click=on_click)
            self.listener.daemon = True
            self.listener.start()
        except Exception as exc:
            self.events.put(("status", f"Global drag detection could not start: {exc}", None))

    def _setup_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError:
            # The UI still works if tray dependencies are missing; setup script installs them.
            return
        image = Image.new("RGBA", (64, 64), (11, 16, 32, 255))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((7, 7, 57, 57), radius=13, fill=(23, 34, 58, 255), outline=(97, 230, 220, 255), width=3)
        draw.ellipse((22, 22, 42, 42), fill=(97, 230, 220, 255))
        menu = pystray.Menu(
            pystray.MenuItem("Open AirLink", lambda _icon, _item: self.events.put(("open", None, None)), default=True),
            pystray.MenuItem("Show drop panel", lambda _icon, _item: self.events.put(("show_overlay", None, None))),
            pystray.MenuItem("Quit AirLink", lambda _icon, _item: self.events.put(("quit", None, None))),
        )
        self.tray = pystray.Icon("AirLink", image, "AirLink is running", menu)
        threading.Thread(target=self.tray.run, name="AirLinkTray", daemon=True).start()

    def hide_dashboard(self):
        self.root.withdraw()

    def _poll_events(self):
        if not self.alive:
            return
        try:
            while True:
                name, payload, extra = self.events.get_nowait()
                if name == "drag_start":
                    self.overlay.show()
                    self.overlay.status("Drop a file onto a laptop card.", CYAN)
                elif name == "drag_end":
                    # Give OLE/TkDND a moment to dispatch <<Drop>> before hiding.
                    self.root.after(900, self._hide_if_no_recent_drop)
                elif name == "open":
                    self.root.deiconify()
                    self.root.lift()
                elif name == "show_overlay":
                    self.overlay.show()
                elif name == "quit":
                    self.quit()
                    return
                elif name == "status":
                    self.overlay.show()
                    self.overlay.status(payload, ORANGE)
        except queue.Empty:
            pass
        self.root.after(60, self._poll_events)

    def _hide_if_no_recent_drop(self):
        if time.monotonic() - self.overlay.last_drop_at > 1.4:
            self.overlay.hide()

    def quit(self):
        self.alive = False
        try:
            if self.listener is not None:
                self.listener.stop()
        except Exception:
            pass
        try:
            if self.tray is not None:
                self.tray.stop()
        except Exception:
            pass
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description="AirLink Windows drag-to-share prototype")
    parser.add_argument("--background", action="store_true", help="start hidden in the system tray")
    args = parser.parse_args()
    root = TkinterDnD.Tk()
    try:
        root.tk.call("tk", "scaling", 1.1)
    except tk.TclError:
        pass
    dashboard = AirLink(root)
    host = AirLinkHost(root, dashboard, background=args.background)
    # Keep host referenced for the lifetime of the Tk main loop.
    root._airlink_host = host
    root.mainloop()


if __name__ == "__main__":
    main()
