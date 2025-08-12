# hiviz.py
from __future__ import annotations
import atexit
import json
import os
import queue
import threading
import time

from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import IO, Any

from _glasses import (
    COLOR_DICT,
    RESET,
    Colors,
    LogLevel,
    _parse_level,
    _strip_ansi,
    bugout,
    handle_iter,
    stamp_date,
    stdout,
)
from colorama import init as colorama_init


colorama_init(autoreset=False, strip=False, convert=False)


@dataclass(slots=True)
class LogRecord:
    ts: str
    level: str
    message: str
    color: str
    pid: int
    thread: str
    file: str
    line: int
    ctx: dict[str, Any]


class _Rotation:
    def __init__(self, path: Path, max_bytes: int, backup_count: int):
        self.path = path
        self.max_bytes = max_bytes
        self.backup_count = backup_count

    def maybe_rotate(self) -> None:
        if self.max_bytes <= 0:
            return
        try:
            if self.path.exists() and self.path.stat().st_size >= self.max_bytes:
                with suppress(FileNotFoundError):
                    for i in range(self.backup_count - 1, 0, -1):
                        src = Path(f'{self.path.with_suffix(self.path.suffix)}.{i})')
                        dst = Path(
                            f'{self.path.with_suffix(self.path.suffix)}.{i + 1})'
                        )
                        if src.exists():
                            src.rename(dst)
                    if self.backup_count:
                        self.path.rename(f"{self.path.with_suffix(self.path.suffix)}.1")
                self.path.touch(exist_ok=True)
        except Exception as e:
            bugout(f"Rotation error: {e!r}")

