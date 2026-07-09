"""Shared functional logger for Pressure & Level / Flow & Temp."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Literal

from paths import writable_path

Subsystem = Literal["pressurelevel", "flowtemp"]
Level = Literal["INFO", "CAUTION", "ERROR", "CRITICAL"]


class FuncLogger:
    """Append-only daily functional logs under flog_<subsystem>/YYYY/MM/DD.txt."""

    def __init__(self, subsystem: Subsystem, source: str):
        if subsystem not in ("pressurelevel", "flowtemp"):
            raise ValueError(f"Unsupported subsystem: {subsystem}")
        self.subsystem = subsystem
        self.source = source
        self._root = writable_path(f"flog_{subsystem}")

    def info(self, message: str) -> None:
        self._write("INFO", message)

    def caution(self, message: str) -> None:
        self._write("CAUTION", message)

    def error(self, message: str) -> None:
        self._write("ERROR", message)

    def critical(self, message: str) -> None:
        self._write("CRITICAL", message)

    def _write(self, level: Level, message: str) -> None:
        now = datetime.now()
        year = now.strftime("%Y")
        month = now.strftime("%m")
        day = now.strftime("%d")
        dir_path = os.path.join(self._root, year, month)
        line = (
            f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] "
            f"[{level}] [{self.source}] {message}\n"
        )
        try:
            os.makedirs(dir_path, exist_ok=True)
            path = os.path.join(dir_path, f"{day}.txt")
            with open(path, "a", encoding="utf-8") as file:
                file.write(line)
        except Exception as e:
            print(f"Failed to write functional log: {e}")
            print(line.rstrip())
