"""AirLink Glass UI — Windows wallpaper-adaptive drag-to-share UI prototype.

The app uses Qt translucent widgets plus the Windows Acrylic composition API.
Device discovery and byte transfer are intentionally not claimed as implemented.
"""
from __future__ import annotations

import argparse
import ctypes
import math
import os
import sys
import socket
import threading
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QBrush, QAction
from PySide6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow,
    QMenu, QMessageBox, QFileDialog, QPushButton, QSizePolicy, QSystemTrayIcon,
    QVBoxLayout, QWidget, QSpacerItem, QInputDialog, QProgressDialog,
)

try:
    from pynput import mouse
except ImportError:
    mouse = None

from proximity_policy import ProximityPolicy
from wallpaper_theme import current_wallpaper_path, palette_for_wallpaper
from transfer_service import TransferReceiver, PORT as TRANSFER_PORT, local_ip, send_file as send_file_over_lan


DEVICES = [
    ("LAN receiver", "Connect using the receiving laptop IPv4 address", None),
]


def rgb(hex_color: str) -> tuple[int, int, int]:
    raw = hex_color.lstrip("#")
    return tuple(int(raw[i:i + 2], 16) for i in (0, 2, 4))


def rgba(hex_color: str, alpha: int) -> str:
    r, g, b = rgb(hex_color)
    return f"rgba({r}, {g}, {b}, {alpha})"


def blend(hex_a: str, hex_b: str, factor: float) -> str:
    a, b = rgb(hex_a), rgb(hex_b)
    factor = max(0.0, min(1.0, factor))
    vals = [round(a[i] * (1 - factor) + b[i] * factor) for i in range(3)]
    return "#{:02x}{:02x}{:02x}".format(*vals)


def make_icon(size: int = 64, accent: str = "#6aa8ff") -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor("#101a2f")))
    p.drawRoundedRect(2, 2, size - 4, size - 4, size * .22, size * .22)
    p.setBrush(QBrush(QColor(accent)))
    # Stylized AirLink / transfer glyph.
    points = [QPoint(int(size*.23), int(size*.70)), QPoint(int(size*.48), int(size*.24)),
              QPoint(int(size*.77), int(size*.70)), QPoint(int(size*.58), int(size*.70)),
              QPoint(int(size*.48), int(size*.53)), QPoint(int(size*.39), int(size*.70))]
    from PySide6.QtGui import QPolygon
    p.drawPolygon(QPolygon(points))
    p.end()
    return QIcon(pix)


def make_stylesheet(palette: dict[str, str]) -> str:
    """Generate a translucent glass stylesheet from the current wallpaper palette."""
    accent = palette["BLUE"]
    accent_hi = palette["CYAN"]
    return f"""
    * {{
        color: {palette['TEXT']};
        font-family: 'Segoe UI';
        font-size: 10pt;
        outline: 0;
    }}
    QWidget {{ background: transparent; }}
    QLabel {{ background: transparent; }}
    QFrame#GlassShell {{
        background-color: {rgba(palette['BG'], 162)};
        border: 1px solid rgba(255,255,255,68);
        border-radius: 22px;
    }}
    QFrame#TitleBar {{ background: transparent; border: none; }}
    QFrame#Sidebar {{
        background-color: {rgba(palette['PANEL'], 126)};
        border: 1px solid rgba(255,255,255,28);
        border-radius: 17px;
    }}
    QFrame#GlassCard {{
        background-color: {rgba(palette['PANEL'], 132)};
        border: 1px solid rgba(255,255,255,45);
        border-radius: 16px;
    }}
    QFrame#HeroCard {{
        background-color: {rgba(accent, 43)};
        border: 1px solid {rgba(accent_hi, 125)};
        border-radius: 18px;
    }}
    QFrame#DeviceCard {{
        background-color: {rgba(palette['PANEL2'], 104)};
        border: 1px solid rgba(255,255,255,44);
        border-radius: 15px;
    }}
    QFrame#DeviceCard[selected="true"] {{
        background-color: {rgba(accent, 56)};
        border: 1px solid {rgba(accent_hi, 205)};
    }}
    QFrame#DeviceCard:hover {{
        background-color: {rgba(accent, 48)};
        border: 1px solid {rgba(accent_hi, 155)};
    }}
    QFrame#DropSurface {{
        background-color: {rgba(palette['PANEL2'], 102)};
        border: 1px dashed {rgba(accent_hi, 185)};
        border-radius: 16px;
    }}
    QLabel#AppMark {{
        background-color: {rgba(accent, 235)};
        border-radius: 11px;
        color: #ffffff;
        font-size: 16pt;
        font-weight: 800;
    }}
    QLabel#PageTitle {{ font-size: 23pt; font-weight: 700; }}
    QLabel#SectionTitle {{ font-size: 11pt; font-weight: 650; }}
    QLabel#Muted {{ color: {palette['MUTED']}; }}
    QLabel#Accent {{ color: {accent_hi}; font-weight: 650; }}
    QLabel#Eyebrow {{ color: {accent_hi}; font-size: 8pt; font-weight: 750; letter-spacing: 1px; }}
    QLabel#Badge {{
        background-color: {rgba(accent, 56)};
        border: 1px solid {rgba(accent_hi, 88)};
        border-radius: 9px;
        padding: 5px 9px;
        font-size: 8pt;
        font-weight: 650;
    }}
    QPushButton {{
        background-color: {rgba(palette['PANEL2'], 124)};
        border: 1px solid rgba(255,255,255,42);
        border-radius: 10px;
        padding: 9px 13px;
        color: {palette['TEXT']};
        font-weight: 600;
    }}
    QPushButton:hover {{ background-color: {rgba(accent, 66)}; border-color: {rgba(accent_hi, 175)}; }}
    QPushButton:pressed {{ background-color: {rgba(accent, 115)}; }}
    QPushButton#PrimaryButton {{
        background-color: {rgba(accent, 210)};
        border: 1px solid {rgba(accent_hi, 200)};
        color: #ffffff;
        font-weight: 700;
    }}
    QPushButton#PrimaryButton:hover {{ background-color: {rgba(accent_hi, 222)}; color: #091321; }}
    QPushButton#TitleButton {{
        border: none; background-color: rgba(255,255,255,17); border-radius: 9px;
        padding: 4px; min-width: 29px; max-width: 29px; min-height: 27px; max-height: 27px;
        font-size: 12pt;
    }}
    QPushButton#TitleButton:hover {{ background-color: {rgba(accent, 100)}; }}
    QPushButton#CloseButton:hover {{ background-color: rgba(232,75,90,205); }}
    QPushButton#NavButton {{
        text-align: left; padding: 11px 13px; border: 1px solid transparent;
        background-color: transparent; border-radius: 10px; font-weight: 550;
    }}
    QPushButton#NavButton:checked {{
        background-color: {rgba(accent, 62)}; border: 1px solid {rgba(accent_hi, 95)};
        color: {accent_hi}; font-weight: 700;
    }}
    QPushButton#NavButton:hover:!checked {{ background-color: rgba(255,255,255,22); }}
    QLineEdit {{
        background-color: rgba(255,255,255,17); border: 1px solid rgba(255,255,255,42);
        border-radius: 10px; padding: 9px 11px;
    }}
    QScrollArea {{ border: none; background: transparent; }}
    QToolTip {{ color: {palette['TEXT']}; background: {rgba(palette['PANEL'], 245)}; border: 1px solid {palette['BORDER']}; padding: 5px; }}
    """


