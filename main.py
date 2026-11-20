"""
SnowDesk — Windows Desktop Live Snow & Winter Atmosphere Overlay.
"""

import faulthandler
import sys
import traceback

try:
    _crash_f = open("snowdesk_error.log", "w", encoding="utf-8")
    faulthandler.enable(_crash_f)
except Exception:
    pass

from snowdesk.overlay import run_app


if __name__ == "__main__":
    try:
        sys.exit(run_app())
    except Exception:
        with open("snowdesk_error.log", "a", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        traceback.print_exc()
        sys.exit(1)
