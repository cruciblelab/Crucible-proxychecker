"""
╔═══════════════════════════════════════════════════════════════════════════╗
║              CRUCIBLE PROXY SUITE — ULTIMATE EDITION                     ║
║              pip install crucible-proxychecker                           ║
╚═══════════════════════════════════════════════════════════════════════════╝

FEATURES:
  ✦ HTTP / HTTPS / SOCKS4 / SOCKS5 full support
  ✦ Fully configurable source count and URLs
  ✦ Advanced filtering (country, latency, anonymity, score, port, regex)
  ✦ Proxy quality scoring system (0–100, letter grade S/A/B/C/D/F)
  ✦ Live stats panel + colored histogram
  ✦ Re-check, single verify, bulk verify
  ✦ Custom file source support
  ✦ Multiple output formats (txt / json / csv)
  ✦ Session archive + debug report
  ✦ Proxy rotation simulator
  ✦ Multi-type duplicate analysis
  ✦ Port statistics
  ✦ Latency/anonymity histogram
  ✦ Interactive Q&A menu + full CLI mode
  ✦ Colored ASCII banner + type icons
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from crucible_proxy import (
    Anonymity, CheckResult, Config, Proxy, ProxyType, Stats,
    check_all, check_proxy, fetch_proxies, load_config,
    save_results, write_debug_report,
)
from crucible_proxy.constants import PROXY_SOURCES, TIMEOUT_SEC
from crucible_proxy.fetcher import _make_session, parse_line

# ══════════════════════════════════════════════════════════════════════════════
# COLOR SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

try:
    from colorama import Fore, Style, init as _ci
    _ci(autoreset=True)
    G=Fore.GREEN; R=Fore.RED; Y=Fore.YELLOW; C=Fore.CYAN
    M=Fore.MAGENTA; W=Fore.WHITE; B=Fore.BLUE
    DM=Style.DIM; BR=Style.BRIGHT; RS=Style.RESET_ALL
except ImportError:
    G=R=Y=C=M=W=B=DM=BR=RS=""

# ══════════════════════════════════════════════════════════════════════════════
# ASCII ART & BANNER
# ══════════════════════════════════════════════════════════════════════════════

BANNER = f"""{C}{BR}
 ██████╗██████╗ ██╗   ██╗ ██████╗██╗██████╗ ██╗     ███████╗