# Windows WCA_ACCENT_POLICY acrylic. If unsupported, Qt's alpha/QSS remains as fallback.
def apply_windows_acrylic(widget: QWidget, palette: dict[str, str], alpha: int = 0xB8) -> bool:
    if os.name != "nt":
        return False
    try:
        from ctypes import wintypes

        class ACCENT_POLICY(ctypes.Structure):
            _fields_ = [
                ("AccentState", ctypes.c_int),
                ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_uint),
                ("AnimationId", ctypes.c_int),
            ]

        class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
            _fields_ = [
                ("Attribute", ctypes.c_int),
                ("Data", ctypes.c_void_p),
                ("SizeOfData", ctypes.c_size_t),
            ]

        r, g, b = rgb(palette["BG"])
        # AccentPolicy GradientColor is ARGB packed as 0xAABBGGRR on current builds.
        gradient = ((alpha & 0xff) << 24) | ((b & 0xff) << 16) | ((g & 0xff) << 8) | (r & 0xff)
        policy = ACCENT_POLICY(4, 2, gradient, 0)  # ACCENT_ENABLE_ACRYLICBLURBEHIND
        data = WINDOWCOMPOSITIONATTRIBDATA(19, ctypes.addressof(policy), ctypes.sizeof(policy))  # WCA_ACCENT_POLICY
        function = ctypes.windll.user32.SetWindowCompositionAttribute
        function.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
        function.restype = wintypes.BOOL
        hwnd = wintypes.HWND(int(widget.winId()))
        ok = bool(function(hwnd, ctypes.byref(data)))
        # Windows 11 supports an additional native acrylic/transient backdrop.
        # Request it as well; unsupported builds simply keep the AccentPolicy result.
        try:
            dwm = ctypes.windll.dwmapi.DwmSetWindowAttribute
            dwm.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
            dwm.restype = ctypes.c_long
            backdrop = ctypes.c_int(3)  # DWMSBT_TRANSIENTWINDOW (acrylic-like)
            dwm(hwnd, 38, ctypes.byref(backdrop), ctypes.sizeof(backdrop))  # DWMWA_SYSTEMBACKDROP_TYPE
            dark = ctypes.c_int(1)
            dwm(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))  # DWMWA_USE_IMMERSIVE_DARK_MODE
            pref = ctypes.c_int(2)  # DWMWCP_ROUND
            dwm(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))  # DWMWA_WINDOW_CORNER_PREFERENCE
        except Exception:
            pass
        return ok
    except Exception:
        return False


class WallpaperTheme:
    def __init__(self):
        self.path = current_wallpaper_path()
        self.palette = palette_for_wallpaper(self.path)
        self.signature = tuple(sorted(self.palette.items()))

    def refresh(self) -> bool:
        path = current_wallpaper_path()
        new_palette = palette_for_wallpaper(path)
        signature = tuple(sorted(new_palette.items()))
        changed = signature != self.signature
        self.path = path
        self.palette = new_palette
        self.signature = signature
        return changed


class DragSignals(QObject):
    started = Signal()
    ended = Signal()
    problem = Signal(str)


