"""
BANKSER' Desktop v2.0
=====================
A Linux Mint inspired desktop environment built with PySide6.

  * Mint green (Cinnamon) colour scheme, symbolic vector icons
  * 10 switchable colour schemes - type 'color 1-10' in the terminal
  * Custom painted splash screen with animated leaf emblem
  * Demo shell terminal - type `-welcome` for the ASCII bank picture
  * bankserAI assistant - runs Qwen3.5-4B locally through llama.cpp
  * ART studio - a full drawing program (pencil, brush, fill, save PNG)
  * MATRIX RAIN - a cmatrix style digital rain of falling glyphs
  * PASTESHELL ASCII tool built into the desktop

Run:  python bankser_desktop.py
"""

import concurrent.futures
import html
import ipaddress
import json
import math
import os
import platform
import queue
import random
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    Qt, QTimer, QRect, QRectF, QPointF, QPoint, QPropertyAnimation, QEasingCurve
)
from PySide6.QtGui import (
    QColor, QPainter, QPen, QFont, QFontDatabase, QFontMetricsF,
    QLinearGradient, QRadialGradient, QPainterPath, QKeySequence,
    QTextCursor, QTextCharFormat, QImage
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QTextEdit, QLineEdit,
    QListWidget, QMessageBox, QGraphicsDropShadowEffect, QMenu,
    QAbstractButton, QSizePolicy, QSlider, QColorDialog, QFileDialog
)

# ==========================================================
# CONSTANTS / THEME
# ==========================================================

APP_NAME = "BANKSER'"
VERSION = "2.0"

HOME = Path.home() / ".bankser"
HOME.mkdir(exist_ok=True)
NOTES_FILE = HOME / "notes.txt"

# --- local AI runtime (llama.cpp + Qwen3.5-4B) -----------------
AI_MODEL_DIR = HOME / "models"
AI_RUNTIME_DIR = HOME / "runtime"
AI_MODEL_FILE = AI_MODEL_DIR / "qwen3.5-4b-Q4_K_M.gguf"
AI_MODEL_LABEL = "Qwen3.5-4B (Q4_K_M, local)"
AI_SERVER_HOST = "127.0.0.1"
AI_SERVER_PORT = 18080
AI_PID_FILE = HOME / "model_server.pid"

# ==========================================================
# THEMES  (10 colour schemes for the whole desktop)
# ==========================================================

def _mix(color_a, color_b, ratio):
    """Blend two hex colours; ratio is the weight of color_b."""
    a, b = QColor(color_a), QColor(color_b)
    red = int(round(a.red() + (b.red() - a.red()) * ratio))
    green = int(round(a.green() + (b.green() - a.green()) * ratio))
    blue = int(round(a.blue() + (b.blue() - a.blue()) * ratio))
    return "#%02x%02x%02x" % (red, green, blue)


class Theme:
    """One complete colour scheme - every surface derives from its accent."""

    def __init__(self, index, name, accent, accent_light, accent_dark):
        self.index = index
        self.name = name
        self.accent = accent
        self.accent_light = accent_light
        self.accent_dark = accent_dark

        # panels and windows
        self.panel_bg = _mix("#3b3b3b", accent_dark, 0.14)
        self.header_bg = _mix("#414141", accent_dark, 0.20)
        self.window_bg = _mix("#333333", accent_dark, 0.16)
        self.deep_bg = _mix("#252525", accent_dark, 0.13)
        self.border = _mix("#4d4d4d", accent, 0.30)

        # text
        self.text = _mix("#e7e7e7", accent, 0.08)
        self.text_dim = _mix("#a6b3a6", accent, 0.16)
        self.text_muted = _mix("#879487", accent, 0.18)

        # terminal
        self.terminal_bg = _mix("#1b2019", accent_dark, 0.16)
        self.prompt = accent

        # buttons
        self.on_accent = _mix("#111111", accent_dark, 0.20)
        self.button_bg = _mix("#4a4a4a", accent_dark, 0.18)
        self.button_border = _mix("#595959", accent, 0.22)
        self.gauge_track = _mix("#3d3d3d", accent_dark, 0.14)

        rgb = QColor(accent)
        self.accent_soft = (f"rgba({rgb.red()}, {rgb.green()}, "
                            f"{rgb.blue()}, 45)")
        self.accent_faint = (f"rgba({rgb.red()}, {rgb.green()}, "
                             f"{rgb.blue()}, 26)")

        # wallpaper
        self.wallpaper_top = _mix("#0a0f08", accent_dark, 0.12)
        self.wallpaper_mid = _mix("#141d10", accent_dark, 0.26)
        self.wallpaper_bottom = _mix("#1d2a18", accent_dark, 0.38)
        self.hill_fill = _mix("#1e381c", accent_dark, 0.35)
        self.hill_line = _mix("#78aa50", accent, 0.55)


THEMES = [
    Theme(1, "MINT", "#87cf3e", "#a6d96b", "#5e9e31"),
    Theme(2, "AMETHYST", "#a56de2", "#c9a2f7", "#7a48c4"),
    Theme(3, "AZURE", "#4a9eff", "#8cc4ff", "#2f6fd0"),
    Theme(4, "CRIMSON", "#e05252", "#ff8f8f", "#a83232"),
    Theme(5, "TANGERINE", "#f0954a", "#ffc08f", "#c2651f"),
    Theme(6, "EMERALD", "#2fbf71", "#7ee2ac", "#1d8f52"),
    Theme(7, "MAGENTA", "#ef5fa8", "#ff9fcd", "#bd3a7f"),
    Theme(8, "GOLDEN", "#e5b83c", "#ffdc85", "#b18a1e"),
    Theme(9, "GRAPHITE", "#9aa5b1", "#ccd4dd", "#6d7883"),
    Theme(10, "CYAN", "#37d7e8", "#8bf0f8", "#1a9fb0"),
]

CURRENT_THEME = THEMES[0]


def use_theme(index):
    """Point every global surface colour at the chosen theme."""
    global CURRENT_THEME, MINT, MINT_LIGHT, MINT_DARK, PANEL_BG, \
        PANEL_BG_DARK, HEADER_BG, WINDOW_BG, WINDOW_BG_DEEP, BORDER, \
        TEXT, TEXT_DIM, TEXT_MUTED, TERMINAL_BG, PROMPT, WALLPAPER_TOP, \
        WALLPAPER_MID, WALLPAPER_BOTTOM, HILL_FILL, HILL_LINE

    theme = THEMES[index]
    CURRENT_THEME = theme

    MINT = theme.accent
    MINT_LIGHT = theme.accent_light
    MINT_DARK = theme.accent_dark
    PANEL_BG = theme.panel_bg
    PANEL_BG_DARK = theme.panel_bg
    HEADER_BG = theme.header_bg
    WINDOW_BG = theme.window_bg
    WINDOW_BG_DEEP = theme.deep_bg
    BORDER = theme.border
    TEXT = theme.text
    TEXT_DIM = theme.text_dim
    TEXT_MUTED = theme.text_muted
    TERMINAL_BG = theme.terminal_bg
    PROMPT = theme.prompt
    WALLPAPER_TOP = theme.wallpaper_top
    WALLPAPER_MID = theme.wallpaper_mid
    WALLPAPER_BOTTOM = theme.wallpaper_bottom
    HILL_FILL = theme.hill_fill
    HILL_LINE = theme.hill_line

    return theme


# --- active palette (updated by use_theme) --------------------
MINT = CURRENT_THEME.accent
MINT_LIGHT = CURRENT_THEME.accent_light
MINT_DARK = CURRENT_THEME.accent_dark
PANEL_BG = CURRENT_THEME.panel_bg
PANEL_BG_DARK = CURRENT_THEME.panel_bg
HEADER_BG = CURRENT_THEME.header_bg
WINDOW_BG = CURRENT_THEME.window_bg
WINDOW_BG_DEEP = CURRENT_THEME.deep_bg
BORDER = CURRENT_THEME.border
TEXT = CURRENT_THEME.text
TEXT_DIM = CURRENT_THEME.text_dim
TEXT_MUTED = CURRENT_THEME.text_muted
TERMINAL_BG = CURRENT_THEME.terminal_bg
PROMPT = CURRENT_THEME.prompt
WALLPAPER_TOP = CURRENT_THEME.wallpaper_top
WALLPAPER_MID = CURRENT_THEME.wallpaper_mid
WALLPAPER_BOTTOM = CURRENT_THEME.wallpaper_bottom
HILL_FILL = CURRENT_THEME.hill_fill
HILL_LINE = CURRENT_THEME.hill_line

UI_FONT_NAME = "Segoe UI"
MONO_FONT_NAME = "Consolas"

THEME_FILE = HOME / "theme.json"


def load_theme():
    """Restore the colour scheme chosen in a previous session."""
    try:
        data = json.loads(THEME_FILE.read_text(encoding="utf-8"))
        number = int(data.get("theme", 1))
        if 1 <= number <= len(THEMES):
            use_theme(number - 1)
    except (OSError, ValueError, TypeError):
        pass


def save_theme(number):
    """Remember the colour scheme for the next session."""
    try:
        THEME_FILE.write_text(json.dumps({"theme": number}), encoding="utf-8")
    except OSError:
        pass


def _init_fonts():
    """Pick the nicest available font family (Mint uses Noto Sans / Ubuntu)."""
    global UI_FONT_NAME, MONO_FONT_NAME

    available = set(QFontDatabase.families())

    for candidate in ("Noto Sans", "Ubuntu", "Cantarell",
                      "DejaVu Sans", "Segoe UI"):
        if candidate in available:
            UI_FONT_NAME = candidate
            break

    for candidate in ("Noto Sans Mono", "DejaVu Sans Mono",
                      "Cascadia Mono", "Consolas", "Courier New"):
        if candidate in available:
            MONO_FONT_NAME = candidate
            break


def ui_font(size=10, bold=False):
    font = QFont(UI_FONT_NAME, size)
    font.setBold(bold)
    return font


def mono_font(size=9, bold=False):
    font = QFont(MONO_FONT_NAME, size)
    font.setBold(bold)
    return font


# ==========================================================
# VECTOR ICON PAINTER
# ==========================================================

def draw_icon(painter, kind, box, color, weight=1.7):
    """Paint a monochrome symbolic icon (Mint style) inside `box`."""
    x, y = box.x(), box.y()
    w, h = box.width(), box.height()
    cx, cy = x + w / 2.0, y + h / 2.0

    pen = QPen(color)
    pen.setWidthF(weight)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)

    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    if kind == "menu":
        for i in range(3):
            yy = y + h * (0.24 + i * 0.26)
            painter.drawLine(QPointF(x + w * 0.15, yy),
                             QPointF(x + w * 0.85, yy))

    elif kind == "apps":
        cell = min(w, h) / 4.2
        gap = cell * 0.42
        for row in range(3):
            for col in range(3):
                px = x + (w - (cell * 3 + gap * 2)) / 2 + col * (cell + gap)
                py = y + (h - (cell * 3 + gap * 2)) / 2 + row * (cell + gap)
                painter.setBrush(color)
                painter.drawRoundedRect(QRectF(px, py, cell, cell), 1.6, 1.6)
                painter.setBrush(Qt.NoBrush)

    elif kind == "notes":
        painter.drawRoundedRect(
            QRectF(x + w * 0.22, y + h * 0.12, w * 0.56, h * 0.76), 3, 3)
        for i in range(4):
            yy = y + h * (0.3 + i * 0.16)
            painter.drawLine(QPointF(x + w * 0.32, yy),
                             QPointF(x + w * (0.68 if i % 2 else 0.62), yy))

    elif kind == "folder":
        path = QPainterPath()
        path.moveTo(x + w * 0.12, y + h * 0.72)
        path.lineTo(x + w * 0.12, y + h * 0.30)
        path.lineTo(x + w * 0.40, y + h * 0.30)
        path.lineTo(x + w * 0.47, y + h * 0.42)
        path.lineTo(x + w * 0.88, y + h * 0.42)
        path.lineTo(x + w * 0.88, y + h * 0.72)
        path.closeSubpath()
        painter.drawPath(path)

    elif kind == "terminal":
        painter.drawRoundedRect(
            QRectF(x + w * 0.10, y + h * 0.18, w * 0.80, h * 0.64), 4, 4)
        painter.drawLine(QPointF(x + w * 0.26, y + h * 0.40),
                         QPointF(x + w * 0.40, y + h * 0.50))
        painter.drawLine(QPointF(x + w * 0.40, y + h * 0.50),
                         QPointF(x + w * 0.26, y + h * 0.60))
        painter.drawLine(QPointF(x + w * 0.48, y + h * 0.62),
                         QPointF(x + w * 0.72, y + h * 0.62))

    elif kind == "monitor":
        painter.drawRoundedRect(
            QRectF(x + w * 0.10, y + h * 0.16, w * 0.80, h * 0.54), 4, 4)
        painter.drawLine(QPointF(cx, y + h * 0.70),
                         QPointF(cx, y + h * 0.82))
        painter.drawLine(QPointF(x + w * 0.28, y + h * 0.84),
                         QPointF(x + w * 0.72, y + h * 0.84))

    elif kind == "music":
        painter.drawLine(QPointF(x + w * 0.62, y + h * 0.16),
                         QPointF(x + w * 0.62, y + h * 0.62))
        painter.drawLine(QPointF(x + w * 0.62, y + h * 0.16),
                         QPointF(x + w * 0.86, y + h * 0.28))
        painter.drawLine(QPointF(x + w * 0.86, y + h * 0.28),
                         QPointF(x + w * 0.86, y + h * 0.48))
        painter.setBrush(color)
        painter.drawEllipse(QPointF(x + w * 0.44, y + h * 0.66),
                            w * 0.13, h * 0.10)
        painter.drawEllipse(QPointF(x + w * 0.70, y + h * 0.52),
                            w * 0.13, h * 0.10)
        painter.setBrush(Qt.NoBrush)

    elif kind == "lock":
        painter.drawRoundedRect(
            QRectF(x + w * 0.22, y + h * 0.44, w * 0.56, h * 0.40), 4, 4)
        arc = QRectF(x + w * 0.32, y + h * 0.16, w * 0.36, h * 0.40)
        painter.drawArc(arc, 0, 180 * 16)

    elif kind == "power":
        painter.drawArc(QRectF(x + w * 0.18, y + h * 0.18,
                               w * 0.64, h * 0.64), 60 * 16, 240 * 16)
        painter.drawLine(QPointF(cx, y + h * 0.08),
                         QPointF(cx, y + h * 0.42))

    elif kind == "network":
        painter.drawEllipse(QRectF(x + w * 0.16, y + h * 0.16,
                                   w * 0.68, h * 0.68))
        painter.drawLine(QPointF(x + w * 0.16, cy),
                         QPointF(x + w * 0.84, cy))
        painter.drawArc(QRectF(x + w * 0.30, y + h * 0.16,
                               w * 0.40, h * 0.68), 0, 360 * 16)

    elif kind == "volume":
        painter.drawLine(QPointF(x + w * 0.22, y + h * 0.38),
                         QPointF(x + w * 0.22, y + h * 0.62))
        painter.drawLine(QPointF(x + w * 0.22, y + h * 0.38),
                         QPointF(x + w * 0.38, y + h * 0.38))
        painter.drawLine(QPointF(x + w * 0.38, y + h * 0.38),
                         QPointF(x + w * 0.58, y + h * 0.18))
        painter.drawLine(QPointF(x + w * 0.38, y + h * 0.62),
                         QPointF(x + w * 0.58, y + h * 0.82))
        painter.drawLine(QPointF(x + w * 0.58, y + h * 0.18),
                         QPointF(x + w * 0.58, y + h * 0.82))
        painter.drawArc(QRectF(x + w * 0.54, y + h * 0.28,
                               w * 0.26, h * 0.44), -60 * 16, 120 * 16)
        painter.drawArc(QRectF(x + w * 0.62, y + h * 0.14,
                               w * 0.40, h * 0.72), -55 * 16, 110 * 16)

    elif kind == "close":
        painter.drawLine(QPointF(x + w * 0.26, y + h * 0.26),
                         QPointF(x + w * 0.74, y + h * 0.74))
        painter.drawLine(QPointF(x + w * 0.74, y + h * 0.26),
                         QPointF(x + w * 0.26, y + h * 0.74))

    elif kind == "minimize":
        painter.drawLine(QPointF(x + w * 0.22, cy),
                         QPointF(x + w * 0.78, cy))

    elif kind == "maximize":
        painter.drawRoundedRect(
            QRectF(x + w * 0.20, y + h * 0.20, w * 0.60, h * 0.60), 2, 2)

    elif kind == "restore":
        painter.drawRoundedRect(
            QRectF(x + w * 0.12, y + h * 0.26, w * 0.54, h * 0.54), 2, 2)
        painter.drawLine(QPointF(x + w * 0.30, y + h * 0.26),
                         QPointF(x + w * 0.30, y + h * 0.16))
        painter.drawLine(QPointF(x + w * 0.30, y + h * 0.26),
                         QPointF(x + w * 0.78, y + h * 0.26))
        painter.drawLine(QPointF(x + w * 0.78, y + h * 0.26),
                         QPointF(x + w * 0.78, y + h * 0.72))

    elif kind == "skull":
        painter.drawEllipse(QRectF(x + w * 0.22, y + h * 0.10,
                                   w * 0.56, h * 0.50))
        painter.drawRoundedRect(QRectF(x + w * 0.34, y + h * 0.54,
                                       w * 0.32, h * 0.24), 4, 4)
        painter.setBrush(color)
        painter.drawEllipse(QRectF(x + w * 0.31, y + h * 0.28,
                                   w * 0.13, h * 0.14))
        painter.drawEllipse(QRectF(x + w * 0.56, y + h * 0.28,
                                   w * 0.13, h * 0.14))
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(QPointF(x + w * 0.50, y + h * 0.44),
                         QPointF(x + w * 0.44, y + h * 0.52))
        painter.drawLine(QPointF(x + w * 0.50, y + h * 0.44),
                         QPointF(x + w * 0.56, y + h * 0.52))
        for i in range(3):
            tx = x + w * (0.40 + i * 0.08)
            painter.drawLine(QPointF(tx, y + h * 0.60),
                             QPointF(tx, y + h * 0.74))

    elif kind == "spark":
        # four point sparkle plus a small companion
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        path = QPainterPath()
        path.moveTo(cx, y + h * 0.08)
        path.quadTo(cx + w * 0.07, cy, x + w * 0.78, cy)
        path.quadTo(cx + w * 0.07, cy, cx, y + h * 0.86)
        path.quadTo(cx - w * 0.07, cy, x + w * 0.22, cy)
        path.quadTo(cx - w * 0.07, cy, cx, y + h * 0.08)
        path.closeSubpath()
        painter.drawPath(path)

        small = QPainterPath()
        small.moveTo(x + w * 0.84, y + h * 0.20)
        small.quadTo(x + w * 0.87, y + h * 0.36, x + w * 0.72, y + h * 0.38)
        small.quadTo(x + w * 0.87, y + h * 0.40, x + w * 0.84, y + h * 0.54)
        small.quadTo(x + w * 0.81, y + h * 0.40, x + w * 0.66, y + h * 0.38)
        small.quadTo(x + w * 0.81, y + h * 0.36, x + w * 0.84, y + h * 0.20)
        small.closeSubpath()
        painter.drawPath(small)
        painter.setBrush(Qt.NoBrush)

    elif kind == "brush":
        # paint brush tilted like a real one
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-40)

        painter.setBrush(color)
        painter.setPen(Qt.NoPen)

        # handle
        painter.drawRoundedRect(
            QRectF(-w * 0.085, -h * 0.46, w * 0.17, h * 0.48),
            w * 0.085, w * 0.085)

        # ferrule
        painter.drawRoundedRect(
            QRectF(-w * 0.115, 0.0, w * 0.23, h * 0.10), 2, 2)

        # bristles
        bristles = QPainterPath()
        bristles.moveTo(-w * 0.115, h * 0.09)
        bristles.lineTo(w * 0.115, h * 0.09)
        bristles.lineTo(w * 0.055, h * 0.42)
        bristles.quadTo(cx * 0, h * 0.47, -w * 0.055, h * 0.42)
        bristles.closeSubpath()
        painter.drawPath(bristles)

        painter.restore()
        painter.setBrush(Qt.NoBrush)

    elif kind == "matrix":
        # three columns of falling code
        columns = [(0.16, 0.92), (0.44, 0.66), (0.72, 0.80)]
        painter.setPen(Qt.NoPen)
        for index, (cx_pos, height) in enumerate(columns):
            segments = 5 - index
            segment_h = (h * 0.78) / 6.0
            for step in range(segments):
                width = w * (0.13 - step * 0.018)
                alpha = 235 - step * 42
                painter.setBrush(QColor(color.red(), color.green(),
                                       color.blue(), alpha))
                painter.drawRoundedRect(
                    QRectF(x + w * cx_pos, y + h * 0.10 + step * segment_h,
                           width, segment_h * 0.62), 1.5, 1.5)
        painter.setBrush(Qt.NoBrush)

    elif kind == "leaf":
        path = QPainterPath()
        path.moveTo(cx, y + h * 0.82)
        path.cubicTo(x + w * 0.10, y + h * 0.56,
                     x + w * 0.26, y + h * 0.10,
                     cx, y + h * 0.10)
        path.cubicTo(x + w * 0.74, y + h * 0.10,
                     x + w * 0.90, y + h * 0.56,
                     cx, y + h * 0.82)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawPath(path)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 90), weight * 0.8))
        painter.drawLine(QPointF(cx, y + h * 0.76),
                         QPointF(cx, y + h * 0.16))