██╔════╝██╔══██╗██║   ██║██╔════╝██║██╔══██╗██║     ██╔════╝
██║     ██████╔╝██║   ██║██║     ██║██████╔╝██║     █████╗
██║     ██╔══██╗██║   ██║██║     ██║██╔══██╗██║     ██╔══╝
╚██████╗██║  ██║╚██████╔╝╚██████╗██║██████╔╝███████╗███████╗
 ╚═════╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝╚═╝╚═════╝╚══════╝╚══════╝
   C  R  U  C  I  B  L  E    P  R  O  X  Y  C  H  E  C  K  E  R{RS}
{M}{BR}                 P R O X Y   S U I T E   v 7 . 0 . 1{RS}
{DM}            HTTP · HTTPS · SOCKS4 · SOCKS5 · Elite Detection{RS}
"""

TYPE_ART = {
    ProxyType.HTTP:   f"{C}[HTTP  ]{RS}",
    ProxyType.HTTPS:  f"{G}[HTTPS ]{RS}",
    ProxyType.SOCKS4: f"{Y}[SOCKS4]{RS}",
    ProxyType.SOCKS5: f"{M}[SOCKS5]{RS}",
}

ANON_ICON = {
    Anonymity.ELITE:       f"{G}◆ elite      {RS}",
    Anonymity.ANONYMOUS:   f"{C}◇ anonymous  {RS}",
    Anonymity.TRANSPARENT: f"{R}△ transparent{RS}",
    Anonymity.UNKNOWN:     f"{DM}· unknown    {RS}",
}


# ══════════════════════════════════════════════════════════════════════════════
# SOURCE MANAGER
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SourceManager:
    """Manages source URLs for each proxy type."""
    max_sources_per_type: int = 999
    custom_urls:   dict[str, list[str]] = field(default_factory=dict)
    extra_urls:    dict[str, list[str]] = field(default_factory=dict)
    exclude_hosts: set[str]             = field(default_factory=set)

    def get_urls(self, proxy_type: ProxyType) -> list[str]:
        key  = proxy_type.value
        base = list(PROXY_SOURCES.get(key, []))
        if self.exclude_hosts:
            base = [u for u in base if not any(h in u for h in self.exclude_hosts)]
        if key in self.custom_urls and self.custom_urls[key]:
            urls = self.custom_urls[key]
        else:
            urls = base[: self.max_sources_per_type]
        if key in self.extra_urls:
            urls = urls + self.extra_urls[key]
        return urls

    def source_count(self, proxy_type: ProxyType) -> int:
        return len(self.get_urls(proxy_type))

    def list_sources(self, proxy_type: ProxyType) -> None:
        urls = self.get_urls(proxy_type)
        print(f"\n  {BR}{TYPE_ART[proxy_type]} Sources ({len(urls)}):{RS}")
        for i, url in enumerate(urls, 1):
            domain = url.split("/")[2] if "/" in url else url
            print(f"  {DM}{i:>3}.{RS} {domain}")


def fetch_from_source_manager(sm: SourceManager, proxy_type: ProxyType,
                              verbose: bool = True, source_timeout: int = 20) -> list[Proxy]:
    urls    = sm.get_urls(proxy_type)
    seen:   set[str]     = set()
    proxies: list[Proxy] = []
    if verbose:
        print(f"  {DM}{len(urls)} sources scanning... (source timeout: {source_timeout}s){RS}")
    with _make_session() as session:
        for url in urls:
            domain = url.split("/")[2] if "/" in url else url
            try:
                resp = session.get(url, timeout=source_timeout)
                resp.raise_for_status()
                before = len(proxies)
                for line in resp.text.splitlines():
                    p = parse_line(line, proxy_type)
                    if p and str(p) not in seen:
                        seen.add(str(p))
                        proxies.append(p)
                added = len(proxies) - before
                if verbose:
                    print(f"  {G}✔{RS} {domain:<45} {DM}+{added}{RS}")
            except Exception as exc:
                err = str(exc)
                if "timed out" in err.lower() or "timeout" in err.lower():
                    tag = f"{Y}timeout{RS}"
                else:
                    tag = f"{R}error{RS}"
                if verbose:
                    print(f"  {R}✘{RS} {domain:<45} {tag} {DM}{err[:40]}{RS}")
    return proxies


# ══════════════════════════════════════════════════════════════════════════════
# ADVANCED STATISTICS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class AdvancedStats:
    total:        int   = 0
    alive:        int   = 0
    dead:         int   = 0
    elite:        int   = 0
    anonymous:    int   = 0
    transparent:  int   = 0
    unknown_anon: int   = 0
    latencies:    list[float]       = field(default_factory=list)
    countries:    Counter           = field(default_factory=Counter)
    ports:        Counter           = field(default_factory=Counter)
    errors:       Counter           = field(default_factory=Counter)
    scores:       list[float]       = field(default_factory=list)
    _lock:        Lock              = field(default_factory=Lock, repr=False)
    _start:       float             = field(default_factory=time.perf_counter, repr=False)

    def record(self, result: CheckResult) -> None:
        with self._lock:
            self.total += 1
            self.ports[result.proxy.port] += 1
            if result.alive:
                self.alive += 1
                if result.latency_ms is not None:
                    self.latencies.append(result.latency_ms)
                self.countries[result.country or "??"] += 1
                self.scores.append(score_proxy(result))
                anon = result.anonymity
                if anon == Anonymity.ELITE:       self.elite += 1
                elif anon == Anonymity.ANONYMOUS: self.anonymous += 1
                elif anon == Anonymity.TRANSPARENT: self.transparent += 1
                else:                             self.unknown_anon += 1
            else:
                self.dead += 1
                if result.error:
                    self.errors[_classify_error(result.error)] += 1

    @property
    def success_rate(self) -> float:
        return (self.alive / self.total * 100) if self.total else 0.0

    @property
    def avg_latency(self) -> float:
        return sum(self.latencies) / len(self.latencies) if self.latencies else 0.0

    @property
    def median_latency(self) -> float:
        if not self.latencies: return 0.0
        s = sorted(self.latencies); n = len(s)
        return (s[n // 2] + s[(n - 1) // 2]) / 2

    @property
    def min_latency(self) -> float: return min(self.latencies) if self.latencies else 0.0

    @property
    def max_latency(self) -> float: return max(self.latencies) if self.latencies else 0.0

    @property
    def avg_score(self) -> float:
        return sum(self.scores) / len(self.scores) if self.scores else 0.0

    @property
    def top_countries(self) -> list[tuple[str, int]]:
        return self.countries.most_common(10)

    @property
    def top_ports(self) -> list[tuple[int, int]]:
        return self.ports.most_common(10)


def _classify_error(err: str) -> str:
    e = err.lower()
    if "timeout" in e or "timed out" in e: return "timeout"
    if "refused" in e:                     return "connection_refused"
    if "reset" in e or "forcibly" in e:    return "connection_reset"
    if "ssl" in e or "certificate" in e:   return "ssl_error"
    if "proxy" in e:                       return "proxy_error"
    if any(c in e for c in ("404","403","502","503")): return "http_error"
    if "name" in e or "resolve" in e:      return "dns_error"
    return "other"


# ══════════════════════════════════════════════════════════════════════════════
# PROXY SKORLAMA
# ══════════════════════════════════════════════════════════════════════════════

def score_proxy(result: CheckResult) -> float:
    if not result.alive: return 0.0
    score = 40.0
    score += {Anonymity.ELITE: 35, Anonymity.ANONYMOUS: 20,
              Anonymity.UNKNOWN: 5, Anonymity.TRANSPARENT: -15}.get(result.anonymity, 0)
    lat = result.latency_ms or 9999
    if   lat <  150: score += 25
    elif lat <  300: score += 20
    elif lat <  600: score += 15
    elif lat < 1000: score += 10
    elif lat < 2000: score += 5
    elif lat < 4000: score += 2
    else:            score -= 5
    if result.country and result.country != "??": score += 3
    return max(0.0, min(100.0, round(score, 1)))


def score_grade(score: float) -> str:
    if score >= 90: return f"{G}{BR}S{RS}"
    if score >= 75: return f"{G}A{RS}"
    if score >= 60: return f"{C}B{RS}"
    if score >= 45: return f"{Y}C{RS}"
    if score >= 30: return f"{Y}D{RS}"
    return f"{R}F{RS}"


def score_bar(score: float, width: int = 10) -> str:
    filled = int(score / 100 * width)
    col = G if score >= 75 else (Y if score >= 50 else R)
    return f"{col}{'█' * filled}{DM}{'░' * (width - filled)}{RS}"


# ══════════════════════════════════════════════════════════════════════════════
# OUTPUT UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def progress_bar(alive: int, total: int, width: int = 20) -> str:
    if total == 0: return f"{DM}{'░' * width}{RS}"
    filled = int(width * alive / total)
    pct = alive / total
    col = G if pct >= 0.2 else (Y if pct >= 0.1 else R)
    return f"{col}{'█' * filled}{DM}{'░' * (width - filled)}{RS}"


def mini_histogram(values: list[float], bins: list[float], labels: list[str], width: int = 18) -> None:
    counts = [0] * len(labels)
    for v in values:
        for i in range(len(bins) - 1):
            if bins[i] <= v < bins[i + 1]:
                counts[i] += 1; break
    if not any(counts): return
    mx = max(counts)
    for label, cnt in zip(labels, counts):
        if cnt == 0: continue
        bar_len = int(cnt / mx * width) if mx else 0
        pct = cnt / len(values) * 100 if values else 0
        print(f"    {label:<10} {G}{'█' * bar_len}{DM}{'░' * (width - bar_len)}{RS} {cnt} ({pct:.0f}%)")


def SEP():  print(f"  {C}{'─' * 66}{RS}")
def SEP2(): print(f"  {C}{'═' * 66}{RS}")


def print_result_line(result: CheckResult, stats: AdvancedStats,
                      show_score: bool = True, show_dead: bool = False) -> None:
    prog   = progress_bar(stats.alive, stats.total)
    marker = f"{DM}{stats.alive}/{stats.total}{RS}"
    if result.alive:
        lat   = result.latency_ms or 0
        lat_c = G if lat < 500 else (Y if lat < 2000 else R)
        ctry  = f"[{result.country or '??'}]"
        sc    = score_proxy(result)
        anon  = ANON_ICON.get(result.anonymity, "")
        line  = (f"  {G}✓{RS} {W}{BR}{str(result.proxy):<26}{RS}"
                 f"{lat_c}{lat:>7.0f}ms{RS}  {C}{ctry:<6}{RS}  {anon}")
        if show_score:
            line += f" {score_bar(sc, 8)} {score_grade(sc)} {DM}{sc:.0f}{RS}"
        line += f"  {prog} {marker}"
        print(line)
    elif show_dead:
        err_s = (result.error or "")[:35]
        print(f"  {R}✗{RS} {DM}{str(result.proxy):<26}{RS}{R}dead{RS}  {DM}{err_s}{RS}  {prog} {marker}")
    else:
        print(f"  {R}✗{RS} {DM}{str(result.proxy):<26} dead{RS}  {prog} {marker}", end="\r")


# ══════════════════════════════════════════════════════════════════════════════
# RAPOR
# ══════════════════════════════════════════════════════════════════════════════

def print_full_report(stats: AdvancedStats, proxy_type: ProxyType, elapsed: float) -> None:
    SEP2()
    print(f"  {TYPE_ART[proxy_type]}  {BR}RESULTS REPORT{RS}")
    SEP2()
    print(f"  {BR}General:{RS}")
    print(f"    {'Total checked':<22} {stats.total}")
    print(f"    {'Alive':<22} {G}{stats.alive}{RS}")
    print(f"    {'Dead':<22} {R}{stats.dead}{RS}")
    sr_c = G if stats.success_rate >= 15 else (Y if stats.success_rate >= 5 else R)
    print(f"    {'Success rate':<22} {sr_c}{stats.success_rate:.1f}%{RS}")
    print(f"    {'Average score':<22} {score_bar(stats.avg_score)} {stats.avg_score:.1f}/100")
    print(f"    {'Duration':<22} {elapsed:.1f}s")
    if stats.total > 0 and elapsed > 0:
        print(f"    {'Speed':<22} {stats.total / elapsed:.0f} proxies/s")

    SEP()
    print(f"  {BR}Anonymity Distribution:{RS}")
    total_a = stats.alive or 1
    for label, cnt, col in [("Elite", stats.elite, G), ("Anonymous", stats.anonymous, C),
                              ("Transparent", stats.transparent, R), ("Unknown", stats.unknown_anon, DM)]:
        if cnt == 0: continue
        bl = int(cnt / total_a * 20)
        print(f"    {label:<14} {col}{'█' * bl}{DM}{'░' * (20 - bl)}{RS} {cnt} ({cnt/total_a*100:.0f}%)")

    if stats.latencies:
        SEP()
        print(f"  {BR}Latency Statistics:{RS}")
        print(f"    {'Min':<14} {G}{stats.min_latency:.0f}ms{RS}")
        print(f"    {'Average':<14} {stats.avg_latency:.0f}ms")
        print(f"    {'Median':<14} {stats.median_latency:.0f}ms")
        print(f"    {'Max':<14} {R}{stats.max_latency:.0f}ms{RS}")
        print(f"\n  {BR}Latency Distribution:{RS}")
        mini_histogram(stats.latencies,
            bins=[0,200,500,1000,2000,5000,float("inf")],
            labels=["<200ms","<500ms","<1s","<2s","<5s","5s+"])

    if stats.top_countries:
        SEP()
        print(f"  {BR}Top Countries:{RS}")
        mx = stats.top_countries[0][1]
        for country, cnt in stats.top_countries[:8]:
            bl = int(cnt / mx * 18)
            print(f"    {country:<6} {C}{'█' * bl}{DM}{'░' * (18 - bl)}{RS} {cnt}")

    if stats.top_ports:
        SEP()
        print(f"  {BR}Top Ports:{RS}")
        mx = stats.top_ports[0][1]
        for port, cnt in stats.top_ports[:6]:
            bl = int(cnt / mx * 18)
            print(f"    {port:<8} {M}{'█' * bl}{DM}{'░' * (18 - bl)}{RS} {cnt}")

    if stats.errors:
        SEP()
        print(f"  {BR}Error Analysis:{RS}")
        for err_type, cnt in stats.errors.most_common():
            pct = cnt / stats.dead * 100 if stats.dead else 0
            print(f"    {err_type:<24} {R}{cnt}{RS} ({pct:.0f}%)")
    SEP2()


# ══════════════════════════════════════════════════════════════════════════════
# FILTER SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class AdvancedFilter:
    max_latency:       float | None     = None
    min_latency:       float | None     = None
    min_score:         float | None     = None
    max_score:         float | None     = None
    countries:         list[str] | None = None
    exclude_countries: list[str] | None = None
    anonymity_levels:  list[str] | None = None
    only_elite:        bool             = False
    only_anonymous:    bool             = False
    ports:             list[int] | None = None
    exclude_ports:     list[int] | None = None
    pattern:           str | None       = None

    def matches(self, result: CheckResult) -> bool:
        if not result.alive: return False
        if self.only_elite and result.anonymity != Anonymity.ELITE: return False
        if self.only_anonymous and result.anonymity not in (Anonymity.ELITE, Anonymity.ANONYMOUS): return False
        if self.anonymity_levels and result.anonymity.value not in self.anonymity_levels: return False
        lat = result.latency_ms
        if self.max_latency is not None and (lat is None or lat > self.max_latency): return False
        if self.min_latency is not None and (lat is None or lat < self.min_latency): return False
        sc = score_proxy(result)
        if self.min_score is not None and sc < self.min_score: return False
        if self.max_score is not None and sc > self.max_score: return False
        ctry = (result.country or "??").upper()
        if self.countries and ctry not in [c.upper() for c in self.countries]: return False
        if self.exclude_countries and ctry in [c.upper() for c in self.exclude_countries]: return False
        port = result.proxy.port
        if self.ports and port not in self.ports: return False
        if self.exclude_ports and port in self.exclude_ports: return False
        if self.pattern and not re.search(self.pattern, result.proxy.host): return False
        return True

    def describe(self) -> str:
        parts = []
        if self.only_elite:        parts.append("elite-only")
        if self.only_anonymous:    parts.append("anon-only")
        if self.max_latency:       parts.append(f"<{self.max_latency:.0f}ms")
        if self.min_score:         parts.append(f"score≥{self.min_score}")
        if self.countries:         parts.append(f"country={','.join(self.countries)}")
        if self.exclude_countries: parts.append(f"excl={','.join(self.exclude_countries)}")
        if self.ports:             parts.append(f"ports={self.ports}")
        if self.pattern:           parts.append(f"regex={self.pattern}")
        return " | ".join(parts) if parts else "none"


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def load_from_file(path: Path, proxy_type: ProxyType) -> list[Proxy]:
    if not path.exists():
        print(f"  {R}File not found: {path}{RS}"); return []
    proxies: list[Proxy] = []; seen: set[str] = set()
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            p = parse_line(line, proxy_type)
            if p and str(p) not in seen:
                seen.add(str(p)); proxies.append(p)
    print(f"  {G}✔{RS} {path.name} → {len(proxies)} proxy")
    return proxies


def print_top_proxies(results: list[CheckResult], proxy_type: ProxyType, top_n: int = 10) -> None:
    alive = [r for r in results if r.alive]
    if not alive: return
    ranked = sorted(alive, key=score_proxy, reverse=True)[:top_n]
    print(f"\n  {BR}Top {len(ranked)} Proxies — {proxy_type.value.upper()}:{RS}")
    SEP()
    for i, r in enumerate(ranked, 1):
        sc = score_proxy(r)
        print(f"  {DM}{i:>2}.{RS} {G}{str(r.proxy):<26}{RS}"
              f"  {r.latency_ms:>7.0f}ms  [{r.country or '??'}]"
              f"  {ANON_ICON.get(r.anonymity,'')}"
              f"  {score_bar(sc, 10)} {score_grade(sc)} {DM}{sc:.0f}{RS}")
    SEP()


def rotation_demo(results: list[CheckResult], count: int = 5) -> None:
    alive = [r for r in results if r.alive and score_proxy(r) >= 50]
    if not alive: return
    print(f"\n  {BR}Proxy Rotation Simulation ({count} istek):{RS}")
    SEP()
    for i in range(1, count + 1):
        r  = random.choice(alive)
        sc = score_proxy(r)
        print(f"  Request {i:<3}  {G}{str(r.proxy):<26}{RS}"
              f"  {r.latency_ms:.0f}ms  [{r.country or '??'}]"
              f"  {ANON_ICON.get(r.anonymity,'')}  {score_grade(sc)}")
        time.sleep(0.05)
    SEP()


def analyze_duplicates(all_results: dict[str, list[CheckResult]]) -> None:
    proxy_types: dict[str, list[str]] = defaultdict(list)
    for ptype, results in all_results.items():
        for r in results:
            if r.alive: proxy_types[str(r.proxy)].append(ptype)
    multi = {p: t for p, t in proxy_types.items() if len(t) > 1}
    if not multi: return
    print(f"\n  {BR}Proxies Working on Multiple Types ({len(multi)}):{RS}")
    SEP()
    for proxy, types in list(multi.items())[:10]:
        print(f"  {G}{proxy:<26}{RS}  {' + '.join(t.upper() for t in types)}")
    SEP()


def verify_single(proxy_str: str, proxy_type: ProxyType, cfg: Config) -> None:
    parts = proxy_str.strip().split(":")
    if len(parts) != 2: print(f"{R}Invalid format. Expected: host:port{RS}"); return
    host = parts[0]
    try: port = int(parts[1])
    except ValueError: print(f"{R}Invalid port{RS}"); return
    proxy = Proxy(host=host, port=port, type=proxy_type)
    print(f"\n  {C}Checking: {proxy}  [{proxy_type.value.upper()}]{RS}\n")
    t0     = time.perf_counter()
    result = check_proxy(proxy, verify_twice=True, timeout=cfg.timeout)
    el     = time.perf_counter() - t0
    sc     = score_proxy(result)
    print(f"  {'Proxy':<18} {proxy}")
    print(f"  {'Type':<18} {proxy_type.value.upper()}")
    print(f"  {'Status':<18} {G+'Alive ✓'+RS if result.alive else R+'Dead ✗'+RS}")
    if result.alive:
        print(f"  {'Latency':<18} {result.latency_ms:.1f}ms")
        print(f"  {'Country':<18} {result.country or '??'}")
        print(f"  {'Anonymity':<18} {ANON_ICON.get(result.anonymity,'')}")
        print(f"  {'Score':<18} {score_bar(sc)} {score_grade(sc)} {sc:.1f}/100")
        print(f"  {'Check URL':<18} {result.check_url or '-'}")
    else:
        print(f"  {'Error':<18} {R}{result.error}{RS}")
    print(f"  {'Duration':<18} {el:.2f}s\n")


def recheck_mode(path: Path, proxy_type: ProxyType, cfg: Config, output_dir: Path, fmt: str) -> None:
    proxies = load_from_file(path, proxy_type)
    if not proxies: return
    print(f"\n  {C}Re-check: {len(proxies)} proxy → checking...{RS}\n")
    stats = AdvancedStats(); results = []; t0 = time.perf_counter()
    for result in check_all(proxies, max_workers=cfg.workers, timeout=cfg.timeout, verify_twice=cfg.verify_twice):
        stats.record(result); results.append(result)
        print_result_line(result, stats, show_dead=False)
    elapsed = time.perf_counter() - t0
    print_full_report(stats, proxy_type, elapsed)
    if any(r.alive for r in results):
        simple, _ = save_results(results, proxy_type, output_dir=output_dir, fmt=fmt)
        print(f"  {DM}↳ {simple.name}{RS}")


def verify_bulk(path: Path, proxy_type: ProxyType, cfg: Config, output_dir: Path) -> None:
    proxies = load_from_file(path, proxy_type)
    if not proxies: return
    print(f"\n  {C}Bulk verify: {len(proxies)} proxy{RS}\n")
    stats = AdvancedStats(); results = []; t0 = time.perf_counter()
    for result in check_all(proxies, max_workers=cfg.workers, timeout=cfg.timeout, verify_twice=True):
        stats.record(result); results.append(result)
        print_result_line(result, stats, show_dead=True)
    elapsed = time.perf_counter() - t0
    print_full_report(stats, proxy_type, elapsed)
    if any(r.alive for r in results):
        save_results(results, proxy_type, output_dir=output_dir, fmt="txt")


def archive_session(all_results: dict[str, list[CheckResult]],
                    all_stats: dict[str, AdvancedStats],
                    output_dir: Path, session_id: str, flt: AdvancedFilter) -> Path:
    archive_dir = output_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    path = archive_dir / f"session_{session_id}.json"
    grand_total = grand_alive = 0
    doc: dict[str, Any] = {
        "session_id": session_id,
        "generated":  datetime.now(timezone.utc).isoformat(),
        "filter":     flt.describe(),
        "summary":    {},
        "proxy_types": {},
    }
    for ptype, results in all_results.items():
        st = all_stats.get(ptype, AdvancedStats())
        alive = [r for r in results if r.alive]
        grand_total += st.total; grand_alive += st.alive
        doc["proxy_types"][ptype] = {
            "total": st.total, "alive": st.alive,
            "success_pct": round(st.success_rate, 1),
            "avg_latency": round(st.avg_latency, 1),
            "avg_score":   round(st.avg_score, 1),
            "elite": st.elite, "anonymous": st.anonymous,
            "proxies": [
                {"proxy": str(r.proxy), "host": r.proxy.host, "port": r.proxy.port,
                 "latency_ms": r.latency_ms, "country": r.country,
                 "anonymity": r.anonymity.value, "score": score_proxy(r),
                 "check_url": r.check_url}
                for r in sorted(alive, key=lambda x: score_proxy(x), reverse=True)
            ],
        }
    doc["summary"] = {
        "grand_total": grand_total, "grand_alive": grand_alive,
        "success_pct": round(grand_alive / grand_total * 100, 1) if grand_total else 0,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
    return path


# ══════════════════════════════════════════════════════════════════════════════
# ANA PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def run_pipeline(proxy_type: ProxyType, cfg: Config, sm: SourceManager, flt: AdvancedFilter,
                 output_dir: Path, fmt: str, custom_file: Path | None = None,
                 show_dead: bool = False, show_score: bool = True, top_n: int = 10,
                 rotation: bool = False, debug: bool = False, verbose_src: bool = True,
                 source_timeout: int = 20,
                 ) -> tuple[AdvancedStats, list[CheckResult]]:

    print(f"\n  {C}{'═' * 66}{RS}")
    print(f"  {TYPE_ART[proxy_type]}  {BR}Pipeline Starting{RS}")
    print(f"  {DM}Sources: {sm.source_count(proxy_type)} URL  |  Filter: {flt.describe()}{RS}")
    SEP()

    t0 = time.perf_counter()

    if custom_file:
        proxies = load_from_file(custom_file, proxy_type)
    else:
        proxies = fetch_from_source_manager(sm, proxy_type, verbose=verbose_src,
                                             source_timeout=source_timeout)

    if not proxies:
        print(f"  {Y}No proxies found.{RS}")
        return AdvancedStats(), []

    fetch_time = time.perf_counter() - t0
    print(f"\n  {C}{len(proxies)}{RS} proxies found ({fetch_time:.1f}s) → {BR}checking...{RS}\n")

    stats: AdvancedStats = AdvancedStats(); results: list[CheckResult] = []

    for result in check_all(proxies, max_workers=cfg.workers, timeout=cfg.timeout, verify_twice=cfg.verify_twice):
        stats.record(result); results.append(result)
        print_result_line(result, stats, show_score=show_score, show_dead=show_dead)

    elapsed = time.perf_counter() - t0

    filtered = [r for r in results if flt.matches(r)]
    dead     = [r for r in results if not r.alive]

    if len(filtered) != stats.alive:
        print(f"\n  {Y}Filter applied: {stats.alive} → {len(filtered)} proxies{RS}")

    print_full_report(stats, proxy_type, elapsed)

    if top_n > 0 and filtered:
        print_top_proxies(filtered, proxy_type, top_n)

    if rotation and filtered:
        rotation_demo(filtered)

    if debug and results:
        dbg_path = write_debug_report(results, proxy_type, elapsed, output_dir)
        print(f"  {DM}↳ debug: {dbg_path}{RS}")

    if filtered:
        simple, detailed = save_results(filtered + dead, proxy_type, output_dir=output_dir, fmt=fmt)
        print(f"  {DM}↳ simple : {simple.resolve()}{RS}")
        if simple != detailed:
            print(f"  {DM}↳ detailed: {detailed.resolve()}{RS}")

    return stats, results


# ══════════════════════════════════════════════════════════════════════════════
# GRAND SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

def print_grand_summary(all_stats: dict[str, AdvancedStats], all_results: dict[str, list[CheckResult]],
                        wall_elapsed: float, archive_path: Path | None, session_id: str) -> None:
    SEP2()
    print(f"  {BR}GRAND SUMMARY  —  session: {DM}{session_id}{RS}")
    SEP2()
    grand_total = grand_alive = grand_elite = 0
    for ptype, st in all_stats.items():
        grand_total += st.total; grand_alive += st.alive; grand_elite += st.elite
        sr_c = G if st.success_rate >= 15 else (Y if st.success_rate >= 5 else R)
        print(f"  {TYPE_ART[ProxyType(ptype)]:<20}  {G}{st.alive:<5}{RS} / {st.total:<5}"
              f"  {sr_c}{st.success_rate:.1f}%{RS}  ort:{st.avg_latency:.0f}ms"
              f"  skor:{st.avg_score:.0f}  elite:{G}{st.elite}{RS}")
    SEP()
    grand_rate = (grand_alive / grand_total * 100) if grand_total else 0
    print(f"  {'TOTAL':<22} {grand_total} checked  |  {G}{grand_alive} alive{RS}  |  {Y}{grand_rate:.1f}%{RS}")
    print(f"  {'Elite proxies':<22} {G}{grand_elite}{RS}")
    print(f"  {'Total time':<22} {wall_elapsed:.1f}s")
    if archive_path:
        print(f"  {'Archive':<22} {DM}{archive_path}{RS}")
    SEP2()
    if len(all_results) > 1:
        analyze_duplicates(all_results)


# ══════════════════════════════════════════════════════════════════════════════
# INTERACTIVE MENU
# ══════════════════════════════════════════════════════════════════════════════

def interactive_menu() -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    print(f"\n  {BR}[ 1 ] Proxy Type{RS}")
    print(f"    {C}1{RS} HTTP  {C}2{RS} HTTPS  {C}3{RS} SOCKS4  {C}4{RS} SOCKS5  {C}0{RS} All")
    raw = input("  Selection: ").strip()
    type_map = {"1":"http","2":"https","3":"socks4","4":"socks5"}
    cfg["types"] = [type_map[t] for t in raw.split() if t in type_map] if raw and raw != "0" else ["http","https","socks4","socks5"]

    print(f"\n  {BR}[ 2 ] Source Count{RS}")
    total_src = {k: len(v) for k, v in PROXY_SOURCES.items()}
    print(f"    {DM}Available sources: " + "  ".join(f"{k}={v}" for k,v in total_src.items()) + f"{RS}")
    raw = input("  Max sources/type [Enter=all]: ").strip()
    cfg["max_sources"] = int(raw) if raw.isdigit() else 999
    raw = input("  Source timeout seconds [20]: ").strip()
    cfg["src_timeout"] = int(raw) if raw.isdigit() else 20

    print(f"\n  {BR}[ 3 ] Network Settings{RS}")
    raw = input("  Workers [200]: ").strip()
    cfg["workers"] = int(raw) if raw.isdigit() else 200
    raw = input("  Timeout seconds [8]: ").strip()
    cfg["timeout"] = int(raw) if raw.isdigit() else 8
    raw = input("  Double verify? (y/n) [n]: ").strip().lower()
    cfg["verify_twice"] = raw in ("y", "yes")

    print(f"\n  {BR}[ 4 ] Filters{RS}")
    raw = input("  Max latency ms [unlimited]: ").strip()
    cfg["max_latency"] = float(raw) if raw.replace(".","").isdigit() else None
    raw = input("  Elite only? (y/n) [n]: ").strip().lower()
    cfg["elite_only"] = raw in ("y", "yes")
    raw = input("  Min score 0-100 [none]: ").strip()
    cfg["min_score"] = float(raw) if raw.replace(".","").isdigit() else None
    raw = input("  Allowed countries (TR DE US ...) [all]: ").strip()
    cfg["countries"] = raw.upper().split() if raw else None
    raw = input("  Excluded countries [none]: ").strip()
    cfg["exclude_countries"] = raw.upper().split() if raw else None

    print(f"\n  {BR}[ 5 ] Output{RS}")
    raw = input("  Format (txt/json/csv) [txt]: ").strip().lower()
    cfg["format"] = raw if raw in ("txt","json","csv") else "txt"
    raw = input("  Output directory [./proxies]: ").strip()
    cfg["output_dir"] = raw if raw else "./proxies"
    raw = input("  How many top proxies to show? [10]: ").strip()
    cfg["top_n"] = int(raw) if raw.isdigit() else 10

    print(f"\n  {BR}[ 6 ] Extra{RS}")
    raw = input("  Show dead proxies? (y/n) [n]: ").strip().lower()
    cfg["show_dead"] = raw in ("y", "yes")
    raw = input("  Rotation simulator? (y/n) [n]: ").strip().lower()
    cfg["rotation"] = raw in ("y", "yes")
    raw = input("  Debug report? (y/n) [n]: ").strip().lower()
    cfg["debug"] = raw in ("y", "yes")
    raw = input("  Create archive? (y/n) [y]: ").strip().lower()
    cfg["archive"] = raw not in ("n", "no")

    return cfg


# ══════════════════════════════════════════════════════════════════════════════
# CLI PARSER
# ══════════════════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="proxy_suite", description="Crucible Proxy Suite — Ultimate Edition",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python proxy_suite.py                             # interactive\n"
            "  python proxy_suite.py --all                       # all types\n"
            "  python proxy_suite.py --types http socks5\n"
            "  python proxy_suite.py --all --elite-only --max-lat 1000\n"
            "  python proxy_suite.py --all --min-score 70 --format json\n"
            "  python proxy_suite.py --all --max-sources 3       # 3 sources/type\n"
            "  python proxy_suite.py --all --countries TR DE US\n"
            "  python proxy_suite.py --all --exclude CN RU\n"
            "  python proxy_suite.py --all --ports 80 8080 3128\n"
            "  python proxy_suite.py --all --rotation --top-n 20\n"
            "  python proxy_suite.py --verify 1.2.3.4:8080 --type http\n"
            "  python proxy_suite.py --recheck saved.txt --type socks5\n"
            "  python proxy_suite.py --bulk verify.txt --type http\n"
            "  python proxy_suite.py --file mylist.txt --type socks4\n"
            "  python proxy_suite.py --list-sources\n"
        ),
    )
    tg = p.add_mutually_exclusive_group()
    tg.add_argument("--types", nargs="+", choices=["http","https","socks4","socks5"], metavar="T")
    tg.add_argument("--all",   action="store_true")

    mg = p.add_mutually_exclusive_group()
    mg.add_argument("--verify",       metavar="HOST:PORT")
    mg.add_argument("--recheck",      metavar="PATH")
    mg.add_argument("--bulk",         metavar="PATH")
    mg.add_argument("--file",         metavar="PATH")
    mg.add_argument("--list-sources", action="store_true")

    src = p.add_argument_group("source")
    src.add_argument("--max-sources",  type=int,   default=999,   metavar="N",   help="Max sources/type (default: all)")
    src.add_argument("--src-timeout",  type=int,   default=20,    metavar="SEC", help="Timeout per source in seconds (default: 20)")
    src.add_argument("--exclude-src",  nargs="+",  default=None,  metavar="HOST")
    src.add_argument("--add-url",      nargs="+",  default=None,  metavar="URL")

    net = p.add_argument_group("network")
    net.add_argument("--workers",      type=int,   default=200)
    net.add_argument("--timeout",      type=int,   default=8)
    net.add_argument("--verify-twice", action="store_true")
    net.add_argument("--type",         choices=["http","https","socks4","socks5"], default="http", metavar="T")

    fil = p.add_argument_group("filtreler")
    fil.add_argument("--max-lat",       type=float, default=None,  metavar="MS")
    fil.add_argument("--min-lat",       type=float, default=None,  metavar="MS")
    fil.add_argument("--min-score",     type=float, default=None,  metavar="N",  help="0-100")
    fil.add_argument("--max-score",     type=float, default=None,  metavar="N")
    fil.add_argument("--elite-only",    action="store_true")
    fil.add_argument("--anon-only",     action="store_true")
    fil.add_argument("--countries",     nargs="+",  default=None,  metavar="CC")
    fil.add_argument("--exclude",       nargs="+",  default=None,  metavar="CC")
    fil.add_argument("--ports",         nargs="+",  type=int,      default=None, metavar="P")
    fil.add_argument("--exclude-ports", nargs="+",  type=int,      default=None, metavar="P")
    fil.add_argument("--pattern",       default=None, metavar="REGEX",           help="IP regex filtresi")

    out = p.add_argument_group("output")
    out.add_argument("--format",       choices=["txt","json","csv"], default="txt")
    out.add_argument("--output-dir",   default="./proxies",  metavar="DIR")
    out.add_argument("--top-n",        type=int, default=10, metavar="N")
    out.add_argument("--show-dead",    action="store_true")
    out.add_argument("--no-score",     action="store_true")
    out.add_argument("--no-archive",   action="store_true")
    out.add_argument("--no-clear",     action="store_true")
    out.add_argument("--rotation",     action="store_true",                       help="Rotation simulator")
    out.add_argument("--debug",        action="store_true",                       help="Debug raporu")
    out.add_argument("--verbose-src",  action="store_true",                       help="Verbose source output")
    out.add_argument("--quiet",        action="store_true",                       help="Minimal output")
    return p


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args   = parser.parse_args(argv)

    if not args.no_clear:
        os.system("cls" if os.name == "nt" else "clear")

    print(BANNER)

    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sm = SourceManager(max_sources_per_type=args.max_sources)
    if args.exclude_src: sm.exclude_hosts = set(args.exclude_src)
    if args.add_url:
        for t in ["http","https","socks4","socks5"]:
            sm.extra_urls[t] = list(args.add_url)

    if args.list_sources:
        for pt in ProxyType: sm.list_sources(pt)
        return

    cfg = Config(workers=args.workers, timeout=args.timeout, verify_twice=args.verify_twice,
                 output_dir=output_dir, output_format=args.format)

    flt = AdvancedFilter(
        max_latency=args.max_lat, min_latency=args.min_lat,
        min_score=args.min_score, max_score=args.max_score,
        countries=args.countries, exclude_countries=args.exclude,
        only_elite=args.elite_only, only_anonymous=args.anon_only,
        ports=args.ports, exclude_ports=args.exclude_ports, pattern=args.pattern,
    )

    pt = ProxyType(args.type)

    if args.verify:
        verify_single(args.verify, pt, cfg); return
    if args.recheck:
        recheck_mode(Path(args.recheck), pt, cfg, output_dir, args.format); return
    if args.bulk:
        verify_bulk(Path(args.bulk), pt, cfg, output_dir); return

    # Type selection
    if args.all:
        selected = list(ProxyType)
    elif args.types:
        selected = [ProxyType(t) for t in args.types]
    else:
        icfg = interactive_menu()
        selected = [ProxyType(t) for t in icfg["types"]]
        sm.max_sources_per_type = icfg["max_sources"]
        args.src_timeout = icfg.get("src_timeout", 20)
        output_dir = Path(icfg["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        cfg = Config(workers=icfg["workers"], timeout=icfg["timeout"],
                     verify_twice=icfg["verify_twice"], output_dir=output_dir,
                     output_format=icfg["format"])
        flt = AdvancedFilter(max_latency=icfg["max_latency"], min_score=icfg["min_score"],
                              countries=icfg["countries"], exclude_countries=icfg["exclude_countries"],
                              only_elite=icfg["elite_only"])
        args.show_dead  = icfg["show_dead"]
        args.rotation   = icfg["rotation"]
        args.debug      = icfg["debug"]
        args.no_archive = not icfg["archive"]
        args.top_n      = icfg["top_n"]
        args.no_score   = False
        args.format     = icfg["format"]

    # Info line
    src_info = f"{'∞' if sm.max_sources_per_type >= 999 else sm.max_sources_per_type} sources/type"
    print(f"  {DM}Workers:{cfg.workers}  Timeout:{cfg.timeout}s  Format:{args.format}  "
          f"Typeler:{','.join(t.value for t in selected)}  {src_info}  Filter:{flt.describe()}{RS}\n")

    # Pipeline
    all_results: dict[str, list[CheckResult]] = {}
    all_stats:   dict[str, AdvancedStats]     = {}
    wall_start   = time.perf_counter()

    for proxy_type in selected:
        custom_file = Path(args.file) if args.file else None
        st, res = run_pipeline(
            proxy_type=proxy_type, cfg=cfg, sm=sm, flt=flt,
            output_dir=output_dir, fmt=args.format,
            custom_file=custom_file, show_dead=args.show_dead,
            show_score=not args.no_score, top_n=args.top_n,
            rotation=args.rotation, debug=args.debug,
            verbose_src=args.verbose_src or not args.quiet,
            source_timeout=args.src_timeout,
        )
        all_stats[proxy_type.value]   = st
        all_results[proxy_type.value] = res

    wall_elapsed = time.perf_counter() - wall_start

    archive_path = None
    if not args.no_archive and any(r.alive for rs in all_results.values() for r in rs):
        archive_path = archive_session(all_results, all_stats, output_dir, session_id, flt)

    print_grand_summary(all_stats, all_results, wall_elapsed, archive_path, session_id)

    if not args.all and not args.types:
        input(f"\n  {DM}Press Enter to exit...{RS}")


if __name__ == "__main__":
    main()