class GlobalDragDetector:
    """Detects a global mouse drag; Windows does not expose a universal file-only drag-start event."""
    def __init__(self, bridge: DragSignals):
        self.bridge = bridge
        self.listener = None
        self.pressed = False
        self.start_xy = None
        self.dragging = False
        self.lock = threading.Lock()

    def start(self):
        if mouse is None:
            self.bridge.problem.emit("pynput missing; run setup_and_run.bat to install dependencies.")
            return
        try:
            def on_click(x, y, button, pressed):
                if button != mouse.Button.left:
                    return
                with self.lock:
                    if pressed:
                        self.pressed = True
                        self.start_xy = (x, y)
                        self.dragging = False
                    else:
                        was_dragging = self.dragging
                        self.pressed = False
                        self.start_xy = None
                        self.dragging = False
                if not pressed and was_dragging:
                    self.bridge.ended.emit()

            def on_move(x, y):
                start = False
                with self.lock:
                    if self.pressed and self.start_xy and not self.dragging:
                        sx, sy = self.start_xy
                        if math.hypot(x - sx, y - sy) > 9:
                            self.dragging = True
                            start = True
                if start:
                    self.bridge.started.emit()

            self.listener = mouse.Listener(on_move=on_move, on_click=on_click)
            self.listener.daemon = True
            self.listener.start()
        except Exception as exc:
            self.bridge.problem.emit(f"Global drag detection could not start: {exc}")

    def stop(self):
        try:
            if self.listener:
                self.listener.stop()
        except Exception:
            pass


