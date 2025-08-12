# HiViz

[ ]

- Threaded, non‑blocking colored terminal output
- Selective stdout / stderr routing by level
- File logging with optional JSON lines and size rotation
- Context (temporary) option overrides
- Structured contextual key=value enrichment
- Lightweight timing and exception helpers

---

## Key Features

- Colorized messages (ANSI via colorama) using [`Colors`](\_glasses.py) palette
- Log levels (`DEBUG, INFO, WARNING, ERROR, CRITICAL`) via [`LogLevel`](\_glasses.py)
- Threaded queue writer in [`HiViz`](hiviz.py) to avoid I/O stalls
- Environment variable driven defaults (see below)
- Optional JSON log records (structured, one per line)
- Lightweight file rotation (`max_bytes`, `backup_count`)
- Context manager + reversible option stack (`set_options` / `options`)
- Timing helper: [`HiViz.timeit`](hiviz.py)
- Exception wrapper: [`HiViz.wrap_exceptions`](hiviz.py)
- Convenience functions: [`viz`](hiviz.py), [`visualize`](hiviz.py), [`bug`](hiviz.py)
- Safe ANSI stripping via [`_strip_ansi`](\_glasses.py)
- Argument normalization via [`handle_iter`](\_glasses.py)

---

## Installation

Local (editable):

```bash
git clone https://github.com/RI7TE/HiViz.git
cd HiViz
pip install -e .
```

Or directly (non‑editable):

```bash

pip install git+https://github.com/RI7TE/HiViz.git
```


### Dependencies: `colorama==0.4.6` (see [requirements.txt](vscode-file://vscode-app/Applications/Visual%20Studio%20Code%20-%20Insiders.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html))


## Quick Start


```python
from hiviz import viz, hiviz, HiViz, bug
from _glasses import Colors, LogLevel

# Simple info (defaults to level=INFO to stdout)
viz("Hello world")

# Explicit level + color
viz("Something happened", level="WARNING", color="yellow")

# Include contextual fields (appear in file / JSON output)
viz("User login", level="INFO", color="green", user="alice", ip="10.0.0.5")

# Switch on file logging + JSON temporarily
with hiviz.options(to_log=True, json_logs=True, log_file="debug.log"):
    viz("Structured event", level="DEBUG", feature="beta")

# Timing block
with hiviz.timeit("process_stage"):
    ...  # do work

# Exception wrapping
@hiviz.wrap_exceptions()
def risky():
    raise RuntimeError("boom")

with suppress(RuntimeError):
    risky()

# Direct methods (equivalents)
hiviz.debug("Low level detail")
hiviz.info("Informational")
hiviz.warning("Heads up")
hiviz.error("Something failed")
hiviz.critical("Critical path issue")
```


## Log Levels & Routing

|  |  |  |  |  |
| - | - | - | - | - |

| Level        | Minimum stdout (TERM_LEVEL) | stderr threshold (STDERR_LEVEL) | File threshold (FILE_LEVEL)    |
| ------------ | --------------------------- | ------------------------------- | ------------------------------ |
| DEBUG (10)   | default INFO → filtered    | default WARNING → filtered     | written if FILE_LEVEL <= DEBUG |
| INFO (20)    | shown                       | filtered                        | written if FILE_LEVEL <= INFO  |
| WARNING (30) | shown                       | shown                           | written                        |
| ERROR (40)   | shown                       | shown                           | written                        |
| CRITICAL(50) | shown                       | shown                           | written                        |



## Streams:

* stdout: levels >= TERM_LEVEL and < STDERR_LEVEL
* stderr: levels >= max(TERM_LEVEL, STDERR_LEVEL)
* file: levels >= FILE_LEVEL (if `to_log=True`)
* debug tracer: if `to_debug=True`, echoes via [`bugout`](vscode-file://vscode-app/Applications/Visual%20Studio%20Code%20-%20Insiders.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html)


## Environment Variables


| Variable         | Effect                                              | Default       |
| ---------------- | --------------------------------------------------- | ------------- |
| `DEBUG`        | Enable debug tracer output (`to_debug`)           | `0`         |
| `LOG`          | Enable file logging (`to_log`)                    | `0`         |
| `LOG_FILE`     | Target log filename if not overridden               | `debug.log` |
| `TERM_LEVEL`   | Minimum level for terminal (stdout/stderr)          | `INFO`      |
| `FILE_LEVEL`   | Minimum level for file logging                      | `DEBUG`     |
| `STDERR_LEVEL` | Level at/above which terminal output goes to stderr | `WARNING`   |

Values can be symbolic (`INFO`) or numeric (`20`).


## Colors

All valid color names are defined in [`Colors`](vscode-file://vscode-app/Applications/Visual%20Studio%20Code%20-%20Insiders.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html):
`black, red, green, yellow, blue, magenta, cyan, white`

If `color` is omitted, an automatic default mapping is applied by level:

* ERROR+ → red
* WARNING → yellow
* INFO → green
* DEBUG → cyan


## JSON Log Format

When `json_logs=True`, each eligible file record is a JSON line with fields from [`LogRecord`](vscode-file://vscode-app/Applications/Visual%20Studio%20Code%20-%20Insiders.app/Contents/Resources/app/out/vs/code/electron-browser/workbench/workbench.html):

```json

{
  "ts": "2025-01-01 12:00:00.123",
  "level": "INFO",
  "message": "User login",
  "color": "\u001b[32m",
  "pid": 12345,
  "thread": "HiVizWorker",
  "file": "/abs/path/app.py",
  "line": 42,
  "ctx": {"user": "alice", "ip": "10.0.0.5"}
}

```
