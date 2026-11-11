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

New in 2.1
  * Holographic HUD boot sequence (replay with 'boot' in the terminal)
  * Glass windows, aurora wallpaper, floating dock with open-app dots
  * App launcher with search + theme swatches (Ctrl+Space)
  * Live system monitor (CPU / memory / disk / network / processes)
  * Real music player, real file browser, autosaving searchable notes
  * Terminal history, Tab completion, neofetch, calc, ls/cd, top, ...
  * Calendar, volume and power menus in the top panel; toasts

Run:  python bankser_desktop.py   (pip install PySide6 psutil)
"""

import array
import concurrent.futures
import html
import ipaddress
import itertools
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
from urllib.parse import quote_plus
import webbrowser
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    Qt, QTimer, QRect, QRectF, QPointF, QPoint, QPropertyAnimation,
    QEasingCurve, QUrl, Property, QSize, QEvent
)
from PySide6.QtGui import (
    QColor, QPainter, QPen, QFont, QFontDatabase, QFontMetricsF,
    QLinearGradient, QRadialGradient, QPainterPath, QKeySequence,
    QTextCursor, QTextCharFormat, QImage, QIcon, QPixmap, QShortcut, QBrush,
    QConicalGradient
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QTextEdit, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect, QMenu, QAbstractButton, QSizePolicy, QSlider,
    QColorDialog, QFileDialog, QToolButton, QCalendarWidget, QWidgetAction
)

try:
    import psutil          # live CPU / memory / disk / network / processes
except ImportError:
    psutil = None

try:
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
except ImportError:
    QMediaPlayer = QAudioOutput = None

AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".wma"}

# stops ping/netsh flashing console windows when run with pythonw
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# ==========================================================
# CONSTANTS / THEME
# ==========================================================

APP_NAME = "BANKSER'"
VERSION = "2.1"
BOOT_STYLE = "hud"          # "hud" = holographic boot, "classic" = Mint splash

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


def _rgba(hex_color, alpha):
    """Hex colour -> QSS rgba() string with the given alpha (0-255)."""
    c = QColor(hex_color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"


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

        self.accent_soft = _rgba(accent, 45)
        self.accent_faint = _rgba(accent, 26)

        # translucent "glass" surfaces that let the wallpaper glow through
        self.panel_glass = _rgba(_mix("#15181a", accent_dark, 0.10), 205)
        self.window_glass = _rgba(_mix("#202322", accent_dark, 0.12), 228)
        self.header_glass = _rgba(_mix("#2a2e2c", accent_dark, 0.16), 235)
        self.deep_glass = _rgba(_mix("#121514", accent_dark, 0.10), 215)
        self.hairline = "rgba(255, 255, 255, 22)"

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

    elif kind in ("play", "next", "prev"):
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        if kind == "play":
            path = QPainterPath()
            path.moveTo(x + w * 0.32, y + h * 0.20)
            path.lineTo(x + w * 0.80, cy)
            path.lineTo(x + w * 0.32, y + h * 0.80)
            path.closeSubpath()
            painter.drawPath(path)
        else:
            sign = 1 if kind == "next" else -1
            for offset in (-0.17, 0.05):
                ox = cx + sign * w * offset
                path = QPainterPath()
                path.moveTo(ox - sign * w * 0.16, y + h * 0.28)
                path.lineTo(ox + sign * w * 0.12, cy)
                path.lineTo(ox - sign * w * 0.16, y + h * 0.72)
                path.closeSubpath()
                painter.drawPath(path)
            painter.drawRect(QRectF(cx + sign * w * 0.18 - w * 0.04,
                                    y + h * 0.28, w * 0.08, h * 0.44))
        painter.setBrush(Qt.NoBrush)

    elif kind == "pause":
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        for left in (0.28, 0.56):
            painter.drawRoundedRect(
                QRectF(x + w * left, y + h * 0.22, w * 0.16, h * 0.56), 2, 2)
        painter.setBrush(Qt.NoBrush)

    elif kind == "up":
        painter.drawLine(QPointF(cx, y + h * 0.80), QPointF(cx, y + h * 0.22))
        painter.drawLine(QPointF(x + w * 0.28, y + h * 0.44),
                         QPointF(cx, y + h * 0.22))
        painter.drawLine(QPointF(x + w * 0.72, y + h * 0.44),
                         QPointF(cx, y + h * 0.22))

    elif kind == "home":
        path = QPainterPath()
        path.moveTo(x + w * 0.16, y + h * 0.48)
        path.lineTo(cx, y + h * 0.16)
        path.lineTo(x + w * 0.84, y + h * 0.48)
        painter.drawPath(path)
        painter.drawRoundedRect(
            QRectF(x + w * 0.26, y + h * 0.42, w * 0.48, h * 0.42), 2, 2)

    elif kind == "file":
        path = QPainterPath()
        path.moveTo(x + w * 0.26, y + h * 0.12)
        path.lineTo(x + w * 0.58, y + h * 0.12)
        path.lineTo(x + w * 0.76, y + h * 0.30)
        path.lineTo(x + w * 0.76, y + h * 0.88)
        path.lineTo(x + w * 0.26, y + h * 0.88)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(x + w * 0.58, y + h * 0.12),
                         QPointF(x + w * 0.58, y + h * 0.30))
        painter.drawLine(QPointF(x + w * 0.58, y + h * 0.30),
                         QPointF(x + w * 0.76, y + h * 0.30))

    elif kind == "search":
        painter.drawEllipse(QRectF(x + w * 0.18, y + h * 0.18,
                                   w * 0.46, h * 0.46))
        painter.drawLine(QPointF(x + w * 0.58, y + h * 0.58),
                         QPointF(x + w * 0.82, y + h * 0.82))


def icon_pixmap(kind, size, color):
    """Render a symbolic icon into a QIcon (for menus, tiles and lists)."""
    pixmap = QPixmap(size * 2, size * 2)          # 2x for crisp HiDPI
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    draw_icon(painter, kind, QRectF(0, 0, size, size), QColor(color))
    painter.end()
    return QIcon(pixmap)


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
        self.hover = QColor(hover) if hover else None   # None = follow theme
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
            hover_tint = QColor(self.hover if self.hover is not None
                                else MINT)
            hover_tint.setAlpha(45)
            painter.setBrush(hover_tint)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 7, 7)
            painter.setBrush(Qt.NoBrush)

        base = QColor(TEXT_DIM) if self.theme_bound else self.color
        accent = self.hover if self.hover is not None else QColor(MINT_LIGHT)

        color = accent if self._hovered else base
        side = min(self.width(), self.height())     # icon stays square
        draw_icon(painter, self.kind,
                  QRectF((self.width() - side) / 2, 0, side, side), color)


class DockButton(IconButton):
    """The original flat dock icon, plus a dot while its app is open."""

    def __init__(self, kind, tooltip, is_running=None, size=36, parent=None):
        super().__init__(kind, tooltip, size, theme_bound=True, parent=parent)
        self.setFixedSize(size, size + 6)            # room for the dot
        self.is_running = is_running

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.is_running and self.is_running():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(MINT_LIGHT))
            painter.drawEllipse(QPointF(self.width() / 2, self.height() - 3),
                                2.4, 2.4)


# ==========================================================
# TOAST NOTIFICATIONS
# ==========================================================

class Toast(QLabel):
    """Small glass notification that fades in at the top right and away."""

    def __init__(self, parent, text):
        super().__init__(text, parent)
        self.setStyleSheet(f"""
            background: {CURRENT_THEME.header_glass};
            color: {TEXT};
            border: 1px solid {MINT};
            border-radius: 10px;
            padding: 10px 16px;
            font-size: 12px;
        """)
        self.adjustSize()
        self.move(parent.width() - self.width() - 18, 46)

        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        self._fade = QPropertyAnimation(effect, b"opacity", self)
        self._fade.setDuration(220)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self.show()
        self.raise_()
        self._fade.start()
        QTimer.singleShot(2600, self._fade_out)

    def _fade_out(self):
        self._fade.setDirection(QPropertyAnimation.Backward)
        self._fade.finished.connect(self.deleteLater)
        self._fade.start()


# ==========================================================
# SPARKLINE  (CPU history graph in the monitor)
# ==========================================================

class Sparkline(QWidget):
    def __init__(self, parent=None, points=60):
        super().__init__(parent)
        self.values = [0.0] * points
        self.setMinimumHeight(54)

    def push(self, value):
        self.values = self.values[1:] + [value]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        step = w / max(1, len(self.values) - 1)

        line = QPainterPath()
        for i, value in enumerate(self.values):
            point = QPointF(i * step, h - 2 - (h - 4) * value / 100.0)
            line.moveTo(point) if i == 0 else line.lineTo(point)

        area = QPainterPath(line)
        area.lineTo(w, h)
        area.lineTo(0, h)
        area.closeSubpath()
        fill = QLinearGradient(0, 0, 0, h)
        top = QColor(MINT)
        top.setAlpha(110)
        fill.setColorAt(0, top)
        fill.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillPath(area, fill)

        painter.setPen(QPen(QColor(MINT_LIGHT), 1.6))
        painter.drawPath(line)


# ==========================================================
# WALLPAPER  (aurora sky over Mint hills)
# ==========================================================

class Wallpaper(QWidget):
    """Painted once per size/theme into a pixmap; repaints just blit it
    (the glass windows on top make the wallpaper repaint constantly)."""

    _cache_key = None

    def paintEvent(self, event):
        ratio = self.devicePixelRatioF()
        key = (self.width(), self.height(), ratio, CURRENT_THEME.index)
        if key != self._cache_key:
            self._cache = QPixmap(int(self.width() * ratio),
                                  int(self.height() * ratio))
            self._cache.setDevicePixelRatio(ratio)
            self._render(QPainter(self._cache))
            self._cache_key = key
        QPainter(self).drawPixmap(0, 0, self._cache)

    def _render(self, painter):
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        w, h = rect.width(), rect.height()

        gradient = QLinearGradient(0, 0, 0, h)
        gradient.setColorAt(0.0, QColor(WALLPAPER_TOP))
        gradient.setColorAt(0.45, QColor(WALLPAPER_MID))
        gradient.setColorAt(1.0, QColor(WALLPAPER_BOTTOM))
        painter.fillRect(rect, gradient)

        # starfield - seeded so the stars stay put between repaints
        stars = random.Random(1337)
        painter.setPen(Qt.NoPen)
        for _ in range(int(w * h / 5200)):
            sx, sy = stars.random() * w, stars.random() * h * 0.62
            size = stars.choice((0.6, 0.8, 1.0, 1.4))
            painter.setBrush(QColor(255, 255, 255, stars.randint(40, 190)))
            painter.drawEllipse(QPointF(sx, sy), size, size)

        # soft aurora blobs in the theme colours
        for fx, fy, radius, colour, alpha in (
                (0.18, 0.22, 0.42, MINT, 70),
                (0.78, 0.14, 0.38, MINT_LIGHT, 45),
                (0.55, 0.40, 0.30, MINT_DARK, 60)):
            blob = QRadialGradient(w * fx, h * fy, w * radius)
            tint = QColor(colour)
            tint.setAlpha(alpha)
            blob.setColorAt(0, tint)
            blob.setColorAt(1, QColor(0, 0, 0, 0))
            painter.fillRect(rect, blob)

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

        # vignette pulls the eye to the centre
        vignette = QRadialGradient(w * 0.5, h * 0.5, max(w, h) * 0.75)
        vignette.setColorAt(0.6, QColor(0, 0, 0, 0))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 120))
        painter.fillRect(rect, vignette)

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

/* app windows (bankserAI, ART, ...) are real OS windows: solid, square */
QFrame#mintwindow {
    background: %(win)s;
    border: 1px solid %(border)s;
}

QWidget#winheader {
    background: %(header)s;
    border-bottom: 1px solid %(border)s;
}

/* panels on the desktop are glass over the wallpaper, with round corners */
QWidget#desktopbody QFrame#mintwindow {
    background: %(win_glass)s;
    border: 1px solid %(hairline)s;
    border-radius: 12px;
}

QWidget#desktopbody QWidget#winheader {
    background: %(header_glass)s;
    border-bottom: 1px solid %(hairline)s;
    border-top-left-radius: 11px;
    border-top-right-radius: 11px;
}

QLabel#wintitle {
    color: %(text)s;
    font-size: 11px;
    font-weight: bold;
}

QLabel#status {
    color: %(muted)s;
    font-size: 10px;
}

QSlider::groove:horizontal {
    height: 4px;
    background: %(button_bg)s;
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background: %(mint)s;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: %(mint_light)s;
    width: 12px;
    margin: -5px 0;
    border-radius: 6px;
}

QMenu {
    background: %(header)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 10px;
    padding: 6px;
}

QMenu::item {
    padding: 7px 26px 7px 12px;
    border-radius: 6px;
}

QMenu::item:selected {
    background: %(mint)s;
    color: %(on_accent)s;
}

QMenu::separator {
    height: 1px;
    background: %(border)s;
    margin: 5px 8px;
}

QCalendarWidget QWidget {
    alternate-background-color: %(deep)s;
}

QCalendarWidget QWidget#qt_calendar_navigationbar {
    background: %(header)s;
}

QCalendarWidget QToolButton {
    background: transparent;
    color: %(text)s;
    border: none;
    padding: 4px 8px;
    font-weight: bold;
}

QCalendarWidget QAbstractItemView {
    background: %(deep)s;
    color: %(text)s;
    selection-background-color: %(mint)s;
    selection-color: %(on_accent)s;
    border: none;
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
    border-radius: 8px;
    padding: 6px 13px;
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
    background: %(deep_glass)s;
    color: %(text)s;
    border: 1px solid %(hairline)s;
    border-radius: 8px;
    padding: 6px;
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
        "win_glass": theme.window_glass,
        "header_glass": theme.header_glass,
        "deep_glass": theme.deep_glass,
        "hairline": theme.hairline,
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
# HUD BOOT SCREEN  (holographic heads-up-display boot sequence)
# ==========================================================

HUD_CYAN = "#5ad8ff"
HUD_AMBER = "#ffb347"


def _clamp(value):
    return max(0.0, min(1.0, value))


def _hud(alpha=255, colour=HUD_CYAN):
    tint = QColor(colour)
    tint.setAlpha(int(max(0, min(255, alpha))))
    return tint


class HudBootScreen(QWidget):
    """Holographic boot: power-on line, assembling reactor rings, live
    diagnostics, telemetry, decrypting welcome, then rings burst outward
    while the screen fades into the desktop. Any key or click skips."""

    DURATION = 6.2          # seconds before the exit begins
    EXIT = 0.9              # length of the fade into the desktop

    def __init__(self, on_finished):
        super().__init__()
        self.on_finished = on_finished
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setCursor(Qt.BlankCursor)

        self.start = time.monotonic()
        self.exit_at = None
        self._backdrop = None
        self.user = (os.environ.get("USERNAME") or os.environ.get("USER")
                     or "bankser").upper()
        self.log = self._diagnostics()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)

    # ------------------------------------------------------
    # TIMELINE
    # ------------------------------------------------------

    @staticmethod
    def _diagnostics():
        """Boot log lines - real numbers from this machine where we can."""
        memory = _human(psutil.virtual_memory().total) if psutil else "online"
        return [
            ("Power-on self test", "OK"),
            (f"Processor array // {os.cpu_count() or 1} threads", "ONLINE"),
            (f"Memory banks // {memory}", "OK"),
            (f"Host node // {platform.node() or 'local'}", "LINKED"),
            (f"Python runtime // {platform.python_version()}", "OK"),
            ("Holographic display calibration", "OK"),
            ("Filecore storage mount", "OK"),
            ("bsh command shell", "READY"),
            ("bankserAI cognitive core", "STANDBY"),
            ("Security perimeter", "ARMED"),
            ("Desktop interface", "ONLINE"),
        ]

    def elapsed(self):
        return time.monotonic() - self.start

    def _tick(self):
        if self.exit_at is None and self.elapsed() >= self.DURATION:
            self.begin_exit()
        self.update()

    def begin_exit(self):
        """Show the desktop underneath and fade this screen away."""
        if self.exit_at is not None:
            return
        self.exit_at = self.elapsed()
        self.on_finished()
        self.raise_()
        self.activateWindow()
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(int(self.EXIT * 1000))
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.InCubic)
        fade.finished.connect(self.close)
        fade.start()

    def keyPressEvent(self, event):
        self.begin_exit()

    def mousePressEvent(self, event):
        self.begin_exit()

    # ------------------------------------------------------
    # PAINTING
    # ------------------------------------------------------

    def backdrop(self):
        """Static layer (grid, glow, scanlines, vignette), drawn once."""
        if self._backdrop is not None and self._backdrop.size() == self.size():
            return self._backdrop
        w, h = self.width(), self.height()
        pixmap = QPixmap(self.size())
        pixmap.fill(QColor("#02070b"))
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)

        p.setPen(QPen(_hud(13), 1))
        for x in range(0, w, 40):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 40):
            p.drawLine(0, y, w, y)

        glow = QRadialGradient(w / 2, h * 0.46, max(w, h) * 0.45)
        glow.setColorAt(0, _hud(46))
        glow.setColorAt(1, _hud(0))
        p.fillRect(pixmap.rect(), glow)

        p.setPen(QPen(QColor(0, 0, 0, 55), 1))
        for y in range(0, h, 3):
            p.drawLine(0, y, w, y)

        vignette = QRadialGradient(w / 2, h / 2, max(w, h) * 0.72)
        vignette.setColorAt(0.55, QColor(0, 0, 0, 0))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 200))
        p.fillRect(pixmap.rect(), vignette)
        p.end()

        self._backdrop = pixmap
        return pixmap

    def paintEvent(self, event):
        t = self.elapsed()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.drawPixmap(0, 0, self.backdrop())

        if t < 0.6:
            self._power_on(p, t, w, h)

        reveal = _clamp((t - 0.35) / 0.5)
        if reveal <= 0:
            return
        # a few early flickers, like a projector warming up
        flicker = 0.45 if t < 1.1 and int(t * 23) % 5 == 0 else 1.0
        p.setOpacity(reveal * flicker)

        burst = _clamp((t - self.exit_at) / self.EXIT) if self.exit_at else 0
        progress = 1.0 if self.exit_at else _clamp((t - 0.8) / (self.DURATION - 1.8))
        radius = min(w, h) * 0.2 * (1 + 0.8 * burst)
        cx, cy = w / 2, h * 0.46

        self._reactor(p, t, cx, cy, radius, progress)
        self._diagnostics_panel(p, t, w, h)
        self._telemetry_panel(p, t, w, h)
        self._frame(p, t, w, h, progress)
        self._scan_band(p, t, w, h)
        self._welcome(p, t, w, cy + min(w, h) * 0.26)

    def _power_on(self, p, t, w, h):
        """A CRT-style line that snaps open from the centre."""
        width = w * _clamp(t / 0.3)
        height = 2 + h * 0.5 * _clamp((t - 0.3) / 0.3)
        band = QLinearGradient(w / 2 - width / 2, 0, w / 2 + width / 2, 0)
        band.setColorAt(0, _hud(0))
        band.setColorAt(0.5, QColor(225, 250, 255, 230))
        band.setColorAt(1, _hud(0))
        alpha = 1 - _clamp((t - 0.35) / 0.25)
        p.setOpacity(alpha)
        p.fillRect(QRectF(w / 2 - width / 2, h / 2 - height / 2,
                          width, height), band)
        p.setOpacity(1)

    def _reactor(self, p, t, cx, cy, R, progress):
        p.save()
        p.translate(cx, cy)

        def grow(i):        # each ring assembles a little after the last
            return _clamp((t - 0.5 - 0.22 * i) / 0.8)

        # pulsing core
        pulse = 0.75 + 0.25 * math.sin(t * 4)
        core = QRadialGradient(0, 0, R * 0.55)
        core.setColorAt(0, _hud(150 * pulse))
        core.setColorAt(0.6, _hud(40 * pulse))
        core.setColorAt(1, _hud(0))
        p.setPen(Qt.NoPen)
        p.setBrush(core)
        p.drawEllipse(QPointF(0, 0), R * 0.55, R * 0.55)

        # 1. outer segmented ring, slow clockwise
        k = grow(0)
        if k:
            pen = QPen(_hud(190), R * 0.055)
            pen.setCapStyle(Qt.FlatCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            rect = QRectF(-R, -R, R * 2, R * 2)
            for segment in range(12):
                start = -t * 12 + segment * 30
                p.drawArc(rect, int(start * 16), int(22 * k * 16))
            p.setPen(QPen(_hud(70), 1))
            p.drawEllipse(QPointF(0, 0), R * 1.08, R * 1.08)

        # 2. tick ring, counter-clockwise
        k = grow(1)
        if k:
            p.save()
            p.rotate(t * 20)
            for i in range(int(72 * k)):
                major = i % 6 == 0
                p.setPen(QPen(_hud(230 if major else 110), 2 if major else 1))
                angle = math.radians(i * 5)
                inner, outer = R * 0.80, R * (0.89 if major else 0.85)
                p.drawLine(QPointF(math.cos(angle) * inner,
                                   math.sin(angle) * inner),
                           QPointF(math.cos(angle) * outer,
                                   math.sin(angle) * outer))
            p.restore()

        # 3. radar sweep + three fast arcs
        k = grow(2)
        if k:
            sweep = QConicalGradient(0, 0, (t * 140) % 360)
            sweep.setColorAt(0, _hud(110 * k))
            sweep.setColorAt(0.14, _hud(0))
            sweep.setColorAt(1, _hud(0))
            p.setPen(Qt.NoPen)
            p.setBrush(sweep)
            p.drawEllipse(QPointF(0, 0), R * 0.66, R * 0.66)

            pen = QPen(_hud(235), 3)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            rect = QRectF(-R * 0.72, -R * 0.72, R * 1.44, R * 1.44)
            for arc in range(3):
                start = t * 95 + arc * 120
                p.drawArc(rect, int(start * 16), int(70 * k * 16))

        # 4. progress ring
        k = grow(3)
        if k:
            rect = QRectF(-R * 0.5, -R * 0.5, R, R)
            p.setPen(QPen(_hud(45), 6))
            p.drawEllipse(rect)
            pen = QPen(_hud(255), 6)
            pen.setCapStyle(Qt.FlatCap)
            p.setPen(pen)
            p.drawArc(rect, 90 * 16, -int(360 * progress * k * 16))

            p.save()
            p.rotate(-t * 35)
            dashed = QPen(_hud(120), 1, Qt.DashLine)
            p.setPen(dashed)
            p.drawEllipse(QPointF(0, 0), R * 0.41, R * 0.41)
            p.restore()

            number = QFont(UI_FONT_NAME)
            number.setPixelSize(max(12, int(R * 0.2)))
            number.setBold(True)
            p.setFont(number)
            p.setPen(_hud(255))
            p.drawText(QRectF(-R * 0.4, -R * 0.2, R * 0.8, R * 0.28),
                       Qt.AlignCenter, f"{int(progress * 100)}%")
            label = QFont(UI_FONT_NAME)
            label.setPixelSize(max(8, int(R * 0.055)))
            label.setLetterSpacing(QFont.AbsoluteSpacing, 2)
            p.setFont(label)
            p.setPen(_hud(170))
            p.drawText(QRectF(-R * 0.4, R * 0.08, R * 0.8, R * 0.12),
                       Qt.AlignCenter, "SYSTEM INTEGRITY")

        p.restore()

    def _heading(self, p, x, y, width, text):
        font = QFont(UI_FONT_NAME)
        font.setPixelSize(12)
        font.setBold(True)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 3)
        p.setFont(font)
        p.setPen(_hud(230))
        p.drawText(QPointF(x, y), text)
        p.setPen(QPen(_hud(120), 1))
        p.drawLine(QPointF(x, y + 8), QPointF(x + width, y + 8))
        p.setPen(QPen(_hud(255), 3))
        p.drawLine(QPointF(x, y + 8), QPointF(x + 40, y + 8))

    def _diagnostics_panel(self, p, t, w, h):
        x, y, width = w * 0.05, h * 0.2, w * 0.27
        self._heading(p, x, y, width, "BOOT DIAGNOSTICS")
        font = QFont(MONO_FONT_NAME)
        font.setPixelSize(13)
        p.setFont(font)
        metrics = QFontMetricsF(font)

        for row, (label, status) in enumerate(self.log):
            appear = 1.0 + row * 0.36
            if t < appear:
                break
            typed = _clamp((t - appear) / 0.28)
            line_y = y + 36 + row * 24
            shown = label[:int(len(label) * typed)]
            p.setPen(_hud(200))
            p.drawText(QPointF(x, line_y), "› " + shown)
            if typed < 1:
                continue
            warm = status in ("STANDBY", "ARMED")
            tag = f"[{status}]"
            tag_x = x + width - metrics.horizontalAdvance(tag)
            dots_from = x + metrics.horizontalAdvance("› " + label) + 6
            p.setPen(_hud(60))
            dots = "." * max(0, int((tag_x - dots_from - 6)
                                    / max(1, metrics.horizontalAdvance("."))))
            p.drawText(QPointF(dots_from, line_y), dots)
            p.setPen(_hud(255, HUD_AMBER if warm else "#9dfcff"))
            p.drawText(QPointF(tag_x, line_y), tag)

    def _telemetry_panel(self, p, t, w, h):
        x, y, width = w * 0.68, h * 0.2, w * 0.27
        self._heading(p, x, y, width, "TELEMETRY")

        font = QFont(MONO_FONT_NAME)
        font.setPixelSize(12)
        p.setFont(font)
        show = _clamp((t - 0.9) / 0.6)
        for i, name in enumerate(("CPU", "MEM", "NET", "PWR", "I/O", "THM")):
            bar_y = y + 30 + i * 24
            level = 0.55 + 0.35 * math.sin(t * (1.3 + i * 0.37) + i * 1.7)
            level *= show
            p.setPen(_hud(200))
            p.drawText(QPointF(x, bar_y + 10), name)
            track = QRectF(x + 44, bar_y, width - 96, 10)
            p.setPen(Qt.NoPen)
            p.setBrush(_hud(35))
            p.drawRect(track)
            p.setBrush(_hud(220, HUD_AMBER if level > 0.85 else HUD_CYAN))
            p.drawRect(QRectF(track.x(), track.y(),
                              track.width() * level, track.height()))
            p.setPen(_hud(170))
            p.drawText(QPointF(x + width - 44, bar_y + 10),
                       f"{int(level * 100):3d}%")

        # voice-style waveform
        box = QRectF(x, y + 186, width, 70)
        p.setPen(QPen(_hud(70), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(box)
        wave = QPainterPath()
        steps = 90
        for i in range(steps + 1):
            fx = i / steps
            envelope = math.sin(math.pi * fx)
            value = (math.sin(fx * 23 + t * 9) * 0.5
                     + math.sin(fx * 51 - t * 13) * 0.3
                     + math.sin(fx * 7 + t * 3) * 0.2)
            point = QPointF(box.x() + fx * box.width(),
                            box.center().y()
                            + value * envelope * box.height() * 0.42 * show)
            wave.moveTo(point) if i == 0 else wave.lineTo(point)
        p.setPen(QPen(_hud(240), 1.6))
        p.drawPath(wave)

        # scrolling hex stream
        p.setPen(_hud(110))
        tick = int(t * 12)
        for row in range(6):
            rng = random.Random(tick * 31 + row)
            line = " ".join(f"{rng.randrange(256):02X}" for _ in range(8))
            p.drawText(QPointF(x, y + 285 + row * 18), line)

    def _frame(self, p, t, w, h, progress):
        margin, arm = 28, 70
        p.setPen(QPen(_hud(170), 2))
        for sx, sy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            cx = w - margin if sx else margin
            cy = h - margin if sy else margin
            dx = -arm if sx else arm
            dy = -arm if sy else arm
            p.drawLine(QPointF(cx, cy), QPointF(cx + dx, cy))
            p.drawLine(QPointF(cx, cy), QPointF(cx, cy + dy))

        font = QFont(UI_FONT_NAME)
        font.setPixelSize(12)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 3)
        p.setFont(font)
        p.setPen(_hud(210))
        p.drawText(QRectF(0, margin - 6, w, 20), Qt.AlignCenter,
                   f"{APP_NAME} SYSTEMS  //  BOOT SEQUENCE  v{VERSION}")
        p.drawText(QRectF(margin + 12, h - margin - 22, w / 2, 20),
                   Qt.AlignLeft, f"OPERATOR: {self.user}")
        p.drawText(QRectF(w / 2, h - margin - 22, w / 2 - margin - 12, 20),
                   Qt.AlignRight, datetime.now().strftime("%d.%m.%Y  %H:%M:%S"))

        # long progress line along the bottom
        line_w = w * 0.4
        left = (w - line_w) / 2
        base = h - margin - 12
        p.setPen(QPen(_hud(50), 2))
        p.drawLine(QPointF(left, base), QPointF(left + line_w, base))
        p.setPen(QPen(_hud(255), 2))
        p.drawLine(QPointF(left, base), QPointF(left + line_w * progress, base))

    def _scan_band(self, p, t, w, h):
        y = (t * 0.45 % 1.0) * h
        band = QLinearGradient(0, y - 60, 0, y + 6)
        band.setColorAt(0, _hud(0))
        band.setColorAt(0.9, _hud(26))
        band.setColorAt(1, _hud(70))
        p.fillRect(QRectF(0, y - 60, w, 66), band)

    def _welcome(self, p, t, w, y):
        start = self.DURATION - 1.5
        if t < start:
            return

        def decrypt(text, begin):
            """Random glyphs that lock into the real letters one by one."""
            rng = random.Random(int(t * 30))
            return "".join(
                ch if ch == " " or t >= begin + 0.035 * i + 0.3
                else rng.choice("ABCDEF0123456789#%&@$")
                for i, ch in enumerate(text))

        small = QFont(UI_FONT_NAME)
        small.setPixelSize(13)
        small.setLetterSpacing(QFont.AbsoluteSpacing, 5)
        p.setFont(small)
        p.setPen(_hud(220, HUD_AMBER))
        p.drawText(QRectF(0, y, w, 22), Qt.AlignCenter,
                   decrypt("ALL SYSTEMS ONLINE", start))

        big = QFont(UI_FONT_NAME)
        big.setPixelSize(30)
        big.setBold(True)
        big.setLetterSpacing(QFont.AbsoluteSpacing, 6)
        p.setFont(big)
        text = decrypt(f"WELCOME BACK, {self.user}", start + 0.25)
        rect = QRectF(0, y + 26, w, 44)
        p.setPen(_hud(55))
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):    # soft glow
            p.drawText(rect.translated(dx, dy), Qt.AlignCenter, text)
        p.setPen(QColor("#e8fbff"))
        p.drawText(rect, Qt.AlignCenter, text)


# ==========================================================
# MINT WINDOW  (panelled window with a Cinnamon title bar)
# ==========================================================

class TitleBar(QWidget):
    """Window header you can grab to move the window.

    App windows (bankserAI, ART, ...) move as whole top-level windows.
    Desktop panels set `owner.on_drag_start`; it pulls the panel out of
    the grid so it can float freely inside the desktop."""

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self._press = None              # where the button went down
        self._offset = None             # set once the drag really starts
        self.setCursor(Qt.OpenHandCursor)

    def _target(self):
        return self.owner if self.owner.on_drag_start else self.window()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        self._press = event.globalPosition().toPoint()
        self._target().raise_()

    def mouseMoveEvent(self, event):
        if self._press is None:
            return super().mouseMoveEvent(event)
        now = event.globalPosition().toPoint()
        if self._offset is None:
            # a plain click must not pull a panel out of the grid
            if (now - self._press).manhattanLength() < 5:
                return
            start = self.owner.on_drag_start
            if start and not start(self.owner):
                self._press = None      # e.g. the panel is maximized
                return
            self._offset = self._press - self._target().mapToGlobal(
                QPoint(0, 0))
            self.setCursor(Qt.ClosedHandCursor)
        target = self._target()
        top_left = now - self._offset
        if target.isWindow():
            target.move(top_left)
            return
        # keep at least the title bar inside the desktop
        area = target.parentWidget().rect()
        point = target.parentWidget().mapFromGlobal(top_left)
        x = min(max(point.x(), 80 - target.width()), area.width() - 80)
        y = min(max(point.y(), 0), area.height() - self.height())
        target.move(x, y)

    def mouseReleaseEvent(self, event):
        self._press = self._offset = None
        self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.owner._toggle_maximize()


class MintWindow(QFrame):
    def __init__(self, title, icon_kind, on_close=None, on_maximize=None,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("mintwindow")
        self.on_drag_start = None       # set by the desktop for its panels

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = TitleBar(self)
        header.setObjectName("winheader")
        header.setAttribute(Qt.WA_StyledBackground)
        header.setFixedHeight(36)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 6, 0)
        header_layout.setSpacing(8)

        icon = IconWidget(icon_kind, 16, MINT_LIGHT, theme_bound=True)
        header_layout.addWidget(icon)

        label = QLabel(title)
        label.setObjectName("wintitle")
        title_font = ui_font(9, bold=True)
        title_font.setLetterSpacing(QFont.AbsoluteSpacing, 1.6)
        label.setFont(title_font)
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
        self.body.setContentsMargins(12, 11, 12, 12)
        self.body.setSpacing(8)

        outer.addWidget(header)
        outer.addLayout(self.body, 1)

        self._on_close = on_close

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 140))
        shadow.setOffset(0, 6)
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
        self.subtitle = ""
        self.setMinimumSize(96, 130)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._anim = QPropertyAnimation(self, b"shown", self)
        self._anim.setDuration(600)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def _get_shown(self):
        return float(self.value)

    def _set_shown(self, value):
        self.value = value
        self.update()

    shown = Property(float, _get_shown, _set_shown)

    def set_value(self, value, subtitle=""):
        """Glide the ring to a new percentage."""
        self.subtitle = subtitle
        self._anim.stop()
        self._anim.setStartValue(float(self.value))
        self._anim.setEndValue(float(value))
        self._anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        label_h = 32
        size = min(w, h - label_h) - 16
        if size <= 10:
            return

        rect = QRectF((w - size) / 2.0, 6, size, size)

        track = QPen(QColor(CURRENT_THEME.gauge_track), 8)
        track.setCapStyle(Qt.RoundCap)
        painter.setPen(track)
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(rect, 0, 360 * 16)

        # ring turns warm when the value runs high
        hot = QColor("#ff6b6b") if self.value > 85 else QColor(MINT_LIGHT)
        ring = QLinearGradient(rect.topLeft(), rect.bottomRight())
        ring.setColorAt(0, hot)
        ring.setColorAt(1, QColor(MINT_DARK))
        value_pen = QPen(QBrush(ring), 8)
        value_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(value_pen)
        painter.drawArc(rect, 90 * 16, -int(self.value * 3.6 * 16))

        painter.setFont(ui_font(14, bold=True))
        painter.setPen(QColor(TEXT))
        painter.drawText(rect, Qt.AlignCenter, f"{round(self.value)}%")

        painter.setFont(ui_font(9, bold=True))
        painter.setPen(QColor(TEXT_DIM))
        painter.drawText(QRectF(0, h - label_h, w, 16),
                         Qt.AlignCenter, self.title)
        if self.subtitle:
            painter.setFont(ui_font(8))
            painter.setPen(QColor(TEXT_MUTED))
            painter.drawText(QRectF(0, h - 16, w, 16),
                             Qt.AlignCenter, self.subtitle)


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

            network = self.find_local_network()
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
                                   timeout=2, creationflags=NO_WINDOW)
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

    def find_local_network(self):
        """The IPv4 network of the adapter that holds the default route.

        Works on any Windows language: the local IP comes from the routing
        table (a UDP 'connect' sends no packets), and the mask is simply the
        first 255.x.x.x address printed after that IP in ipconfig."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.connect(("192.0.2.1", 9))     # TEST-NET, never sent
                local_ip = probe.getsockname()[0]
        except OSError:
            return None
        if local_ip.startswith(("0.", "127.")):
            return None

        mask = "255.255.255.0"
        output = self.run_command(["ipconfig"]) or ""
        at = output.find(local_ip)
        if at >= 0:
            found = re.search(r"\b(255\.\d{1,3}\.\d{1,3}\.\d{1,3})\b",
                              output[at + len(local_ip):])
            if found:
                mask = found.group(1)

        try:
            network = ipaddress.ip_network(f"{local_ip}/{mask}", strict=False)
        except ValueError:
            return None
        if network.num_addresses > 1024:
            # a /16 would mean 65k pings; scan the /24 around us instead
            self.scan_queue.put(f"{network} is large - scanning the /24 "
                                "around this computer only.")
            network = ipaddress.ip_network(f"{local_ip}/24", strict=False)
        return network

    @staticmethod
    def run_command(command):
        """Run a system command and return its text output (or None)."""
        try:
            result = subprocess.run(command, capture_output=True,
                                    timeout=20, creationflags=NO_WINDOW)
            if result.returncode != 0 and not result.stdout:
                return None
            return result.stdout.decode("utf-8", errors="ignore")
        except (OSError, subprocess.SubprocessError):
            return None

    # ------------------------------------------------------
    # WEAK WIFI SCANNER
    # ------------------------------------------------------

    def scan_weak_wifi(self):
        """Start the Wi-Fi scan on a worker (netsh can take ~20 s)."""
        if self.scan_running:
            self.console_print("A scan is already running!")
            return
        self.scan_running = True
        self.console_print("\n[ WEAKWIFI ] Scanning nearby Wi-Fi...")
        threading.Thread(target=self.wifi_worker, daemon=True).start()

    def wifi_worker(self):
        try:
            self._wifi_scan(self.scan_queue.put)
        except Exception as error:
            self.scan_queue.put(f"Wi-Fi scan error: {error}")
        finally:
            self.scan_queue.put("__SCAN_FINISHED__")

    @staticmethod
    def _wifi_scan(say):
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "networks", "mode=bssid"],
                capture_output=True, timeout=20, creationflags=NO_WINDOW)
        except (OSError, subprocess.SubprocessError):
            say("Wi-Fi scan failed: 'netsh' is not available here.")
            return

        output = result.stdout.decode("utf-8", errors="ignore")
        if result.returncode != 0:
            # e.g. Windows 11 needs Location turned on - netsh says so
            say("Wi-Fi scan failed:")
            say(output.strip() or "Check your Wi-Fi adapter.")
            return

        networks = {}
        current_ssid = None

        for line in output.splitlines():
            ssid_match = re.match(r"\s*SSID \d+ :\s*(.*)", line)
            # only signal lines end in '%', whatever the Windows language
            signal_match = re.match(r"[^:]*:\s*(\d+)\s*%\s*$", line)

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

        say("=" * 45)
        say(" NETWORK NAME          SIGNAL")
        say("=" * 45)

        for name, signal in results:
            say(f"{name[:22]:<24} {signal:.0f}%")

            if signal < 30:
                say("  STATUS: VERY WEAK")
            elif signal < 60:
                say("  STATUS: WEAK")
            elif signal < 80:
                say("  STATUS: GOOD")
            else:
                say("  STATUS: STRONG")

            say("-" * 45)

        say(f"\nFound {len(results)} Wi-Fi networks.")
        if not results:
            say("Is Wi-Fi switched on?")

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


