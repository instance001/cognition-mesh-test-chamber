#!/usr/bin/env python3
"""Start the Cognition Mesh Test Chamber dashboard from a source checkout."""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the local dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--no-open", action="store_true", help="Do not open the browser automatically.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    sys.path.insert(0, str(repo_root / "src"))

    from cm_test_chamber.dashboard import run_dashboard_server

    server = run_dashboard_server(repo_root, args.host, args.port)
    dashboard_url = f"http://{args.host}:{args.port}"
    print(f"Dashboard running at {dashboard_url}")
    if not args.no_open:
        threading.Thread(target=lambda: webbrowser.open(dashboard_url), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