THEME_ICONS = []


class IconWidget(QWidget):
    """A widget that simply renders one symbolic icon."""

    def __init__(self, kind, size=18, color=TEXT, theme_bound=False,
                 parent=None):
        super().__init__(parent)
        self.kind = kind
        self.color = QColor(color)
        self.setFixedSize(size, size)

        if theme_bound:
            THEME_ICONS.append(self)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        draw_icon(painter, self.kind,
                  QRectF(0, 0, self.width(), self.height()), self.color)


class IconButton(QAbstractButton):
    """Mint style toolbar / dock button with hover state."""

    def __init__(self, kind, tooltip="", size=34, color=None, hover=None,
                 theme_bound=False, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.theme_bound = theme_bound
        self.color = QColor(color) if color else QColor(TEXT)
        self.hover = QColor(hover) if hover else QColor(MINT_LIGHT)
        self._hovered = False
        self.setFixedSize(size, size)
        self.setToolTip(tooltip)
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self._hovered:
            hover_tint = QColor(MINT)
            hover_tint.setAlpha(45)
            painter.setBrush(hover_tint)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(self.rect().adjusted(0, 3, 0, 3), 7, 7)
            painter.setBrush(Qt.NoBrush)

        if self.theme_bound:
            base = QColor(TEXT_DIM)
            accent = self.hover if self.hover != QColor(MINT_LIGHT) \
                else QColor(MINT_LIGHT)
        else:
            base = self.color
            accent = self.hover

        color = accent if self._hovered else base
        draw_icon(painter, self.kind,
                  QRectF(0, 0, self.width(), self.height()), color)


# ==========================================================
# WALLPAPER  (Mint green hills)
# ==========================================================

class Wallpaper(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        w, h = rect.width(), rect.height()

        gradient = QLinearGradient(0, 0, 0, h)
        gradient.setColorAt(0.0, QColor(WALLPAPER_TOP))
        gradient.setColorAt(0.45, QColor(WALLPAPER_MID))
        gradient.setColorAt(1.0, QColor(WALLPAPER_BOTTOM))
        painter.fillRect(rect, gradient)

        glow = QRadialGradient(w * 0.5, h * 0.92, w * 0.62)
        glow_color = QColor(MINT)
        glow_color.setAlpha(80)
        glow.setColorAt(0, glow_color)
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillRect(rect, glow)

        # layered hills - the classic Cinnamon curve
        for i in range(7):
            hill_color = QColor(HILL_LINE)
            hill_color.setAlpha(max(14, 60 - i * 7))
            pen = QPen(hill_color, 1.6)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            y = h * (0.60 + i * 0.035)
            painter.drawArc(
                QRectF(-w * 0.22, y - h * 0.32, w * 1.44, h * 0.64),
                0, 180 * 16
            )

        # foreground hills
        painter.setPen(Qt.NoPen)
        for i, (scale, alpha) in enumerate(((0.82, 150), (0.66, 190))):
            hill_color = QColor(HILL_FILL)
            hill_color.setAlpha(alpha)
            painter.setBrush(hill_color)
            rect_hill = QRectF(-w * 0.22, h * (0.80 + i * 0.08),
                               w * 1.44, h * 0.55)
            painter.drawPath(self._hill(rect_hill))

        painter.end()

    @staticmethod
    def _hill(rect):
        path = QPainterPath()
        path.moveTo(rect.left(), rect.bottom())
        path.cubicTo(rect.left() + rect.width() * 0.22, rect.top() - rect.height() * 0.35,
                     rect.left() + rect.width() * 0.78, rect.top() - rect.height() * 0.35,
                     rect.right(), rect.bottom())
        path.closeSubpath()
        return path


# ==========================================================
# STYLE SHEET
# ==========================================================

STYLE_SHEET_TEMPLATE = """
QWidget {
    color: %(text)s;
}

QFrame#mintwindow {
    background: %(win)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
}

QWidget#winheader {
    background: %(header)s;
    border-bottom: 1px solid %(border)s;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
}

QLabel#wintitle {
    color: %(text)s;
    font-size: 12px;
    font-weight: bold;
}

QLabel {
    color: %(text_dim)s;
}

QLabel#accent {
    color: %(accent_light)s;
    font-weight: bold;
}

QLabel#dim {
    color: %(text_dim)s;
    font-weight: bold;
}

QLabel#strong {
    color: %(text)s;
}

QLabel#muted {
    color: %(muted)s;
}

QLabel#dimpad {
    color: %(text_dim)s;
    padding: 8px;
}

QPushButton {
    background: %(button_bg)s;
    color: %(text)s;
    border: 1px solid %(button_border)s;
    border-radius: 6px;
    padding: 5px 11px;
    font-size: 11px;
}

QPushButton:hover {
    background: %(mint)s;
    color: %(on_accent)s;
    border-color: %(mint_light)s;
}

QPushButton:pressed {
    background: %(mint_dark)s;
    color: %(on_accent)s;
}

QPushButton#ghost {
    background: transparent;
    border: 1px solid transparent;
    color: %(text_dim)s;
}

QPushButton#ghost:hover {
    background: %(accent_soft)s;
    color: %(text)s;
}

QLineEdit, QTextEdit, QListWidget {
    background: %(deep)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 6px;
    padding: 5px;
    selection-background-color: %(mint)s;
    selection-color: %(on_accent)s;
}

QLineEdit:focus, QTextEdit:focus, QListWidget:focus {
    border: 1px solid %(mint)s;
}

QLineEdit::placeholder {
    color: %(muted)s;
}

QListWidget::item {
    padding: 4px 3px;
    border-radius: 4px;
}

QListWidget::item:selected {
    background: %(accent_soft)s;
    color: %(text)s;
}

QListWidget::item:hover {
    background: %(accent_faint)s;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px 2px 2px 0;
}

QScrollBar::handle:vertical {
    background: %(button_border)s;
    border-radius: 4px;
    min-height: 28px;
}

QScrollBar::handle:vertical:hover {
    background: %(mint)s;
}

QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 0 2px 2px 2px;
}

QScrollBar::handle:horizontal {
    background: %(button_border)s;
    border-radius: 4px;
    min-width: 28px;
}

QScrollBar::handle:horizontal:hover {
    background: %(mint)s;
}

QScrollBar::add-line, QScrollBar::sub-line {
    height: 0;
    width: 0;
}

QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
}

QToolTip {
    background: %(header)s;
    color: %(text)s;
    border: 1px solid %(mint)s;
    padding: 4px 7px;
    border-radius: 4px;
}
"""


def build_stylesheet():
    """Build the QSS once the real UI font family is known."""
    theme = CURRENT_THEME
    return STYLE_SHEET_TEMPLATE % {
        "text": TEXT,
        "text_dim": TEXT_DIM,
        "muted": TEXT_MUTED,
        "win": WINDOW_BG,
        "header": HEADER_BG,
        "deep": WINDOW_BG_DEEP,
        "border": BORDER,
        "mint": MINT,
        "mint_light": MINT_LIGHT,
        "mint_dark": MINT_DARK,
        "accent_light": theme.accent_light,
        "on_accent": theme.on_accent,
        "button_bg": theme.button_bg,
        "button_border": theme.button_border,
        "accent_soft": theme.accent_soft,
        "accent_faint": theme.accent_faint,
    }


# ==========================================================
# ASCII BANK PICTURE  (used by the -welcome command)
# ==========================================================

_ART_W = 46
_ART_BW = 34
_ART_LEFT = (_ART_W - _ART_BW) // 2


def _art_blank():
    return [" "] * _ART_W


def _art_put(line, x, text):
    for i, ch in enumerate(text):
        if 0 <= x + i < _ART_W:
            line[x + i] = ch


def build_bank_art():
    """A bank facade drawn entirely from letters, numbers and symbols."""
    grid = []

    # floating currency glyphs
    line = _art_blank()
    _art_put(line, 6, "$  €  £  ¥  ¤  %  &  #  @  *  +  =  ~")
    grid.append(line)
    grid.append(_art_blank())

    # crest medallion
    for text in ("╭─╮", "│$│", "╰─╯"):
        line = _art_blank()
        _art_put(line, _ART_LEFT + (_ART_BW - 3) // 2, text)
        grid.append(line)
    grid.append(_art_blank())

    # roof
    for span in (6, 10, 14, 18, 22, 26, 30, 34):
        line = _art_blank()
        x0 = _ART_LEFT + (_ART_BW - span) // 2
        x1 = x0 + span - 1
        line[x0] = "/"
        line[x1] = "\\"
        for x in range(x0 + 1, x1):
            line[x] = "_"
        grid.append(line)

    # sign board
    line = _art_blank()
    line[_ART_LEFT] = "╔"
    line[_ART_LEFT + _ART_BW - 1] = "╗"
    for x in range(_ART_LEFT + 1, _ART_LEFT + _ART_BW - 1):
        line[x] = "═"
    grid.append(line)

    for text in (" B A N K ", "4.25% APR - $1,250 - #77421"):
        line = _art_blank()
        line[_ART_LEFT] = "║"
        line[_ART_LEFT + _ART_BW - 1] = "║"
        _art_put(line, _ART_LEFT + (_ART_BW - len(text)) // 2, text)
        grid.append(line)

    line = _art_blank()
    line[_ART_LEFT] = "╚"
    line[_ART_LEFT + _ART_BW - 1] = "╝"
    for x in range(_ART_LEFT + 1, _ART_LEFT + _ART_BW - 1):
        line[x] = "═"
    grid.append(line)

    grid.append(_art_blank())

    # colonnade - each pillar holds a currency symbol
    glyphs = ["$", "€", "£", "¥", "%"]
    pillar_x = [_ART_LEFT + 3 + i * 6 for i in range(5)]

    def column_row(text):
        line = _art_blank()
        for x in pillar_x:
            _art_put(line, x, text)
        return line

    grid.append(column_row("╔══╗"))
    grid.append(column_row("║ ║"))

    line = _art_blank()
    for x, g in zip(pillar_x, glyphs):
        _art_put(line, x, "║" + g + " ║")
    grid.append(line)

    grid.append(column_row("║ ║"))
    grid.append(column_row("╚══╝"))

    # base with column feet
    line = _art_blank()
    line[_ART_LEFT] = "└"
    line[_ART_LEFT + _ART_BW - 1] = "┘"
    for x in range(_ART_LEFT + 1, _ART_LEFT + _ART_BW - 1):
        line[x] = "─"
    for x in pillar_x:
        line[x + 2] = "┴"
    grid.append(line)

    # steps
    line = _art_blank()
    line[_ART_LEFT - 2] = "╔"
    line[_ART_LEFT + _ART_BW + 1] = "╗"
    for x in range(_ART_LEFT - 1, _ART_LEFT + _ART_BW + 1):
        line[x] = "═"
    grid.append(line)

    line = _art_blank()
    line[_ART_LEFT - 4] = "╚"
    line[_ART_LEFT + _ART_BW + 3] = "╝"
    for x in range(_ART_LEFT - 3, _ART_LEFT + _ART_BW + 3):
        line[x] = "═"
    grid.append(line)

    grid.append(_art_blank())

    # ground
    line = _art_blank()
    _art_put(line, 4, "▪ " * 16)
    grid.append(line)

    return "\n".join("".join(row).rstrip() for row in grid)


# ==========================================================
# BOOT SCREEN  (animated splash)
# ==========================================================

class BootScreen(QWidget):
    """Custom painted Mint style splash with a live animated emblem."""

    FRAME_MS = 16
    STEP_MS = 620

    STEPS = [
        ("INITIALIZING", "» power-on self check"),
        ("LOADING CORE", "» loading BANKSER' core services"),
        ("MOUNTING WORKSPACE", "» mounting user workspace"),
        ("CONFIGURING", "» initializing desktop interface"),
        ("CHECKING MODULES", "» checking system modules"),
        ("STARTING DESKTOP", "» launching window manager"),
        ("READY", "» system ready — welcome back"),
    ]

    def __init__(self, on_finished):
        super().__init__()

        self.on_finished = on_finished
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setStyleSheet("background: #0d1509;")

        self.step = 0
        self.progress = 0.0
        self.target_progress = 0.0
        self.spinner = 0.0
        self.phase = 0.0
        self.log_target = ""
        self.log_typed = 0.0
        self.finishing = False

        self.frame_timer = QTimer(self)
        self.frame_timer.timeout.connect(self._tick)
        self.frame_timer.start(self.FRAME_MS)

        self.step_timer = QTimer(self)
        self.step_timer.timeout.connect(self._advance)
        self.step_timer.start(self.STEP_MS)

        self.setCursor(Qt.BlankCursor)

    # ------------------------------------------------------
    # ANIMATION
    # ------------------------------------------------------

    def _tick(self):
        self.spinner = (self.spinner + 2.4) % 360
        self.phase += 0.016

        diff = self.target_progress - self.progress
        self.progress += diff * 0.12
        if abs(diff) < 0.001:
            self.progress = self.target_progress

        if self.log_typed < len(self.log_target):
            self.log_typed = min(len(self.log_target),
                                 self.log_typed + 0.9)
        else:
            self.log_typed = len(self.log_target)

        self.update()

    def _advance(self):
        if self.step >= len(self.STEPS):
            self.step_timer.stop()
            self.target_progress = 1.0
            QTimer.singleShot(700, self._fade_out)
            return

        status, message = self.STEPS[self.step]
        self.target_progress = (self.step + 1) / len(self.STEPS)
        self.log_target = message
        self.log_typed = 0.0
        self.step += 1

    def _fade_out(self):
        if self.finishing:
            return
        self.finishing = True
        self.frame_timer.stop()

        animation = QPropertyAnimation(self, b"windowOpacity", self)
        animation.setDuration(700)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setEasingCurve(QEasingCurve.InOutSine)
        animation.finished.connect(self._done)
        animation.start()

    def _done(self):
        self.close()
        self.on_finished()

    def skip(self):
        """Any key / click jumps straight to the desktop."""
        if self.finishing:
            return
        self.step_timer.stop()
        self.progress = 1.0
        self.target_progress = 1.0
        self.log_target = self.STEPS[-1][1]
        self.log_typed = len(self.log_target)
        self._fade_out()

    def keyPressEvent(self, event):
        self.skip()

    def mousePressEvent(self, event):
        self.skip()

    # ------------------------------------------------------
    # PAINTING
    # ------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()

        # --- background
        background = QLinearGradient(0, 0, 0, h)
        background.setColorAt(0.0, QColor(WALLPAPER_TOP))
        background.setColorAt(0.55, QColor(WALLPAPER_MID))
        background.setColorAt(1.0, QColor(WALLPAPER_BOTTOM))
        painter.fillRect(self.rect(), background)

        # --- drifting glow
        gx = w * (0.5 + 0.16 * math.sin(self.phase * 0.35))
        gy = h * (0.34 + 0.03 * math.cos(self.phase * 0.27))
        glow = QRadialGradient(gx, gy, w * 0.46)
        glow_color = QColor(MINT)
        glow_color.setAlpha(60)
        glow.setColorAt(0, glow_color)
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), glow)

        glow2 = QRadialGradient(w * 0.12, h * 0.85, w * 0.34)
        glow2_color = QColor(MINT_DARK)
        glow2_color.setAlpha(46)
        glow2.setColorAt(0, glow2_color)
        glow2.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), glow2)

        # --- emblem (leaf + comet spinner)
        emblem_y = h * 0.315
        emblem_r = 74

        painter.save()
        painter.translate(w / 2.0, emblem_y)
        painter.rotate(self.spinner)
        painter.setBrush(Qt.NoBrush)

        # faint track so the spinner reads as a ring
        track_color = QColor(MINT_LIGHT)
        track_color.setAlpha(38)
        track_pen = QPen(track_color, 2.0)
        painter.setPen(track_pen)
        painter.drawEllipse(QRectF(-emblem_r, -emblem_r,
                                   emblem_r * 2, emblem_r * 2))

        # comet tail
        for offset, alpha, width in ((0, 235, 3.4), (22, 175, 3.0),
                                     (42, 120, 2.6), (60, 75, 2.2)):
            comet_color = QColor(MINT_LIGHT)
            comet_color.setAlpha(alpha)
            ring_pen = QPen(comet_color, width)
            ring_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(ring_pen)
            painter.drawArc(QRectF(-emblem_r, -emblem_r,
                                    emblem_r * 2, emblem_r * 2),
                            offset * 16, 20 * 16)
        painter.restore()

        painter.save()
        painter.translate(w / 2.0, emblem_y)
        painter.rotate(4 * math.sin(self.phase * 0.9))
        self._leaf(painter, 0, 0, 38)
        painter.restore()

        # --- wordmark (gradient filled text path, with letter spacing)
        title_font = QFont(UI_FONT_NAME)
        title_font.setPointSize(30)
        title_font.setBold(True)
        spacing = 9
        metrics = QFontMetricsF(title_font)

        text_gradient = QLinearGradient(0, h * 0.42, 0, h * 0.53)
        text_gradient.setColorAt(0, QColor("#ffffff"))
        text_gradient.setColorAt(0.55, QColor(MINT_LIGHT))
        text_gradient.setColorAt(1, QColor(MINT))

        total_width = (sum(metrics.horizontalAdvance(ch) for ch in APP_NAME)
                       + spacing * (len(APP_NAME) - 1))
        x = (w - total_width) / 2.0
        baseline = h * 0.42 + metrics.ascent()

        painter.setPen(Qt.NoPen)
        painter.setBrush(Qt.NoBrush)
        for ch in APP_NAME:
            glyph = QPainterPath()
            glyph.addText(x, baseline, title_font, ch)
            painter.fillPath(glyph, text_gradient)
            x += metrics.horizontalAdvance(ch) + spacing

        # --- subtitle
        sub_font = QFont(UI_FONT_NAME)
        sub_font.setPointSize(10)
        sub_font.setLetterSpacing(QFont.AbsoluteSpacing, 4)
        painter.setFont(sub_font)
        painter.setPen(QColor(TEXT_DIM))
        painter.drawText(QRectF(0, h * 0.505, w, h * 0.05),
                         Qt.AlignCenter, "PERSONAL DESKTOP ENVIRONMENT")

        # --- progress bar
        bar_w = min(460, w * 0.55)
        bar_h = 8
        bar_x = (w - bar_w) / 2.0
        bar_y = h * 0.62

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 30))
        painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 4, 4)

        fill_w = bar_w * self.progress
        if fill_w > 0:
            bar_gradient = QLinearGradient(bar_x, 0, bar_x + bar_w, 0)
            bar_gradient.setColorAt(0, QColor(MINT_DARK))
            bar_gradient.setColorAt(1, QColor(MINT_LIGHT))
            painter.setBrush(bar_gradient)
            painter.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 4, 4)

            # glowing head of the bar
            head = QRadialGradient(bar_x + fill_w, bar_y + bar_h / 2, 16)
            head.setColorAt(0, QColor(MINT_LIGHT))
            head.setColorAt(1, QColor(0, 0, 0, 0))
            painter.setBrush(head)
            painter.drawEllipse(QRectF(bar_x + fill_w - 16, bar_y - 8,
                                       32, bar_h + 16))

        # --- percentage
        percent_font = mono_font(10)
        painter.setFont(percent_font)
        painter.setPen(QColor(TEXT_DIM))
        painter.drawText(QRectF(bar_x, bar_y - 24, bar_w, 18),
                         Qt.AlignRight, f"{int(self.progress * 100):3d}%")

        # --- status line
        status = self.STEPS[min(self.step, len(self.STEPS) - 1)][0]
        status_font = QFont(UI_FONT_NAME)
        status_font.setPointSize(10)
        status_font.setBold(True)
        status_font.setLetterSpacing(QFont.AbsoluteSpacing, 3)
        painter.setFont(status_font)
        painter.setPen(QColor(MINT_LIGHT))
        painter.drawText(QRectF(0, bar_y + 24, w, 22),
                         Qt.AlignCenter, status)

        # --- typed log line
        shown = self.log_target[:int(self.log_typed)]
        log_font = mono_font(9)
        painter.setFont(log_font)
        painter.setPen(QColor(TEXT_MUTED))
        cursor = "█" if int(self.phase * 2) % 2 == 0 else " "
        painter.drawText(QRectF(0, bar_y + 50, w, 22),
                         Qt.AlignCenter, shown + cursor)

    @staticmethod
    def _leaf(painter, cx, cy, size):
        path = QPainterPath()
        path.moveTo(cx, cy + size * 0.96)
        path.cubicTo(cx - size * 0.60, cy + size * 0.46,
                     cx - size * 0.56, cy - size * 0.62,
                     cx, cy - size * 0.96)
        path.cubicTo(cx + size * 0.56, cy - size * 0.62,
                     cx + size * 0.60, cy + size * 0.46,
                     cx, cy + size * 0.96)

        gradient = QLinearGradient(cx - size * 0.5, cy - size * 0.9,
                                   cx + size * 0.5, cy + size * 0.9)
        gradient.setColorAt(0, QColor(MINT_LIGHT))
        gradient.setColorAt(1, QColor(MINT_DARK))
        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawPath(path)

        painter.setBrush(Qt.NoBrush)
        vein = QPen(QColor(255, 255, 255, 120), 1.6)
        painter.setPen(vein)
        painter.drawLine(QPointF(cx, cy + size * 0.86),
                         QPointF(cx, cy - size * 0.86))
        painter.setPen(QPen(QColor(255, 255, 255, 75), 1.1))
        for i in range(3):
            offset = size * (0.50 - i * 0.30)
            painter.drawLine(QPointF(cx, cy - offset * 0.45),
                             QPointF(cx - size * 0.34, cy - offset))
            painter.drawLine(QPointF(cx, cy - offset * 0.45),
                             QPointF(cx + size * 0.34, cy - offset))

        # stem
        stem_color = QColor(MINT_DARK)
        stem_color.setAlpha(200)
        painter.setPen(QPen(stem_color, 2.0))
        painter.drawLine(QPointF(cx, cy + size * 0.92),
                         QPointF(cx, cy + size * 1.18))