MAX_DIGITS = 4000                  # under Python's 4300-digit str() limit
MAX_BITS = int(MAX_DIGITS * 3.33)


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
            # huge integers freeze the whole app (CPython holds the GIL
            # during one big multiplication), so refuse them up front
            if (isinstance(node.op, ast.Pow) and abs(left) > 1 and right > 0
                    and right * math.log10(abs(left)) > MAX_DIGITS):
                raise ValueError("result too large")
            result = operation(left, right)
            if isinstance(result, int) and result.bit_length() > MAX_BITS:
                raise ValueError("result too large")
            return result
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
        self.shutting_down = False  # set by stop(); halts any startup
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

        # only our own '--alias qwen'; a generic id like 'local' could be a
        # server the user runs themselves
        for entry in body.get("data") or []:
            if entry.get("id") == "qwen":
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
            port_was_free = self._port_free(self.port)

            try:
                process = subprocess.Popen(
                    self._command(),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=NO_WINDOW,
                )
            except OSError as error:
                self.state = "failed"
                self.error = str(error)
                return False

            # record it right away: if the desktop quits during the wait
            # below, stop() must still find and kill it
            self.process = process
            self.pid = process.pid
            self._write_pid(process.pid)
            if self.shutting_down:
                self.stop()
                return False

            time.sleep(2.5)

            if process.poll() is None:
                return True

            self.process = self.pid = None
            if port_was_free:
                # nothing else had the port - the server itself is broken
                self.state = "failed"
                self.error = ("llama-server exited on startup - check the "
                              "model file and runtime in ~/.bankser")
                return False
            # the port was taken; try the next one

        self.state = "failed"
        self.error = "could not start llama-server (every port is busy)"
        return False

    @staticmethod
    def _port_free(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind((AI_SERVER_HOST, port))
                return True
            except OSError:
                return False

    @staticmethod
    def _is_llama_server(pid):
        """Only ever kill a process that really is llama-server."""
        if not pid:
            return False
        try:
            if psutil is not None:
                return psutil.Process(pid).name().lower().startswith(
                    "llama-server")
            if os.name == "nt":
                listing = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
                    capture_output=True, text=True, timeout=10,
                    creationflags=NO_WINDOW).stdout.lower()
                return "llama-server" in listing
        except Exception:
            return False
        return False

    def ensure_ready(self, timeout=600):
        """Start the server if needed and wait until it can answer."""
        with self.lock:
            if self.state == "ready" and self._alive():
                return True

            if self.shutting_down:
                return False

            # adopt a server that is already running this model (usually an
            # orphan from a crashed session); remember its PID only once it
            # is confirmed to be llama-server, so stop() never kills anything
            # else
            if self.process is None and self._serving_our_model():
                self.state = "ready"
                pid = self._read_pid() or self._pid_on_port(self.port)
                self.pid = pid if self._is_llama_server(pid) else None
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
                process = self.process          # stop() may clear it
                if self.shutting_down or process is None:
                    return False

                if self._alive():
                    self.state = "ready"
                    return True

                if process.poll() is not None:
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
        self.shutting_down = True      # a startup in progress gives up
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

        # an adopted server has to be killed by its process id - re-check
        # the name in case Windows reused the PID for something else
        if not self._is_llama_server(pid):
            return
        if os.name == "nt":
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

        # a site name only counts right after an "open" style verb, or on
        # its own - "explain how a bank works" must not open a bank site
        bare = self._clean_site(lowered)
        for name, url in AI_SITES.items():
            if bare == name or re.search(
                    rf"\b(open|go to|visit|launch|load|browse)\s+(the\s+)?"
                    rf"{re.escape(name)}\b", lowered):
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
                return base + quote_plus(query)

        # "can you search the web for X" - whole words only, so 'research'
        # or 'format' never trigger it
        match = re.search(r"\bsearch(?:\s+(?:the\s+web|online|google))?"
                          r"\s+for\s+(.+)$", lowered)
        if match:
            query = match.group(1).strip(" ?!.")
            if query:
                return "https://www.google.com/search?q=" + quote_plus(query)

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

        bare = lowered.strip(" .!?:")

        for app, aliases in self.AI_APP_ALIASES.items():
            for alias in aliases:
                if bare == alias or self._verb_then_alias(lowered, alias):
                    return app

        return None

    def _verb_then_alias(self, lowered, alias):
        """'open the matrix rain' yes; 'run python in a terminal' no -
        the app name must follow the verb within two words."""
        name = re.escape(alias).replace(r"\ ", r"\s+")
        pattern = (self.AI_VERBS.pattern + r"\s+(?:\S+\s+){0,2}?"
                   + name + r"\b")
        return bool(re.search(pattern, lowered))

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
        self.setAttribute(Qt.WA_DeleteOnClose)   # free it, don't just hide
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
            "'explain how compound interest works'")
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

                if url and not re.match(r"https?://", url, re.IGNORECASE):
                    # a model answer must never open local files/programs
                    self.say(f"Blocked a non-web link: {url}", "ai")
                elif url:
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
        # stop acting on answers that arrive after the window is gone
        self.drain_timer.stop()
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
        self.dirty = False             # unsaved changes?

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
        self.dirty = True              # every edit pushes undo first
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

        # scanline fill over the raw 32-bit pixels: fills whole row runs at
        # once instead of one QPoint per pixel (which froze the UI for
        # seconds and used hundreds of MB on a blank canvas)
        # ponytail: still pure Python (~0.5 s for a full 1000x700 fill);
        # use numpy/scipy if huge photos need instant fills
        if self.image.format() != QImage.Format_ARGB32:
            self.image = self.image.convertToFormat(QImage.Format_ARGB32)
        width, height = self.image.width(), self.image.height()
        pixels = array.array("I")
        pixels.frombytes(bytes(self.image.constBits())[:width * height * 4])

        target = pixels[point.y() * width + point.x()]
        replacement = self.color.rgba() & 0xFFFFFFFF
        if target == replacement:
            return

        stack = [(point.x(), point.y())]
        while stack:
            x, y = stack.pop()
            row = y * width
            if pixels[row + x] != target:
                continue
            left = x
            while left > 0 and pixels[row + left - 1] == target:
                left -= 1
            right = x
            while right < width - 1 and pixels[row + right + 1] == target:
                right += 1
            pixels[row + left:row + right + 1] = \
                array.array("I", [replacement]) * (right - left + 1)

            # seed one point per run of target pixels above and below
            for ny in (y - 1, y + 1):
                if not 0 <= ny < height:
                    continue
                above = ny * width
                in_run = False
                for nx in range(left, right + 1):
                    if pixels[above + nx] == target:
                        if not in_run:
                            stack.append((nx, ny))
                            in_run = True
                    else:
                        in_run = False

        self.image = QImage(pixels.tobytes(), width, height, width * 4,
                            QImage.Format_ARGB32).copy()
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
        self.dirty = False
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
        self.setAttribute(Qt.WA_DeleteOnClose)   # frees the undo history
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
        if path and self.canvas.save(path):
            self.file_label.setText(Path(path).name)
            self.canvas.dirty = False
            return True
        return False

    def keyPressEvent(self, event):
        key = event.key()
        shortcuts = {Qt.Key_P: "pencil", Qt.Key_B: "brush",
                     Qt.Key_E: "eraser", Qt.Key_L: "line",
                     Qt.Key_R: "rect", Qt.Key_O: "ellipse",
                     Qt.Key_F: "fill", Qt.Key_I: "picker"}

        # plain letters pick tools; Ctrl+O etc. fall through to the menu keys
        no_modifier = not (event.modifiers() & (
            Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))
        if key in shortcuts and no_modifier:
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
        if self.canvas.dirty:
            answer = QMessageBox.question(
                self, "ART Studio", "Save your drawing before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save)
            if answer == QMessageBox.Cancel or (
                    answer == QMessageBox.Save and not self.save_image()):
                event.ignore()
                return
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

        if key == "q" or event.key() == Qt.Key_Escape:
            window = self.window()
            window.close()
            return

        if key in MATRIX_COLOR_KEYS:
            self.set_color(MATRIX_COLOR_KEYS[key])
            return

        if len(key) == 1 and key in "0123456789":   # not '²' and friends
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
        self.setAttribute(Qt.WA_DeleteOnClose)
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

TERMINAL_COMMANDS = (
    "help", "color", "-welcome", "ai", "art", "matrix", "pasteshell",
    "ipsea", "weakwifi", "neofetch", "calc", "ls", "cd", "pwd", "open",
    "top", "uptime", "history", "echo", "notify", "boot", "whoami", "date",
    "system", "files", "clear", "open-home", "website",
)


def _human(size):
    """Bytes -> '1.4 MB'."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024.0


def _is_dir(path):
    """Path.is_dir() that treats 'access denied' as 'not a folder'."""
    try:
        return path.is_dir()
    except OSError:
        return False


def _duration(seconds):
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes = seconds // 60
    return (f"{days}d " if days else "") + f"{hours}h {minutes:02d}m"


class HistoryLineEdit(QLineEdit):
    """Terminal input: Up/Down walk the history, Tab completes commands."""

    def __init__(self, completions=(), parent=None):
        super().__init__(parent)
        self.history = []
        self.index = 0
        self.completions = sorted(completions)

    def remember(self, command):
        if not self.history or self.history[-1] != command:
            self.history.append(command)
        self.index = len(self.history)

    def event(self, event):
        # Tab normally moves focus, so catch it before QWidget does
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Tab:
            text = self.text()
            matches = [c for c in self.completions if c.startswith(text)]
            if len(matches) == 1:
                self.setText(matches[0] + " ")
            elif matches:
                self.setText(os.path.commonprefix(matches))
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up and self.history:
            self.index = max(0, self.index - 1)
            self.setText(self.history[self.index])
            return
        if event.key() == Qt.Key_Down and self.history:
            self.index = min(len(self.history), self.index + 1)
            self.setText(self.history[self.index]
                         if self.index < len(self.history) else "")
            return
        super().keyPressEvent(event)


class Launcher(QWidget):
    """Full-desktop app launcher: search, app grid, theme swatches."""

    COLUMNS = 5

    def __init__(self, desktop):
        super().__init__(desktop.wallpaper)
        self.desktop = desktop
        self.hide()

        outer = QVBoxLayout(self)
        outer.addStretch(1)
        center = QHBoxLayout()
        outer.addLayout(center)
        outer.addStretch(2)

        self.card = QFrame()
        self.card.setObjectName("launchcard")
        self.card.setFixedWidth(640)
        center.addStretch(1)
        center.addWidget(self.card)
        center.addStretch(1)

        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(60)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 12)
        self.card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        title = QLabel(f"{APP_NAME}  Applications")
        title.setObjectName("launchtitle")
        title.setFont(ui_font(15, bold=True))
        layout.addWidget(title)

        self.search = QLineEdit()
        self.search.setObjectName("launchsearch")
        self.search.setFixedHeight(40)
        self.search.setPlaceholderText(
            "Search apps…   Enter opens · Esc closes")
        self.search.textChanged.connect(self.filter)
        self.search.returnPressed.connect(self.launch_first)
        layout.addWidget(self.search)

        self.grid = QGridLayout()
        self.grid.setSpacing(8)
        layout.addLayout(self.grid)

        self.tiles = []
        for kind, name, action, _running in desktop.apps:
            tile = QToolButton(self.card)
            tile.setObjectName("tile")
            tile.setText(name)
            tile.setIconSize(QSize(30, 30))
            tile.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            tile.setFixedSize(110, 86)
            tile.setCursor(Qt.PointingHandCursor)
            tile.kind = kind
            tile.clicked.connect(lambda _=False, a=action: self.run(a))
            self.tiles.append((name, tile, action))

        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        label = QLabel("THEME")
        label.setObjectName("dim")
        bottom.addWidget(label)

        self.swatches = []
        for theme in THEMES:
            swatch = QPushButton()
            swatch.setFixedSize(24, 24)
            swatch.setToolTip(theme.name.title())
            swatch.setCursor(Qt.PointingHandCursor)
            swatch.clicked.connect(
                lambda _=False, n=theme.index: self.pick_theme(n))
            bottom.addWidget(swatch)
            self.swatches.append((theme, swatch))

        bottom.addStretch(1)
        for text, action in (("About", desktop.show_about),
                             ("Shut down", desktop.close)):
            button = QPushButton(text)
            button.clicked.connect(lambda _=False, a=action: self.run(a))
            bottom.addWidget(button)
        layout.addLayout(bottom)

        self.visible_tiles = []
        self.filter("")

    def restyle(self):
        theme = CURRENT_THEME
        self.setStyleSheet(f"""
            QFrame#launchcard {{
                background: {theme.header_glass};
                border: 1px solid {_rgba(MINT, 120)};
                border-radius: 18px;
            }}
            QLabel#launchtitle {{ color: {TEXT}; }}
            QLineEdit#launchsearch {{
                font-size: 14px;
                padding: 4px 12px;
                border-radius: 10px;
            }}
            QToolButton#tile {{
                background: transparent;
                color: {TEXT};
                border: none;
                border-radius: 12px;
                padding: 6px;
                font-size: 11px;
            }}
            QToolButton#tile:hover {{ background: {theme.accent_soft}; }}
        """)
        for _name, tile, _action in self.tiles:
            tile.setIcon(icon_pixmap(tile.kind, 30, MINT_LIGHT))
        for swatch_theme, swatch in self.swatches:
            ring = TEXT if swatch_theme is CURRENT_THEME else "transparent"
            swatch.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 {swatch_theme.accent_light},
                        stop:1 {swatch_theme.accent_dark});
                    border: 2px solid {ring};
                    border-radius: 12px;
                    padding: 0;
                }}
            """)

    def filter(self, text):
        while self.grid.count():
            self.grid.takeAt(0)
        needle = text.strip().lower()
        self.visible_tiles = [t for t in self.tiles if needle in t[0].lower()]
        for _name, tile, _action in self.tiles:
            tile.hide()
        for i, (_name, tile, _action) in enumerate(self.visible_tiles):
            self.grid.addWidget(tile, i // self.COLUMNS, i % self.COLUMNS)
            tile.show()

    def launch_first(self):
        if self.visible_tiles:
            self.run(self.visible_tiles[0][2])

    def run(self, action):
        self.hide()
        action()

    def pick_theme(self, number):
        self.desktop.set_theme(number)
        self.restyle()

    def open(self):
        self.setGeometry(self.parentWidget().rect())
        self.restyle()
        self.search.clear()
        self.show()
        self.raise_()
        self.search.setFocus()

    def paintEvent(self, event):
        QPainter(self).fillRect(self.rect(), QColor(0, 0, 0, 150))

    def mousePressEvent(self, event):
        if not self.card.geometry().contains(event.position().toPoint()):
            self.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)


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
        self.started = time.time()

        def window_open(attr):
            return lambda: (getattr(self, attr, None) is not None
                            and getattr(self, attr).isVisible())

        def panel_open(attr):
            return lambda: getattr(self, attr).isVisible()

        # one list drives the dock, the launcher and the 'open' command
        self.apps = [
            ("notes", "Notes", self.focus_notes, panel_open("notes_win")),
            ("folder", "Filecore", self.focus_files, panel_open("files_win")),
            ("terminal", "Terminal", self.focus_terminal,
             panel_open("terminal_win")),
            ("monitor", "System Monitor", self.focus_monitor,
             panel_open("monitor_win")),
            ("music", "Music", self.focus_music, panel_open("music_win")),
            ("spark", "bankserAI", self.open_bankserai,
             window_open("ai_window")),
            ("brush", "ART Studio", self.open_art, window_open("art_window")),
            ("matrix", "Matrix Rain", self.open_matrix,
             window_open("matrix_window")),
            ("skull", "PASTESHELL", self.open_pasteshell,
             window_open("paste_window")),
            ("lock", "Security Center", self.show_security, None),
        ]

        # never leave the local model server running behind our back
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown_model)

        self.build_desktop()
        self.launcher = Launcher(self)

        for keys, action in (("Ctrl+Space", self.toggle_launcher),
                             ("Ctrl+Alt+T", self.focus_terminal),
                             ("Ctrl+Alt+F", self.focus_files),
                             ("Ctrl+S", self.save_notes),
                             ("F11", self.toggle_fullscreen)):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.activated.connect(action)

        self._net_last = None
        self._monitor_ticks = 0
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.update_monitor)
        self.monitor_timer.start(1500)
        self.update_monitor()

        # dock dots follow which apps are open
        self.dock_timer = QTimer(self)
        self.dock_timer.timeout.connect(
            lambda: [b.update() for b in self.dock_buttons])
        self.dock_timer.start(600)

    # ------------------------------------------------------
    # LAYOUT
    # ------------------------------------------------------

    def build_desktop(self):

        root = QVBoxLayout(self.wallpaper)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self.build_top_panel())

        body = QWidget()
        body.setObjectName("desktopbody")
        body.setAttribute(Qt.WA_TranslucentBackground)
        grid = QGridLayout(body)
        self.grid = grid
        grid.setContentsMargins(14, 14, 14, 6)
        grid.setSpacing(12)
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
        self.floating = {}      # panel -> geometry, once dragged out of grid
        for window in self.panel_home:
            window.on_drag_start = self.float_panel

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
        panel.setFixedHeight(36)
        panel.setObjectName("toppanel")
        panel.setAttribute(Qt.WA_StyledBackground)
        self.top_panel = panel
        self.style_top_panel()

        layout = QHBoxLayout(panel)
        layout.setContentsMargins(8, 4, 6, 4)
        layout.setSpacing(4)

        # --- menu button (Mint style)
        menu_button = QPushButton(f"  {APP_NAME}")
        menu_button.setToolTip("Applications  (Ctrl+Space)")
        menu_button.setCursor(Qt.PointingHandCursor)
        menu_button.setFixedHeight(26)
        self.menu_button = menu_button
        self.style_menu_button()
        menu_button.clicked.connect(self.toggle_launcher)
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

        self.battery_label = QLabel()
        self.battery_label.setFont(ui_font(9))
        tray_layout.addWidget(self.battery_label)

        self.tray = {}
        for kind, tip, action in (
                ("network", "Network", self.focus_monitor),
                ("volume", "Volume: 70%", self.show_volume_menu),
                ("power", "Power options", self.show_power_menu)):
            button = IconButton(kind, tip, 28, theme_bound=True)
            button.clicked.connect(action)
            tray_layout.addWidget(button)
            self.tray[kind] = button

        layout.addWidget(tray)

        # --- clock (click for a calendar)
        self.clock = QPushButton()
        self.clock.setCursor(Qt.PointingHandCursor)
        self.clock.setFont(ui_font(10, bold=True))
        self.clock.clicked.connect(self.show_calendar)
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
                background: {CURRENT_THEME.panel_glass};
                border-bottom: 1px solid {CURRENT_THEME.hairline};
            }}
            QLabel {{ color: {TEXT_DIM}; padding: 0 4px; }}
        """)

    def style_menu_button(self):
        self.menu_button.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {MINT}, stop:1 {MINT_DARK});
                color: #ffffff;
                border: none;
                border-radius: 13px;
                padding: 0 14px 0 10px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {MINT_LIGHT}, stop:1 {MINT});
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
        self.clock.setStyleSheet(f"""
            QPushButton {{
                color: {TEXT}; background: transparent; border: none;
                border-radius: 8px; padding: 3px 12px;
            }}
            QPushButton:hover {{ background: {CURRENT_THEME.accent_soft}; }}
        """)

    def style_taskbar(self):
        self.dock.setStyleSheet(f"""
            QFrame#dock {{
                background: {CURRENT_THEME.panel_glass};
                border: 1px solid {CURRENT_THEME.hairline};
                border-radius: 20px;
            }}
            QFrame#docksep {{ background: {CURRENT_THEME.hairline}; }}
        """)

    def style_terminal(self):
        self.terminal_output.setStyleSheet(
            f"background: {_rgba(TERMINAL_BG, 235)}; color: #cfdcc6;")

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
        self.cpu_graph.update()
        self.refresh_files()          # folder icons follow the accent

        self.wallpaper.update()
        self.update()

    # ------------------------------------------------------
    # BOTTOM PANEL  (taskbar)
    # ------------------------------------------------------

    def build_bottom_panel(self):

        # transparent strip with a floating, centred glass dock
        panel = QWidget()
        panel.setAttribute(Qt.WA_TranslucentBackground)
        self.taskbar = panel

        outer = QHBoxLayout(panel)
        outer.setContentsMargins(0, 4, 0, 10)
        outer.addStretch(1)

        dock = QFrame()
        dock.setObjectName("dock")
        self.dock = dock
        self.style_taskbar()
        outer.addWidget(dock)
        outer.addStretch(1)

        shadow = QGraphicsDropShadowEffect(dock)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 6)
        dock.setGraphicsEffect(shadow)

        layout = QHBoxLayout(dock)
        layout.setContentsMargins(10, 6, 10, 2)
        layout.setSpacing(5)

        def separator():
            line = QFrame()
            line.setObjectName("docksep")
            line.setFixedSize(1, 26)
            layout.addWidget(line)

        self.dock_buttons = []

        def add(kind, tip, action, running=None, size=36):
            button = DockButton(kind, tip, running, size)
            button.clicked.connect(action)
            layout.addWidget(button)
            self.dock_buttons.append(button)

        add("apps", "Show Applications  (Ctrl+Space)", self.toggle_launcher)
        separator()
        for kind, name, action, running in self.apps:
            add(kind, name, action, running)
        separator()
        add("minimize", "Show desktop", self.toggle_panels, size=32)

        return panel

    # ------------------------------------------------------
    # PANELS
    # ------------------------------------------------------

    def notes_panel(self):

        panel = MintWindow("NOTES", "notes",
                           on_maximize=lambda w: self.toggle_zoom(w))

        self.note_search = QLineEdit()
        self.note_search.setPlaceholderText("Search notes…")
        self.note_search.addAction(icon_pixmap("search", 16, TEXT_DIM),
                                   QLineEdit.LeadingPosition)
        self.note_search.textChanged.connect(self.highlight_notes)
        panel.body.addWidget(self.note_search)

        self.notes = QTextEdit()
        self.notes.setAcceptRichText(False)
        self.notes.setPlaceholderText("Your thoughts, ideas and plans…")
        self.notes.setFont(ui_font(11))

        if NOTES_FILE.exists():
            self.notes.setPlainText(
                NOTES_FILE.read_text(encoding="utf-8")
            )

        panel.body.addWidget(self.notes, 1)

        # autosave a moment after typing stops
        self.note_timer = QTimer(self)
        self.note_timer.setSingleShot(True)
        self.note_timer.setInterval(800)
        self.note_timer.timeout.connect(self.autosave_notes)
        self.notes.textChanged.connect(lambda: self.note_timer.start())

        row = QHBoxLayout()
        self.note_status = QLabel()
        self.note_status.setObjectName("status")
        row.addWidget(self.note_status, 1)
        save = QPushButton("Save")
        save.setToolTip("Ctrl+S")
        save.clicked.connect(self.save_notes)
        row.addWidget(save)
        panel.body.addLayout(row)
        self.update_note_status("Autosave on")

        return panel

    def files_panel(self):

        panel = MintWindow("FILECORE", "folder",
                           on_maximize=lambda w: self.toggle_zoom(w))

        self.cwd = Path.home()

        nav = QHBoxLayout()
        nav.setSpacing(4)
        up = IconButton("up", "Up one folder", 30, theme_bound=True)
        up.clicked.connect(lambda: self.browse(self.cwd.parent))
        home = IconButton("home", "Home folder", 30, theme_bound=True)
        home.clicked.connect(lambda: self.browse(Path.home()))
        nav.addWidget(up)
        nav.addWidget(home)

        path = QLabel()
        path.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.path_label = path
        self.style_path_label()
        nav.addWidget(path, 1)
        panel.body.addLayout(nav)

        self.file_filter = QLineEdit()
        self.file_filter.setPlaceholderText("Filter this folder…")
        self.file_filter.addAction(icon_pixmap("search", 16, TEXT_DIM),
                                   QLineEdit.LeadingPosition)
        self.file_filter.textChanged.connect(lambda _: self.refresh_files())
        panel.body.addWidget(self.file_filter)

        self.file_list = QListWidget()
        self.file_list.setIconSize(QSize(16, 16))
        self.file_list.itemActivated.connect(self.file_activated)
        panel.body.addWidget(self.file_list, 1)

        row = QHBoxLayout()
        self.file_status = QLabel()
        self.file_status.setObjectName("status")
        row.addWidget(self.file_status, 1)

        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_files)
        row.addWidget(refresh)

        open_folder = QPushButton("Open in system")
        open_folder.clicked.connect(lambda: self.open_path(self.cwd))
        row.addWidget(open_folder)

        panel.body.addLayout(row)

        self.refresh_files()

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
            f"{APP_NAME} Terminal [bsh]\n"
            "Type 'help' for commands, 'neofetch' for system info.\n"
            "↑/↓ walks history · Tab completes\n"
        )
        panel.body.addWidget(self.terminal_output, 1)

        self.terminal_input = HistoryLineEdit(TERMINAL_COMMANDS)
        self.terminal_input.setFont(mono_font(9))
        self.terminal_input.setPlaceholderText("bankser@desktop:~$ ")
        self.terminal_input.returnPressed.connect(self.run_command)
        panel.body.addWidget(self.terminal_input)

        return panel

    def music_panel(self):

        panel = MintWindow("MUSIC", "music",
                           on_maximize=lambda w: self.toggle_zoom(w))

        self.music_dir = Path.home() / "Music"
        self.tracks = []
        self.track_index = -1

        header = QHBoxLayout()
        header.addWidget(IconWidget("music", 30, MINT_LIGHT, theme_bound=True))
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.now_playing = QLabel("Nothing playing")
        self.now_playing.setObjectName("strong")
        self.now_playing.setFont(ui_font(11, bold=True))
        self.now_playing.setSizePolicy(QSizePolicy.Ignored,
                                       QSizePolicy.Preferred)
        self.music_time = QLabel("0:00 / 0:00")
        self.music_time.setObjectName("status")
        titles.addWidget(self.now_playing)
        titles.addWidget(self.music_time)
        header.addLayout(titles, 1)
        panel.body.addLayout(header)

        self.music_seek = QSlider(Qt.Horizontal)
        panel.body.addWidget(self.music_seek)

        controls = QHBoxLayout()
        controls.setSpacing(2)
        for kind, tip, action in (("prev", "Previous", self.music_prev),
                                  ("play", "Play / pause", self.music_toggle),
                                  ("next", "Next", self.music_next)):
            button = IconButton(kind, tip, 32, theme_bound=True)
            button.clicked.connect(action)
            controls.addWidget(button)
            if kind == "play":
                self.play_button = button
        controls.addStretch(1)
        controls.addWidget(IconWidget("volume", 18, TEXT_DIM))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(90)
        controls.addWidget(self.volume_slider)
        panel.body.addLayout(controls)

        self.track_list = QListWidget()
        self.track_list.itemActivated.connect(
            lambda item: self.music_play(self.track_list.row(item)))
        panel.body.addWidget(self.track_list, 1)

        row = QHBoxLayout()
        choose = QPushButton("Choose folder…")
        choose.clicked.connect(self.music_choose_folder)
        open_folder = QPushButton("Open folder")
        open_folder.clicked.connect(lambda: self.open_path(self.music_dir))
        row.addWidget(choose)
        row.addWidget(open_folder)
        panel.body.addLayout(row)

        if QMediaPlayer is None:
            self.player = None
            self.track_list.addItem("Qt Multimedia is not available.")
            return panel

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.audio.setVolume(0.7)
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.music_seek.sliderMoved.connect(self.player.setPosition)
        self.player.durationChanged.connect(
            lambda ms: self.music_seek.setRange(0, ms))
        self.player.positionChanged.connect(self.music_position)
        self.player.playbackStateChanged.connect(self.music_state)
        self.player.mediaStatusChanged.connect(
            lambda status: status == QMediaPlayer.EndOfMedia
            and self.music_next())

        self.load_music()
        return panel

    def monitor_panel(self):

        panel = MintWindow("SYSTEM MONITOR", "monitor",
                           on_maximize=lambda w: self.toggle_zoom(w))
        panel.setMinimumWidth(380)

        gauges = QHBoxLayout()

        for title, value in (("CPU", 8), ("MEMORY", 38), ("DISK", 72)):
            gauge = Gauge(title, value)
            self.gauges.append(gauge)
            gauges.addWidget(gauge)
        self.cpu_gauge, self.mem_gauge, self.disk_gauge = self.gauges

        panel.body.addLayout(gauges)

        section = QLabel("CPU HISTORY")
        section.setFont(ui_font(9, bold=True))
        section.setObjectName("dim")
        panel.body.addWidget(section)
        self.cpu_graph = Sparkline()
        panel.body.addWidget(self.cpu_graph)

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
        self.info_labels = []

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
            self.info_labels.append(value)

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
        self.processes.setToolTip("Top processes by CPU")
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

        if window in self.floating:
            self.floating[window] = window.geometry()   # come back here
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

        self.grid.removeWidget(window)
        if window in self.floating:
            window.setGeometry(self.floating[window])
        else:
            self.grid.addWidget(window, *self.panel_home[window])
        self.zoomed_window = None

        if window is self.terminal_win:
            self.terminal_output.setAlignment(Qt.AlignLeft)
            self.terminal_output.setFont(mono_font(9))

        window.set_zoomed(False)
        window.raise_()

    def float_panel(self, window):
        """Title bar grabbed: lift the panel out of the grid so it can move.
        Returns False while maximized (restore it first)."""
        if self.zoomed_window is window:
            return False
        if window not in self.floating:
            geometry = window.geometry()
            self.grid.removeWidget(window)
            window.setGeometry(geometry)
            self.floating[window] = geometry
        return True

    def reset_layout(self):
        """Snap every dragged panel back into the grid."""
        if self.zoomed_window is not None:
            self.restore_panel(self.zoomed_window)
        for window in self.floating:
            self.grid.addWidget(window, *self.panel_home[window])
        self.floating.clear()

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
        self.notify(f"Theme changed to {theme.name.title()}")
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
        self.clock.setText(datetime.now().strftime("%a %d %b   %H:%M"))

    def notify(self, text):
        Toast(self.wallpaper, text)

    def toggle_launcher(self):
        if self.launcher.isVisible():
            self.launcher.hide()
        else:
            self.launcher.open()

    def _popup(self, widget, anchor):
        """Show any widget as a drop-down under `anchor`."""
        menu = QMenu(self)
        action = QWidgetAction(menu)
        action.setDefaultWidget(widget)
        menu.addAction(action)
        point = anchor.mapToGlobal(QPoint(0, anchor.height() + 4))
        menu.exec(point)

    def show_calendar(self):
        calendar = QCalendarWidget()
        calendar.setGridVisible(False)
        calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        calendar.setMinimumSize(300, 230)
        self._popup(calendar, self.clock)

    def show_volume_menu(self):
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(12, 8, 12, 8)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setFixedWidth(170)
        slider.setValue(self.volume_slider.value())
        label = QLabel(f"{slider.value()}%")
        label.setFixedWidth(36)
        slider.valueChanged.connect(self.volume_slider.setValue)
        slider.valueChanged.connect(lambda v: label.setText(f"{v}%"))
        row.addWidget(IconWidget("volume", 18, TEXT_DIM))
        row.addWidget(slider)
        row.addWidget(label)
        self._popup(holder, self.tray["volume"])

    def show_power_menu(self):
        menu = QMenu(self)
        for kind, text, action, colour in (
                ("apps", "Applications", self.toggle_launcher, TEXT),
                ("minimize", "Minimize desktop", self.showMinimized, TEXT),
                ("leaf", f"About {APP_NAME}", self.show_about, TEXT),
                (None, None, None, None),
                ("power", "Shut down", self.close, "#ff8a80")):
            if kind is None:
                menu.addSeparator()
                continue
            menu.addAction(icon_pixmap(kind, 16, colour), text) \
                .triggered.connect(action)
        button = self.tray["power"]
        menu.exec(button.mapToGlobal(QPoint(0, button.height() + 4)))

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

    # --- notes ----------------------------------------------

    def update_note_status(self, prefix):
        words = len(self.notes.toPlainText().split())
        self.note_status.setText(f"{prefix}  ·  {words} words")

    def autosave_notes(self):
        try:
            NOTES_FILE.write_text(self.notes.toPlainText(), encoding="utf-8")
        except OSError as error:
            self.update_note_status(f"Not saved: {error.strerror}")
            return False
        self.update_note_status(
            "Saved " + datetime.now().strftime("%H:%M:%S"))
        return True

    def save_notes(self):
        self.note_timer.stop()
        if self.autosave_notes():
            self.notify("Notes saved")

    def highlight_notes(self, text):
        """Highlight every match of the search box inside the notes."""
        selections = []
        if text:
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(MINT))
            fmt.setForeground(QColor(CURRENT_THEME.on_accent))
            document = self.notes.document()
            cursor = document.find(text)
            while not cursor.isNull():
                selection = QTextEdit.ExtraSelection()
                selection.cursor = cursor
                selection.format = fmt
                selections.append(selection)
                cursor = document.find(text, cursor)
            if selections:
                jump = QTextCursor(selections[0].cursor)
                jump.clearSelection()
                self.notes.setTextCursor(jump)
            self.note_status.setText(f"{len(selections)} matches")
        else:
            self.update_note_status("Autosave on")
        self.notes.setExtraSelections(selections)

    # --- files ----------------------------------------------

    def browse(self, path):
        path = Path(path).expanduser()
        if not _is_dir(path):
            return False
        self.cwd = path.resolve()
        self.file_filter.blockSignals(True)
        self.file_filter.clear()
        self.file_filter.blockSignals(False)
        self.refresh_files()
        return True

    def refresh_files(self):
        self.file_list.clear()
        needle = self.file_filter.text().lower()
        try:
            entries = [p for p in self.cwd.iterdir()
                       if not p.name.startswith(".")
                       and needle in p.name.lower()]
        except OSError as error:
            entries = []
            self.file_list.addItem(f"Cannot open: {error.strerror}")

        entries.sort(key=lambda p: (not _is_dir(p), p.name.lower()))
        folder_icon = icon_pixmap("folder", 16, MINT_LIGHT)
        file_icon = icon_pixmap("file", 16, TEXT_DIM)

        for entry in entries[:500]:
            is_dir = _is_dir(entry)
            item = QListWidgetItem(folder_icon if is_dir else file_icon,
                                   entry.name)
            item.setData(Qt.UserRole, str(entry))
            if not is_dir:
                try:
                    stat = entry.stat()
                    item.setToolTip(
                        f"{_human(stat.st_size)}  ·  modified "
                        + datetime.fromtimestamp(stat.st_mtime)
                        .strftime("%d %b %Y %H:%M"))
                except OSError:
                    pass
            self.file_list.addItem(item)

        folders = sum(1 for e in entries if _is_dir(e))
        self.file_status.setText(
            f"{folders} folders · {len(entries) - folders} files")
        self.path_label.setText(str(self.cwd))
        self.path_label.setToolTip(str(self.cwd))

    def file_activated(self, item):
        target = item.data(Qt.UserRole)
        if not target:
            return
        target = Path(target)
        if _is_dir(target):
            self.browse(target)
        else:
            self.open_path(target)

    def open_home(self):
        self.open_path(HOME)

    def open_path(self, path):
        try:
            if not path.exists():
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

    def contextMenuEvent(self, event):
        """Right-click on the wallpaper: every app plus themes."""
        menu = QMenu(self)
        for kind, name, action, _running in self.apps:
            menu.addAction(icon_pixmap(kind, 16, MINT_LIGHT), name) \
                .triggered.connect(action)
        menu.addSeparator()
        themes = menu.addMenu("Themes")
        for theme in THEMES:
            themes.addAction(
                ("● " if theme is CURRENT_THEME else "   ") + theme.name.title()
            ).triggered.connect(
                lambda _=False, n=theme.index: self.set_theme(n))
        menu.addAction("Reset window layout").triggered.connect(
            self.reset_layout)
        menu.addAction("About BANKSER'").triggered.connect(self.show_about)
        menu.exec(event.globalPos())

    # ------------------------------------------------------
    # MUSIC PLAYER
    # ------------------------------------------------------

    def load_music(self):
        self.track_list.clear()
        try:
            found = (p for p in self.music_dir.rglob("*")
                     if p.suffix.lower() in AUDIO_EXTENSIONS)
            self.tracks = sorted(itertools.islice(found, 500))
        except OSError:
            self.tracks = []
        note_icon = icon_pixmap("music", 16, MINT_LIGHT)
        for track in self.tracks:
            self.track_list.addItem(QListWidgetItem(note_icon, track.stem))
        if not self.tracks:
            self.track_list.addItem(
                f"No music in {self.music_dir}. Choose a folder below.")

    def music_choose_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Choose music folder", str(self.music_dir))
        if folder:
            self.music_dir = Path(folder)
            self.load_music()

    def music_play(self, index):
        if self.player is None or not self.tracks:
            return
        self.track_index = index % len(self.tracks)
        track = self.tracks[self.track_index]
        self.player.setSource(QUrl.fromLocalFile(str(track)))
        self.player.play()
        self.now_playing.setText(track.stem)
        self.now_playing.setToolTip(str(track))
        self.track_list.setCurrentRow(self.track_index)

    def music_toggle(self):
        if self.player is None:
            return
        if self.track_index < 0:
            self.music_play(0)
        elif self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def music_next(self):
        self.music_play(self.track_index + 1)

    def music_prev(self):
        self.music_play(max(self.track_index, 0) - 1)

    def set_volume(self, value):
        self.audio.setVolume(value / 100.0)
        self.tray["volume"].setToolTip(f"Volume: {value}%")

    def music_state(self, state):
        playing = state == QMediaPlayer.PlayingState
        self.play_button.kind = "pause" if playing else "play"
        self.play_button.update()

    def music_position(self, ms):
        if not self.music_seek.isSliderDown():
            self.music_seek.setValue(ms)

        def clock(value):
            return f"{value // 60000}:{value // 1000 % 60:02d}"

        self.music_time.setText(
            f"{clock(ms)} / {clock(self.player.duration())}")

    # ------------------------------------------------------
    # LIVE SYSTEM MONITOR
    # ------------------------------------------------------

    @staticmethod
    def local_address():
        """(interface, IPv4) of the first connected adapter, or None."""
        stats = psutil.net_if_stats()
        for name, addresses in psutil.net_if_addrs().items():
            if not (stats.get(name) and stats[name].isup):
                continue
            for address in addresses:
                ip = address.address
                if (address.family == socket.AF_INET
                        and not ip.startswith(("127.", "169.254."))):
                    return name, ip
        return None

    def top_processes(self, count=8):
        """Busiest processes as (name, cpu %, memory bytes)."""
        cores = psutil.cpu_count() or 1
        rows = []
        # ponytail: walks every process on the UI thread (~50 ms on
        # Windows); move to a worker thread if the monitor ever stutters
        for proc in psutil.process_iter(["name", "cpu_percent",
                                         "memory_info"]):
            info = proc.info
            if not info["name"] or info["name"] == "System Idle Process":
                continue
            memory = info["memory_info"].rss if info["memory_info"] else 0
            rows.append((info["name"], (info["cpu_percent"] or 0) / cores,
                         memory))
        rows.sort(key=lambda r: (r[1], r[2]), reverse=True)
        return rows[:count]

    def update_monitor(self):
        if psutil is None:
            return
        self._monitor_ticks += 1

        cpu = psutil.cpu_percent(None)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(Path.home().anchor or "/")

        self.cpu_gauge.set_value(cpu, f"{psutil.cpu_count()} threads")
        self.mem_gauge.set_value(
            memory.percent,
            f"{_human(memory.used)} / {_human(memory.total)}")
        self.disk_gauge.set_value(disk.percent,
                                  f"{_human(disk.free)} free")
        self.cpu_graph.push(cpu)

        net, now = psutil.net_io_counters(), time.monotonic()
        if self._net_last:
            last, then = self._net_last
            seconds = max(now - then, 0.001)
            down = (net.bytes_recv - last.bytes_recv) / seconds
            up = (net.bytes_sent - last.bytes_sent) / seconds
            self.info_labels[1].setText(
                f"↓ {_human(down)}/s\n\n↑ {_human(up)}/s")
        self._net_last = (net, now)

        battery = psutil.sensors_battery() if hasattr(
            psutil, "sensors_battery") else None
        if battery is not None:
            plug = "⚡ " if battery.power_plugged else ""
            self.battery_label.setText(f"{plug}{battery.percent:.0f}%")

        # slower details every other tick
        if self._monitor_ticks % 2 != 1:
            return

        link = self.local_address()
        if link:
            self.info_labels[0].setText(
                f"{link[0]}\n{link[1]}\n\nStatus: Online")
            self.tray["network"].setToolTip(f"Online · {link[0]} · {link[1]}")
        else:
            self.info_labels[0].setText("No connection\n\nStatus: Offline")
            self.tray["network"].setToolTip("Offline")

        self.info_labels[2].setText(
            f"{platform.system()} {platform.release()}\n"
            f"Python {platform.python_version()}\n"
            f"Up {_duration(time.time() - psutil.boot_time())}\n"
            f"Session {_duration(time.time() - self.started)}")

        self.processes.clear()
        for name, cpu_share, memory in self.top_processes():
            self.processes.addItem(
                f"{name[:22]:<22} {cpu_share:5.1f}%  {_human(memory):>9}")

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
        # give ART the chance to ask about an unsaved drawing first
        if self.art_window is not None and not self.art_window.close():
            event.ignore()
            return
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

    def short_cwd(self):
        try:
            return "~/" + self.cwd.relative_to(Path.home()).as_posix() \
                if self.cwd != Path.home() else "~"
        except ValueError:
            return self.cwd.as_posix()

    def show_neofetch(self):
        logo = [
            "        .-~~~-.        ",
            "      .'  /    '.      ",
            "     /   /       \\     ",
            "    |   /   _.-'  |    ",
            "    |  / .-'      |    ",
            "     \\ |/        /     ",
            "      '.|     .'       ",
            "        '-...-'        ",
        ]
        screen = (self.screen() or QApplication.primaryScreen()).size()
        info = [
            ("", f"{os.environ.get('USERNAME') or os.environ.get('USER') or 'bankser'}"
                 f"@{platform.node()}"),
            ("", "─" * 24),
            ("OS", f"{APP_NAME} Desktop v{VERSION}"),
            ("Host", f"{platform.system()} {platform.release()}"),
            ("Python", platform.python_version()),
            ("Shell", "bsh"),
            ("Theme", CURRENT_THEME.name.title()),
            ("Resolution", f"{screen.width()}x{screen.height()}"),
        ]
        if psutil is not None:
            memory = psutil.virtual_memory()
            info += [
                ("CPU", f"{psutil.cpu_count()} threads · "
                        f"{psutil.cpu_percent(None):.0f}% busy"),
                ("Memory", f"{_human(memory.used)} / {_human(memory.total)}"),
                ("Uptime", _duration(time.time() - psutil.boot_time())),
            ]

        rows = []
        for i in range(max(len(logo), len(info))):
            art = logo[i] if i < len(logo) else " " * len(logo[0])
            line = f"<span style='color:{MINT}'>{html.escape(art)}</span>"
            if i < len(info):
                key, value = info[i]
                if key:
                    line += (f"<span style='color:{MINT_LIGHT};"
                             f"font-weight:bold'>{key}</span>: ")
                line += f"<span style='color:{TEXT}'>{html.escape(value)}</span>"
            rows.append(line)
        swatches = "".join(
            f"<span style='color:{t.accent}'>███</span>" for t in THEMES)
        rows.append(" " * len(logo[0]) + swatches)
        self.term_html("<pre style='margin:0'>" + "<br>".join(
            row.replace("  ", "&nbsp;&nbsp;") for row in rows) + "</pre>")

    def run_extra_command(self, name, rest):
        """The newer bsh commands. Returns True when one handled `name`."""
        if name == "neofetch":
            self.show_neofetch()
        elif name == "calc":
            try:
                self.term_write(f"= {_safe_math(rest)}")
            except Exception as error:
                self.term_write(f"calc: {error or 'invalid expression'}")
        elif name == "echo":
            self.term_write(rest)
        elif name == "whoami":
            self.term_write(os.environ.get("USERNAME")
                            or os.environ.get("USER") or "bankser")
        elif name == "history":
            self.term_write("\n".join(
                f"{i:>4}  {c}"
                for i, c in enumerate(self.terminal_input.history, 1)))
        elif name == "pwd":
            self.term_write(str(self.cwd))
        elif name == "cd":
            target = self.cwd / Path(rest or "~").expanduser()
            if not self.browse(target):
                self.term_write(f"cd: no such folder: {rest}")
        elif name in ("ls", "dir"):
            target = (self.cwd / Path(rest).expanduser()) if rest else self.cwd
            try:
                names = sorted(
                    (p.name + ("/" if _is_dir(p) else ""))
                    for p in target.iterdir() if not p.name.startswith("."))
                self.term_write("  ".join(names) or "(empty)")
            except OSError as error:
                self.term_write(f"ls: {error.strerror}: {target}")
        elif name == "open":
            if self.launch_app(rest):
                self.term_write(f"Opening {rest}…")
            else:
                self.term_write(f"open: no app called '{rest}'. "
                                "Try notes, files, music, art, matrix…")
        elif name == "top":
            if psutil is None:
                self.term_write("top: needs psutil (pip install psutil)")
            else:
                lines = [f"{'PROCESS':<24} {'CPU':>6}  {'MEMORY':>9}"]
                lines += [f"{n[:24]:<24} {c:5.1f}%  {_human(m):>9}"
                          for n, c, m in self.top_processes(12)]
                self.term_write("\n".join(lines))
        elif name == "uptime":
            text = f"session: {_duration(time.time() - self.started)}"
            if psutil is not None:
                text = (f"system: {_duration(time.time() - psutil.boot_time())}"
                        f"\n{text}")
            self.term_write(text)
        elif name == "notify":
            self.notify(rest or "Hello from bsh")
            self.term_write("Notification sent.")
        elif name == "boot":
            # keep a reference, or Python would collect the window at once
            self._boot_replay = HudBootScreen(lambda: None)
            self._boot_replay.showFullScreen()
            self.term_write("Replaying the boot sequence… (any key skips)")
        else:
            return False
        return True

    def run_command(self):

        command = self.terminal_input.text().strip()
        self.terminal_input.clear()

        if not command:
            return

        self.terminal_input.remember(command)
        name = command.split()[0].lower()
        rest = command[len(command.split()[0]):].strip()

        if name in ("clear", "cls"):
            self.terminal_output.clear()
            return

        self.term_html(
            f"<span style='color:{PROMPT};font-weight:bold'>bankser@desktop"
            f"</span><span style='color:{TEXT_MUTED}'>:"
            f"{html.escape(self.short_cwd())}$</span> "
            f"<span style='color:{TEXT}'>{html.escape(command)}</span>"
        )

        if self.run_extra_command(name, rest):
            return

        if name in ("color", "colors", "colour", "colours", "theme"):

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
            self.term_write("ART Studio launched.")
            return

        if name in ("pasteshell", "ps"):
            self.open_pasteshell()
            self.term_write("PASTESHELL launched.")
            return

        if name in ("matrix", "matrixrain", "rain", "cmatrix"):
            self.open_matrix()
            self.term_write("MATRIX RAIN launched.")
            self.term_write("Hotkeys: q quit · 0-9 speed · a async · b bold")
            return

        if name in ("ipsea", "weakwifi"):
            self.open_pasteshell()
            if name == "ipsea":
                self.paste_window.start_network_scan()
                self.term_write("IPSEA scan running inside PASTESHELL.")
            else:
                self.paste_window.scan_weak_wifi()
                self.term_write("Wi-Fi scan running inside PASTESHELL.")
            return

        if name in ("-welcome", "--welcome", "welcome"):
            self.zoom_panel(self.terminal_win)
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
                "  neofetch      system info with the BANKSER' logo\n"
                "  calc <expr>   calculator, e.g. calc sqrt(2)*10\n"
                "  ls [path]     list a folder\n"
                "  cd <path>     change folder (Filecore follows)\n"
                "  pwd           show the current folder\n"
                "  open <app>    open any desktop app by name\n"
                "  top           busiest processes right now\n"
                "  uptime        system and session uptime\n"
                "  history       commands typed this session\n"
                "  echo <text>   print text\n"
                "  notify <text> pop a desktop notification\n"
                "  boot          replay the holographic boot sequence\n"
                "  whoami        current user\n"
                "  date          current date and time\n"
                "  system        platform information\n"
                "  files         list ~/.bankser\n"
                "  clear         clear the terminal\n"
                "  open-home     open the BANKSER' home folder\n"
                "  website       open a browser\n"
                "\n"
                "Shortcuts: Ctrl+Space apps · Ctrl+Alt+T terminal · "
                "Ctrl+Alt+F files · Ctrl+S save notes · F11 fullscreen"
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

    screen_class = HudBootScreen if BOOT_STYLE == "hud" else BootScreen
    boot = screen_class(lambda: desktop.showFullScreen())
    boot.showFullScreen()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
