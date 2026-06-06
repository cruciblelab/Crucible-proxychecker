# API Reference

## Core functions

- `fetch_proxies(proxy_type)` → `list[Proxy]`
- `fetch_proxies_with_stats(proxy_type)` → `(list[Proxy], list[SourceStats])`
- `check_proxy(proxy, ...)` → `CheckResult`
- `check_all(proxies, ..., cache=None)` → `Iterator[CheckResult]`
- `save_results(results, proxy_type, ...)` → `(Path, Path)`

## Classes

- `Session` — high-level declarative API
- `Proxy` — a single proxy (host, port, type)
- `CheckResult` — validation result (alive, latency, country, city, asn, isp, anonymity)
- `ProxyCache` — thread-safe result cache
- `SourceStats` — per-source health stats
- `Config` — CLI/library configuration

## Enums

- `ProxyType` — HTTP, HTTPS, SOCKS4, SOCKS5
- `Anonymity` — ELITE, ANONYMOUS, TRANSPARENT, UNKNOWN