class TitleBar(QFrame):
    def __init__(self, owner: QMainWindow, palette: dict[str, str], title: str):
        super().__init__()
        self.owner = owner
        self.drag_offset: Optional[QPoint] = None
        self.setObjectName("TitleBar")
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 6, 8, 8)
        row.setSpacing(9)
        mark = QLabel("A")
        mark.setObjectName("AppMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(36, 36)
        row.addWidget(mark)
        brand = QVBoxLayout()
        brand.setSpacing(0)
        name = QLabel("AirLink")
        name.setStyleSheet("font-size: 14pt; font-weight: 750;")
        sub = QLabel("WALLPAPER-ADAPTIVE GLASS")
        sub.setObjectName("Muted")
        sub.setStyleSheet("font-size: 7.5pt; letter-spacing: 1px;")
        brand.addWidget(name)
        brand.addWidget(sub)
        row.addLayout(brand)
        row.addStretch(1)
        self.sync = QLabel("●  WALLPAPER SYNC")
        self.sync.setObjectName("Badge")
        row.addWidget(self.sync)
        self.min_btn = QPushButton("—")
        self.min_btn.setObjectName("TitleButton")
        self.min_btn.clicked.connect(owner.showMinimized)
        row.addWidget(self.min_btn)
        self.close_btn = QPushButton("×")
        self.close_btn.setObjectName("TitleButton")
        self.close_btn.clicked.connect(owner.hide_to_tray)
        row.addWidget(self.close_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_offset = event.globalPosition().toPoint() - self.owner.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.owner.move(event.globalPosition().toPoint() - self.drag_offset)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_offset = None
        super().mouseReleaseEvent(event)


class DeviceCard(QFrame):
    clicked = Signal(str)
    dropped = Signal(str, str)

    def __init__(self, name: str, kind: str, rssi: int, palette: dict[str, str], selected=False, overlay=False):
        super().__init__()
        self.name, self.kind, self.rssi = name, kind, rssi
        self.palette = palette
        self.overlay = overlay
        self.setObjectName("DeviceCard")
        self.setProperty("selected", "true" if selected else "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAcceptDrops(overlay)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if overlay:
            self.setMinimumHeight(83)
        else:
            self.setMinimumHeight(156)
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(13, 12, 13, 12)
        outer.setSpacing(8)
        top = QHBoxLayout()
        top.setSpacing(10)
        avatar = QLabel("▣" if "PC" in self.kind or "DESKTOP" in self.name else self.name[:1].upper())
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFixedSize(41 if self.overlay else 46, 41 if self.overlay else 46)
        avatar.setStyleSheet(
            f"background-color: {rgba(self.palette['BLUE'], 90)}; border: 1px solid {rgba(self.palette['CYAN'], 130)};"
            "border-radius: 13px; font-size: 14pt; font-weight: 700;"
        )
        labels = QVBoxLayout()
        labels.setSpacing(3)
        name = QLabel(self.name)
        name.setStyleSheet("font-size: 10.5pt; font-weight: 700;")
        name.setWordWrap(True)
        kind = QLabel(self.kind)
        kind.setObjectName("Muted")
        kind.setStyleSheet("font-size: 8.5pt;")
        labels.addWidget(name)
        labels.addWidget(kind)
        top.addWidget(avatar)
        top.addLayout(labels, 1)
        outer.addLayout(top)

        decision = None
        if self.rssi is not None:
            decision = ProximityPolicy().evaluate(self.rssi, True, True, [self.rssi - 1, self.rssi, self.rssi + 1])
        footer = QHBoxLayout()
        if self.rssi is None:
            signal_text = "DROP FILE HERE" if self.overlay else "Enter receiver IP when sending"
            badge_text, badge_color = "MANUAL IP", self.palette["CYAN"]
        else:
            if self.overlay:
                signal_text = "DROP HERE" if decision.allowed else "OUT OF DEMO RANGE"
            else:
                signal_text = f"RSSI {self.rssi} dBm  ·  ~{decision.estimated_metres:.1f} m estimate"
            badge_text = "READY" if decision.allowed else "BLOCKED"
            badge_color = "#6FE3A1" if decision.allowed else "#FFC878"
        status = QLabel(signal_text)
        status.setObjectName("Accent" if (decision is None or decision.allowed) else "Muted")
        status.setStyleSheet("font-size: 8pt; font-weight: 700;" if self.overlay else "font-size: 8pt;")
        footer.addWidget(status)
        footer.addStretch(1)
        badge = QLabel(badge_text)
        badge.setObjectName("Badge")
        badge.setStyleSheet(f"QLabel#Badge {{ color: {badge_color}; font-size: 7.5pt; }}")
        footer.addWidget(badge)
        outer.addLayout(footer)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.overlay:
            self.clicked.emit(self.name)
        super().mousePressEvent(event)

    def dragEnterEvent(self, event):
        if self.overlay and event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            self.setStyleSheet(f"QFrame#DeviceCard {{ background-color: {rgba(self.palette['BLUE'], 95)}; border: 1px solid {self.palette['CYAN']}; border-radius: 15px; }}")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        urls = [u for u in event.mimeData().urls() if u.isLocalFile()]
        self.setStyleSheet("")
        if self.overlay and urls:
            self.dropped.emit(urls[0].toLocalFile(), self.name)
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()


class DragPanel(QWidget):
    fileDropped = Signal(str, str)

    def __init__(self, theme: WallpaperTheme):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.theme = theme
        self.palette = theme.palette
        self.cards: list[DeviceCard] = []
        self.last_drop_at = 0.0
        self.setObjectName("DragPanelWindow")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAcceptDrops(True)
        self.setMinimumWidth(330)
        self.setMaximumWidth(360)
        self.setWindowTitle("AirLink — Drop to share")
        self._build()
        self.setStyleSheet(make_stylesheet(self.palette))

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        self.shell = QFrame()
        self.shell.setObjectName("GlassShell")
        box = QVBoxLayout(self.shell)
        box.setContentsMargins(14, 14, 14, 14)
        box.setSpacing(12)
        head = QHBoxLayout()
        mark = QLabel("A")
        mark.setObjectName("AppMark")
        mark.setFixedSize(38, 38)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand = QVBoxLayout()
        lbl = QLabel("AirLink")
        lbl.setStyleSheet("font-size: 15pt; font-weight: 750;")
        sub = QLabel("GLASS SHARE PANEL")
        sub.setObjectName("Muted")
        sub.setStyleSheet("font-size: 7.2pt; letter-spacing: 1px;")
        brand.addWidget(lbl)
        brand.addWidget(sub)
        head.addWidget(mark)
        head.addLayout(brand, 1)
        close = QPushButton("×")
        close.setObjectName("TitleButton")
        close.clicked.connect(self.hide)
        head.addWidget(close)
        box.addLayout(head)

        drop = QFrame()
        drop.setObjectName("DropSurface")
        dl = QVBoxLayout(drop)
        dl.setContentsMargins(12, 16, 12, 16)
        dl.setSpacing(5)
        arrow = QLabel("↗")
        arrow.setObjectName("Accent")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setStyleSheet("font-size: 28pt; font-weight: 400;")
        title = QLabel("Drop file to send")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 12pt; font-weight: 700;")
        helper = QLabel("Release on a nearby device")
        helper.setObjectName("Muted")
        helper.setAlignment(Qt.AlignmentFlag.AlignCenter)
        helper.setStyleSheet("font-size: 8.5pt;")
        dl.addWidget(arrow)
        dl.addWidget(title)
        dl.addWidget(helper)
        box.addWidget(drop)

        row = QHBoxLayout()
        eyebrow = QLabel("NEARBY DEVICES")
        eyebrow.setObjectName("Eyebrow")
        row.addWidget(eyebrow)
        row.addStretch(1)
        self.count = QLabel("MANUAL LAN")
        self.count.setObjectName("Muted")
        self.count.setStyleSheet("font-size: 7.5pt;")
        row.addWidget(self.count)
        box.addLayout(row)

        self.device_list = QVBoxLayout()
        self.device_list.setSpacing(7)
        for name, kind, rssi in DEVICES:
            card = DeviceCard(name, kind, rssi, self.palette, overlay=True)
            card.dropped.connect(self.fileDropped.emit)
            self.cards.append(card)
            self.device_list.addWidget(card)
        box.addLayout(self.device_list)
        self.status_label = QLabel("Drag a file from File Explorer, then drop it on a device.")
        self.status_label.setObjectName("Muted")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 8.5pt;")
        box.addWidget(self.status_label)
        shortcut = QLabel("ESC  ·  HIDE PANEL")
        shortcut.setObjectName("Muted")
        shortcut.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shortcut.setStyleSheet("font-size: 7pt; letter-spacing: .6px;")
        box.addWidget(shortcut)
        outer.addWidget(self.shell)

    def show_on_right(self):
        screen = QApplication.primaryScreen()
        if screen:
            rect = screen.availableGeometry()
            height = min(700, max(500, rect.height() - 48))
            width = 344
            self.setGeometry(rect.right() - width - 12, rect.top() + max(10, (rect.height() - height)//2), width, height)
        self.show()
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(180, lambda: apply_windows_acrylic(self, self.palette, 0xC4))

    def set_status(self, text: str, color: Optional[str] = None):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"font-size: 8.5pt; color: {color or self.palette['MUTED']};")

    def apply_theme(self, palette: dict[str, str]):
        self.palette = palette
        self.setStyleSheet(make_stylesheet(palette))
        # Rebuild cards so avatars/accent badges get the new hue.
        while self.device_list.count():
            item = self.device_list.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.cards = []
        for name, kind, rssi in DEVICES:
            card = DeviceCard(name, kind, rssi, palette, overlay=True)
            card.dropped.connect(self.fileDropped.emit)
            self.cards.append(card)
            self.device_list.addWidget(card)
        if self.isVisible():
            QTimer.singleShot(100, lambda: apply_windows_acrylic(self, palette, 0xC4))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.set_status("Drop the file directly on a device card.", self.palette['CYAN'])
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = [u for u in event.mimeData().urls() if u.isLocalFile()]
        if urls:
            self.set_status("Now drop the file on a device card.", self.palette['ORANGE'])
            event.acceptProposedAction()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)


class TransferSignals(QObject):
    progress = Signal(str, str, int)
    finished = Signal(str, bool, str)


class AirLinkWindow(QMainWindow):
    def __init__(self, theme: WallpaperTheme, tray: QSystemTrayIcon):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.theme = theme
        self.palette = theme.palette
        self.tray = tray
        self.policy = ProximityPolicy(target_metres=5)
        self.selected_device: Optional[str] = None
        self.selected_file: Optional[str] = None
        self.activity: list[str] = []
        self.current_page = "Nearby"
        self.drag_offset = None
        self.setWindowTitle("AirLink — Wallpaper-adaptive glass sharing")
        self.setWindowIcon(make_icon(64, self.palette['BLUE']))
        self.setMinimumSize(930, 650)
        self.resize(1120, 760)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet(make_stylesheet(self.palette))
        self._build()
        self.render_page("Nearby")
        self.center()

    def center(self):
        screen = QApplication.primaryScreen()
        if screen:
            rect = screen.availableGeometry()
            self.move(rect.center().x() - self.width()//2, rect.center().y() - self.height()//2)

    def _build(self):
        self.shell = QFrame()
        self.shell.setObjectName("GlassShell")
        root_layout = QVBoxLayout(self.shell)
        root_layout.setContentsMargins(12, 10, 12, 12)
        root_layout.setSpacing(10)
        self.titlebar = TitleBar(self, self.palette, "AirLink")
        root_layout.addWidget(self.titlebar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(196)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(10, 14, 10, 14)
        side.setSpacing(7)
        caption = QLabel("WORKSPACE")
        caption.setObjectName("Muted")
        caption.setStyleSheet("font-size: 8pt; font-weight: 700; letter-spacing: 1px; padding: 0 8px 6px 8px;")
        side.addWidget(caption)
        self.nav_buttons = {}
        for name, glyph in [("Nearby", "⌁"), ("Activity", "◷"), ("Settings", "⚙")]:
            btn = QPushButton(f"{glyph}     {name}")
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setMinimumHeight(43)
            btn.clicked.connect(lambda checked=False, n=name: self.render_page(n))
            side.addWidget(btn)
            self.nav_buttons[name] = btn
        side.addStretch(1)
        adaptive = QFrame()
        adaptive.setObjectName("GlassCard")
        ad = QVBoxLayout(adaptive)
        ad.setContentsMargins(10, 11, 10, 11)
        ad.setSpacing(6)
        small = QLabel("✦  ADAPTIVE GLASS")
        small.setObjectName("Accent")
        small.setStyleSheet("font-size: 8pt; font-weight: 750;")
        desc = QLabel("Accent colours follow your desktop wallpaper automatically.")
        desc.setObjectName("Muted")
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 8pt;")
        ad.addWidget(small)
        ad.addWidget(desc)
        side.addWidget(ad)
        host = QVBoxLayout()
        host.setContentsMargins(0, 0, 0, 0)
        host.setSpacing(8)
        self.content = QWidget()
        self.content.setObjectName("ContentArea")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(5, 3, 5, 2)
        self.content_layout.setSpacing(13)
        host.addWidget(self.content, 1)
        body.addWidget(self.sidebar)
        body.addLayout(host, 1)
        root_layout.addLayout(body, 1)
        foot = QHBoxLayout()
        foot.setContentsMargins(5, 1, 5, 0)
        disclaimer = QLabel("LAN TRANSFER  ·  RECEIVER APPROVAL REQUIRED")
        disclaimer.setObjectName("Muted")
        disclaimer.setStyleSheet("font-size: 7.5pt; letter-spacing: .8px;")
        foot.addWidget(disclaimer)
        foot.addStretch(1)
        self.theme_state = QLabel("● WALLPAPER-MATCHED")
        self.theme_state.setObjectName("Accent")
        self.theme_state.setStyleSheet("font-size: 8pt; font-weight: 700;")
        foot.addWidget(self.theme_state)
        root_layout.addLayout(foot)
        self.setCentralWidget(self.shell)

    def clear_content(self):
        layout = self.content_layout

        def clear_nested(nested):
            while nested.count():
                child = nested.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
                elif child.layout():
                    clear_nested(child.layout())
                    child.layout().deleteLater()

        clear_nested(layout)
        return layout

    def render_page(self, name: str):
        self.current_page = name
        for nav_name, button in self.nav_buttons.items():
            button.setChecked(nav_name == name)
        root = self.clear_content()
        if name == "Nearby":
            self._build_nearby(root)
        elif name == "Activity":
            self._build_activity(root)
        else:
            self._build_settings(root)
        self.content.setStyleSheet("background: transparent;")

    def _page_header(self, layout, title: str, subtitle: str):
        h = QHBoxLayout()
        names = QVBoxLayout()
        title_lbl = QLabel(title)
        title_lbl.setObjectName("PageTitle")
        sub = QLabel(subtitle)
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        names.addWidget(title_lbl)
        names.addWidget(sub)
        h.addLayout(names, 1)
        layout.addLayout(h)

    def _build_nearby(self, root):
        self._page_header(root, "Nearby devices", "Wallpaper-adaptive glass UI with receiver-approved transfers over a trusted local network.")
        hero = QFrame()
        hero.setObjectName("HeroCard")
        hl = QHBoxLayout(hero)
        hl.setContentsMargins(17, 15, 17, 15)
        hl.setSpacing(12)
        symbol = QLabel("↗")
        symbol.setObjectName("Accent")
        symbol.setStyleSheet("font-size: 28pt; font-weight: 300;")
        hl.addWidget(symbol)
        message = QVBoxLayout()
        eyebrow = QLabel("DRAG-TO-SHARE")
        eyebrow.setObjectName("Eyebrow")
        heading = QLabel("Drop a file on a device")
        heading.setStyleSheet("font-size: 12pt; font-weight: 700;")
        detail = QLabel("Select a file, enter the receiving laptop IP, and approve on the other device.")
        detail.setObjectName("Muted")
        detail.setWordWrap(True)
        detail.setStyleSheet("font-size: 8.5pt;")
        message.addWidget(eyebrow)
        message.addWidget(heading)
        message.addWidget(detail)
        hl.addLayout(message, 1)
        choose = QPushButton("＋  Choose file")
        choose.setObjectName("PrimaryButton")
        choose.clicked.connect(self.choose_file)
        hl.addWidget(choose, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(hero)
        receive_address = QLabel(f"THIS PC RECEIVES AT  {local_ip()}:{TRANSFER_PORT}   ·   APPROVAL REQUIRED")
        receive_address.setObjectName("Badge")
        receive_address.setWordWrap(True)
        root.addWidget(receive_address)

        row = QHBoxLayout()
        eyebrow = QLabel("RECEIVER CONNECTION")
        eyebrow.setObjectName("Eyebrow")
        row.addWidget(eyebrow)
        row.addStretch(1)
        sim = QLabel("MANUAL LAN CONNECTION")
        sim.setObjectName("Badge")
        row.addWidget(sim)
        root.addLayout(row)
        grid_frame = QWidget()
        grid = QGridLayout(grid_frame)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        for index, (device, kind, rssi) in enumerate(DEVICES):
            card = DeviceCard(device, kind, rssi, self.palette, selected=(device == self.selected_device), overlay=False)
            card.clicked.connect(self.select_device)
            grid.addWidget(card, index // 2, index % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        root.addWidget(grid_frame)

        action = QFrame()
        action.setObjectName("GlassCard")
        al = QHBoxLayout(action)
        al.setContentsMargins(14, 11, 14, 11)
        al.setSpacing(9)
        info = QVBoxLayout()
        label = QLabel("READY TO SHARE")
        label.setObjectName("Eyebrow")
        selected = QLabel("Recipient: " + (self.selected_device or "Enter a receiver IP"))
        selected.setStyleSheet("font-weight: 650;")
        selected.setWordWrap(True)
        file = QLabel("File: " + (Path(self.selected_file).name if self.selected_file else "No file selected"))
        file.setObjectName("Muted")
        file.setWordWrap(True)
        info.addWidget(label)
        info.addWidget(selected)
        info.addWidget(file)
        al.addLayout(info, 1)
        send = QPushButton("Send file  →")
        send.setObjectName("PrimaryButton")
        send.clicked.connect(self.send_file)
        al.addWidget(send, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(action)
        root.addStretch(1)

    def _build_activity(self, root):
        self._page_header(root, "Activity", "Real transfer events and incoming file approvals on this PC.")
        if not self.activity:
            card = QFrame()
            card.setObjectName("GlassCard")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(20, 22, 20, 22)
            empty = QLabel("◷")
            empty.setObjectName("Accent")
            empty.setStyleSheet("font-size: 30pt;")
            text = QLabel("Nothing here yet")
            text.setStyleSheet("font-size: 14pt; font-weight: 700;")
            note = QLabel("Select a file or test a drop-panel interaction to create a local demo activity entry.")
            note.setObjectName("Muted")
            note.setWordWrap(True)
            cl.addWidget(empty, 0, Qt.AlignmentFlag.AlignHCenter)
            cl.addWidget(text, 0, Qt.AlignmentFlag.AlignHCenter)
            cl.addWidget(note, 0, Qt.AlignmentFlag.AlignHCenter)
            root.addWidget(card)
        else:
            for item in reversed(self.activity):
                card = QFrame()
                card.setObjectName("GlassCard")
                l = QHBoxLayout(card)
                l.setContentsMargins(14, 12, 14, 12)
                glyph = QLabel("↗")
                glyph.setObjectName("Accent")
                glyph.setStyleSheet("font-size: 18pt;")
                desc = QLabel(item)
                desc.setWordWrap(True)
                l.addWidget(glyph)
                l.addWidget(desc, 1)
                root.addWidget(card)
        root.addStretch(1)

    def _build_settings(self, root):
        self._page_header(root, "Settings & policy", "Glass appearance adapts automatically; policy and proximity remain demo-only.")
        blocks = [
            ("Appearance", "Wallpaper-matched accent", "AirLink samples Windows wallpaper colors about every 5 seconds."),
            ("Material", "Windows Acrylic + translucent cards", "If Windows composition support is unavailable, translucent Qt styling remains as a fallback."),
            ("Proximity", "Not used to authorize real LAN transfers yet", "Wi-Fi RSSI is not a reliable exact 5-metre measurement; LAN transfers require receiver approval instead."),
            ("Discovery", "Manual LAN address", "Enter the receiving laptop IPv4 address. Automatic Bluetooth/Wi-Fi discovery is not implemented."),
            ("Transfer", "Real file bytes over private LAN", "The receiver must approve each incoming file. First version uses unencrypted HTTP; use only on a trusted private network."),
        ]
        for title, value, detail in blocks:
            card = QFrame()
            card.setObjectName("GlassCard")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(15, 12, 15, 12)
            lbl = QLabel(title.upper())
            lbl.setObjectName("Eyebrow")
            value_lbl = QLabel(value)
            value_lbl.setStyleSheet("font-size: 11pt; font-weight: 700;")
            detail_lbl = QLabel(detail)
            detail_lbl.setObjectName("Muted")
            detail_lbl.setWordWrap(True)
            cl.addWidget(lbl)
            cl.addWidget(value_lbl)
            cl.addWidget(detail_lbl)
            root.addWidget(card)
        root.addStretch(1)

    def select_device(self, name: str):
        self.selected_device = name
        self.render_page(self.current_page)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose a file to preview", str(Path.home()), "All files (*.*)")
        if path:
            self.selected_file = path
            self.activity.append(f"Selected {Path(path).name} · no data sent")
            self.render_page("Nearby")

    def send_file(self):
        if hasattr(self, "host_app"):
            self.host_app.send_file_action()
        else:
            QMessageBox.warning(self, "AirLink", "Transfer service is not initialized.")

    def handle_file_drop(self, path: str, device_name: str):
        p = Path(path)
        if not p.exists() or not p.is_file():
            if hasattr(self, "panel"):
                self.panel.set_status("That drop is not a regular file.", self.palette['ORANGE'])
            return
        self.selected_file = str(p)
        self.selected_device = device_name
        self.activity.append(f"Selected {p.name} for LAN transfer")
        if hasattr(self, "panel"):
            self.panel.set_status(f"Selected {p.name}. Enter the receiver's LAN IP in the dashboard to send.", self.palette['CYAN'])
            self.panel.last_drop_at = time.monotonic()
        self.render_page("Nearby")
        if hasattr(self, "host_app"):
            QTimer.singleShot(120, self.host_app.send_file_action)

    def refresh_theme(self, palette: dict[str, str]):
        self.palette = palette
        self.setWindowIcon(make_icon(64, palette['BLUE']))
        self.setStyleSheet(make_stylesheet(palette))
        if hasattr(self, "panel"):
            self.panel.apply_theme(palette)
        self.render_page(self.current_page)
        if self.isVisible():
            QTimer.singleShot(100, lambda: apply_windows_acrylic(self, palette, 0xC4))

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(180, lambda: apply_windows_acrylic(self, self.palette, 0xC4))

    def closeEvent(self, event):
        # Keep the background service alive; use the tray menu to quit completely.
        event.ignore()
        self.hide()
        if self.tray.isVisible():
            self.tray.showMessage("AirLink is still running", "Open AirLink from the system tray or drag a file to show the panel.", QSystemTrayIcon.MessageIcon.Information, 2500)

    def hide_to_tray(self):
        self.hide()


class AirLinkApp:
    def __init__(self, app: QApplication, background=False):
        self.app = app
        self.theme = WallpaperTheme()
        self.palette = self.theme.palette
        self.receiver = TransferReceiver()
        self.receiver.start()
        self.transfer_signals = TransferSignals()
        self.transfer_signals.progress.connect(self.on_transfer_progress)
        self.transfer_signals.finished.connect(self.on_transfer_finished)
        self.progress_dialog = None
        self.active_job = None
        self.bridge = DragSignals()
        self.bridge.started.connect(self.drag_started)
        self.bridge.ended.connect(self.drag_ended)
        self.bridge.problem.connect(self.detector_problem)

        self.tray = QSystemTrayIcon(make_icon(64, self.palette['BLUE']), app)
        self.tray.setToolTip("AirLink · Wallpaper-adaptive glass sharing")
        menu = QMenu()
        open_action = QAction("Open AirLink", app)
        open_action.triggered.connect(self.open_dashboard)
        show_action = QAction("Show drop panel", app)
        show_action.triggered.connect(self.show_panel)
        quit_action = QAction("Quit AirLink", app)
        quit_action.triggered.connect(self.quit)
        menu.addAction(open_action)
        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.show()

        self.window = AirLinkWindow(self.theme, self.tray)
        self.window.host_app = self
        self.panel = DragPanel(self.theme)
        self.window.panel = self.panel
        self.panel.fileDropped.connect(self.window.handle_file_drop)
        self.incoming_timer = QTimer()
        self.incoming_timer.timeout.connect(self.check_incoming_offers)
        self.incoming_timer.start(500)
        self.detector = GlobalDragDetector(self.bridge)
        self.detector.start()
        self.background = background
        if not background:
            self.window.show()
        QTimer.singleShot(220, lambda: apply_windows_acrylic(self.window, self.theme.palette, 0xC4) if self.window.isVisible() else None)
        self.theme_timer = QTimer()
        self.theme_timer.timeout.connect(self.check_wallpaper)
        self.theme_timer.start(5000)
        self.hide_timer: Optional[QTimer] = None

    def send_file_action(self):
        path = self.window.selected_file
        if not path or not Path(path).is_file():
            path, _ = QFileDialog.getOpenFileName(self.window, "Choose a file to send", str(Path.home()), "All files (*.*)")
            if not path:
                return
            self.window.selected_file = path
        dialog_parent = self.panel if self.panel.isVisible() else self.window
        host, ok = QInputDialog.getText(
            dialog_parent, "Send to another laptop",
            f"Enter the receiving laptop's IPv4 address (same private Wi-Fi/LAN).\nThis PC receives at {local_ip()}:{TRANSFER_PORT}",
            text="192.168.1.25"
        )
        if not ok or not host.strip():
            return
        host = host.strip()
        port = TRANSFER_PORT
        if ":" in host and host.count(":") == 1:
            host, port_text = host.rsplit(":", 1)
            try:
                port = int(port_text)
            except ValueError:
                QMessageBox.warning(self.window, "Invalid address", "Port must be a number.")
                return
        if not host or any(ch in host for ch in "/\\ ?#") or not 1 <= port <= 65535:
            QMessageBox.warning(self.window, "Invalid address", "Enter an IPv4 address such as 192.168.1.25, optionally followed by :port.")
            return
        file_path = path
        job_id = str(time.time_ns())
        self.active_job = job_id
        self.progress_dialog = QProgressDialog("Connecting to receiver…", "", 0, 100, dialog_parent)
        self.progress_dialog.setWindowTitle("AirLink transfer")
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        self.progress_dialog.show()
        self.window.activity.append(f"Offering {Path(file_path).name} to {host}:{port}…")
        self.window.render_page("Activity")
        def worker():
            try:
                send_file_over_lan(host, file_path, socket.gethostname(), self.transfer_signals, job_id, port=port)
            except Exception as exc:
                self.transfer_signals.finished.emit(job_id, False, f"Could not send {Path(file_path).name}: {exc}")
        threading.Thread(target=worker, name="AirLinkSender", daemon=True).start()

    def on_transfer_progress(self, job_id: str, message: str, percent: int):
        if job_id != self.active_job or self.progress_dialog is None:
            return
        self.progress_dialog.setLabelText(message)
        self.progress_dialog.setValue(max(0, min(100, percent)))

    def on_transfer_finished(self, job_id: str, success: bool, message: str):
        if job_id != self.active_job:
            return
        if self.progress_dialog is not None:
            self.progress_dialog.close()
            self.progress_dialog = None
        self.window.activity.append(("✓ " if success else "✕ ") + message)
        self.window.render_page("Activity")
        dialog_parent = self.panel if self.panel.isVisible() else self.window
        if success:
            QMessageBox.information(dialog_parent, "AirLink transfer complete", message)
        else:
            QMessageBox.warning(dialog_parent, "AirLink transfer failed", message + "\n\nConfirm both laptops are on the same trusted private network, the receiving AirLink is running, and Windows Firewall allows Python on Private networks.")

    def check_incoming_offers(self):
        # The receiver prompts on the GUI thread; incoming HTTP threads only queue offers.
        offer = self.receiver.next_pending()
        if not offer:
            return
        size_text = f"{offer['size']:,} bytes"
        if offer["size"] >= 1024 * 1024:
            size_text += f" ({offer['size'] / (1024*1024):.1f} MiB)"
        answer = QMessageBox.question(
            self.window, "Incoming AirLink file",
            f"{offer['sender']} wants to send this file to your PC:\n\n"
            f"File: {offer['filename']}\nSize: {size_text}\n\n"
            f"Accept and save it to:\n{self.receiver.inbox}\n\nAccept this file?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        self.receiver.decide(offer["id"], answer == QMessageBox.StandardButton.Yes)
        if answer == QMessageBox.StandardButton.Yes:
            self.window.activity.append(f"Accepted incoming file {offer['filename']} from {offer['sender']}")
        else:
            self.window.activity.append(f"Declined incoming file {offer['filename']} from {offer['sender']}")
        self.window.render_page("Activity")

    def open_dashboard(self):
        self.window.showNormal()
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()
        QTimer.singleShot(150, lambda: apply_windows_acrylic(self.window, self.theme.palette, 0xC4))

    def show_panel(self):
        self.panel.show_on_right()
        self.panel.set_status("Manual preview: drag a file from Explorer onto a device.", self.theme.palette['CYAN'])

    def drag_started(self):
        self.panel.show_on_right()
        self.panel.set_status("Release your file on a device card.", self.theme.palette['CYAN'])
        if self.hide_timer:
            self.hide_timer.stop()

    def drag_ended(self):
        if self.hide_timer:
            self.hide_timer.stop()
        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_panel_after_drag)
        self.hide_timer.start(1600)

    def hide_panel_after_drag(self):
        if time.monotonic() - self.panel.last_drop_at > 1.45:
            self.panel.hide()

    def detector_problem(self, message: str):
        self.tray.setToolTip("AirLink · drag detector needs attention")
        self.panel.set_status(message, self.theme.palette['ORANGE'])

    def check_wallpaper(self):
        old = self.theme.signature
        if self.theme.refresh():
            self.palette = self.theme.palette
            self.tray.setIcon(make_icon(64, self.palette['BLUE']))
            self.window.refresh_theme(self.palette)
            if self.panel.isVisible():
                self.panel.apply_theme(self.palette)
                QTimer.singleShot(100, lambda: apply_windows_acrylic(self.panel, self.palette, 0xC4))

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.open_dashboard()

    def quit(self):
        self.detector.stop()
        self.receiver.stop()
        self.panel.hide()
        self.tray.hide()
        self.app.quit()


def main():
    parser = argparse.ArgumentParser(description="AirLink wallpaper-adaptive glass UI and LAN file transfer")
    parser.add_argument("--background", action="store_true", help="start hidden in the system tray")
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("AirLink")
    app.setOrganizationName("AirLink")
    app.setQuitOnLastWindowClosed(False)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("Warning: Windows system tray is unavailable; background mode may be harder to reopen.")
    host = AirLinkApp(app, background=args.background)
    # Keep live references on QApplication.
    app._airlink_host = host
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
