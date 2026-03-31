"""Service entrypoint compatible with Render-style deployment."""

import importlib
import os
import signal
import sys
import time
import traceback
from pathlib import Path

import uvicorn

_shutdown_requested = False
_crash_log_path = Path("/tmp/ohmycaptcha-supervisor.log")


def _handle_shutdown(signum, _frame):
    global _shutdown_requested
    _shutdown_requested = True
    try:
        _crash_log_path.write_text(
            f"received shutdown signal {signum}\n",
            encoding="utf-8",
        )
    except Exception:
        pass


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    while True:
        try:
            from src.core.config import config

            port = int(os.environ.get("PORT", config.server_port))
            app_module = importlib.import_module("src.main")
            app = app_module.app
            uvicorn.run(
                app,
                host=config.server_host,
                port=port,
                reload=False,
                access_log=False,
                loop="asyncio",
                http="h11",
            )
        except BaseException:
            if _shutdown_requested:
                raise
            traceback_text = traceback.format_exc()
            try:
                _crash_log_path.write_text(traceback_text, encoding="utf-8")
            except Exception:
                pass
            print(traceback_text, flush=True)
            sys.modules.pop("src.main", None)
            time.sleep(1)
            continue

        if _shutdown_requested:
            break

        unexpected = "uvicorn exited without a shutdown signal; restarting in 1 second\n"
        try:
            _crash_log_path.write_text(unexpected, encoding="utf-8")
        except Exception:
            pass
        print(unexpected, flush=True)
        time.sleep(1)
