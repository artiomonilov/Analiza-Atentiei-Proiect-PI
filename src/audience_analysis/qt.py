"""PySide6 first; existing PyQt5 is a development-only fallback."""
try:
    from PySide6 import QtCore, QtGui, QtWidgets
    BINDING = "PySide6"
except ImportError:
    from PyQt5 import QtCore, QtGui, QtWidgets
    BINDING = "PyQt5 (compatibilitate locală)"

