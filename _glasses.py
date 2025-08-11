from __future__ import annotations
import re
import sys
import datetime as dt
from collections import OrderedDict
from enum import IntEnum, StrEnum
from typing import Iterable, Any

from colorama import Fore, Style


def stamp_date() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


class Colors(StrEnum):
    BLACK = Fore.BLACK
    RED = Fore.RED
    GREEN = Fore.GREEN
    YELLOW = Fore.YELLOW
    BLUE = Fore.BLUE
    MAGENTA = Fore.MAGENTA
    CYAN = Fore.CYAN
    WHITE = Fore.WHITE
    RESET = Style.RESET_ALL

    @classmethod
    def all_colors(cls, string: bool | None = None) -> Iterable[str]:
        if string:
            return [c.name.lower() for c in cls if c != cls.RESET]
        return [c.value for c in cls]

    def inverse(self) -> str:
        return self.name.lower()

    def code(self) -> str:
        return self.value


RESET = Colors.RESET.value
COLOR_STRINGS = Colors.all_colors(string=True)
COLOR_DICT: OrderedDict[str, Colors] = OrderedDict(zip(COLOR_STRINGS, Colors))


class LogLevel(IntEnum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


def _parse_level(val: int | str | None, default: LogLevel) -> LogLevel:
    if val is None:
        return default
    if isinstance(val, int):
        try:
            return LogLevel(val)
        except ValueError:
            return default
    s = str(val).strip().upper()
    return {
        "DEBUG": LogLevel.DEBUG,
        "INFO": LogLevel.INFO,
        "WARN": LogLevel.WARNING,
        "WARNING": LogLevel.WARNING,
        "ERROR": LogLevel.ERROR,
        "CRITICAL": LogLevel.CRITICAL,
    }.get(s, default)


ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


def _strip_ansi(s: str) -> str:
    return ANSI_RE.sub("", s)


def handle_iter(i: Any) -> str:
    if isinstance(i, (list, tuple)):
        return " ".join(map(handle_iter, i))
    if isinstance(i, dict):
        return handle_iter([f"{k}={v}" for k, v in i.items()])
    return str(i)


def stdout(*msg: Any, debug: bool = False) -> None:
    target = sys.stderr if debug else sys.stdout
    target.write(f"{handle_iter(msg)}\n")
    target.flush()


def bugout(msg: Any) -> None:
    stdout(f"DEBUG: {handle_iter(msg)}", debug=True)

stdout(stamp_date())
