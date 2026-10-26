from __future__ import annotations

import argparse
import multiprocessing
import os

import uvicorn

from app.main import app as web_app
from app.config import SETTINGS
from app.logging_setup import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Transcriber backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    arguments = parser.parse_args()
    setup_logging(SETTINGS, web_app.version)
    uvicorn.run(
        web_app,
        host=arguments.host,
        port=arguments.port,
        log_level="warning",
        access_log=False,
    )
    # uvicorn returns after the shell's SIGTERM, but a transcription still
    # running on the worker thread would keep the process alive (the
    # executor's threads are joined at interpreter exit) with no window to
    # show its result. The source file is kept in data/uploads for such an
    # interrupted job, so ending the process here loses nothing.
    os._exit(0)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