# ==========================================================
# MINT WINDOW  (panelled window with a Cinnamon title bar)
# ==========================================================

class MintWindow(QFrame):
    def __init__(self, title, icon_kind, on_close=None, on_maximize=None,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("mintwindow")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QWidget()
        header.setObjectName("winheader")
        header.setFixedHeight(32)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 0, 6, 0)
        header_layout.setSpacing(7)

        icon = IconWidget(icon_kind, 16, MINT_LIGHT, theme_bound=True)
        header_layout.addWidget(icon)

        label = QLabel(title)
        label.setObjectName("wintitle")
        header_layout.addWidget(label)
        header_layout.addStretch(1)

        minimize = IconButton("minimize", "Minimize", 26, TEXT_DIM, TEXT)
        maximize = IconButton("maximize", "Maximize", 26, TEXT_DIM, TEXT)
        close = IconButton("close", "Close window", 26, TEXT_DIM, "#ff8a80")

        header_layout.addWidget(minimize)
        header_layout.addWidget(maximize)
        header_layout.addWidget(close)

        self.maximize_button = maximize

        minimize.clicked.connect(self.hide)
        maximize.clicked.connect(self._toggle_maximize)
        close.clicked.connect(self._handle_close)

        self._on_maximize = on_maximize

        self.body = QVBoxLayout()
        self.body.setContentsMargins(11, 10, 11, 11)
        self.body.setSpacing(8)

        outer.addWidget(header)
        outer.addLayout(self.body, 1)

        self._on_close = on_close

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setColor(QColor(0, 0, 0, 90))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

    def _toggle_maximize(self):
        if self._on_maximize:
            self._on_maximize(self)

    def set_zoomed(self, zoomed):
        """Swap the maximize icon / tooltip."""
        self.maximize_button.kind = "restore" if zoomed else "maximize"
        self.maximize_button.setToolTip(
            "Restore window" if zoomed else "Maximize")
        self.maximize_button.update()

    def _handle_close(self):
        if self._on_close:
            self._on_close(self)
        else:
            self.hide()


# ==========================================================
# SYSTEM GAUGE
# ==========================================================

class Gauge(QWidget):
    def __init__(self, title, value, parent=None):
        super().__init__(parent)
        self.title = title
        self.value = value
        self.setMinimumSize(96, 118)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        label_h = 20
        size = min(w, h - label_h) - 16
        if size <= 10:
            return

        rect = QRectF((w - size) / 2.0, 6, size, size)

        track = QPen(QColor(CURRENT_THEME.gauge_track), 9)
        track.setCapStyle(Qt.RoundCap)
        painter.setPen(track)
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(rect, 0, 360 * 16)

        value_pen = QPen(QColor(MINT), 9)
        value_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(value_pen)
        painter.drawArc(rect, 90 * 16, -int(self.value * 3.6) * 16)

        painter.setFont(ui_font(13, bold=True))
        painter.setPen(QColor(TEXT))
        painter.drawText(rect, Qt.AlignCenter, f"{self.value}%")

        painter.setFont(ui_font(9, bold=True))
        painter.setPen(QColor(TEXT_DIM))
        painter.drawText(QRectF(0, h - label_h, w, label_h),
                         Qt.AlignCenter, self.title)


# ==========================================================
# PASTESHELL  (ASCII system tool - ported into the desktop)
# ==========================================================

PASTESHELL_FRAMES = (
    r'''
       .-""""-.
      /  .--.  \
     |  /    \  |
     | | O  O | |
     | |  /\  | |
     |  \_==_/  |
      \  ____  /
       /| || |\
      /_|_||_|_\
        /  \
       /____\
''',

    r'''
          .---.
        .'     `.
       /  O   O  \
      |     ^     |
      |   .---.   |
       \  `---'  /
        `._____.'
          | | |
         _|_|_|_
        /_______
''',

    r'''
       .-""""-.
      /  .--.  \
     |  /    \  |
     | | 0  0 | |
     | |  /\  | |
     |  \_==_/  |
      \  ____  /
       /| || |\
      /_|_||_|_\
        /  \
       /____\
''',

    r'''
          .---.
        .'     `.
       /  o   o  \
      |     ^     |
      |   .---.   |
       \  `---'  /
        `._____.'
          | | |
         _|_|_|_
        /_______
'''
)

PASTESHELL_COLORS = {
    1: "#00ff66",
    2: "#00ccff",
    3: "#ff0000",
    4: "#bb00ff",
    5: "#ffff00",
    6: "#ffffff",
    7: "#ff8800",
    8: "#ff69b4",
}


class PasteShellWindow(QWidget):
    """PASTESHELL v2.0 - the ASCII tool, now a native app inside the OS."""

    def __init__(self, parent=None, on_closed=None):
        super().__init__(parent, Qt.Window)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setWindowTitle("PASTESHELL v2.0")
        self.setFixedSize(900, 730)
        self._on_closed = on_closed

        self.skull_color = PASTESHELL_COLORS[1]
        self.animation_index = 0
        self.scan_queue = queue.Queue()
        self.scan_running = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.frame = MintWindow("PASTESHELL v2.0", "skull",
                                on_close=lambda w: self.close())
        outer.addWidget(self.frame)

        # --- title block
        self.title = QLabel("PASTESHELL")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setFont(ui_font(34, bold=True))
        self.title.setStyleSheet(f"color: {self.skull_color};")
        self.frame.body.addWidget(self.title)

        subtitle = QLabel(">>> SYSTEM INITIALIZED <<<")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setFont(mono_font(11))
        subtitle.setStyleSheet("color: #777777;")
        self.frame.body.addWidget(subtitle)

        # --- animated skull
        self.skull = QLabel()
        self.skull.setAlignment(Qt.AlignCenter)
        self.skull.setFont(mono_font(13, bold=True))
        self.skull.setStyleSheet(f"color: {self.skull_color};")
        self.frame.body.addWidget(self.skull)

        # --- console
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(mono_font(10))
        self.console.setLineWrapMode(QTextEdit.NoWrap)
        self.console.setStyleSheet(
            f"background: #020202; color: {self.skull_color}; "
            "border: 1px solid #1c3a26; border-radius: 5px;")
        self.frame.body.addWidget(self.console, 1)

        self.entry = QLineEdit()
        self.entry.setFont(mono_font(11))
        self.entry.setPlaceholderText("root@pasteshell:~$")
        self.entry.setStyleSheet(
            f"background: #111111; color: {self.skull_color}; "
            "border: 1px solid #1c3a26; border-radius: 5px;")
        self.entry.returnPressed.connect(self.execute_command)
        self.frame.body.addWidget(self.entry)

        # --- action buttons
        buttons = QHBoxLayout()

        scan_button = QPushButton("[ SCAN NETWORK ]")
        scan_button.clicked.connect(self.start_network_scan)

        wifi_button = QPushButton("[ SCAN WIFI ]")
        wifi_button.clicked.connect(self.scan_weak_wifi)

        terminal_button = QPushButton("[ OPEN TERMINAL ]")
        terminal_button.clicked.connect(self.focus_console)

        for button in (scan_button, wifi_button, terminal_button):
            button.setFont(mono_font(10, bold=True))
            buttons.addWidget(button)

        self.frame.body.addLayout(buttons)

        footer = QLabel("PASTESHELL v2.0 | ASCII SYSTEM | "
                        "running inside BANKSER' Desktop")
        footer.setAlignment(Qt.AlignCenter)
        footer.setFont(mono_font(9))
        footer.setStyleSheet("color: #4a4a4a;")
        self.frame.body.addWidget(footer)

        # --- timers
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.animate)
        self.animation_timer.start(250)

        self.queue_timer = QTimer(self)
        self.queue_timer.timeout.connect(self.process_scan_queue)
        self.queue_timer.start(100)

        self.animate()
        self.console_print("PASTESHELL TERMINAL READY.")
        self.console_print("Type help to see available commands.")
        self.console_print("")

    # ------------------------------------------------------
    # ANIMATION
    # ------------------------------------------------------

    def animate(self):
        self.skull.setText(PASTESHELL_FRAMES[self.animation_index].strip("\n"))
        self.animation_index = (self.animation_index + 1) % len(PASTESHELL_FRAMES)

    # ------------------------------------------------------
    # CONSOLE
    # ------------------------------------------------------

    def console_print(self, message):
        self.console.append(str(message))
        self.console.ensureCursorVisible()

    def focus_console(self):
        self.entry.setFocus()

    # ------------------------------------------------------
    # COMMANDS
    # ------------------------------------------------------

    def execute_command(self):

        command = self.entry.text().strip()
        self.entry.clear()

        if not command:
            return

        self.console_print("root@pasteshell:~$ " + command)

        lowered = command.lower()

        if lowered.startswith("color "):
            try:
                number = int(command.split()[1])
                if number in PASTESHELL_COLORS:
                    self.skull_color = PASTESHELL_COLORS[number]
                    self.skull.setStyleSheet(f"color: {self.skull_color};")
                    self.title.setStyleSheet(f"color: {self.skull_color};")
                    self.console.setStyleSheet(
                        f"background: #020202; color: {self.skull_color}; "
                        "border: 1px solid #1c3a26; border-radius: 5px;")
                    self.entry.setStyleSheet(
                        f"background: #111111; color: {self.skull_color}; "
                        "border: 1px solid #1c3a26; border-radius: 5px;")
                    self.console_print("Color changed successfully!")
                else:
                    self.console_print("Invalid color. Use 1-8.")
            except (ValueError, IndexError):
                self.console_print("Usage: color <number>")

        elif lowered == "ipsea":
            self.start_network_scan()

        elif lowered == "weakwifi":
            self.scan_weak_wifi()

        elif lowered == "help":
            self.console_print("AVAILABLE COMMANDS:")
            self.console_print("color 1-8  - Change skull color")
            self.console_print("ipsea      - Scan local network")
            self.console_print("weakwifi   - Scans weak wifi spots")
            self.console_print("help       - Show commands")
            self.console_print("clear      - Clear terminal")
            self.console_print("exit       - Close terminal")

        elif lowered == "clear":
            self.console.clear()

        elif lowered == "exit":
            self.close()

        else:
            self.console_print("Unknown command. Type help.")

        self.focus_console()

    # ------------------------------------------------------
    # NETWORK SCANNER  (IPSEA)
    # ------------------------------------------------------

    def start_network_scan(self):
        if self.scan_running:
            self.console_print("A scan is already running!")
            return

        self.scan_running = True
        threading.Thread(target=self.scan_network_worker, daemon=True).start()

    def scan_network_worker(self):
        try:
            self.scan_queue.put("Starting IPSEA scan...")

            output = self.run_command(["ipconfig"])
            if output is None:
                self.scan_queue.put("IPSEA ERROR: 'ipconfig' is not available "
                                    "on this system.")
                return

            blocks = re.split(r"\r?\n\r?\n", output)
            network = None

            for block in blocks:
                ip_match = re.search(
                    r"IPv4 Address[^\n]*:\s*([\d.]+)", block)
                mask_match = re.search(
                    r"Subnet Mask[^\n]*:\s*([\d.]+)", block)

                if ip_match and mask_match:
                    local_ip = ip_match.group(1)
                    subnet_mask = mask_match.group(1)

                    try:
                        candidate = ipaddress.ip_network(
                            f"{local_ip}/{subnet_mask}", strict=False)
                        if candidate.num_addresses <= 256:
                            network = candidate
                            break
                    except ValueError:
                        continue

            if network is None:
                self.scan_queue.put(
                    "Could not find a suitable local IPv4 network.")
                return

            self.scan_queue.put(f"Network detected: {network}")
            self.scan_queue.put("Checking devices...")

            def ping_device(ip):
                try:
                    subprocess.run(["ping", "-n", "1", "-w", "300", str(ip)],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL,
                                   timeout=2)
                except (subprocess.SubprocessError, OSError):
                    pass

            with concurrent.futures.ThreadPoolExecutor(
                    max_workers=32) as executor:
                list(executor.map(ping_device, network.hosts()))

            arp_output = self.run_command(["arp", "-a"])
            if arp_output is None:
                self.scan_queue.put("IPSEA ERROR: 'arp' is not available "
                                    "on this system.")
                return

            pattern = (r"(\d{1,3}(?:\.\d{1,3}){3})"
                       r"\s+([0-9a-fA-F-]{17})"
                       r"\s+(dynamic|static)")

            devices = re.findall(pattern, arp_output, re.IGNORECASE)
            found = set()

            self.scan_queue.put("")
            self.scan_queue.put("=" * 65)
            self.scan_queue.put("IP ADDRESS       MAC ADDRESS          ENTRY")
            self.scan_queue.put("=" * 65)

            for ip, mac, entry in devices:
                if ip in found:
                    continue
                if ipaddress.ip_address(ip) not in network:
                    continue

                found.add(ip)

                try:
                    hostname = socket.gethostbyaddr(ip)[0]
                except (socket.herror, socket.gaierror, OSError):
                    hostname = "Unknown"

                self.scan_queue.put(f"{ip:<16} {mac:<20} {entry.upper()}")
                self.scan_queue.put(f"Hostname: {hostname}")
                self.scan_queue.put("-" * 65)

            self.scan_queue.put("")
            self.scan_queue.put(
                f"IPSEA COMPLETE: {len(found)} ARP entries found.")

        except Exception as error:
            self.scan_queue.put(f"IPSEA ERROR: {error}")

        finally:
            self.scan_queue.put("__SCAN_FINISHED__")

    @staticmethod
    def run_command(command):
        """Run a system command and return its text output (or None)."""
        try:
            result = subprocess.run(command, capture_output=True,
                                    timeout=20)
            if result.returncode != 0 and not result.stdout:
                return None
            return result.stdout.decode("utf-8", errors="ignore")
        except (OSError, subprocess.SubprocessError):
            return None

    # ------------------------------------------------------
    # WEAK WIFI SCANNER
    # ------------------------------------------------------

    def scan_weak_wifi(self):
        self.console_print("\n[ WEAKWIFI ] Scanning nearby Wi-Fi...")

        output = self.run_command(
            ["netsh", "wlan", "show", "networks", "mode=bssid"])

        if output is None:
            self.console_print("Wi-Fi scan failed. Check your Wi-Fi adapter.")
            return

        networks = {}
        current_ssid = None

        for line in output.splitlines():
            ssid_match = re.match(r"\s*SSID \d+ :\s*(.*)", line)
            signal_match = re.match(r"\s*Signal\s*:\s*(\d+)%", line)

            if ssid_match:
                current_ssid = ssid_match.group(1).strip()
                if not current_ssid:
                    current_ssid = "[Hidden network]"
                networks.setdefault(current_ssid, [])

            elif signal_match and current_ssid:
                networks[current_ssid].append(int(signal_match.group(1)))

        results = []
        for name, signals in networks.items():
            if signals:
                results.append((name, sum(signals) / len(signals)))

        results.sort(key=lambda x: x[1])

        self.console_print("=" * 45)
        self.console_print(" NETWORK NAME          SIGNAL")
        self.console_print("=" * 45)

        for name, signal in results:
            self.console_print(f"{name[:22]:<24} {signal:.0f}%")

            if signal < 30:
                self.console_print("  STATUS: VERY WEAK")
            elif signal < 60:
                self.console_print("  STATUS: WEAK")
            elif signal < 80:
                self.console_print("  STATUS: GOOD")
            else:
                self.console_print("  STATUS: STRONG")

            self.console_print("-" * 45)

        self.console_print(f"\nFound {len(results)} Wi-Fi networks.")

    # ------------------------------------------------------
    # QUEUE DRAIN
    # ------------------------------------------------------

    def process_scan_queue(self):
        try:
            while True:
                message = self.scan_queue.get_nowait()

                if message == "__SCAN_FINISHED__":
                    self.scan_running = False
                else:
                    self.console_print(message)
        except queue.Empty:
            pass

    def closeEvent(self, event):
        self.animation_timer.stop()
        self.queue_timer.stop()
        if self._on_closed:
            self._on_closed()
        super().closeEvent(event)


