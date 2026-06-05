"""
crucible_proxy.output
~~~~~~~~~~~~~~~~~~~~~
Result persistence in three formats: TXT (plain), JSON, CSV.
Also writes an optional machine-readable debug report.
"""
from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .models import CheckResult, ProxyType

log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _alive_sorted(results: list[CheckResult]) -> list[CheckResult]:
    return sorted(
        (r for r in results if r.alive),
        key=lambda r: r.latency_ms or float("inf"),
    )


def _result_to_dict(r: CheckResult) -> dict:
    return {
        "proxy":      str(r.proxy),
        "host":       r.proxy.host,
        "port":       r.proxy.port,
        "type":       r.proxy.type.value,
        "latency_ms": r.latency_ms,
        "country":    r.country,
        "anonymity":  r.anonymity.value,
        "check_url":  r.check_url,
    }


# ── Format writers ────────────────────────────────────────────────────────────

def _write_txt(alive: list[CheckResult], simple_path: Path, detailed_path: Path) -> None:
    with simple_path.open("w", encoding="utf-8") as fh:
        for r in alive:
            fh.write(f"{r.proxy}\n")

    col_w = max((len(str(r.proxy)) for r in alive), default=24)
    with detailed_path.open("w", encoding="utf-8") as fh:
        fh.write(f"# Generated : {datetime.now().isoformat()}\n")
        fh.write(f"# Count     : {len(alive)}\n")
        fh.write("# Columns   : proxy | latency_ms | country | anonymity\n\n")
        for r in alive:
            lat     = f"{r.latency_ms}ms" if r.latency_ms is not None else "  —  "
            country = r.country or "??"
            fh.write(
                f"{str(r.proxy):<{col_w}}  |  {lat:<10}  |  {country:<4}  |  {r.anonymity.value}\n"
            )


def _write_json(alive: list[CheckResult], detailed_path: Path) -> None:
    data = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "count":     len(alive),
        "proxies":   [_result_to_dict(r) for r in alive],
    }
    with detailed_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def _write_csv(alive: list[CheckResult], detailed_path: Path) -> None:
    fieldnames = ["proxy", "host", "port", "type", "latency_ms", "country", "anonymity", "check_url"]
    with detailed_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in alive:
            writer.writerow(_result_to_dict(r))


# ── Debug report ──────────────────────────────────────────────────────────────

def write_debug_report(
    results:    list[CheckResult],
    proxy_type: ProxyType,
    elapsed_s:  float,
    output_dir: Path,
) -> Path:
    """
    Write a full JSON debug report including dead proxies and their error messages.
    Useful for diagnosing source quality and network issues.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"{proxy_type.value}_{ts}_debug.json"

    alive = [r for r in results if r.alive]
    dead  = [r for r in results if not r.alive]

    report = {
        "meta": {
            "generated":   datetime.now(timezone.utc).isoformat(),
            "proxy_type":  proxy_type.value,
            "elapsed_s":   round(elapsed_s, 2),
            "total":       len(results),
            "alive":       len(alive),
            "dead":        len(dead),
            "success_pct": round(len(alive) / len(results) * 100, 1) if results else 0,
        },
        "alive": [_result_to_dict(r) for r in alive],
        "dead": [
            {
                "proxy": str(r.proxy),
                "error": r.error,
            }
            for r in dead
        ],
    }

    with path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    log.info("Debug report written to %s", path)
    return path


# ── Public API ────────────────────────────────────────────────────────────────

def save_results(
    results:    list[CheckResult],
    proxy_type: ProxyType,
    output_dir: Path | None = None,
    fmt:        str         = "txt",
) -> tuple[Path, Path]:
    """
    Persist live proxies to *output_dir* in the requested format.

    Parameters
    ----------
    results:    All CheckResult objects (alive + dead).
    proxy_type: Used in the output filenames.
    output_dir: Target directory (created if absent). Falls back to constants.OUTPUT_DIR.
    fmt:        ``"txt"`` | ``"json"`` | ``"csv"``

    Returns
    -------
    (simple_path, detailed_path)
        *simple_path* contains one ``host:port`` per line (TXT only; equals
        detailed_path for JSON/CSV).
    """
    from .constants import OUTPUT_DIR
    out = Path(output_dir) if output_dir else OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    ptype = proxy_type.value
    alive = _alive_sorted(results)

    if fmt == "json":
        path = out / f"{ptype}_{ts}.json"
        _write_json(alive, path)
        return path, path

    if fmt == "csv":
        path = out / f"{ptype}_{ts}.csv"
        _write_csv(alive, path)
        return path, path

    # Default: txt
    simple   = out / f"{ptype}_{ts}_simple.txt"
    detailed = out / f"{ptype}_{ts}_detailed.txt"
    _write_txt(alive, simple, detailed)
    return simple, detailed
