"""Entry point when running `python -m User_Interface` or `python User_Interface`."""

import argparse
import sys
from pathlib import Path

# Ensure root directory is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from User_Interface.app import run_web_server
from User_Interface.desktop_app import run_desktop_app


def main() -> None:
    parser = argparse.ArgumentParser(description="FAULTLINE User Interface (Red & White Theme)")
    parser.add_argument("--desktop", action="store_true", help="Launch native Tkinter desktop GUI")
    parser.add_argument("--port", type=int, default=5050, help="Web UI port (default: 5050)")
    parser.add_argument("--host", default="127.0.0.1", help="Web UI host (default: 127.0.0.1)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")
    args = parser.parse_args()

    if args.desktop:
        run_desktop_app()
    else:
        run_web_server(host=args.host, port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