'''log_file: st
to_debug: bo
to_log: bool
to_term: boo
term_level:
file_level:
stderr_level
default_colo
color: Color
json_logs: b
max_bytes: i
backup_count'''
class HiViz:
    __slots__ = (
        '_color',
        '_ctx_stack',
        '_default_color',
        '_file_level',
        '_io_lock',
        '_json_logs',
        '_level',
        '_log_path',
        '_msg',
        '_q',
        '_rotation',
        '_stderr_level',
        '_stop',
        '_term_level',
        '_to_debug',
        '_to_log',
        '_to_term',
        '_worker',
    )
    colors = COLOR_DICT
    def __init__(
        self,
        *,
        log_file: str | Path | None = None,
        to_debug: bool | None = None,
        to_log: bool | None = None,
        to_term: bool | None = None,
        term_level: int | str | None = None,
        file_level: int | str | None = None,
        stderr_level: int | str | None = None,
        default_color: Colors | str | None = None,
        color: Colors | str | None = None,
        json_logs: bool = False,
        max_bytes: int = 2_000_000,
        backup_count: int = 3,
    ):
        self._level = LogLevel.INFO
        self._color = self._resolve_color(
            (color if isinstance(color, str) else getattr(color, "name", None))
            or (
                default_color
                if isinstance(default_color, str)
                else getattr(default_color, "name", None)
            )
            or "blue"
        )
        self._default_color = self._color
        self._msg = ""

        self._to_debug = bool(to_debug or os.getenv("DEBUG", "0") == "1")
        self._to_log = bool(to_log or os.getenv("LOG", "0") == "1")
        self._to_term = True if to_term is None else bool(to_term)

        self._term_level = _parse_level(
            term_level or os.getenv("TERM_LEVEL"), LogLevel.INFO
        )
        self._file_level = _parse_level(
            file_level or os.getenv("FILE_LEVEL"), LogLevel.DEBUG
        )
        self._stderr_level = _parse_level(
            stderr_level or os.getenv("STDERR_LEVEL"), LogLevel.WARNING
        )

        self._log_path = (
            Path(log_file)
            if log_file
            else Path.cwd() / (os.getenv("LOG_FILE", "debug.log"))
        )
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_path.touch(exist_ok=True)
        self._rotation = _Rotation(
            self._log_path, max_bytes=max_bytes, backup_count=backup_count
        )

        self._json_logs = json_logs

        self._q: queue.Queue[
            tuple[str, LogLevel, Colors | str, dict[str, Any], str, int]
        ] = queue.Queue()
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self._io_lock = threading.RLock()
        self._ctx_stack: list[dict[str, Any]] = []

        self.start()
        atexit.register(self.stop, True)

    # ---------- properties ----------
    @property
    def level(self) -> LogLevel:
        return self._level

    @level.setter
    def level(self, value: int | str | LogLevel):
        self._level = (
            value if isinstance(value, LogLevel) else _parse_level(value, self._level)
        )

    @property
    def color(self) -> str:
        return self._color.code()

    @color.setter
    def color(self, value: Colors | str | None):
        if value is None:
            self._color = self._color_default(self._level)
        elif isinstance(value, Colors):
            self._color = value
        else:
            self._color = self._resolve_color(value)

    @property
    def default_color(self) -> str:
        return self._default_color.code()

    @default_color.setter
    def default_color(self, value: Colors | str | None):
        if value is None:
            self._default_color = self._color_default(self._level)
        elif isinstance(value, Colors):
            self._default_color = value
        else:
            self._default_color = self._resolve_color(value)

    @property
    def to_term(self) -> bool:
        return self._to_term

    @property
    def to_log(self) -> bool:
        return self._to_log

    @property
    def to_debug(self) -> bool:
        return self._to_debug

    @property
    def term_level(self) -> LogLevel:
        return self._term_level

    @property
    def file_level(self) -> LogLevel:
        return self._file_level

    @property
    def stderr_level(self) -> LogLevel:
        return self._stderr_level

    @property
    def log_file(self) -> Path:
        return self._log_path

    # ---------- core ----------
    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop.clear()
        self._worker = threading.Thread(
            target=self._run, name="HiVizWorker", daemon=True
        )
        self._worker.start()
        if self._to_debug:
            bugout("HiViz worker started")

    def stop(self, drain: bool = True, timeout: float | None = 2.0) -> None:
        if not self._worker:
            return
        if self._to_debug:
            bugout("HiViz stopping")
        if drain:
            self._q.put(("", LogLevel.DEBUG, self._color, {}, "", 0))  # nudge
        self._stop.set()
        self._q.put_nowait(("__SENTINEL__", LogLevel.DEBUG, self._color, {}, "", 0))
        if threading.current_thread() is not self._worker:
            self._worker.join(timeout=timeout)
        self._worker = None
        if self._to_debug:
            bugout("HiViz stopped")

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                msg, lvl, color, ctx, src, lineno = self._q.get(timeout=0.25)
            except queue.Empty:
                continue
            if msg == "__SENTINEL__":
                break
            try:
                self._emit(msg, lvl, color, ctx, src, lineno)
            except Exception as e:
                bugout(f"Emit error: {e!r}")
            finally:
                self._q.task_done()

    def _emit(
        self,
        msg: str,
        level: LogLevel,
        color: Colors | str,
        ctx: dict[str, Any],
        src: str,
        lineno: int,
    ) -> None:
        ts = stamp_date()
        color_code = (
            color.code()
            if isinstance(color, Colors)
            else self._resolve_color(color).code()
        )
        plain = _strip_ansi(msg)
        rec = LogRecord(
            ts=ts,
            level=level.name,
            message=plain,
            color=color_code,
            pid=os.getpid(),
            thread=threading.current_thread().name,
            file=src,
            line=lineno,
            ctx=ctx,
        )
        out_line = (
            (json.dumps(asdict(rec), ensure_ascii=False) + "\n")
            if self._json_logs
            else f"{ts} [{level.name}] {plain}\n"
        )

        with self._io_lock:
            # file
            if self._to_log and level >= self._file_level:
                self._rotation.maybe_rotate()
                with self._log_path.open("a", encoding="utf-8", newline="") as f:
                    f.write(out_line)
            # terminal/stdout or stderr
            if self._to_term and level >= self._term_level:
                stream: IO[str] = (  # stderr for >= threshold
                    (__import__("sys").stderr)
                    if level >= self._stderr_level
                    else (__import__("sys").stdout)
                )
                stream.write(f"{color_code}{msg}{RESET}\n")
                stream.flush()
            # debug stream (forced to stderr)
            if self._to_debug and level >= LogLevel.DEBUG:
                bugout(f"{level.name}: {plain}")

    # ---------- convenience ----------
    def _resolve_color(self, color: str | Colors) -> Colors:
        if isinstance(color, Colors):
            return color
        name = str(color).strip().lower()
        if name in self.colors:
            return self.colors[name]
        raise ValueError(f"Invalid color: {color}. Options: {list(self.colors.keys())}")

    def _color_default(self, level: LogLevel) -> Colors:
        if level >= LogLevel.ERROR:
            return self.colors["red"]
        if level >= LogLevel.WARNING:
            return self.colors["yellow"]
        return self.colors["green"] if level >= LogLevel.INFO else self.colors["cyan"]

    def log(
        self,
        *msg: Any,
        level: int | str | LogLevel,
        color: Colors | str | None = None,
        **ctx: Any,
    ) -> None:
        def extract_ctx(
            msg_kwds: dict[str, Any],
        ) -> tuple[dict[str, Any], dict[str, Any]]:
            context = {}
            for k, v in msg_kwds.items():
                if (k in self.__slots__ or f"_{k}" in self.__slots__) and not callable(
                    v
                ):
                    context[k] = msg_kwds.pop(k)
                else:
                    continue
            return context, msg_kwds

        msg_kwds, ctx = extract_ctx(ctx)
        lvl = (
            self._level
            if level is None
            else (
                level
                if isinstance(level, LogLevel)
                else _parse_level(level, self._level)
            )
        )
        c = (
            self._color_default(lvl)
            if color is None
            else (color if isinstance(color, Colors) else self._resolve_color(color))
        )
        text = handle_iter(msg)
        if len(msg_kwds):
            msg_kwds = handle_iter(msg_kwds)
            text = f"{text}\n{msg_kwds}"
        frame = __import__("inspect").currentframe()
        # step back two frames to caller
        if frame and frame.f_back and frame.f_back.f_back:
            fi = __import__("inspect").getframeinfo(frame.f_back.f_back)
            src, lineno = str(fi.filename), int(fi.lineno)
        else:
            src, lineno = "unknown", 0

        self._q.put((text, lvl, c, ctx, src, lineno))

    def debug(self, *msg: Any, **ctx: Any) -> None:
        self.log(LogLevel.DEBUG, *msg, **ctx)

    def info(self, *msg: Any, **ctx: Any) -> None:
        self.log(LogLevel.INFO, *msg, **ctx)

    def warning(self, *msg: Any, **ctx: Any) -> None:
        self.log(LogLevel.WARNING, *msg, **ctx)

    def error(self, *msg: Any, **ctx: Any) -> None:
        self.log(LogLevel.ERROR, *msg, **ctx)

    def critical(self, *msg: Any, **ctx: Any) -> None:
        self.log(LogLevel.CRITICAL, *msg, **ctx)

    # ---------- context + configuration ----------
    def set_options(
        self,
        *,
        to_debug: bool | None = None,
        to_log: bool | None = None,
        to_term: bool | None = None,
        color: Colors | str | None = None,
        default_color: Colors | str | None = None,
        term_level: int | str | LogLevel | None = None,
        file_level: int | str | LogLevel | None = None,
        stderr_level: int | str | LogLevel | None = None,
        log_file: str | Path | None = None,
        json_logs: bool | None = None,
    ) -> None:
        snap = dict(
            _to_debug=self._to_debug,
            _to_log=self._to_log,
            _to_term=self._to_term,
            _color=self._color,
            _default_color=self._default_color,
            _term_level=self._term_level,
            _file_level=self._file_level,
            _stderr_level=self._stderr_level,
            _log_path=self._log_path,
            _json_logs=self._json_logs,
        )
        self._ctx_stack.append(snap)

        if to_debug is not None:
            self._to_debug = bool(to_debug)
        if to_log is not None:
            self._to_log = bool(to_log)
        if to_term is not None:
            self._to_term = bool(to_term)
        if color is not None:
            self.color = color
        if default_color is not None:
            self.default_color = default_color
        if term_level is not None:
            self._term_level = _parse_level(term_level, self._term_level)
        if file_level is not None:
            self._file_level = _parse_level(file_level, self._file_level)
        if stderr_level is not None:
            self._stderr_level = _parse_level(stderr_level, self._stderr_level)
        if log_file is not None:
            p = Path(log_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch(exist_ok=True)
            self._log_path = p
        if json_logs is not None:
            self._json_logs = bool(json_logs)

    def reset_options(self) -> None:
        if not self._ctx_stack:
            return
        snap = self._ctx_stack.pop()
        self._to_debug = snap["_to_debug"]
        self._to_log = snap["_to_log"]
        self._to_term = snap["_to_term"]
        self._color = snap["_color"]
        self._default_color = snap["_default_color"]
        self._term_level = snap["_term_level"]
        self._file_level = snap["_file_level"]
        self._stderr_level = snap["_stderr_level"]
        self._log_path = snap["_log_path"]
        self._json_logs = snap["_json_logs"]

    @contextmanager
    def options(self, **kw: Any):
        self.set_options(**kw)
        try:
            yield self
        finally:
            self.reset_options()

    # ---------- helpers ----------
    def timeit(self, label: str = "duration", level: LogLevel = LogLevel.INFO):
        @contextmanager
        def _ctx():
            t0 = time.perf_counter()
            try:
                yield
            except Exception as e:
                self.error(f"{label} errored: {e!r}")
                raise
            finally:
                dt = (time.perf_counter() - t0) * 1000.0
                self.log(f"{label}: {dt:.2f} ms",level=level)

        return _ctx()

    def wrap_exceptions(self, level: LogLevel = LogLevel.ERROR):
        def deco(fn):
            def inner(*a, **kw):
                try:
                    return fn(*a, **kw)
                except Exception as e:
                    self.log(f"Exception in {fn.__name__}: {e!r}", level=level, exc_info=True)
                    raise

            return inner

        return deco

    # ---------- dunder ----------
    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        if et is not None:
            self.error(f"Exception in context: {ev!r}", exc_info=(et, ev, tb))
            return False
        return True

    def __bool__(self) -> bool:
        return not self._q.empty()

    def __len__(self) -> int:
        return self._q.qsize()


# --------- module-level convenience ---------
hiviz = HiViz()


def viz(
    *msg: Any,
    level: int | str | LogLevel = LogLevel.INFO,
    color: str | Colors | None = None,
    **ctx: Any,
) -> None:
    hiviz.log(*msg, level=level, color=color, **ctx)


def visualize(*msg: Any, **kw: Any) -> None:
    viz(*msg, **kw)


def bug(*msg: Any, **ctx: Any) -> None:
    hiviz.debug(*msg, **ctx)


if __name__ == "__main__":
    hiviz.set_options(to_log=True, log_file="debug.log", json_logs=True)
    viz("Threaded info to stdout and file", level="INFO", color="green", user="skellum")
    viz("A warning goes to stderr", level="WARNING", color="yellow", reason="demo")
    with hiviz.timeit("sleep(100ms)"):
        time.sleep(0.1)

    @hiviz.wrap_exceptions()
    def boom():
        raise RuntimeError("kaboom")

    with suppress(RuntimeError):
        boom()
    with hiviz.options(to_term=False, json_logs=True):
        viz("logged only to file as JSON", level="DEBUG", color="cyan", tag="json-only")
    hiviz.stop()
