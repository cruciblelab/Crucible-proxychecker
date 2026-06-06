"""
crucible_proxy.session
~~~~~~~~~~~~~~~~~~~~~~~
High-level, declarative API for non-programmers.

Instead of wiring together ``fetch_proxies`` + ``check_all`` + filters + savers,
configure everything in one place — like a JSON config — and call ``.run()``.

Quick start
-----------
>>> from crucible_proxy import Session
>>> s = Session(types=["http", "socks5"], elite=True, max_latency=1000)
>>> results = s.run()

From a dict / JSON
------------------
>>> s = Session.from_dict({"types": ["socks5"], "workers": 300, "elite": True})
>>> s = Session.from_json("config.json")

Everything is optional and has sensible defaults.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Callable

from .checker import check_all
from .constants import MAX_WORKERS, PROXY_SOURCES, TIMEOUT_SEC
from .fetcher import fetch_from_source_manager_compat, parse_line
from .models import (
    Anonymity,
    CheckResult,
    Proxy,
    ProxyCache,
    ProxyType,
    SourceStats,
)
from .output import save_results


@dataclass
class Session:
    """
    A fully-configurable proxy scraping + validation session.

    Parameters
    ----------
    types:
        Proxy types to process. Any of ``"http"``, ``"https"``, ``"socks4"``,
        ``"socks5"``. Defaults to all four.
    workers:
        Number of concurrent validation threads. Default ``200``.
    timeout:
        Per-request timeout in seconds. Default ``8``.
    verify_twice:
        Confirm each live proxy with a second request. Default ``False``.
    source_timeout:
        Timeout in seconds per source URL when downloading lists. Default ``20``.
    max_sources:
        Maximum source URLs to use per type (``None`` = all). Default ``None``.
    source_file:
        Path to a local proxy list to use *instead* of online sources.
    extra_sources:
        Extra source URLs to append, e.g. ``{"http": ["https://my.list/http.txt"]}``.
    exclude_sources:
        Substrings of source hosts to skip, e.g. ``["geonode", "proxy-list.download"]``.

    Filters
    -------
    elite:
        Keep only ELITE proxies. Default ``False``.
    anonymous:
        Keep only ELITE + ANONYMOUS proxies. Default ``False``.
    max_latency / min_latency:
        Latency bounds in milliseconds.
    min_score / max_score:
        Quality-score bounds (0–100).
    countries:
        Allowed country codes, e.g. ``["US", "DE", "TR"]``.
    exclude_countries:
        Country codes to drop.
    ports / exclude_ports:
        Port allow / deny lists.

    Output
    ------
    save:
        Write result files to disk. Default ``True``.
    output_format:
        ``"txt"``, ``"json"``, or ``"csv"``. Default ``"txt"``.
    output_dir:
        Where to write files. Default ``"./proxies"``.
    use_cache:
        Re-use a :class:`ProxyCache` across types / runs. Default ``True``.
    """

    # ── Source / network ──────────────────────────────────────────────────────
    types:           list[str]            = field(default_factory=lambda: ["http", "https", "socks4", "socks5"])
    workers:         int                  = 200
    timeout:         int                  = 8
    verify_twice:    bool                 = False
    source_timeout:  int                  = 20
    max_sources:     int | None           = None
    source_file:     str | None           = None
    extra_sources:   dict[str, list[str]] = field(default_factory=dict)
    exclude_sources: list[str]            = field(default_factory=list)

    # ── Filters ───────────────────────────────────────────────────────────────
    elite:             bool             = False
    anonymous:         bool             = False
    max_latency:       float | None     = None
    min_latency:       float | None     = None
    min_score:         float | None     = None
    max_score:         float | None     = None
    countries:         list[str] | None = None
    exclude_countries: list[str] | None = None
    cities:            list[str] | None = None
    exclude_asn:       list[str] | None = None
    ports:             list[int] | None = None
    exclude_ports:     list[int] | None = None

    # ── Output ──────────────────────────────────────────────────────────────────
    save:          bool   = True
    output_format: str    = "txt"
    output_dir:    str    = "./proxies"
    use_cache:     bool   = True

    # ── Callbacks (advanced — bring your own functions) ─────────────────────────
    on_result:    "Callable[[CheckResult], None] | None" = None  # called for every checked proxy
    on_alive:     "Callable[[CheckResult], None] | None" = None  # called only for live proxies
    on_progress:  "Callable[[int, int], None]      | None" = None  # called with (checked, total)

    # ── Internal ────────────────────────────────────────────────────────────────
    _cache: ProxyCache | None = field(default=None, repr=False)

    # ── Constructors ────────────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        """Build a Session from a plain dict (e.g. parsed JSON)."""
        valid = {f.name for f in fields(cls) if not f.name.startswith("_")}
        unknown = set(data) - valid
        if unknown:
            raise ValueError(f"Unknown Session option(s): {sorted(unknown)}")
        return cls(**{k: v for k, v in data.items() if k in valid})

    @classmethod
    def from_json(cls, path: str | Path) -> Session:
        """Build a Session from a JSON config file."""
        with Path(path).open("r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    def to_dict(self) -> dict[str, Any]:
        """Export current settings as a dict (JSON-serializable)."""
        return {
            f.name: getattr(self, f.name)
            for f in fields(self)
            if not f.name.startswith("_")
        }

    def save_config(self, path: str | Path) -> Path:
        """Write the current settings to a JSON file."""
        p = Path(path)
        with p.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        return p

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _proxy_types(self) -> list[ProxyType]:
        return [ProxyType(t) for t in self.types]

    def _matches_filter(self, r: CheckResult) -> bool:
        if not r.alive:
            return False
        if self.elite and r.anonymity != Anonymity.ELITE:
            return False
        if self.anonymous and r.anonymity not in (Anonymity.ELITE, Anonymity.ANONYMOUS):
            return False
        lat = r.latency_ms
        if self.max_latency is not None and (lat is None or lat > self.max_latency):
            return False
        if self.min_latency is not None and (lat is None or lat < self.min_latency):
            return False
        sc = score(r)
        if self.min_score is not None and sc < self.min_score:
            return False
        if self.max_score is not None and sc > self.max_score:
            return False
        ctry = (r.country or "??").upper()
        if self.countries and ctry not in [c.upper() for c in self.countries]:
            return False
        if self.exclude_countries and ctry in [c.upper() for c in self.exclude_countries]:
            return False
        if self.cities:
            city = (r.city or "").lower()
            if not any(c.lower() in city for c in self.cities):
                return False
        if self.exclude_asn and r.asn:
            asn_lower = r.asn.lower()
            if any(a.lower() in asn_lower for a in self.exclude_asn):
                return False
        if self.ports and r.proxy.port not in self.ports:
            return False
        if self.exclude_ports and r.proxy.port in self.exclude_ports:
            return False
        return True

    def _gather(self, proxy_type: ProxyType) -> tuple[list[Proxy], list[SourceStats]]:
        # Local file overrides everything
        if self.source_file:
            path = Path(self.source_file)
            proxies, seen = [], set()
            if path.exists():
                with path.open("r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        p = parse_line(line, proxy_type)
                        if p and str(p) not in seen:
                            seen.add(str(p))
                            proxies.append(p)
            return proxies, []

        # Build URL list
        urls = list(PROXY_SOURCES.get(proxy_type.value, []))
        if self.exclude_sources:
            urls = [u for u in urls if not any(h in u for h in self.exclude_sources)]
        if self.max_sources is not None:
            urls = urls[: self.max_sources]
        extra = self.extra_sources.get(proxy_type.value, [])
        urls = urls + list(extra)

        return fetch_from_source_manager_compat(urls, proxy_type, self.source_timeout)

    # ── Public API ──────────────────────────────────────────────────────────────

    def run(self) -> dict[str, list[CheckResult]]:
        """
        Execute the full pipeline for every configured type.

        Returns
        -------
        dict[str, list[CheckResult]]
            Mapping of proxy-type string → filtered live results, e.g.
            ``{"http": [...], "socks5": [...]}``.
        """
        if self.use_cache and self._cache is None:
            self._cache = ProxyCache()

        all_results: dict[str, list[CheckResult]] = {}
        out_dir = Path(self.output_dir)

        for proxy_type in self._proxy_types():
            proxies, _src_stats = self._gather(proxy_type)
            if not proxies:
                all_results[proxy_type.value] = []
                continue

            total   = len(proxies)
            checked = 0
            results: list[CheckResult] = []
            for r in check_all(
                proxies,
                max_workers  = self.workers,
                timeout      = self.timeout,
                verify_twice = self.verify_twice,
                cache        = self._cache,
            ):
                results.append(r)
                checked += 1
                if self.on_result:
                    self.on_result(r)
                if self.on_alive and r.alive:
                    self.on_alive(r)
                if self.on_progress:
                    self.on_progress(checked, total)

            filtered = [r for r in results if self._matches_filter(r)]
            all_results[proxy_type.value] = filtered

            if self.save and filtered:
                dead = [r for r in results if not r.alive]
                save_results(filtered + dead, proxy_type, output_dir=out_dir, fmt=self.output_format)

        return all_results

    def run_with_stats(self) -> dict[str, dict[str, Any]]:
        """
        Like :meth:`run`, but returns richer info per type: live results,
        source health, and summary counts.
        """
        if self.use_cache and self._cache is None:
            self._cache = ProxyCache()

        report: dict[str, dict[str, Any]] = {}
        out_dir = Path(self.output_dir)

        for proxy_type in self._proxy_types():
            t0 = time.perf_counter()
            proxies, src_stats = self._gather(proxy_type)

            results: list[CheckResult] = []
            if proxies:
                results = list(
                    check_all(
                        proxies,
                        max_workers  = self.workers,
                        timeout      = self.timeout,
                        verify_twice = self.verify_twice,
                        cache        = self._cache,
                    )
                )

            filtered = [r for r in results if self._matches_filter(r)]
            alive    = [r for r in results if r.alive]

            if self.save and filtered:
                dead = [r for r in results if not r.alive]
                save_results(filtered + dead, proxy_type, output_dir=out_dir, fmt=self.output_format)

            report[proxy_type.value] = {
                "results":      filtered,
                "total":        len(results),
                "alive":        len(alive),
                "matched":      len(filtered),
                "elapsed_s":    round(time.perf_counter() - t0, 1),
                "source_stats": src_stats,
            }

        return report

    # ── Shortcut methods ────────────────────────────────────────────────────────

    def live_only(self) -> list[CheckResult]:
        """Run and return a flat list of live (filtered) results across all types."""
        results = self.run()
        return [r for proxies in results.values() for r in proxies]

    def to_list(self) -> list[str]:
        """Run and return a flat list of ``host:port`` strings (live only)."""
        return [str(r.proxy) for r in self.live_only()]

    def best(self, n: int = 10) -> list[CheckResult]:
        """Run and return the top *n* results ranked by quality score."""
        live = self.live_only()
        return sorted(live, key=score, reverse=True)[:n]

    def fastest(self, n: int = 10) -> list[CheckResult]:
        """Run and return the *n* lowest-latency live results."""
        live = [r for r in self.live_only() if r.latency_ms is not None]
        return sorted(live, key=lambda r: r.latency_ms or float("inf"))[:n]

    # ── Async support ─────────────────────────────────────────────────────────

    async def run_async(self) -> dict[str, list[CheckResult]]:
        """
        Async wrapper around :meth:`run`. Runs the (thread-pool-based) pipeline in
        an executor so it doesn't block the event loop.

        >>> results = await Session(types=["http"]).run_async()
        """
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as pool:
            return await loop.run_in_executor(pool, self.run)

    async def live_only_async(self) -> list[CheckResult]:
        """Async version of :meth:`live_only`."""
        results = await self.run_async()
        return [r for proxies in results.values() for r in proxies]

    # ── Export formats ──────────────────────────────────────────────────────────

    def export(self, fmt: str, path: str | Path | None = None) -> str:
        """
        Export the current cached live results to a proxy-client config format.

        Parameters
        ----------
        fmt:
            One of ``"clash"``, ``"v2ray"``, ``"shadowsocks"``, ``"txt"``.
        path:
            Optional file path to write to. If omitted, returns the string.

        Note
        ----
        Call :meth:`run` first (or this will run automatically using cached results).
        """
        live = self.live_only()
        content = _export_proxies(live, fmt)
        if path is not None:
            Path(path).write_text(content, encoding="utf-8")
        return content


# ──────────────────────────────────────────────────────────────────────────────
# Export helpers
# ──────────────────────────────────────────────────────────────────────────────

def _export_proxies(results: list[CheckResult], fmt: str) -> str:
    """Render live proxies into a proxy-client config string."""
    fmt = fmt.lower()
    live = [r for r in results if r.alive]

    if fmt == "txt":
        return "\n".join(str(r.proxy) for r in live) + "\n"

    if fmt == "clash":
        # Clash proxies YAML block
        lines = ["proxies:"]
        for i, r in enumerate(live):
            p = r.proxy
            ptype = "socks5" if p.type.value in ("socks4", "socks5") else "http"
            name  = f"{p.type.value}-{p.host}-{p.port}"
            lines.append(f"  - name: \"{name}\"")
            lines.append(f"    type: {ptype}")
            lines.append(f"    server: {p.host}")
            lines.append(f"    port: {p.port}")
        return "\n".join(lines) + "\n"

    if fmt == "v2ray":
        # v2ray-style JSON outbounds
        outbounds = []
        for r in live:
            p = r.proxy
            protocol = "socks" if p.type.value in ("socks4", "socks5") else "http"
            outbounds.append({
                "protocol": protocol,
                "settings": {
                    "servers": [{"address": p.host, "port": p.port}]
                },
                "tag": f"{p.type.value}-{p.host}-{p.port}",
            })
        return json.dumps({"outbounds": outbounds}, indent=2)

    if fmt == "shadowsocks":
        # Plain ss-style list (host:port per line with type prefix)
        lines = []
        for r in live:
            p = r.proxy
            lines.append(f"{p.type.value}://{p.host}:{p.port}")
        return "\n".join(lines) + "\n"

    raise ValueError(f"Unknown export format: {fmt!r}. Use clash, v2ray, shadowsocks, or txt.")


# ──────────────────────────────────────────────────────────────────────────────
# Quality scoring (shared by Session filters)
# ──────────────────────────────────────────────────────────────────────────────

def score(result: CheckResult) -> float:
    """Compute a 0–100 quality score for a CheckResult (latency + anonymity)."""
    if not result.alive:
        return 0.0
    s = 40.0
    s += {
        Anonymity.ELITE:       35,
        Anonymity.ANONYMOUS:   20,
        Anonymity.UNKNOWN:     5,
        Anonymity.TRANSPARENT: -15,
    }.get(result.anonymity, 0)
    lat = result.latency_ms or 9999
    if   lat <  150: s += 25
    elif lat <  300: s += 20
    elif lat <  600: s += 15
    elif lat < 1000: s += 10
    elif lat < 2000: s += 5
    elif lat < 4000: s += 2
    else:            s -= 5
    if result.country and result.country != "??":
        s += 3
    return max(0.0, min(100.0, round(s, 1)))
