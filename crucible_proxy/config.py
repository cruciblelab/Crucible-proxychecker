"""
crucible_proxy.config
~~~~~~~~~~~~~~~~~~~~~
Unified configuration system with three-tier priority:

    CLI flags  >  environment variables  >  config file  >  built-in defaults

Config file locations (first found wins):
    ./crucible_proxy.toml
    ~/.config/crucible_proxy/config.toml
    ~/.crucible_proxy.toml

All settings can also be set via environment variables prefixed with
CRUCIBLE_:
    CRUCIBLE_TIMEOUT=10
    CRUCIBLE_WORKERS=300
    CRUCIBLE_LOG_LEVEL=DEBUG
    CRUCIBLE_OUTPUT_FORMAT=json
    CRUCIBLE_OUTPUT_DIR=./my_output
    CRUCIBLE_VERIFY_TWICE=false
    CRUCIBLE_ANONYMITY_CHECK_URL=http://my-server/headers
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ── Defaults ──────────────────────────────────────────────────────────────────

_CONFIG_SEARCH_PATHS = [
    Path("crucible_proxy.toml"),
    Path.home() / ".config" / "crucible_proxy" / "config.toml",
    Path.home() / ".crucible_proxy.toml",
]

_ENV_PREFIX = "CRUCIBLE_"

_VALID_LOG_LEVELS  = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_VALID_OUTPUT_FMTS = {"txt", "json", "csv"}


# ── Config dataclass ──────────────────────────────────────────────────────────

@dataclass
class Config:
    # Network
    timeout:    int  = 8
    workers:    int  = 200
    retries:    int  = 2
    retry_delay: float = 0.6
    verify_twice: bool = True

    # Anonymity check
    anonymity_check_url: str = "http://httpbin.org/headers"

    # Output
    output_dir:    Path = field(default_factory=lambda: Path("output"))
    output_format: str  = "txt"   # txt | json | csv
    no_color:      bool = False

    # Logging / debug
    log_level:   str  = "WARNING"   # DEBUG | INFO | WARNING | ERROR | CRITICAL
    log_file:    Path | None = None
    debug_report: bool = False       # write a machine-readable debug JSON after each run


    # ── Validation ────────────────────────────────────────────────────────────

    def __post_init__(self) -> None:
        if self.log_level.upper() not in _VALID_LOG_LEVELS:
            raise ValueError(
                f"log_level must be one of {_VALID_LOG_LEVELS}, got {self.log_level!r}"
            )
        if self.output_format.lower() not in _VALID_OUTPUT_FMTS:
            raise ValueError(
                f"output_format must be one of {_VALID_OUTPUT_FMTS}, got {self.output_format!r}"
            )
        if self.timeout < 1:
            raise ValueError("timeout must be >= 1")
        if self.workers < 1:
            raise ValueError("workers must be >= 1")

        # Normalize
        self.log_level     = self.log_level.upper()
        self.output_format = self.output_format.lower()
        self.output_dir    = Path(self.output_dir)
        if self.log_file is not None:
            self.log_file = Path(self.log_file)


# ── TOML loader (stdlib tomllib ≥3.11 / tomli fallback) ──────────────────────

def _load_toml(path: Path) -> dict[str, Any]:
    if sys.version_info >= (3, 11):
        import tomllib
        with path.open("rb") as f:
            return tomllib.load(f)
    try:
        import tomli  # type: ignore[import]
        with path.open("rb") as f:
            return tomli.load(f)
    except ImportError:
        log.debug("tomli not installed — skipping TOML config at %s", path)
        return {}


def _find_config_file() -> Path | None:
    for p in _CONFIG_SEARCH_PATHS:
        if p.exists():
            return p
    return None


# ── Environment variable reader ───────────────────────────────────────────────

def _read_env() -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    _bool = lambda v: v.lower() not in ("false", "0", "no", "off")

    converters: dict[str, Any] = {
        "timeout":             int,
        "workers":             int,
        "retries":             int,
        "retry_delay":         float,
        "verify_twice":        _bool,
        "anonymity_check_url": str,
        "output_dir":          Path,
        "output_format":       str,
        "no_color":            _bool,
        "log_level":           str,
        "log_file":            Path,
        "debug_report":        _bool,
    }

    for key, conv in converters.items():
        env_key = _ENV_PREFIX + key.upper()
        raw = os.environ.get(env_key)
        if raw is not None:
            try:
                mapping[key] = conv(raw)
            except (ValueError, TypeError) as exc:
                log.warning("Bad env var %s=%r: %s", env_key, raw, exc)

    return mapping


# ── Public loader ─────────────────────────────────────────────────────────────

def load_config(overrides: dict[str, Any] | None = None) -> Config:
    """
    Build a Config by merging (lowest → highest priority):
      1. Built-in defaults  (Config dataclass defaults)
      2. Config file        (TOML)
      3. Environment vars   (CRUCIBLE_*)
      4. *overrides* dict   (CLI flags)

    Parameters
    ----------
    overrides:
        Key-value pairs that take highest priority (typically from CLI args).
        ``None`` values in this dict are ignored so argparse defaults don't
        accidentally shadow lower-priority settings.

    Returns
    -------
    Config
        Validated configuration instance.
    """
    merged: dict[str, Any] = {}

    # Layer 2: config file
    cfg_path = _find_config_file()
    if cfg_path:
        raw = _load_toml(cfg_path)
        merged.update({k: v for k, v in raw.items() if k in {f.name for f in fields(Config)}})
        log.debug("Loaded config from %s", cfg_path)

    # Layer 3: env vars
    merged.update(_read_env())

    # Layer 4: CLI overrides (skip None)
    if overrides:
        merged.update({k: v for k, v in overrides.items() if v is not None})

    try:
        return Config(**merged)
    except TypeError as exc:
        raise ValueError(f"Unknown config key: {exc}") from exc


def apply_logging(cfg: Config) -> None:
    """Configure the root logger from *cfg*."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if cfg.log_file:
        cfg.log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(cfg.log_file, encoding="utf-8"))

    logging.basicConfig(
        level    = getattr(logging, cfg.log_level),
        format   = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt  = "%H:%M:%S",
        handlers = handlers,
        force    = True,
    )


def generate_template() -> str:
    """Return a commented TOML config template string."""
    return """\
# crucible_proxy.toml — place in your project root or ~/.config/crucible_proxy/
# All values shown are the built-in defaults.
# Priority order: CLI flags > env vars > this file > built-in defaults.

# ── Network ───────────────────────────────────────────────────────────────────
timeout      = 8        # per-request timeout in seconds
workers      = 200      # max concurrent threads
retries      = 2        # check retries before marking dead
retry_delay  = 0.6      # seconds between retries
verify_twice = true     # confirm live proxies with a second request

# ── Anonymity detection ───────────────────────────────────────────────────────
# Must return JSON with a top-level "headers" object (httpbin /headers format).
anonymity_check_url = "http://httpbin.org/headers"

# ── Output ────────────────────────────────────────────────────────────────────
output_dir    = "output"   # directory for result files
output_format = "txt"      # txt | json | csv
no_color      = false      # disable ANSI colour in terminal output

# ── Logging & debug ───────────────────────────────────────────────────────────
log_level    = "WARNING"   # DEBUG | INFO | WARNING | ERROR | CRITICAL
# log_file   = "crucible.log"   # uncomment to also write logs to a file
debug_report = false       # write a machine-readable JSON debug report per run
"""
