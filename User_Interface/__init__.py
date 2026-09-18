"""FAULTLINE User Interface Package - Red & White Theme.

Provides both modern Web UI and native Desktop GUI.
"""

from .app import run_web_server
from .desktop_app import run_desktop_app

__all__ = ["run_web_server", "run_desktop_app"]