# ==========================================================
# BANKSER AI  (local-first assistant)
# ==========================================================

AI_BRIDGE = (Path.home() / ".minimax" / ".builtin-skills" / "llm-call"
             / "scripts" / "llm_call.py")

AI_SITES = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "wikipedia": "https://www.wikipedia.org",
    "wiki": "https://www.wikipedia.org",
    "github": "https://github.com",
    "gitlab": "https://gitlab.com",
    "gmail": "https://mail.google.com",
    "outlook": "https://outlook.live.com",
    "chatgpt": "https://chat.openai.com",
    "claude": "https://claude.ai",
    "x": "https://x.com",
    "twitter": "https://x.com",
    "reddit": "https://www.reddit.com",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "amazon": "https://www.amazon.com",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
    "twitch": "https://www.twitch.tv",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "linkedin": "https://www.linkedin.com",
    "tiktok": "https://www.tiktok.com",
    "pinterest": "https://www.pinterest.com",
    "maps": "https://maps.google.com",
    "drive": "https://drive.google.com",
    "calendar": "https://calendar.google.com",
    "keep": "https://keep.google.com",
    "weather": "https://wttr.in",
    "translate": "https://translate.google.com",
    "wikipedia en": "https://en.wikipedia.org",
    "news": "https://news.google.com",
    "hacker news": "https://news.ycombinator.com",
    "medium": "https://medium.com",
    "devto": "https://dev.to",
    "npm": "https://www.npmjs.com",
    "pypi": "https://pypi.org",
    "bank": "https://www.bankofamerica.com",
}

AI_KNOWLEDGE = {
    "bankser": "BANKSER' Desktop is a Linux Mint inspired PySide6 desktop "
               "environment. Type 'help' in the terminal for every command.",
    "bankser desktop": "BANKSER' Desktop v2.0 - a Mint styled PySide6 shell "
                       "with panels, a demo terminal, PASTESHELL, ART and AI.",
    "theme": "Type 'color 1-10' in the terminal to re-skin the whole desktop. "
             "'color' alone lists all ten schemes.",
    "commands": "Terminal commands: help, color <1-10>, -welcome, pasteshell, "
                "ipsea, weakwifi, date, system, files, clear, open-home, "
                "website, plus 'ai' and 'art' to launch the new apps.",
    "welcome": "The '-welcome' command zooms the terminal and draws an ASCII "
               "bank made of letters, numbers and symbols.",
    "pasteshell": "PASTESHELL v2.0 is built into the desktop. It has an "
                  "animated ASCII skull and commands: color 1-8, ipsea, "
                  "weakwifi, help, clear, exit.",
    "ipsea": "IPSEA scans your local IPv4 network, pings every host and "
             "lists the ARP table with IP, MAC and hostname.",
    "weakwifi": "weakwifi runs 'netsh wlan show networks' and lists nearby "
                "Wi-Fi networks with signal strength.",
    "art": "The ART studio is a full drawing program: pencil, brush, eraser, "
           "line, rectangle, ellipse, flood fill, eyedropper, undo/redo and "
           "PNG save/open. Launch it with 'art'.",
    "ai": "bankserAI answers questions, does maths and opens websites for "
          "you. Try 'open youtube' or 'search for linux mint'.",
    "python": "Python is a readable, batteries-included programming "
              "language. This desktop is written in it with PySide6.",
    "pyside6": "PySide6 is Qt's official Python binding - widgets, painting, "
               "timers and signals. It is what draws this entire desktop.",
    "qt": "Qt is a cross-platform C++ framework for desktop software. "
          "PySide6 exposes it to Python.",
    "linux": "Linux is a free, open-source Unix-like operating system that "
             "powers most servers, Android and this desktop's visual style.",
    "linux mint": "Linux Mint is a friendly Ubuntu-based distribution whose "
                  "signature green (#87cf3e) this desktop borrows.",
    "python vs java": "Python is dynamic and concise, Java is static and "
                      "strictly typed. Python iterates faster; Java scales "
                      "in big teams.",
    "api": "An API is a contract: a program asks a service to do something "
           "and gets structured data back.",
    "json": "JSON is a lightweight text format for structured data - objects, "
            "arrays, strings, numbers, booleans and null.",
    "html": "HTML is the markup language that structures web pages.",
    "css": "CSS styles web pages: colour, layout, spacing and animation.",
    "javascript": "JavaScript makes web pages interactive and runs on the "
                  "server with Node.js too.",
    "git": "Git is version control: it tracks every change so you can branch, "
           "merge and roll back.",
    "github": "GitHub hosts Git repositories with pull requests and issues.",
    "docker": "Docker packages an app with its dependencies into a container "
              "so it runs the same everywhere.",
    "terminal": "A terminal (shell) takes typed commands and runs them - the "
                "one you are talking to right now.",
    "ip address": "An IP address is a network locator, like 192.168.1.10. "
                  "IPv4 is 32 bits, IPv6 is 128 bits.",
    "ip": "Your IP identifies your host on a network. Run 'ipsea' to discover "
          "the devices around yours.",
    "mac address": "A MAC address is the permanent hardware identifier of a "
                   "network card, used on the local segment.",
    "dns": "DNS translates names like google.com into IP addresses. Flushing "
           "it with 'ipconfig /flushdns' fixes stale lookups.",
    "https": "HTTPS is HTTP wrapped in TLS encryption, so traffic cannot be "
             "read or modified in transit.",
    "port": "A port is a numbered socket on a host - 80 HTTP, 443 HTTPS, "
            "22 SSH.",
    "firewall": "A firewall filters network traffic by rules, blocking "
                "unwanted inbound connections.",
    "vpn": "A VPN tunnels your traffic through a remote server, encrypting "
           "it and masking your IP.",
    "wifi": "Wi-Fi is wireless networking. Signal strength is measured in "
            "percent; below 30% is usually unusable.",
    "ram": "RAM is fast volatile memory holding what programs are using right "
           "now. Closing apps frees it.",
    "cpu": "The CPU executes instructions. Cores are parallel workers and "
           "threads share one core.",
    "ssd": "An SSD stores data on flash with no moving parts: far faster and "
           "more shock resistant than an HDD.",
    "gpu": "The GPU renders graphics and parallel work. It accelerates "
           "video, games and AI inference.",
    "hash": "A hash maps any input to a fixed-size fingerprint. MD5 and SHA "
            "are used for integrity, not security.",
    "regex": "A regular expression is a pattern language for finding and "
             "rewriting text.",
    "backup": "A backup is a second copy of your data. The 3-2-1 rule: three "
              "copies, two media, one off-site.",
    "encryption": "Encryption scrambles data with a key so only holders can "
                  "read it.",
    "malware": "Malware is malicious software - viruses, ransomware, "
               "keyloggers - that damages or steals data.",
    "virus": "A virus is malicious code that attaches itself to files and "
             "spreads when they are opened.",
    "how do i stay safe": "Keep the OS updated, use a password manager, "
                          "enable multi-factor authentication, back up often "
                          "and never run unknown scripts.",
    "how to speed up my pc": "Close startup apps, clear temp files, upgrade "
                             "to an SSD and check for RAM or CPU bottlenecks "
                             "in the system monitor.",
    "how to learn programming": "Pick one language, build small projects "
                                "daily and read other people's code. Python "
                                "is a friendly start.",
    "who are you": "I am bankserAI, the assistant built into BANKSER' "
                   "Desktop. I run a Qwen3.5-4B model on this machine, so I "
                   "can answer almost anything, and I do maths, open "
                   "websites and open the desktop apps for you.",
    "help": "Ask me anything, or say 'open <site>' to launch a website, "
            "'search for <topic>' to search the web, 'open the matrix rain' "
            "to open a desktop app, or 'what is <thing>' for an explanation.",
}


def _safe_math(expression):
    """Evaluate arithmetic without using eval()."""
    import ast

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp):
            left, right = evaluate(node.left), evaluate(node.right)
            operations = {
                ast.Add: lambda a, b: a + b,
                ast.Sub: lambda a, b: a - b,
                ast.Mult: lambda a, b: a * b,
                ast.Div: lambda a, b: a / b,
                ast.FloorDiv: lambda a, b: a // b,
                ast.Mod: lambda a, b: a % b,
                ast.Pow: lambda a, b: a ** b,
            }
            operation = operations.get(type(node.op))
            if operation is None:
                raise ValueError("unsupported operator")
            return operation(left, right)
        if isinstance(node, ast.UnaryOp):
            value = evaluate(node.operand)
            if isinstance(node.op, ast.USub):
                return -value
            if isinstance(node.op, ast.UAdd):
                return value
            raise ValueError("unsupported unary operator")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            functions = {
                "sqrt": math.sqrt, "abs": abs, "round": round,
                "log": math.log, "log10": math.log10, "sin": math.sin,
                "cos": math.cos, "tan": math.tan, "floor": math.floor,
                "ceil": math.ceil, "pow": math.pow,
            }
            function = functions.get(node.func.id)
            if function is None:
                raise ValueError("unknown function")
            return function(*[evaluate(argument) for argument in node.args])
        raise ValueError("unsupported expression")

    return evaluate(ast.parse(expression, mode="eval"))


# ==========================================================
# LOCAL MODEL  (llama.cpp serving Qwen3.5-4B)
# ==========================================================

