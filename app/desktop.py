from __future__ import annotations

import argparse
import multiprocessing

import uvicorn

from app.main import app as web_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Transcriber backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    arguments = parser.parse_args()
    uvicorn.run(
        web_app,
        host=arguments.host,
        port=arguments.port,
        log_level="warning",
        access_log=False,
    )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
