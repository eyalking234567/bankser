"""Quick self-check for the review fixes. Run:  python test_fixes.py"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")   # no window needed

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

import bankser_desktop as bk


def expect_error(expression):
    try:
        bk._safe_math(expression)
    except ValueError:
        return
    raise AssertionError(f"{expression} should be refused")


# calculator: normal maths works, giant numbers are refused fast
assert bk._safe_math("2**10 + 3*4") == 1036
assert bk._safe_math("10**3999") == 10 ** 3999
expect_error("(9**9999)**9999")
expect_error("9**9999")
expect_error("(10**3000)*(10**3000)")

# bankserAI: names only match when meant
ai = bk.AIEngine()
assert ai.find_url("explain how a bank calculates interest") is None
assert ai.find_url("solve for x") is None
assert ai.find_url("x") == bk.AI_SITES["x"]
assert ai.find_url("open youtube") == bk.AI_SITES["youtube"]
assert "c%2B%2B" in ai.find_search("can you search the web for c++")
assert ai.find_search("i did some research before the format change") is None
assert ai.find_app("show me how to run python in a terminal") is None
assert ai.find_app("open the matrix rain") == "matrix"
assert ai.find_app("terminal") == "terminal"

# ART: the new flood fill stays inside a closed shape
app = QApplication([])
canvas = bk.ArtCanvas()
canvas.image = QImage(200, 150, QImage.Format_ARGB32)
canvas.image.fill(QColor("#ffffff"))
painter = QPainter(canvas.image)
painter.setPen(QColor("#000000"))
painter.drawRect(QRect(20, 20, 100, 80))
painter.end()
canvas.color = QColor("#ff0000")
canvas.flood_fill(QPoint(50, 50))
assert canvas.image.pixelColor(50, 50) == QColor("#ff0000"), "inside filled"
assert canvas.image.pixelColor(5, 5) == QColor("#ffffff"), "outside untouched"
assert canvas.image.pixelColor(20, 50) == QColor("#000000"), "border kept"

print("all checks passed")
