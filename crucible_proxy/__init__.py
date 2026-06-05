"""
crucible-proxy
~~~~~~~~~~~~~~
Fast, multi-source proxy scraper and validator.

Quick start (library)::

    from crucible_proxy import fetch_proxies, check_all, ProxyType

    proxies = fetch_proxies(ProxyType.SOCKS5)
    for result in check_all(proxies):
        if result.alive:
            print(result.proxy, result.latency_ms, result.country)

Quick start (CLI)::

    crucible-proxy --type socks5 --output-format json
"""
from .checker import check_all, check_proxy
from .config import Config, load_config
from .fetcher import fetch_proxies, parse_line
from .models import Anonymity, CheckResult, Proxy, ProxyType, Stats
from .output import save_results, write_debug_report

__version__ = "7.0.0"
__all__ = [
    # models
    "Proxy", "ProxyType", "CheckResult", "Stats", "Anonymity",
    # fetcher
    "fetch_proxies", "parse_line",
    # checker
    "check_proxy", "check_all",
    # output
    "save_results", "write_debug_report",
    # config
    "Config", "load_config",
]