class LocalModel:
    """Runs Qwen3.5-4B on this machine through llama.cpp.

    The server is started the first time a question actually needs it and is
    then kept alive for the rest of the session, so only the very first
    answer waits for the weights to load.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.process = None
        self.pid = None
        self.port = AI_SERVER_PORT
        self.state = "idle"        # idle / starting / ready / failed
        self.error = ""
        self.model_path = self._find_model()
        self.server_path = self._find_server()
        self.backend = self._detect_backend()

    # ------------------------------------------------------
    # DISCOVERY
    # ------------------------------------------------------

    @staticmethod
    def _find_model():
        if not AI_MODEL_DIR.exists():
            return None

        candidates = []
        if AI_MODEL_FILE.exists():
            candidates.append(AI_MODEL_FILE)
        candidates += sorted(AI_MODEL_DIR.glob("*.gguf"))

        for path in candidates:
            try:
                if path.stat().st_size > 100_000_000:
                    return path
            except OSError:
                continue
        return None

    @staticmethod
    def _find_server():
        if not AI_RUNTIME_DIR.exists():
            return None

        servers = list(AI_RUNTIME_DIR.rglob("llama-server.exe"))
        if not servers:
            return None

        def rank(path):
            text = str(path).lower()
            for index, key in enumerate(("vulkan", "cuda", "cpu")):
                if key in text:
                    return index
            return 9

        servers.sort(key=rank)
        return servers[0]

    def _detect_backend(self):
        text = str(self.server_path or "").lower()
        if "vulkan" in text:
            return "Vulkan GPU"
        if "cuda" in text:
            return "CUDA GPU"
        if "cpu" in text:
            return "CPU"
        return "unknown"

    def available(self):
        """True when both the runtime and the weights are on disk."""
        return bool(self.server_path and self.model_path)

    def describe(self):
        if not self.available():
            return "not installed"
        return f"{AI_MODEL_LABEL} - {self.backend}"

    # ------------------------------------------------------
    # SERVER
    # ------------------------------------------------------

    def _command(self, port=None):
        return [
            str(self.server_path),
            "-m", str(self.model_path),
            "--host", AI_SERVER_HOST,
            "--port", str(port or self.port),
            "-c", "4096",
            "-ngl", "99",
            "--no-warmup",
            "--alias", "qwen",
        ]

    def _base(self):
        return f"http://{AI_SERVER_HOST}:{self.port}"

    def _alive(self):
        """True when the local server is up and serving."""
        try:
            with urllib.request.urlopen(f"{self._base()}/health",
                                        timeout=4) as response:
                return response.status == 200
        except Exception:
            return False

    def _serving_our_model(self):
        """True when a server on our port is running our model."""
        try:
            with urllib.request.urlopen(f"{self._base()}/v1/models",
                                        timeout=5) as response:
                body = json.loads(response.read().decode("utf-8"))
        except Exception:
            return False

        for entry in body.get("data") or []:
            if entry.get("id") in ("qwen", "local"):
                return True
        return False

    @staticmethod
    def _pid_on_port(port):
        """Find the process listening on a port (Windows only)."""
        if os.name != "nt":
            return None

        try:
            result = subprocess.run(["netstat", "-ano"], capture_output=True,
                                    text=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            return None

        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                try:
                    return int(parts[-1])
                except (ValueError, IndexError):
                    return None
        return None

    @staticmethod
    def _write_pid(pid):
        try:
            AI_PID_FILE.write_text(str(pid), encoding="utf-8")
        except OSError:
            pass

    @staticmethod
    def _read_pid():
        try:
            return int(AI_PID_FILE.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None

    def _start(self):
        """Start llama-server, moving to another port if ours is taken."""
        self.state = "starting"
        self.error = ""

        for attempt in range(4):
            self.port = AI_SERVER_PORT + attempt

            try:
                process = subprocess.Popen(
                    self._command(),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=(subprocess.CREATE_NO_WINDOW
                                   if os.name == "nt" else 0),
                )
            except OSError as error:
                self.state = "failed"
                self.error = str(error)
                return False

            time.sleep(2.5)

            if process.poll() is None:
                self.process = process
                self.pid = process.pid
                self._write_pid(process.pid)
                return True

            # it died straight away, so the port is probably taken
            try:
                process.kill()
            except Exception:
                pass

        self.state = "failed"
        self.error = "could not start llama-server (every port is busy)"
        return False

    def ensure_ready(self, timeout=600):
        """Start the server if needed and wait until it can answer."""
        with self.lock:
            if self.state == "ready" and self._alive():
                return True

            # adopt a server that is already running this model
            if self.process is None and self._serving_our_model():
                self.state = "ready"
                self.pid = self._read_pid() or self._pid_on_port(self.port)
                return True

            if not self.available():
                self.state = "failed"
                self.error = "llama.cpp runtime or model file missing"
                return False

            if self.process is None or self.process.poll() is not None:
                if not self._start():
                    return False

            deadline = time.time() + timeout
            while time.time() < deadline:
                if self._alive():
                    self.state = "ready"
                    return True

                if self.process.poll() is not None:
                    self.state = "failed"
                    self.error = "llama-server exited while loading"
                    return False

                time.sleep(1)

            self.state = "failed"
            self.error = "timed out waiting for the model to load"
            return False

    def chat(self, messages, timeout=240):
        """Ask the local model and return the assistant text."""
        if not self.ensure_ready():
            raise RuntimeError(self.error or "the local model is unavailable")

        payload = json.dumps({
            "model": "qwen",
            "messages": messages,
            "max_tokens": 800,
            "temperature": 0.6,
            "stream": False,
            # Qwen3.5 thinks by default and would spend the whole token
            # budget on reasoning, so turn it off for chat answers
            "chat_template_kwargs": {"enable_thinking": False},
        }).encode("utf-8")

        request = urllib.request.Request(
            f"{self._base()}/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))

        message = body["choices"][0]["message"]
        text = (message.get("content") or "").strip()

        if not text:
            # the model still reasoned its way through the budget
            text = (message.get("reasoning_content") or "").strip()

        if not text:
            raise RuntimeError("the local model returned an empty answer")

        return text

    def stop(self):
        """Shut the server down and free its memory."""
        process = self.process
        pid = self.pid
        self.process = None
        self.pid = None
        self.state = "idle"

        try:
            AI_PID_FILE.unlink()
        except OSError:
            pass

        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()
            return

        # an adopted server has to be killed by its process id
        if pid and os.name == "nt":
            try:
                subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                               capture_output=True, timeout=20)
            except (OSError, subprocess.SubprocessError):
                pass
        elif pid:
            try:
                os.kill(pid, 15)
            except OSError:
                pass


_LOCAL_MODEL = None
_LOCAL_MODEL_LOCK = threading.Lock()


def get_local_model():
    """One shared model server for the whole desktop session."""
    global _LOCAL_MODEL
    with _LOCAL_MODEL_LOCK:
        if _LOCAL_MODEL is None:
            _LOCAL_MODEL = LocalModel()
        return _LOCAL_MODEL


class AIEngine:
    """Deterministic assistant with an optional LLM upgrade."""

    def __init__(self):
        self.history = []
        self.turns = []
        self.backend_ready = self.check_backend()
        self.local_model = get_local_model()

    # ------------------------------------------------------
    # OPTIONAL BACKEND
    # ------------------------------------------------------

    @staticmethod
    def check_backend():
        """True when a real (non placeholder) model key is configured."""
        try:
            if not AI_BRIDGE.exists():
                return False

            config = Path.home() / ".minimax" / "config.yaml"
            if not config.exists():
                return False

            text = config.read_text(encoding="utf-8", errors="ignore")
            match = re.search(r"apiKey:\s*(\S+)", text)

            if not match:
                return False

            key = match.group(1).strip().strip("\"'")
            return len(key) > 8 and "xxx" not in key.lower()

        except OSError:
            return False

    def ask_model(self, question):
        """Send a question to the configured model (blocking)."""
        system = (
            "You are bankserAI, a helpful assistant built into the BANKSER' "
            "desktop. Answer clearly and briefly in 3-6 sentences. If the "
            "user wants a website opened, finish your answer with a line "
            "containing only OPEN:<full-url>."
        )

        result = subprocess.run(
            [sys.executable, str(AI_BRIDGE),
             "--model", "minimax/MiniMax-M3.1-Flash",
             "--system", system,
             "--max-tokens", "600",
             "--timeout", "90",
             "--prompt", question],
            capture_output=True, timeout=120
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode("utf-8", "ignore").strip())

        return result.stdout.decode("utf-8", "ignore").strip()

    # ------------------------------------------------------
    # LOCAL INTENTS
    # ------------------------------------------------------

    @staticmethod
    def _clean_site(text):
        return text.strip().strip(".!?,: ").strip()

    def find_url(self, text):
        """Return a URL if the message asks for a site or contains one."""
        lowered = text.lower()

        match = re.search(r"https?://[^\s<>\"']+", text)
        if match:
            return match.group(0).rstrip(".,)")

        for prefix in ("open ", "go to ", "launch ", "visit ", "browse ",
                       "start ", "load "):
            if lowered.startswith(prefix):
                target = self._clean_site(text[len(prefix):])
                target = re.sub(r"^(the\s+)", "", target).strip()

                if target in AI_SITES:
                    return AI_SITES[target]

                for name, url in AI_SITES.items():
                    if target.startswith(name) and " " not in name:
                        return url

                if re.match(r"^[\w-]+(\.[\w-]+)+(/.*)?$", target):
                    return "https://" + target

                return None

        for name, url in AI_SITES.items():
            if re.search(rf"\b{re.escape(name)}\b", lowered):
                return url

        return None

    def find_search(self, text):
        """Return a search URL when the message asks to look something up."""
        lowered = text.lower()

        patterns = [
            (r"^search(?: for)?\s+(.+)$", "https://www.google.com/search?q="),
            (r"^google\s+(.+)$", "https://www.google.com/search?q="),
            (r"^youtube\s+(.+)$", "https://www.youtube.com/results?search_query="),
            (r"^yt\s+(.+)$", "https://www.youtube.com/results?search_query="),
            (r"^wiki(?:pedia)?\s+(.+)$",
             "https://en.wikipedia.org/w/index.php?search="),
            (r"^look up\s+(.+)$", "https://www.google.com/search?q="),
            (r"^find\s+(.+)$", "https://www.google.com/search?q="),
            (r"^download\s+(.+)$", "https://www.google.com/search?q="),
        ]

        for pattern, base in patterns:
            match = re.match(pattern, lowered)
            if match:
                query = match.group(1).strip()
                if query in AI_SITES:
                    return AI_SITES[query]
                return base + query.replace(" ", "+")

        if "search" in lowered and "for" in lowered:
            query = lowered.split("for", 1)[1].strip()
            if query:
                return "https://www.google.com/search?q=" + query.replace(" ", "+")

        return None

    def knowledge(self, text):
        """Look the question up in the built-in knowledge base."""
        lowered = text.lower()

        best, best_length = None, 0
        for key, answer in AI_KNOWLEDGE.items():
            if key in lowered and len(key) > best_length:
                best, best_length = answer, len(key)

        return best

    def math_answer(self, text):
        """Answer arithmetic questions."""
        lowered = text.lower()

        if not re.search(r"\d", lowered):
            return None

        if not re.search(r"\b(what|calculate|compute|how much|equals|result|"
                         r"solve|math)\b", lowered):
            return None

        expression = re.sub(r"\b(what|is|calculate|compute|how much|does|"
                            r"equal|equals|result|solve|of|the|to)\b",
                            " ", lowered)
        expression = expression.replace("x", "*").replace("^", "**")
        expression = expression.replace(",", "").strip()

        expression = re.sub(r"\s+", " ", expression).strip()
        expression = expression.rstrip("?!.,;:").strip()

        if not expression:
            return None

        # anything left that is not arithmetic means the model should answer
        if re.search(r"[A-Za-z]", expression):
            return None

        # a real calculation needs an operator, otherwise the model answers
        if not re.search(r"[+\-*/]", expression):
            return None

        if not re.search(r"[\d+\-*/().]", expression):
            return None

        try:
            value = _safe_math(expression)
        except (ValueError, SyntaxError, ZeroDivisionError, TypeError,
                OverflowError):
            return None

        if isinstance(value, float) and value.is_integer():
            value = int(value)

        return f"{expression} = {value}"

    def local_facts(self, text):
        """Exact answers the assistant can give without a model."""
        lowered = text.lower().strip()

        if not lowered:
            return ("Ask me anything, or say 'open <site>' to open a website.")

        if lowered in ("hi", "hello", "hey", "yo", "sup", "hello!",
                       "hi!", "good morning", "good evening"):
            return ("Hello! I'm bankserAI. Ask me a question, or tell me to "
                    "'open youtube', 'search for something' or "
                    "'open the matrix rain'.")

        if lowered in ("thanks", "thank you", "ty", "cheers"):
            return "Any time!"

        if lowered in ("how are you", "how're you", "how r u"):
            return ("Running smoothly inside BANKSER' Desktop. All systems "
                    "green.")

        if lowered in ("who are you", "what are you", "your name"):
            return AI_KNOWLEDGE["who are you"]

        if lowered in ("time", "what time is it", "clock"):
            return datetime.now().strftime("It is %H:%M:%S on %A, %d %B %Y.")

        if lowered in ("date", "today", "what date is it"):
            return datetime.now().strftime("Today is %A, %d %B %Y.")

        if lowered in ("system", "system info", "sysinfo"):
            return (f"Platform: {platform.platform()}\n"
                    f"Python: {platform.python_version()}\n"
                    f"Host: {socket.gethostname()}")

        if lowered in ("files", "list files"):
            try:
                names = [item.name for item in HOME.iterdir()]
            except OSError:
                names = []
            listing = "\n".join(names) if names else "(empty)"
            return f"Files in {HOME}:\n{listing}"

        if lowered in ("notes", "my notes"):
            try:
                content = NOTES_FILE.read_text(encoding="utf-8").strip()
            except OSError:
                content = ""
            return (content[:1200] if content else
                    "Your notes file is empty.")

        if lowered in ("joke", "tell me a joke", "say something funny"):
            jokes = [
                "I would tell you a UDP joke, but you might not get it.",
                "There are 10 kinds of people: those who understand binary "
                "and those who don't.",
                "A byte walks into a bar looking miserable. The bartender "
                "asks: What's wrong? Byte says: Parity error.",
                "Why do programmers prefer dark mode? Because light attracts "
                "bugs.",
            ]
            return jokes[datetime.now().second % len(jokes)]

        if lowered in ("help", "commands", "what can you do"):
            return AI_KNOWLEDGE["help"]

        return None

    # ------------------------------------------------------
    # DESKTOP ACTIONS
    # ------------------------------------------------------

    AI_VERBS = re.compile(
        r"\b(open|launch|start|show|run|display|bring\s+up|switch\s+to|"
        r"fire\s+up|play|give\s+me)\b"
    )

    AI_APP_ALIASES = {
        "matrix": ("matrix rain", "matrix digital rain", "digital rain",
                   "falling letters", "matrix", "cmatrix"),
        "art": ("art studio", "drawing program", "paint program", "art",
                "painting"),
        "pasteshell": ("paste shell", "network scanner", "pasteshell"),
        "terminal": ("terminal", "shell", "console"),
        "notes": ("notes", "notepad"),
        "files": ("file manager", "filecore", "files"),
        "monitor": ("system monitor", "task manager", "monitor"),
        "music": ("music player", "music", "audio"),
    }

    AI_LAUNCH_REPLIES = {
        "matrix": "Opening the MATRIX RAIN window.",
        "art": "Opening the ART Studio.",
        "pasteshell": "Opening PASTESHELL.",
        "terminal": "Bringing the terminal forward.",
        "notes": "Opening your notes.",
        "files": "Opening the file manager.",
        "monitor": "Opening the system monitor.",
        "music": "Opening the music player.",
    }

    @staticmethod
    def _alias_hit(lowered, alias):
        pattern = r"\b" + re.escape(alias).replace(r"\ ", r"\s+") + r"\b"
        return bool(re.search(pattern, lowered))

    def find_app(self, text):
        """Detect an 'open the matrix rain' style request."""
        lowered = text.lower().strip()
        if not lowered:
            return None

        has_verb = bool(self.AI_VERBS.search(lowered))
        bare = lowered.strip(" .!?:")

        for app, aliases in self.AI_APP_ALIASES.items():
            for alias in aliases:
                if not self._alias_hit(lowered, alias):
                    continue
                if has_verb or bare == alias:
                    return app

        return None

    def find_app_mention(self, text):
        """Find an app that a reply names, without needing a verb."""
        lowered = text.lower().strip()
        if not lowered:
            return None

        for app, aliases in self.AI_APP_ALIASES.items():
            for alias in aliases:
                if self._alias_hit(lowered, alias):
                    return app

        return None

    # ------------------------------------------------------
    # LOCAL MODEL
    # ------------------------------------------------------

    def desktop_context(self):
        """Facts about this machine, handed to the local model."""
        try:
            files = sorted(item.name for item in HOME.iterdir())
        except OSError:
            files = []

        try:
            notes = NOTES_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            notes = ""

        return (
            f"Operating system: BANKSER' Desktop v{VERSION} "
            f"(PySide6, Windows)\n"
            f"Colour theme: {CURRENT_THEME.name}\n"
            f"Now: {datetime.now().strftime('%A %d %B %Y, %H:%M:%S')}\n"
            f"Platform: {platform.platform()}\n"
            f"Python: {platform.python_version()}\n"
            f"User home folder: {HOME}\n"
            f"Files in the home folder: {', '.join(files) or '(empty)'}\n"
            f"User notes:\n{notes[:800] or '(empty)'}"
        )

    def ask_local_model(self, text):
        """Ask Qwen3.5-4B running on this machine."""
        system = (
            "You are bankserAI, the assistant built into the BANKSER' "
            "Desktop operating system.\n"
            "Answer clearly and briefly - 2 to 6 short sentences - unless "
            "the user asks for detail. Plain text only, no markdown "
            "headings, no bullet symbols.\n\n"
            f"Desktop context:\n{self.desktop_context()}\n\n"
            "Apps you can open on this desktop: matrix (the Matrix digital "
            "rain), art (ART Studio drawing program), pasteshell (network "
            "scanner), terminal, notes, files, monitor (system monitor), "
            "music.\n\n"
            "If the user wants a website opened, finish your answer with a "
            "line containing only OPEN:<full-url>.\n"
            "If the user wants a desktop app opened, finish your answer with "
            "a line containing only LAUNCH:<app>."
        )

        messages = [{"role": "system", "content": system}]
        messages.extend(self.turns[-6:])
        messages.append({"role": "user", "content": text})

        answer = self.local_model.chat(messages)
        return self.split_directives(answer)

    @staticmethod
    def split_directives(answer):
        """Pull OPEN: and LAUNCH: directives out of a model answer."""
        open_url = None
        launch = None
        kept = []

        for line in answer.splitlines():
            match = re.search(r"\bOPEN:\s*(\S+)", line)
            if match:
                open_url = match.group(1)
                line = (line[:match.start()] + line[match.end():]).strip()

            match = re.search(r"\bLAUNCH:\s*([\w -]+)", line)
            if match:
                launch = match.group(1).strip().lower()
                launch = re.sub(r"^the\s+", "", launch).strip()
                line = (line[:match.start()] + line[match.end():]).strip()

            if line:
                kept.append(line)

        reply = "\n".join(kept).strip() or answer
        return reply, open_url, launch

    # ------------------------------------------------------
    # PUBLIC ENTRY
    # ------------------------------------------------------

    def respond(self, text):
        """Return (reply, url_to_open, app_to_launch)."""
        self.history.append(text)

        # 1. desktop apps the user asked us to open
        app = self.find_app(text)
        if app:
            reply = self.AI_LAUNCH_REPLIES.get(
                app, f"Opening {app}.")
            return reply, None, app

        # 2. exact local facts
        reply = self.local_facts(text)
        if reply is not None:
            return reply, None, None

        # 3. arithmetic - the AST evaluator is exact, the model is not
        answer = self.math_answer(text)
        if answer:
            return answer, None, None

        # 4. explicit web requests
        search_url = self.find_search(text)
        if search_url:
            return "Opening a web search for that.", search_url, None

        site_url = self.find_url(text)
        if site_url:
            return "Opening it for you.", site_url, None

        # 5. the local model
        model_error = ""
        if self.local_model.available():
            try:
                reply, url, launch = self.ask_local_model(text)

                if launch is None and self.AI_VERBS.search(text.lower()):
                    # the model named an app instead of using the directive
                    launch = self.find_app_mention(reply)

                self.turns.append({"role": "user", "content": text})
                self.turns.append({"role": "assistant", "content": reply})
                return reply, url, launch
            except Exception as error:
                model_error = str(error)
                self.local_model.error = model_error

        # 6. the built-in knowledge base
        answer = self.knowledge(text)
        if answer:
            return answer, None, None

        # 7. a hosted model, if one is configured
        if self.backend_ready:
            try:
                answer = self.ask_model(text)
            except Exception as error:
                return (f"The AI backend failed ({error}). I answered from "
                        f"my local knowledge instead: try rephrasing, or "
                        f"ask something simpler."), None, None

            reply, url, launch = self.split_directives(answer)
            return reply, url, launch

        trouble = ""
        if model_error:
            trouble = (f"\n\nThe local model could not answer "
                       f"({model_error}).")

        return (
            "I don't have that one in my local knowledge base, and no AI "
            "backend is configured right now.\n\n"
            "You can:\n"
            "  · ask about BANKSER' (try 'what is bankser')\n"
            "  · do maths (try 'what is 24 * 3')\n"
            "  · open a site (try 'open youtube')\n"
            "  · open an app (try 'open the matrix rain')\n"
            "  · search the web (try 'search for linux mint')\n\n"
            "To enable real AI answers, put a valid key in "
            "~/.minimax/config.yaml and restart the desktop." + trouble
        ), None, None


class BankserAIWindow(QWidget):
    """bankserAI - chat window for the assistant."""

    def __init__(self, parent=None, on_closed=None, launcher=None):
        super().__init__(parent, Qt.Window)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setWindowTitle("bankserAI")
        self.setFixedSize(760, 640)
        self._on_closed = on_closed
        self.launcher = launcher

        self.engine = AIEngine()
        self.pending = False
        self.results = queue.Queue()
        self._status_text = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.frame = MintWindow("bankserAI", "spark",
                                on_close=lambda w: self.close())
        outer.addWidget(self.frame)

        # --- transcript
        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setFont(ui_font(10))
        self.transcript.setStyleSheet(
            f"background: {WINDOW_BG_DEEP}; color: {TEXT}; "
            f"border: 1px solid {BORDER}; border-radius: 7px; padding: 8px;")
        self.frame.body.addWidget(self.transcript, 1)

        # --- engine status
        self.status = QLabel()
        self.status.setFont(mono_font(9))
        self.status.setObjectName("muted")
        self.frame.body.addWidget(self.status)

        # --- input
        row = QHBoxLayout()

        self.input = QLineEdit()
        self.input.setFont(ui_font(11))
        self.input.setPlaceholderText("Ask bankserAI something...")
        self.input.returnPressed.connect(self.ask)
        row.addWidget(self.input, 1)

        ask = QPushButton("ASK")
        ask.setFixedWidth(72)
        ask.clicked.connect(self.ask)
        row.addWidget(ask)

        clear = QPushButton("CLEAR")
        clear.setFixedWidth(76)
        clear.clicked.connect(self.clear)
        row.addWidget(clear)

        self.frame.body.addLayout(row)

        hints = QLabel(
            "Try: 'what is 24 * 7' - 'open the matrix rain' - "
            "'open youtube' - 'search for linux mint' - "
            "'explain how a bank calculates interest'")
        hints.setFont(mono_font(9))
        hints.setObjectName("muted")
        hints.setWordWrap(True)
        self.frame.body.addWidget(hints)

        self.update_status()
        self.say(
            "Hello! I'm bankserAI, built into BANKSER' Desktop.\n"
            "I run a real Qwen3.5-4B model on this machine, so I can "
            "answer almost anything. I also do maths, open websites and "
            "open the desktop apps for you.\n\n"
            "Try: 'what is 24 * 7', 'open the matrix rain', "
            "'open youtube' or 'search for linux mint'.",
            "ai")

        self.drain_timer = QTimer(self)
        self.drain_timer.timeout.connect(self._drain_results)
        self.drain_timer.start(120)

        # warm the model up in the background so the first question is quick
        threading.Thread(target=self._warm_up, daemon=True).start()

    def _warm_up(self):
        """Load the local model ahead of the first question."""
        try:
            self.engine.local_model.ensure_ready()
        except Exception:
            pass

    # ------------------------------------------------------
    # UI HELPERS
    # ------------------------------------------------------

    def update_status(self):
        model = self.engine.local_model

        if model.available():
            if model.state == "ready":
                text = f"engine: {model.describe()} - ready"
            elif model.state == "starting":
                text = "engine: loading the local model..."
            elif model.state == "failed":
                text = f"engine: local model failed ({model.error})"
            else:
                text = (f"engine: {model.describe()} - loads on the first "
                        f"question")
        elif self.engine.backend_ready:
            text = "engine: local + AI backend connected"
        else:
            text = "engine: local knowledge base (no AI key configured)"

        if text != self._status_text:
            self._status_text = text
            self.status.setText(text)

    def say(self, text, who="ai"):
        if who == "you":
            block = (f"<div style='color:{MINT};font-weight:bold'>"
                     f"you &gt; {html.escape(text)}</div>")
        else:
            block = (f"<div style='color:{TEXT};margin-bottom:10px'>"
                     f"{html.escape(text).replace(chr(10), '<br>')}</div>")

        self.transcript.append(block)
        self.transcript.ensureCursorVisible()

    # ------------------------------------------------------
    # ASKING
    # ------------------------------------------------------

    def ask(self):
        if self.pending:
            return

        question = self.input.text().strip()
        if not question:
            return

        self.input.clear()
        self.say(question, "you")
        self.pending = True

        model = self.engine.local_model
        label = model.describe() if model.available() else "local"
        self.status.setText(f"thinking...  ({label})")

        threading.Thread(target=self._worker, args=(question,),
                         daemon=True).start()

    def _worker(self, question):
        try:
            reply, url, launch = self.engine.respond(question)
        except Exception as error:
            reply, url, launch = f"Something went wrong: {error}", None, None

        self.results.put((reply, url, launch))

    def _drain_results(self):
        """Pick up the answer produced by the worker thread."""
        try:
            while True:
                reply, url, launch = self.results.get_nowait()
                self.pending = False
                self.say(reply, "ai")

                if launch:
                    opened = False
                    if self.launcher:
                        try:
                            opened = bool(self.launcher(launch))
                        except Exception:
                            opened = False

                    if opened:
                        self.say(f"→ launching {launch}", "ai")
                    else:
                        self.say(f"I could not open {launch}.", "ai")

                if url:
                    self.say(f"↗ opening {url}", "ai")
                    try:
                        webbrowser.open(url)
                    except Exception:
                        self.say("Could not open the browser.", "ai")

        except queue.Empty:
            pass

        self.update_status()

    def clear(self):
        self.transcript.clear()
        self.say("Conversation cleared.", "ai")

    def closeEvent(self, event):
        if self._on_closed:
            self._on_closed()
        super().closeEvent(event)


# ==========================================================
# ART STUDIO  (drawing program)
# ==========================================================

ART_COLORS = [
    "#000000", "#404040", "#808080", "#c0c0c0", "#ffffff",
    "#e05252", "#f0954a", "#e5b83c", "#87cf3e", "#2fbf71",
    "#37d7e8", "#4a9eff", "#a56de2", "#ef5fa8", "#8b4513", "#00ffff",
]


class ArtCanvas(QWidget):
    """The drawing surface."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(520, 420)
        self.setFocusPolicy(Qt.StrongFocus)

        self.image = QImage(self.size(), QImage.Format_ARGB32)
        self.image.fill(QColor("#ffffff"))

        self.undo_stack = []
        self.redo_stack = []

        self.tool = "pencil"
        self.color = QColor("#1b2019")
        self.brush_size = 4
        self.drawing = False
        self.start_point = None
        self.last_point = None
        self.preview = None
        self.preview_image = QImage()

    # ------------------------------------------------------
    # HISTORY
    # ------------------------------------------------------

    def set_color(self, colour):
        """Set the drawing colour."""
        self.color = QColor(colour)

    def push_undo(self):
        self.undo_stack.append(self.image.copy())
        if len(self.undo_stack) > 40:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.image.copy())
            self.image = self.undo_stack.pop()
            self.update()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.image.copy())
            self.image = self.redo_stack.pop()
            self.update()

    def clear_canvas(self):
        self.push_undo()
        self.image.fill(QColor("#ffffff"))
        self.update()

    # ------------------------------------------------------
    # PAINTING
    # ------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawImage(0, 0, self.image)

        if self.preview is not None:
            painter.setOpacity(0.6)
            painter.drawImage(0, 0, self.preview_image)
            painter.setOpacity(1.0)

        painter.setPen(QPen(QColor("#9aa5b1"), 1, Qt.DashLine))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def resizeEvent(self, event):
        old = self.image
        resized = QImage(self.size(), QImage.Format_ARGB32)
        resized.fill(QColor("#ffffff"))
        painter = QPainter(resized)
        painter.drawImage(0, 0, old)
        painter.end()
        self.image = resized
        super().resizeEvent(event)

    def _pen(self):
        pen = QPen(self.color)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)

        if self.tool == "eraser":
            pen.setColor(QColor("#ffffff"))

        if self.tool == "brush":
            pen.setWidthF(self.brush_size * 2.2)
        elif self.tool == "eraser":
            pen.setWidthF(self.brush_size * 3.0)
        else:
            pen.setWidthF(self.brush_size)

        return pen

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        point = event.position().toPoint()
        self.drawing = True
        self.start_point = point
        self.last_point = point

        if self.tool in ("line", "rect", "ellipse"):
            self.preview_image = self.image.copy()
            self.preview = point

        elif self.tool == "fill":
            self.push_undo()
            self.flood_fill(point)
            self.drawing = False

        elif self.tool == "picker":
            color = self.image.pixelColor(point)
            self.color = color
            self.drawing = False
            if self.parent() is not None:
                window = self.parent().window()
                if hasattr(window, "on_color_picked"):
                    window.on_color_picked(color)

        else:
            self.push_undo()
            painter = QPainter(self.image)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(self._pen())
            painter.drawPoint(point)
            painter.end()
            self.update()

    def mouseMoveEvent(self, event):
        if not self.drawing:
            return

        point = event.position().toPoint()

        if self.tool in ("line", "rect", "ellipse"):
            self.preview_image = self.image.copy()
            painter = QPainter(self.preview_image)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(self._pen())
            self.draw_shape(painter, self.start_point, point)
            painter.end()
            self.update()
            return

        painter = QPainter(self.image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(self._pen())
        painter.drawLine(self.last_point, point)
        painter.end()

        self.last_point = point
        self.update()

    def mouseReleaseEvent(self, event):
        if not self.drawing:
            return

        point = event.position().toPoint()

        if self.tool in ("line", "rect", "ellipse"):
            self.push_undo()
            painter = QPainter(self.image)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(self._pen())
            self.draw_shape(painter, self.start_point, point)
            painter.end()
            self.preview = None
            self.update()

        self.drawing = False

    def draw_shape(self, painter, start, end):
        if self.tool == "line":
            painter.drawLine(start, end)
        elif self.tool == "rect":
            painter.drawRect(QRect(start, end).normalized())
        elif self.tool == "ellipse":
            painter.drawEllipse(QRect(start, end).normalized())

    # ------------------------------------------------------
    # FLOOD FILL
    # ------------------------------------------------------

    def flood_fill(self, point):
        if not (0 <= point.x() < self.image.width()
                and 0 <= point.y() < self.image.height()):
            return

        target = self.image.pixelColor(point)
        replacement = self.color

        if target == replacement:
            return

        width, height = self.image.width(), self.image.height()
        stack = [point]
        visited = set()

        while stack:
            current = stack.pop()
            x, y = current.x(), current.y()

            if (x, y) in visited:
                continue
            visited.add((x, y))

            if self.image.pixelColor(current) != target:
                continue

            self.image.setPixelColor(current, replacement)

            for neighbour in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                nx, ny = neighbour
                if 0 <= nx < width and 0 <= ny < height:
                    stack.append(QPoint(nx, ny))

        self.update()

    # ------------------------------------------------------
    # FILE
    # ------------------------------------------------------

    def save(self, path):
        return self.image.save(path, "PNG")

    def load(self, path):
        loaded = QImage(path)
        if loaded.isNull():
            return False
        self.push_undo()
        self.image = loaded.convertToFormat(QImage.Format_ARGB32)
        self.update()
        return True


class ArtStudioWindow(QWidget):
    """ART - a small drawing program inside the desktop."""

    TOOLS = [
        ("pencil", "Pencil", "P"),
        ("brush", "Brush", "B"),
        ("eraser", "Eraser", "E"),
        ("line", "Line", "L"),
        ("rect", "Rectangle", "R"),
        ("ellipse", "Ellipse", "O"),
        ("fill", "Fill", "F"),
        ("picker", "Pick colour", "I"),
    ]

    def __init__(self, parent=None, on_closed=None):
        super().__init__(parent, Qt.Window)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setWindowTitle("ART Studio")
        self.setFixedSize(1020, 700)
        self._on_closed = on_closed

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.frame = MintWindow("ART STUDIO", "brush",
                                on_close=lambda w: self.close())
        outer.addWidget(self.frame)

        layout = QHBoxLayout()
        layout.setSpacing(12)

        # ------------------------------------------------------
        # TOOLBAR
        # ------------------------------------------------------

        sidebar = QFrame()
        sidebar.setFixedWidth(176)
        sidebar.setStyleSheet(f"""
            QFrame#toolbar {{
                background: {WINDOW_BG_DEEP};
                border: 1px solid {BORDER};
                border-radius: 7px;
            }}
        """)
        sidebar.setObjectName("toolbar")

        side = QVBoxLayout(sidebar)
        side.setContentsMargins(10, 10, 10, 10)
        side.setSpacing(6)

        heading = QLabel("TOOLS")
        heading.setFont(ui_font(9, bold=True))
        heading.setObjectName("dim")
        side.addWidget(heading)

        self.tool_buttons = {}

        for tool, label, shortcut in self.TOOLS:
            button = QPushButton(f"{label}  ({shortcut})")
            button.setCheckable(True)
            button.setFont(ui_font(10))
            button.setToolTip(f"{label} - shortcut {shortcut}")
            button.clicked.connect(
                lambda checked, name=tool: self.select_tool(name))
            side.addWidget(button)
            self.tool_buttons[tool] = button

        self.tool_buttons["pencil"].setChecked(True)

        side.addSpacing(8)

        heading = QLabel("COLOUR")
        heading.setFont(ui_font(9, bold=True))
        heading.setObjectName("dim")
        side.addWidget(heading)

        grid = QGridLayout()
        grid.setSpacing(4)

        for index, colour in enumerate(ART_COLORS):
            swatch = QPushButton()
            swatch.setFixedSize(26, 26)
            swatch.setToolTip(colour)
            swatch.setStyleSheet(f"""
                QPushButton {{
                    background: {colour};
                    border: 1px solid {BORDER};
                    border-radius: 4px;
                }}
                QPushButton:hover {{ border: 2px solid {MINT}; }}
            """)
            swatch.clicked.connect(
                lambda checked=False, value=colour: self.set_color(value))
            grid.addWidget(swatch, index // 8, index % 8)

        side.addLayout(grid)

        custom = QPushButton("Custom colour…")
        custom.clicked.connect(self.pick_custom_color)
        side.addWidget(custom)

        side.addSpacing(6)

        heading = QLabel("SIZE")
        heading.setFont(ui_font(9, bold=True))
        heading.setObjectName("dim")
        side.addWidget(heading)

        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(1, 40)
        self.size_slider.setValue(4)
        self.size_slider.valueChanged.connect(self.set_size)
        side.addWidget(self.size_slider)

        self.size_label = QLabel("4 px")
        self.size_label.setFont(mono_font(9))
        self.size_label.setObjectName("muted")
        side.addWidget(self.size_label)

        side.addStretch(1)

        undo = QPushButton("Undo")
        undo.clicked.connect(self.undo)
        side.addWidget(undo)

        redo = QPushButton("Redo")
        redo.clicked.connect(self.redo)
        side.addWidget(redo)

        open_button = QPushButton("Open…")
        open_button.clicked.connect(self.open_image)
        side.addWidget(open_button)

        save_button = QPushButton("Save PNG…")
        save_button.clicked.connect(self.save_image)
        side.addWidget(save_button)

        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.clear_canvas)
        side.addWidget(clear_button)

        layout.addWidget(sidebar)

        # ------------------------------------------------------
        # CANVAS
        # ------------------------------------------------------

        canvas_holder = QVBoxLayout()

        self.canvas = ArtCanvas()
        self.canvas.setStyleSheet(
            f"background: #ffffff; border: 1px solid {BORDER};")
        canvas_holder.addWidget(self.canvas, 1)

        self.file_label = QLabel("untitled.png")
        self.file_label.setFont(mono_font(9))
        self.file_label.setObjectName("muted")
        canvas_holder.addWidget(self.file_label)

        layout.addLayout(canvas_holder, 1)
        self.frame.body.addLayout(layout)

    # ------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------

    def select_tool(self, tool):
        self.canvas.tool = tool
        for name, button in self.tool_buttons.items():
            button.setChecked(name == tool)

    def set_color(self, colour):
        self.canvas.color = QColor(colour)

    def on_color_picked(self, colour):
        self.canvas.color = colour

    def set_size(self, value):
        self.canvas.brush_size = value
        self.size_label.setText(f"{value} px")

    def pick_custom_color(self):
        colour = QColorDialog.getColor(self.canvas.color, self,
                                       "Choose a colour")
        if colour.isValid():
            self.set_color(colour.name())

    def undo(self):
        self.canvas.undo()

    def redo(self):
        self.canvas.redo()

    def clear_canvas(self):
        self.canvas.clear_canvas()

    def open_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open image", str(HOME), "Images (*.png *.jpg *.jpeg)")
        if path:
            if self.canvas.load(path):
                self.file_label.setText(Path(path).name)

    def save_image(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save drawing", str(HOME / "drawing.png"),
            "PNG image (*.png)")
        if path:
            if self.canvas.save(path):
                self.file_label.setText(Path(path).name)

    def keyPressEvent(self, event):
        key = event.key()
        shortcuts = {Qt.Key_P: "pencil", Qt.Key_B: "brush",
                     Qt.Key_E: "eraser", Qt.Key_L: "line",
                     Qt.Key_R: "rect", Qt.Key_O: "ellipse",
                     Qt.Key_F: "fill", Qt.Key_I: "picker"}

        if key in shortcuts:
            self.select_tool(shortcuts[key])
            return

        if event.matches(QKeySequence.Undo):
            self.undo()
        elif event.matches(QKeySequence.Redo):
            self.redo()
        elif event.matches(QKeySequence.Save):
            self.save_image()
        elif event.matches(QKeySequence.Open):
            self.open_image()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if self._on_closed:
            self._on_closed()
        super().closeEvent(event)


# ==========================================================
# MATRIX RAIN  (cmatrix style digital rain)
# ==========================================================

MATRIX_LETTERS = ("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                  "abcdefghijklmnopqrstuvwxyz")
MATRIX_DIGITS = "0123456789"
MATRIX_SYMBOLS = "!@#$%^&*()-_=+[]{};:,.<>/?|~"

MATRIX_PALETTE = {
    "green": "#00ff41",
    "red": "#ff2b2b",
    "blue": "#2b6bff",
    "yellow": "#ffd700",
    "cyan": "#00e5ff",
    "magenta": "#ff2bd6",
    "white": "#ffffff",
    "black": "#3a3a3a",
}

# cmatrix style colour hotkeys: ! @ # $ % ^ & )
MATRIX_COLOR_KEYS = {
    "!": "red", "@": "green", "#": "yellow", "$": "blue",
    "%": "magenta", "^": "cyan", "&": "white", ")": "black",
}


# hue used when matching the rain to the active desktop theme.
# the classic Matrix green reads as 120 even though #00ff41 is a touch cyan.
MATRIX_HUES = {
    "green": 120,
    "red": 0,
    "blue": 210,
    "yellow": 51,
    "cyan": 186,
    "magenta": 313,
}


class MatrixRain(QWidget):
    """Falling glyphs - the head is letters, the trail becomes digits
    and then symbols, exactly like the Matrix digital rain."""

    TRAIL = 18

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAutoFillBackground(True)

        self.columns = []
        self.async_mode = True
        self.bold_mode = False
        self.speed = 1.0
        self.base_color = QColor(MATRIX_PALETTE["green"])
        self.palette_colors = []

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(55)

        self.build_grid()

    # ------------------------------------------------------
    # GRID
    # ------------------------------------------------------

    def build_grid(self):
        font = QFont(MONO_FONT_NAME)
        font.setPointSize(12)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)

        metrics = QFontMetricsF(font)
        self.cell_w = max(6.0, metrics.horizontalAdvance("W"))
        self.cell_h = max(10.0, metrics.height())

        self.cols = max(1, int(self.width() // self.cell_w))
        self.rows = max(1, int(self.height() // self.cell_h))

        self.columns = []
        for index in range(self.cols):
            self.columns.append({
                # spread the heads across the screen so the window is
                # already full of rain the moment it opens
                "head": random.uniform(-self.rows * 0.15,
                                       self.rows * 0.95),
                "speed": random.uniform(0.30, 1.15),
                "trail": [],
            })

        self.build_palette()

    def build_palette(self):
        """Pre-compute the fading colour ramp for the trail."""
        head = QColor(self.base_color).lighter(160)
        tail = QColor(self.base_color).darker(260)

        self.palette_colors = []
        for step in range(self.TRAIL):
            ratio = step / float(max(1, self.TRAIL - 1))
            colour = QColor(
                int(head.red() + (tail.red() - head.red()) * ratio),
                int(head.green() + (tail.green() - head.green()) * ratio),
                int(head.blue() + (tail.blue() - head.blue()) * ratio),
            )
            self.palette_colors.append(colour)

    def resizeEvent(self, event):
        self.build_grid()
        super().resizeEvent(event)

    # ------------------------------------------------------
    # ANIMATION
    # ------------------------------------------------------

    def tick(self):
        for index, column in enumerate(self.columns):

            speed = column["speed"]
            if self.async_mode:
                speed *= random.uniform(0.85, 1.15)

            column["head"] += speed * self.speed

            if column["head"] - len(column["trail"]) > self.rows:
                column["head"] = -random.uniform(0, self.rows * 0.5)
                column["trail"] = []

            trail = column["trail"]
            trail.insert(0, {"char": self.new_glyph(0), "age": 0,
                             "bold": self.bold_mode or random.random() < 0.12})

            for cell in trail:
                cell["age"] += 1

            while len(trail) > self.TRAIL:
                trail.pop()

            # re-roll glyphs as they fall so the trail keeps mutating
            for position, cell in enumerate(trail):
                if cell["age"] % 3 == 0:
                    cell["char"] = self.new_glyph(position)

        self.update()

    @staticmethod
    def new_glyph(depth):
        """Letters at the head, digits a little behind, symbols at the tail.

        `depth` is how far the glyph sits below the head of its column, so a
        character literally changes as it travels down the screen.
        """
        if depth <= 1:
            return random.choice(MATRIX_LETTERS)
        if depth <= 5:
            return random.choice(MATRIX_DIGITS)
        return random.choice(MATRIX_SYMBOLS)

    # ------------------------------------------------------
    # PAINTING
    # ------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        painter.fillRect(self.rect(), QColor("#02050a"))

        font = QFont(self.font())
        painter.setFont(font)

        for index, column in enumerate(self.columns):
            x = index * self.cell_w

            for position, cell in enumerate(column["trail"]):
                # snap to the row grid so every column reads cleanly
                row = int(column["head"]) - position
                if row < 0 or row > self.rows:
                    continue

                y = row * self.cell_h
                colour = self.palette_colors[min(position,
                                                 len(self.palette_colors) - 1)]

                if position == 0:
                    # bright head with a soft halo
                    halo = QPen(colour)
                    halo.setWidthF(3.5)
                    halo.setColor(QColor(colour.red(), colour.green(),
                                         colour.blue(), 70))
                    painter.setPen(halo)
                    painter.drawText(QPointF(x, y + self.cell_h * 0.8),
                                     cell["char"])

                    head_font = QFont(font)
                    head_font.setBold(True)
                    painter.setFont(head_font)
                    painter.setPen(QPen(colour.lighter(180)))
                    painter.drawText(QPointF(x, y + self.cell_h * 0.8),
                                     cell["char"])
                    painter.setFont(font)
                    continue

                glyph_font = QFont(font)
                glyph_font.setBold(cell["bold"])
                painter.setFont(glyph_font)
                painter.setPen(QPen(colour))
                painter.drawText(QPointF(x, y + self.cell_h * 0.8),
                                 cell["char"])

    # ------------------------------------------------------
    # CONTROLS
    # ------------------------------------------------------

    def set_color(self, name):
        if name in MATRIX_PALETTE:
            self.base_color = QColor(MATRIX_PALETTE[name])
            self.build_palette()
            self.update()

    def set_speed(self, speed):
        self.speed = speed
        self.update()

    def toggle_async(self):
        self.async_mode = not self.async_mode
        return self.async_mode

    def toggle_bold(self):
        self.bold_mode = not self.bold_mode
        return self.bold_mode

    def keyPressEvent(self, event):
        key = event.text().lower()

        if key in ("q", "escape"):
            window = self.window()
            window.close()
            return

        if key in MATRIX_COLOR_KEYS:
            self.set_color(MATRIX_COLOR_KEYS[key])
            return

        if key.isdigit():
            # cmatrix style: 0 sprints, 9 crawls
            delay = int(key)
            self.set_speed(max(0.25, 3.4 - delay * 0.35))
            return

        if key == "a":
            self.toggle_async()
            return

        if key == "b":
            self.toggle_bold()
            return


class MatrixWindow(QWidget):
    """MATRIX RAIN - a cmatrix style window inside the desktop."""

    def __init__(self, parent=None, on_closed=None):
        super().__init__(parent, Qt.Window)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setWindowTitle("MATRIX RAIN")
        self.setFixedSize(860, 620)
        self._on_closed = on_closed

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.frame = MintWindow("MATRIX RAIN", "matrix",
                                on_close=lambda w: self.close())
        outer.addWidget(self.frame)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.rain = MatrixRain()
        body.addWidget(self.rain, 1)

        # --- control strip
        hud = QWidget()
        hud.setFixedHeight(34)
        hud.setStyleSheet(f"""
            QWidget#matrixhud {{
                background: {WINDOW_BG_DEEP};
                border-top: 1px solid {BORDER};
            }}
        """)
        hud.setObjectName("matrixhud")

        hud_layout = QHBoxLayout(hud)
        hud_layout.setContentsMargins(10, 0, 10, 0)
        hud_layout.setSpacing(10)

        hints = QLabel("q quit  ·  0-9 speed  ·  a async  ·  b bold  ·  "
                       "!@#$%^&) colour")
        hints.setFont(mono_font(9))
        hints.setObjectName("muted")
        hud_layout.addWidget(hints)
        hud_layout.addStretch(1)

        for name, colour in MATRIX_PALETTE.items():
            swatch = QPushButton()
            swatch.setFixedSize(16, 16)
            swatch.setToolTip(name)
            swatch.setStyleSheet(f"""
                QPushButton {{
                    background: {colour};
                    border: 1px solid {BORDER};
                    border-radius: 3px;
                }}
                QPushButton:hover {{ border: 2px solid {MINT}; }}
            """)
            swatch.clicked.connect(
                lambda checked=False, value=name: self.rain.set_color(value))
            hud_layout.addWidget(swatch)

        body.addWidget(hud)
        self.frame.body.addLayout(body)

        # start in the colour of the active desktop theme
        self.rain.set_color(self.theme_color_name())

    @staticmethod
    def theme_color_name():
        """Match the rain to the current desktop theme when possible.

        Picks the palette entry whose hue is closest to the active accent, so
        Mint rains green, Crimson rains red and Cyan rains cyan. Falls back
        to classic green when nothing is close enough.
        """
        accent = QColor(MINT)
        if not accent.isValid():
            return "green"

        # a washed out accent (graphite) has no colour of its own
        if accent.saturation() < 60:
            return "white"

        accent_hue = accent.hue()
        if accent_hue < 0:
            return "green"

        best = None
        best_distance = 361

        for name, hue in MATRIX_HUES.items():
            distance = abs(accent_hue - hue)
            distance = min(distance, 360 - distance)

            if distance < best_distance:
                best_distance = distance
                best = name

        if best is None or best_distance > 60:
            return "green"
        return best

    def keyPressEvent(self, event):
        self.rain.keyPressEvent(event)

    def closeEvent(self, event):
        self.rain.timer.stop()
        if self._on_closed:
            self._on_closed()
        super().closeEvent(event)


# ==========================================================
# MAIN DESKTOP
# ==========================================================

class BankserDesktop(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(f"{APP_NAME} Desktop v{VERSION}")
        self.setMinimumSize(1040, 660)
        self.resize(1440, 860)
        self.setWindowFlags(Qt.FramelessWindowHint)

        self.wallpaper = Wallpaper()
        self.setCentralWidget(self.wallpaper)

        self.paste_window = None
        self.ai_window = None
        self.art_window = None
        self.matrix_window = None
        self.gauges = []

        # never leave the local model server running behind our back
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown_model)

        self.build_desktop()

    # ------------------------------------------------------
    # LAYOUT
    # ------------------------------------------------------

    def build_desktop(self):

        root = QVBoxLayout(self.wallpaper)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self.build_top_panel())

        body = QWidget()
        body.setAttribute(Qt.WA_TranslucentBackground)
        grid = QGridLayout(body)
        self.grid = grid
        grid.setContentsMargins(11, 11, 11, 9)
        grid.setSpacing(9)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 2)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)

        self.notes_win = self.notes_panel()
        self.files_win = self.files_panel()
        self.terminal_win = self.terminal_panel()
        self.music_win = self.music_panel()
        self.monitor_win = self.monitor_panel()

        self.panel_home = {
            self.notes_win: (0, 0, 1, 1),
            self.files_win: (0, 1, 1, 1),
            self.terminal_win: (1, 0, 1, 1),
            self.music_win: (1, 1, 1, 1),
            self.monitor_win: (0, 2, 2, 1),
        }
        self.zoomed_window = None

        grid.addWidget(self.notes_win, 0, 0)
        grid.addWidget(self.files_win, 0, 1)
        grid.addWidget(self.terminal_win, 1, 0)
        grid.addWidget(self.music_win, 1, 1)
        grid.addWidget(self.monitor_win, 0, 2, 2, 1)

        root.addWidget(body, 1)
        root.addWidget(self.build_bottom_panel())

    # ------------------------------------------------------
    # TOP PANEL  (Cinnamon style)
    # ------------------------------------------------------

    def build_top_panel(self):

        panel = QWidget()
        panel.setFixedHeight(33)
        panel.setObjectName("toppanel")
        self.top_panel = panel
        self.style_top_panel()

        layout = QHBoxLayout(panel)
        layout.setContentsMargins(6, 2, 4, 2)
        layout.setSpacing(4)

        # --- menu button (Mint style)
        menu_button = QPushButton(f"  {APP_NAME}")
        menu_button.setToolTip("Main menu")
        menu_button.setCursor(Qt.PointingHandCursor)
        menu_button.setFixedHeight(26)
        self.menu_button = menu_button
        self.style_menu_button()
        menu_button.clicked.connect(self.show_launcher_menu)
        layout.addWidget(menu_button)

        # --- window list
        window_tab = QPushButton("  Desktop")
        window_tab.setCursor(Qt.PointingHandCursor)
        window_tab.setFixedHeight(26)
        self.window_tab = window_tab
        self.style_window_tab()
        layout.addWidget(window_tab)
        layout.addStretch(1)

        # --- system tray
        tray = QWidget()
        tray.setStyleSheet("background: transparent;")
        tray_layout = QHBoxLayout(tray)
        tray_layout.setContentsMargins(0, 0, 4, 0)
        tray_layout.setSpacing(2)

        for kind, tip in (("network", "Network: offline"),
                          ("volume", "Volume: 70%"),
                          ("power", "Power options")):
            button = IconButton(kind, tip, 26, theme_bound=True)
            button.clicked.connect(self.show_launcher_menu)
            tray_layout.addWidget(button)

        layout.addWidget(tray)

        # --- clock
        self.clock = QLabel()
        self.clock.setFont(ui_font(10))
        self.style_clock()
        layout.addWidget(self.clock)

        # --- window controls
        for kind, tip in (("minimize", "Minimize"),
                          ("maximize", "Maximize"),
                          ("close", "Close")):
            button = IconButton(kind, tip, 28, theme_bound=True,
                                hover="#ff8a80")
            if kind == "minimize":
                button.clicked.connect(self.showMinimized)
            elif kind == "maximize":
                button.clicked.connect(self.toggle_fullscreen)
            else:
                button.clicked.connect(self.close)
            layout.addWidget(button)

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        self.update_clock()

        return panel

    # ------------------------------------------------------
    # THEME STYLING HELPERS  (re-applied on a theme switch)
    # ------------------------------------------------------

    def style_top_panel(self):
        self.top_panel.setStyleSheet(f"""
            QWidget#toppanel {{
                background: {PANEL_BG};
                border-bottom: 1px solid #2a2a2a;
            }}
            QLabel {{ color: {TEXT_DIM}; }}
        """)

    def style_menu_button(self):
        self.menu_button.setStyleSheet(f"""
            QPushButton {{
                background: {MINT_DARK};
                color: {TEXT};
                border: none;
                border-radius: 5px;
                padding: 0 12px 0 9px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {MINT};
                color: {CURRENT_THEME.on_accent};
            }}
        """)

    def style_window_tab(self):
        self.window_tab.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_DIM};
                border: none;
                border-bottom: 2px solid {MINT};
                padding: 0 14px;
                font-size: 11px;
            }}
            QPushButton:hover {{ color: {TEXT}; }}
        """)

    def style_clock(self):
        self.clock.setStyleSheet(
            f"color: {TEXT}; padding: 0 10px; background: transparent;")

    def style_taskbar(self):
        self.taskbar.setStyleSheet(f"""
            QWidget#taskbar {{
                background: {PANEL_BG};
                border-top: 1px solid #2a2a2a;
            }}
        """)

    def style_terminal(self):
        self.terminal_output.setStyleSheet(
            f"background: {TERMINAL_BG}; color: #cfdcc6;")

    def style_path_label(self):
        self.path_label.setStyleSheet(
            f"background: {WINDOW_BG_DEEP}; padding: 7px; "
            f"border-radius: 5px; color: {TEXT_DIM};")

    def style_info_frame(self):
        self.info_frame.setStyleSheet(f"""
            QFrame#infobox {{
                background: {WINDOW_BG_DEEP};
                border: 1px solid {BORDER};
                border-radius: 7px;
            }}
        """)

    def refresh_theme(self):
        """Re-skin every surface after the palette changed."""
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_stylesheet())

        self.style_top_panel()
        self.style_menu_button()
        self.style_window_tab()
        self.style_clock()
        self.style_taskbar()
        self.style_terminal()
        self.style_path_label()
        self.style_info_frame()

        alive = []
        for icon in THEME_ICONS:
            try:
                icon.color = QColor(MINT_LIGHT)
                icon.update()
                alive.append(icon)
            except RuntimeError:
                # the window this icon belonged to was closed
                continue
        THEME_ICONS[:] = alive

        for gauge in self.gauges:
            gauge.update()

        self.wallpaper.update()
        self.update()

    # ------------------------------------------------------
    # BOTTOM PANEL  (taskbar)
    # ------------------------------------------------------

    def build_bottom_panel(self):

        panel = QWidget()
        panel.setFixedHeight(52)
        panel.setObjectName("taskbar")
        self.taskbar = panel
        self.style_taskbar()

        layout = QHBoxLayout(panel)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(5)

        # --- show applications
        apps_button = IconButton("apps", "Show Applications", 36,
                                 theme_bound=True)
        apps_button.clicked.connect(self.show_launcher_menu)
        layout.addWidget(apps_button)

        separator = QFrame()
        separator.setFixedWidth(1)
        separator.setFixedHeight(26)
        separator.setStyleSheet(f"background: {BORDER};")
        layout.addWidget(separator)

        # --- launchers
        launchers = [
            ("notes", "Notes", self.focus_notes),
            ("folder", "Filecore", self.focus_files),
            ("terminal", "Terminal", self.focus_terminal),
            ("monitor", "System Monitor", self.focus_monitor),
            ("spark", "bankserAI", self.open_bankserai),
            ("brush", "ART Studio", self.open_art),
            ("matrix", "Matrix Rain", self.open_matrix),
            ("music", "Music", self.focus_music),
            ("skull", "PASTESHELL", self.open_pasteshell),
            ("lock", "Security Center", self.show_security),
        ]

        for kind, tip, action in launchers:
            button = IconButton(kind, tip, 36, theme_bound=True)
            button.clicked.connect(action)
            layout.addWidget(button)

        layout.addStretch(1)

        # --- show desktop
        show_desktop = IconButton("minimize", "Show desktop", 32,
                                  theme_bound=True)
        show_desktop.clicked.connect(self.toggle_panels)
        layout.addWidget(show_desktop)

        return panel

    # ------------------------------------------------------
    # PANELS
    # ------------------------------------------------------

    def notes_panel(self):

        panel = MintWindow("NOTES", "notes",
                           on_maximize=lambda w: self.toggle_zoom(w))

        self.note_search = QLineEdit()
        self.note_search.setPlaceholderText("Search notes…")
        panel.body.addWidget(self.note_search)

        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Your thoughts, ideas and plans…")
        self.notes.setFont(ui_font(11))

        if NOTES_FILE.exists():
            self.notes.setPlainText(
                NOTES_FILE.read_text(encoding="utf-8")
            )

        panel.body.addWidget(self.notes, 1)

        save = QPushButton("Save notes")
        save.clicked.connect(self.save_notes)
        panel.body.addWidget(save)

        return panel

    def files_panel(self):

        panel = MintWindow("FILECORE", "folder",
                           on_maximize=lambda w: self.toggle_zoom(w))

        path = QLabel("⌂   /home/bankser")
        self.path_label = path
        self.style_path_label()
        panel.body.addWidget(path)

        self.file_list = QListWidget()
        self.file_list.setFont(mono_font(9))
        panel.body.addWidget(self.file_list, 1)

        self.refresh_files()

        row = QHBoxLayout()

        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_files)

        open_folder = QPushButton("Open folder")
        open_folder.clicked.connect(self.open_home)

        row.addWidget(refresh)
        row.addWidget(open_folder)

        panel.body.addLayout(row)

        return panel

    def terminal_panel(self):

        panel = MintWindow("TERMINAL", "terminal",
                           on_maximize=lambda w: self.toggle_zoom(w))

        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setFont(mono_font(9))
        self.terminal_output.setLineWrapMode(QTextEdit.NoWrap)
        self.style_terminal()
        self.terminal_output.setPlainText(
            f"{APP_NAME} Terminal [demo shell]\n"
            "Type 'help' for commands, '-welcome' for the bank.\n\n"
        )
        panel.body.addWidget(self.terminal_output, 1)

        self.terminal_input = QLineEdit()
        self.terminal_input.setFont(mono_font(9))
        self.terminal_input.setPlaceholderText("bankser@desktop:~$ ")
        self.terminal_input.returnPressed.connect(self.run_command)
        panel.body.addWidget(self.terminal_input)

        return panel

    def music_panel(self):

        panel = MintWindow("MUSIC", "music",
                           on_maximize=lambda w: self.toggle_zoom(w))

        panel.body.addStretch(1)

        icon = IconWidget("music", 74, "#f2a6d0")
        holder = QWidget()
        holder_layout = QHBoxLayout(holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.addStretch(1)
        holder_layout.addWidget(icon)
        holder_layout.addStretch(1)
        panel.body.addWidget(holder)

        title = QLabel(f"{APP_NAME} Audio")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(ui_font(15, bold=True))
        title.setObjectName("strong")
        panel.body.addWidget(title)

        description = QLabel(
            "Your personal music space.\nOpen your local music folder.")
        description.setAlignment(Qt.AlignCenter)
        description.setObjectName("muted")
        panel.body.addWidget(description)

        music_button = QPushButton("Open music folder")
        music_button.clicked.connect(
            lambda: self.open_path(Path.home() / "Music")
        )
        panel.body.addWidget(music_button)

        panel.body.addStretch(1)

        return panel

    def monitor_panel(self):

        panel = MintWindow("SYSTEM MONITOR", "monitor",
                           on_maximize=lambda w: self.toggle_zoom(w))
        panel.setMinimumWidth(380)

        gauges = QHBoxLayout()

        for title, value in (("MEMORY", 38), ("DISK", 72), ("CPU", 8)):
            gauge = Gauge(title, value)
            self.gauges.append(gauge)
            gauges.addWidget(gauge)

        panel.body.addLayout(gauges)

        section = QLabel("NETWORK & SYSTEM")
        section.setFont(ui_font(9, bold=True))
        section.setObjectName("dim")
        panel.body.addWidget(section)

        info_frame = QFrame()
        info_frame.setObjectName("infobox")
        self.info_frame = info_frame
        self.style_info_frame()

        info_layout = QHBoxLayout(info_frame)

        sections = [
            ("NETWORKS", "No connection\n\nNetwork status: Offline"),
            ("NETWORK RATES", "↓ 0 KB/s\n\n↑ 0 KB/s"),
            ("SYSTEM",
             f"OS: {APP_NAME} Desktop\n"
             f"Kernel: Hosted prototype\n"
             f"Python: {platform.python_version()}\n"
             "Uptime: Session active"),
        ]

        for heading, text in sections:
            column = QVBoxLayout()

            title = QLabel(heading)
            title.setAlignment(Qt.AlignCenter)
            title.setFont(ui_font(9, bold=True))
            title.setObjectName("accent")

            value = QLabel(text)
            value.setAlignment(Qt.AlignCenter)
            value.setWordWrap(True)
            value.setFont(mono_font(9))
            value.setObjectName("dimpad")

            column.addWidget(title)
            column.addWidget(value, 1)

            info_layout.addLayout(column)

        panel.body.addWidget(info_frame, 1)

        section = QLabel("PROCESSES")
        section.setFont(ui_font(9, bold=True))
        section.setObjectName("dim")
        panel.body.addWidget(section)

        self.processes = QListWidget()
        self.processes.setFont(mono_font(9))
        self.processes.addItems([
            "bankser-shell       Running",
            "filecore             Ready",
            "notes                 Ready",
            "terminal              Ready",
            "system-monitor       Running",
            "music                 Idle",
        ])
        panel.body.addWidget(self.processes, 1)

        return panel

    # ------------------------------------------------------
    # PANEL ZOOM  (a panel can fill the whole desktop)
    # ------------------------------------------------------

    def zoom_panel(self, window):
        """Expand a panel over the whole desktop area."""
        if self.zoomed_window is window:
            self.restore_panel(window)
            return

        if self.zoomed_window is not None:
            self.restore_panel(self.zoomed_window)

        self.grid.removeWidget(window)
        self.grid.addWidget(window, 0, 0, 2, 3)
        self.zoomed_window = window

        if window is self.terminal_win:
            self.terminal_output.setAlignment(Qt.AlignHCenter)
            self.terminal_output.setFont(mono_font(12))

        window.set_zoomed(True)
        window.raise_()

    def restore_panel(self, window):
        """Put a panel back where it came from."""
        if self.zoomed_window is not window:
            return

        row, column, row_span, column_span = self.panel_home[window]
        self.grid.removeWidget(window)
        self.grid.addWidget(window, row, column, row_span, column_span)
        self.zoomed_window = None

        if window is self.terminal_win:
            self.terminal_output.setAlignment(Qt.AlignLeft)
            self.terminal_output.setFont(mono_font(9))

        window.set_zoomed(False)
        window.raise_()

    def toggle_zoom(self, window):
        if self.zoomed_window is window:
            self.restore_panel(window)
        else:
            self.zoom_panel(window)

    # ------------------------------------------------------
    # THEMING
    # ------------------------------------------------------

    def set_theme(self, number):
        """Apply one of the ten colour schemes to the whole desktop."""
        if not 1 <= number <= len(THEMES):
            return None

        theme = use_theme(number - 1)
        self.refresh_theme()
        save_theme(number)
        return theme

    def theme_list(self):
        lines = ["Colour schemes:", ""]
        for theme in THEMES:
            marker = "*" if theme is CURRENT_THEME else " "
            lines.append(
                f"  {marker} {theme.index:>2}. {theme.name:<10} {theme.accent}")
        lines.append("")
        lines.append("Type 'color <number>' to apply a scheme.")
        return "\n".join(lines)

    # ------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------

    def update_clock(self):
        self.clock.setText(datetime.now().strftime("%a %d %b  %H:%M"))

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def toggle_panels(self):
        windows = [self.notes_win, self.files_win, self.terminal_win,
                   self.music_win, self.monitor_win]
        visible = any(win.isVisible() for win in windows)
        for win in windows:
            win.setVisible(not visible)

    def save_notes(self):
        NOTES_FILE.write_text(self.notes.toPlainText(), encoding="utf-8")
        QMessageBox.information(self, f"{APP_NAME} Notes", "Notes saved!")

    def refresh_files(self):
        self.file_list.clear()
        try:
            items = sorted(HOME.iterdir())
        except OSError:
            items = []

        for item in items:
            prefix = "[dir]  " if item.is_dir() else "[file] "
            self.file_list.addItem(prefix + item.name)

        if not self.file_list.count():
            self.file_list.addItem("(empty)")

    def open_home(self):
        self.open_path(HOME)

    def open_path(self, path):
        try:
            path.mkdir(parents=True, exist_ok=True)

            if sys.platform.startswith("win"):
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])

        except Exception as error:
            QMessageBox.warning(self, APP_NAME, str(error))

    # ------------------------------------------------------
    # MENU / DOCK ACTIONS
    # ------------------------------------------------------

    def show_launcher_menu(self):

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {HEADER_BG};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 8px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 7px 24px 7px 14px;
                border-radius: 5px;
            }}
            QMenu::item:selected {{
                background: {MINT};
                color: {CURRENT_THEME.on_accent};
            }}
            QMenu::separator {{ height: 1px; background: {BORDER}; margin: 5px 8px; }}
        """)

        menu.addAction("Notes").triggered.connect(self.focus_notes)
        menu.addAction("Filecore").triggered.connect(self.focus_files)
        menu.addAction("Terminal").triggered.connect(self.focus_terminal)
        menu.addAction("System Monitor").triggered.connect(self.focus_monitor)
        menu.addAction("Music").triggered.connect(self.focus_music)
        menu.addAction("bankserAI").triggered.connect(self.open_bankserai)
        menu.addAction("ART Studio").triggered.connect(self.open_art)
        menu.addAction("Matrix Rain").triggered.connect(self.open_matrix)
        menu.addAction("PASTESHELL").triggered.connect(self.open_pasteshell)
        menu.addSeparator()
        menu.addAction("Security Center").triggered.connect(self.show_security)
        menu.addAction("About BANKSER'").triggered.connect(self.show_about)

        menu.exec(self.cursor().pos())

    def open_matrix(self):
        """Launch the MATRIX RAIN window."""
        if getattr(self, "matrix_window", None) is None:
            self.matrix_window = MatrixWindow(
                self, on_closed=lambda: setattr(self, "matrix_window", None))

        window = self.matrix_window

        if not window.isVisible():
            screen = self.screen() or QApplication.primaryScreen()
            if screen is not None:
                area = screen.availableGeometry()
                window.move(area.center() - window.rect().center())
            window.show()

        window.raise_()
        window.activateWindow()
        window.rain.setFocus()

    def open_bankserai(self):
        """Launch the bankserAI assistant window."""
        if getattr(self, "ai_window", None) is None:
            self.ai_window = BankserAIWindow(
                self, on_closed=lambda: setattr(self, "ai_window", None),
                launcher=self.launch_app)

        window = self.ai_window

        if not window.isVisible():
            screen = self.screen() or QApplication.primaryScreen()
            if screen is not None:
                area = screen.availableGeometry()
                window.move(area.center() - window.rect().center())
            window.show()

        window.raise_()
        window.activateWindow()
        window.input.setFocus()

    def open_art(self):
        """Launch the ART drawing program."""
        if getattr(self, "art_window", None) is None:
            self.art_window = ArtStudioWindow(
                self, on_closed=lambda: setattr(self, "art_window", None))

        window = self.art_window

        if not window.isVisible():
            screen = self.screen() or QApplication.primaryScreen()
            if screen is not None:
                area = screen.availableGeometry()
                window.move(area.center() - window.rect().center())
            window.show()

        window.raise_()
        window.activateWindow()
        window.canvas.setFocus()

    def open_pasteshell(self):
        """Launch PASTESHELL as an app window inside the desktop."""
        if self.paste_window is None:
            self.paste_window = PasteShellWindow(
                self, on_closed=lambda: setattr(self, "paste_window", None))

        window = self.paste_window

        if not window.isVisible():
            screen = self.screen() or QApplication.primaryScreen()
            if screen is not None:
                area = screen.availableGeometry()
                window.move(area.center() - window.rect().center())
            window.show()

        window.raise_()
        window.activateWindow()
        window.focus_console()

    # ------------------------------------------------------
    # APP LAUNCHING  (used by bankserAI)
    # ------------------------------------------------------

    def launch_app(self, name):
        """Open one of the desktop apps by name. Returns True on success."""
        key = (name or "").strip().lower()

        table = {
            "matrix": self.open_matrix,
            "matrix rain": self.open_matrix,
            "cmatrix": self.open_matrix,
            "art": self.open_art,
            "art studio": self.open_art,
            "paint": self.open_art,
            "pasteshell": self.open_pasteshell,
            "paste shell": self.open_pasteshell,
            "terminal": self.focus_terminal,
            "shell": self.focus_terminal,
            "console": self.focus_terminal,
            "notes": self.focus_notes,
            "notepad": self.focus_notes,
            "files": self.focus_files,
            "file manager": self.focus_files,
            "filecore": self.focus_files,
            "monitor": self.focus_monitor,
            "system monitor": self.focus_monitor,
            "music": self.focus_music,
            "music player": self.focus_music,
        }

        action = table.get(key)
        if action is None:
            # tolerate longer names such as 'the matrix digital rain'
            for name, candidate in table.items():
                if name in key:
                    action = candidate
                    break

        if action is None:
            return False

        action()
        return True

    def shutdown_model(self):
        """Stop the local model server."""
        try:
            get_local_model().stop()
        except Exception:
            pass

    def closeEvent(self, event):
        """Shut the local model server down with the desktop."""
        self.shutdown_model()
        super().closeEvent(event)

    def show_about(self):
        QMessageBox.information(
            self, f"About {APP_NAME}",
            f"{APP_NAME} Desktop v{VERSION}\n"
            "Linux Mint inspired desktop environment\n\n"
            "Type '-welcome' in the terminal for the bank picture."
        )

    def show_security(self):
        QMessageBox.information(
            self, f"{APP_NAME} Security",
            "Security Center\n\n"
            "Prototype status: local desktop app.\n"
            "Background security scanning is not active yet."
        )

    def _focus_window(self, window, widget=None):
        window.show()
        window.raise_()
        if widget is not None:
            widget.setFocus()

    def focus_terminal(self):
        self._focus_window(self.terminal_win, self.terminal_input)

    def focus_files(self):
        self._focus_window(self.files_win, self.file_list)

    def focus_notes(self):
        self._focus_window(self.notes_win, self.notes)

    def focus_monitor(self):
        self._focus_window(self.monitor_win, self.processes)

    def focus_music(self):
        self._focus_window(self.music_win)

    # ------------------------------------------------------
    # TERMINAL
    # ------------------------------------------------------

    def term_write(self, text):
        """Append plain text (keeps ASCII art spacing intact)."""
        cursor = self.terminal_output.textCursor()
        cursor.movePosition(QTextCursor.End)

        cursor.insertBlock()

        char_format = QTextCharFormat()
        char_format.setForeground(QColor("#cfdcc6"))
        cursor.setCharFormat(char_format)

        cursor.insertText(text)
        self.terminal_output.setTextCursor(cursor)
        self.terminal_output.ensureCursorVisible()

    def term_html(self, text):
        self.terminal_output.append(text)

    def show_welcome(self):
        """Print the ASCII bank picture."""
        self.term_html(
            f"<span style='color:{MINT};font-weight:bold'>"
            "Welcome back to BANKSER' Desktop</span><br>"
            f"<span style='color:{TEXT_MUTED}'>"
            "session user: bankser &nbsp;·&nbsp; shell: bsh "
            "&nbsp;·&nbsp; host: BANKSER'</span>"
        )
        self.term_write("")
        self.term_write(build_bank_art())
        self.term_write("")
        self.term_html(
            f"<span style='color:{TEXT_DIM}'>"
            "Type 'help' to list every command. "
            "Click ▢ in the title bar to restore the window.</span>"
        )

    def run_command(self):

        command = self.terminal_input.text().strip()
        self.terminal_input.clear()

        if not command:
            return

        name = command.split()[0].lower()

        if name in ("clear", "cls"):
            self.terminal_output.clear()
            return

        if name in ("color", "colors", "colour", "colours", "theme"):

            self.term_html(
                f"<span style='color:{PROMPT}'>"
                f"bankser@desktop:~$ {html.escape(command)}</span>"
            )

            arguments = command.split()[1:]

            if not arguments:
                self.term_write(self.theme_list())
                return

            try:
                number = int(arguments[0])
            except ValueError:
                self.term_write(f"Usage: color <1-{len(THEMES)}>")
                return

            theme = self.set_theme(number)

            if theme is None:
                self.term_write(
                    f"Invalid theme number. Use 1-{len(THEMES)}.")
            else:
                self.term_write(
                    f"Theme changed -> {theme.name}  (accent {theme.accent})")
                self.term_write(
                    "The whole desktop re-skins instantly.")
            return

        if name in ("ai", "bankserai", "assistant"):
            self.open_bankserai()
            self.term_html(
                f"<span style='color:{PROMPT}'>"
                f"bankser@desktop:~$ {html.escape(command)}</span>"
            )
            self.term_write("bankserAI launched.")

            model = get_local_model()
            if model.available():
                self.term_write(f"Local model: {model.describe()}")
                self.term_write("It loads in the background when the window "
                                "opens.")
            else:
                self.term_write("Local model not found - falling back to "
                                "the built-in knowledge base.")
            return

        if name in ("art", "paint", "draw"):
            self.open_art()
            self.term_html(
                f"<span style='color:{PROMPT}'>"
                f"bankser@desktop:~$ {html.escape(command)}</span>"
            )
            self.term_write("ART Studio launched.")
            return

        if name in ("pasteshell", "ps"):
            self.open_pasteshell()
            self.term_html(
                f"<span style='color:{PROMPT}'>"
                f"bankser@desktop:~$ {html.escape(command)}</span>"
            )
            self.term_write("PASTESHELL launched.")
            return

        if name in ("matrix", "matrixrain", "rain", "cmatrix"):
            self.open_matrix()
            self.term_html(
                f"<span style='color:{PROMPT}'>"
                f"bankser@desktop:~$ {html.escape(command)}</span>"
            )
            self.term_write("MATRIX RAIN launched.")
            self.term_write("Hotkeys: q quit · 0-9 speed · a async · b bold")
            return

        if name in ("ipsea", "weakwifi"):
            self.open_pasteshell()
            self.term_html(
                f"<span style='color:{PROMPT}'>"
                f"bankser@desktop:~$ {html.escape(command)}</span>"
            )
            if name == "ipsea":
                self.paste_window.start_network_scan()
                self.term_write("IPSEA scan running inside PASTESHELL.")
            else:
                self.paste_window.scan_weak_wifi()
                self.term_write("Wi-Fi scan running inside PASTESHELL.")
            return

        if name in ("-welcome", "--welcome", "welcome"):
            self.zoom_panel(self.terminal_win)
            self.term_html(
                f"<span style='color:{PROMPT}'>"
                f"bankser@desktop:~$ {html.escape(command)}</span>"
            )
            self.show_welcome()
            return

        commands = {
            "help": (
                "Commands:\n"
                "  help          show this list\n"
                "  color <1-10>  re-skin the whole desktop\n"
                "  -welcome      draw the ASCII bank picture\n"
                "  ai            launch bankserAI\n"
                "  art           launch the ART drawing studio\n"
                "  matrix        launch the MATRIX RAIN (cmatrix style)\n"
                "  pasteshell    launch the PASTESHELL tool\n"
                "  ipsea         scan the local network\n"
                "  weakwifi      list nearby Wi-Fi networks\n"
                "  date          current date and time\n"
                "  system        platform information\n"
                "  files         list ~/.bankser\n"
                "  clear         clear the terminal\n"
                "  open-home     open the BANKSER' home folder\n"
                "  website       open a browser"
            ),

            "date": datetime.now().strftime(
                "%A %d %B %Y — %H:%M:%S"
            ),

            "system": (
                f"Platform: {platform.platform()}\n"
                f"Python: {platform.python_version()}\n"
                "Shell: BANKSER' hosted prototype"
            ),

            "files": "\n".join(
                item.name for item in HOME.iterdir()
            ) or "(empty)",

            "open-home": "Opening BANKSER' home folder...",

            "website": "Opening browser..."
        }

        result = commands.get(name, f"Command not found: {name}. Type help.")

        self.term_html(
            f"<span style='color:{PROMPT}'>"
            f"bankser@desktop:~$ {html.escape(command)}</span>"
        )
        self.term_write(result)

        if name == "open-home":
            self.open_home()

        elif name == "website":
            webbrowser.open(
                "https://www.google.com/search?q=custom+operating+system"
            )


# ==========================================================
# STARTUP
# ==========================================================

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(f"{APP_NAME} Desktop")
    app.setStyle("Fusion")

    _init_fonts()
    load_theme()
    app.setFont(ui_font(10))
    app.setStyleSheet(build_stylesheet())

    desktop = BankserDesktop()

    boot = BootScreen(lambda: desktop.showFullScreen())
    boot.showFullScreen()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
