<div align="center">

# 🔥 crucible-proxy

**Fast, multi-source proxy scraper and validator — CLI tool and Python library.**

[![PyPI version](https://img.shields.io/pypi/v/crucible-proxychecker.svg)](https://pypi.org/project/crucible-proxychecker/)
[![Python](https://img.shields.io/pypi/pyversions/crucible-proxychecker.svg)](https://pypi.org/project/crucible-proxychecker/)
[![CI](https://github.com/cruciblelab/Crucible-proxychecker/actions/workflows/ci.yml/badge.svg)](https://github.com/cruciblelab/Crucible-proxychecker/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Coverage](https://codecov.io/gh/cruciblelab/Crucible-proxychecker/branch/main/graph/badge.svg)](https://codecov.io/gh/cruciblelab/Crucible-proxychecker)

Scrapes proxies from **67 free sources**, validates them concurrently, and reports anonymity level (Elite / Anonymous / Transparent) — all in one command or one import.

**v7.1.0 new:** source health statistics + multi-endpoint anonymity detection (no more httpbin.org single point of failure).

**v7.2.0 new:** proxy cache (skip re-checking already-validated proxies) + coverage reporting.

</div>

---

## Contents

- [Install](#install)
- [CLI Usage](#cli-usage)
  - [Basic examples](#basic-examples)
  - [All flags](#all-flags)
  - [Environment variables](#environment-variables)
  - [Config file](#config-file)
- [Library Usage](#library-usage)
  - [Quick start](#quick-start)
  - [Custom config](#custom-config-programmatic)
  - [Async-friendly pattern](#async-friendly-pattern)
  - [Rotating proxy pool](#rotating-proxy-pool)
  - [Requests integration](#requests-integration)
  - [Playwright integration](#playwright-integration)
  - [Filter by country / anonymity](#filter-by-country--anonymity)
  - [Save results manually](#save-results-manually)
  - [Debug report](#debug-report)
  - [Proxy cache](#proxy-cache)
  - [Source health statistics](#source-health-statistics)
  - [Multiple anonymity check endpoints](#multiple-anonymity-check-endpoints)
- [Output formats](#output-formats)
- [Anonymity levels](#anonymity-levels)
- [Config reference](#config-reference)
- [Examples](#examples)
- [Contributing](#contributing)

---

## Install

```bash
pip install crucible-proxychecker
```

For TOML config file support on Python 3.10:

```bash
pip install "crucible-proxychecker[toml]"
```

> Requires Python ≥ 3.10.  `requests[socks]` and `colorama` are installed automatically.

---

## CLI Usage

### Basic examples

```bash
# Interactive menu — pick proxy types interactively
crucible-proxy

# Check one type
crucible-proxy --type socks5
crucible-proxy --type http

# Check all four types at once
crucible-proxy --all

# Save results as JSON instead of TXT
crucible-proxy --type socks5 --output-format json

# Save results as CSV
crucible-proxy --all --output-format csv --output-dir ./proxies

# Faster: more workers, shorter timeout
crucible-proxy --type http --workers 400 --timeout 5

# Slower but more accurate: verify each proxy twice
crucible-proxy --type socks4 --verify-twice true

# Verbose logging to see what's happening under the hood
crucible-proxy --type https --log-level DEBUG

# Write logs to a file
crucible-proxy --all --log-level INFO --log-file crucible.log

# Write a full debug JSON report (includes dead proxies + error messages)
crucible-proxy --type socks5 --debug-report

# No colours (e.g. for piping / CI)
crucible-proxy --type http --no-color

# Dump a config template you can edit
crucible-proxy --generate-config > crucible_proxy.toml
```

### All flags

| Flag | Default | Description |
|------|---------|-------------|
| `--type TYPE` | — | One of `http`, `https`, `socks4`, `socks5` |
| `--all` | — | Check all four types |
| `--workers N` | 200 | Concurrent validation threads |
| `--timeout SEC` | 8 | Per-request timeout in seconds |
| `--retries N` | 2 | Retries before marking a proxy dead |
| `--verify-twice BOOL` | true | Confirm live proxies with a second request |
| `--output-format FMT` | txt | `txt` \| `json` \| `csv` |
| `--output-dir DIR` | `./output` | Where to write result files |
| `--no-color` | false | Disable ANSI colours |
| `--log-level LEVEL` | WARNING | `DEBUG` `INFO` `WARNING` `ERROR` `CRITICAL` |
| `--log-file PATH` | — | Also write logs to this file |
| `--debug-report` | false | Write a full JSON debug report per run |
| `--generate-config` | — | Print TOML config template and exit |

### Environment variables

All settings can be set via `CRUCIBLE_*` environment variables.  Useful for Docker / CI:

```bash
export CRUCIBLE_WORKERS=400
export CRUCIBLE_TIMEOUT=5
export CRUCIBLE_OUTPUT_FORMAT=json
export CRUCIBLE_OUTPUT_DIR=/data/proxies
export CRUCIBLE_LOG_LEVEL=INFO
export CRUCIBLE_VERIFY_TWICE=false
export CRUCIBLE_DEBUG_REPORT=true
export CRUCIBLE_NO_COLOR=true

# Use your own httpbin-compatible anonymity-check server
export CRUCIBLE_ANONYMITY_CHECK_URL=http://my-server.local/headers

crucible-proxy --all
```

### Config file

Run `crucible-proxy --generate-config > crucible_proxy.toml` to create a template.  
The tool looks for a config file in these locations (first found wins):

1. `./crucible_proxy.toml` (project root)
2. `~/.config/crucible_proxy/config.toml`
3. `~/.crucible_proxy.toml`

**Priority order:** CLI flags → env vars → config file → built-in defaults.

```toml
# crucible_proxy.toml

timeout      = 10
workers      = 300
verify_twice = false

output_dir    = "./results"
output_format = "json"

log_level    = "INFO"
log_file     = "crucible.log"
debug_report = true

anonymity_check_url = "http://my-httpbin.internal/headers"
```

---

## Library Usage

### Quick start

```python
from crucible_proxy import fetch_proxies, check_all, ProxyType

# Fetch from all sources for one protocol
proxies = fetch_proxies(ProxyType.SOCKS5)
print(f"Found {len(proxies)} proxies")

# Validate concurrently; results stream as they complete
for result in check_all(proxies, max_workers=200, timeout=8):
    if result.alive:
        print(
            f"{result.proxy}  "
            f"{result.latency_ms}ms  "
            f"{result.country}  "
            f"{result.anonymity.value}"
        )
```

### Custom config (programmatic)

```python
from crucible_proxy import load_config, fetch_proxies, check_all, ProxyType

cfg = load_config({
    "workers":       300,
    "timeout":       6,
    "verify_twice":  False,
    "output_format": "json",
    "output_dir":    "./results",
    "log_level":     "INFO",
    "debug_report":  True,
})

proxies = fetch_proxies(ProxyType.HTTP)
results = list(check_all(proxies, max_workers=cfg.workers, timeout=cfg.timeout))
```

### Async-friendly pattern

`check_all` is synchronous (uses `ThreadPoolExecutor` internally), but you can
run it in an executor to keep an async event loop unblocked:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from crucible_proxy import fetch_proxies, check_all, ProxyType

async def get_alive_proxies(proto: ProxyType, workers: int = 200):
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=4) as pool:
        proxies = await loop.run_in_executor(pool, fetch_proxies, proto)
        results = await loop.run_in_executor(
            pool,
            lambda: list(check_all(proxies, max_workers=workers))
        )
    return [r for r in results if r.alive]

alive = asyncio.run(get_alive_proxies(ProxyType.SOCKS5))
```

### Rotating proxy pool

```python
import itertools
from crucible_proxy import fetch_proxies, check_all, ProxyType

proxies  = fetch_proxies(ProxyType.HTTP)
alive    = [r.proxy for r in check_all(proxies) if r.alive]
pool     = itertools.cycle(alive)

def next_proxy() -> dict:
    """Returns a requests-compatible proxy dict."""
    return next(pool).as_requests_dict()

# Use it:
import requests
for url in my_urls:
    resp = requests.get(url, proxies=next_proxy(), timeout=10)
```

### Requests integration

```python
import requests
from crucible_proxy import fetch_proxies, check_all, ProxyType, Anonymity

# Get elite-only proxies
proxies = fetch_proxies(ProxyType.HTTPS)
elite = [
    r.proxy for r in check_all(proxies)
    if r.alive and r.anonymity == Anonymity.ELITE
]

proxy = elite[0]
resp  = requests.get("https://httpbin.org/ip", proxies=proxy.as_requests_dict(), timeout=10)
print(resp.json())
```

### Playwright integration

```python
import asyncio
from playwright.async_api import async_playwright
from crucible_proxy import fetch_proxies, check_all, ProxyType

async def scrape(url: str):
    proxies = fetch_proxies(ProxyType.SOCKS5)
    alive   = [r.proxy for r in check_all(proxies, max_workers=100) if r.alive]
    proxy   = alive[0]

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            proxy={
                "server":   f"socks5://{proxy.host}:{proxy.port}",
            }
        )
        page = await browser.new_page()
        await page.goto(url)
        content = await page.content()
        await browser.close()
    return content

asyncio.run(scrape("https://example.com"))
```

### Filter by country / anonymity

```python
from crucible_proxy import fetch_proxies, check_all, ProxyType, Anonymity

results = list(check_all(fetch_proxies(ProxyType.SOCKS5)))

# Fast proxies only (< 1 second latency)
fast = [r for r in results if r.alive and r.latency_ms and r.latency_ms < 1000]

# Only US proxies
us = [r for r in results if r.alive and r.country == "US"]

# Elite only (no headers leaked)
elite = [r for r in results if r.alive and r.anonymity == Anonymity.ELITE]

# Elite US proxies sorted by speed
best = sorted(
    [r for r in results if r.alive and r.country == "US" and r.anonymity == Anonymity.ELITE],
    key=lambda r: r.latency_ms or float("inf"),
)
print(f"Best US elite proxy: {best[0].proxy} @ {best[0].latency_ms}ms")
```

### Save results manually

```python
from pathlib import Path
from crucible_proxy import fetch_proxies, check_all, save_results, ProxyType

results = list(check_all(fetch_proxies(ProxyType.SOCKS5)))

# TXT (default)
simple, detailed = save_results(results, ProxyType.SOCKS5)

# JSON
json_path, _ = save_results(results, ProxyType.SOCKS5, fmt="json", output_dir=Path("./out"))

# CSV
csv_path, _  = save_results(results, ProxyType.SOCKS5, fmt="csv",  output_dir=Path("./out"))
```

### Debug report

```python
import time
from crucible_proxy import fetch_proxies, check_all, write_debug_report, ProxyType
from pathlib import Path

proxies = fetch_proxies(ProxyType.HTTP)
t0      = time.perf_counter()
results = list(check_all(proxies))
elapsed = time.perf_counter() - t0

report_path = write_debug_report(results, ProxyType.HTTP, elapsed, Path("./debug"))
print(f"Debug report: {report_path}")
# JSON contains: meta stats, all alive proxies, all dead proxies + error messages
```


### Proxy cache

Avoid re-checking the same proxy twice within a session using `ProxyCache`:

```python
from crucible_proxy import ProxyCache, fetch_proxies, check_all, ProxyType

cache = ProxyCache()

# First run — checks all proxies over the network
proxies = fetch_proxies(ProxyType.HTTP)
results = list(check_all(proxies, cache=cache))
print(f"Checked {len(proxies)} proxies, cache now has {len(cache)} entries")

# Second run with the same list — cached proxies returned instantly
results2 = list(check_all(proxies, cache=cache))
# No network calls made for already-checked proxies

# Clear the cache when you want fresh results
cache.clear()
```

The cache is type-aware: the same IP address cached as `HTTP` will still be
checked fresh as `SOCKS5`.

---

### Source health statistics

```python
from crucible_proxy import fetch_proxies_with_stats, ProxyType

proxies, stats = fetch_proxies_with_stats(ProxyType.HTTP)

for s in stats:
    status = f"+{s.proxies_found}" if s.success else f"FAIL: {s.error[:40]}"
    print(f"{s.domain:<45} {status}  ({s.elapsed_s}s)")

# Filter out dead sources for next run
good_sources = [s.url for s in stats if s.success and s.proxies_found > 0]
```

### Multiple anonymity check endpoints

By default the library tries 5 httpbin-compatible endpoints in order and uses
the first one that responds. This means `httpbin.org` downtime no longer causes
all proxies to be classified as `UNKNOWN`.

You can override the primary endpoint via env var:

```bash
export CRUCIBLE_ANONYMITY_CHECK_URL=http://my-httpbin.internal/headers
```

Or inspect the full list:

```python
from crucible_proxy.constants import ANONYMITY_CHECK_URLS
print(ANONYMITY_CHECK_URLS)
# ['http://httpbin.org/headers', 'https://httpbin.org/headers',
#  'http://httpbingo.org/headers', 'https://httpbingo.org/headers',
#  'http://eu.httpbin.org/headers']
```

---

## Output formats

### TXT (default)

Two files per run:

```
# simple — host:port only, sorted by latency
103.149.130.38:80
45.77.56.114:30000

# detailed — full info
103.149.130.38:80   |  212ms      |  SG    |  elite
45.77.56.114:30000  |  334ms      |  US    |  anonymous
```

### JSON

```json
{
  "generated": "2025-06-06T10:23:41+00:00",
  "count": 42,
  "proxies": [
    {
      "proxy": "103.149.130.38:80",
      "host": "103.149.130.38",
      "port": 80,
      "type": "http",
      "latency_ms": 212.4,
      "country": "SG",
      "anonymity": "elite",
      "check_url": "http://httpbin.org/ip"
    }
  ]
}
```

### CSV

```csv
proxy,host,port,type,latency_ms,country,anonymity,check_url
103.149.130.38:80,103.149.130.38,80,http,212.4,SG,elite,http://httpbin.org/ip
```

### Debug report (`--debug-report`)

Written in addition to normal output, includes **dead proxies and error messages**:

```json
{
  "meta": {
    "generated": "2025-06-06T10:23:41+00:00",
    "proxy_type": "socks5",
    "elapsed_s": 47.2,
    "total": 1842,
    "alive": 134,
    "dead": 1708,
    "success_pct": 7.3
  },
  "alive": [ ... ],
  "dead": [
    { "proxy": "1.2.3.4:1080", "error": "ConnectTimeout" },
    ...
  ]
}
```

---

## Anonymity levels

| Level | Meaning |
|-------|---------|
| **ELITE** | No forwarding headers sent — destination cannot detect a proxy |
| **ANONYMOUS** | Proxy headers present but your real IP is hidden |
| **TRANSPARENT** | Your real IP is visible in `X-Forwarded-For` or similar headers |
| **UNKNOWN** | Anonymity check endpoint was unreachable |

---

## Config reference

| Key | Env var | CLI flag | Default | Description |
|-----|---------|----------|---------|-------------|
| `timeout` | `CRUCIBLE_TIMEOUT` | `--timeout` | `8` | Per-request timeout (seconds) |
| `workers` | `CRUCIBLE_WORKERS` | `--workers` | `200` | Concurrent threads |
| `retries` | `CRUCIBLE_RETRIES` | `--retries` | `2` | Check retries before marking dead |
| `retry_delay` | `CRUCIBLE_RETRY_DELAY` | — | `0.6` | Seconds between retries |
| `verify_twice` | `CRUCIBLE_VERIFY_TWICE` | `--verify-twice` | `true` | Second-pass confirmation |
| `anonymity_check_url` | `CRUCIBLE_ANONYMITY_CHECK_URL` | — | httpbin | Headers-echo endpoint |
| `output_dir` | `CRUCIBLE_OUTPUT_DIR` | `--output-dir` | `./output` | Result file directory |
| `output_format` | `CRUCIBLE_OUTPUT_FORMAT` | `--output-format` | `txt` | `txt` / `json` / `csv` |
| `no_color` | `CRUCIBLE_NO_COLOR` | `--no-color` | `false` | Disable ANSI colours |
| `log_level` | `CRUCIBLE_LOG_LEVEL` | `--log-level` | `WARNING` | Log verbosity |
| `log_file` | `CRUCIBLE_LOG_FILE` | `--log-file` | — | Log file path |
| `debug_report` | `CRUCIBLE_DEBUG_REPORT` | `--debug-report` | `false` | Write JSON debug report |

---

## Examples

The [`examples/`](examples/) directory contains ready-to-run scripts:

### `proxy_suite.py` — Ultimate Proxy Suite

A feature-rich CLI application built on top of this library:

```bash
pip install crucible-proxychecker
python examples/proxy_suite.py
```

**Features:**
- Interactive menu + full CLI mode (`--all`, `--types`, `--elite-only` …)
- Configurable source count per type (`--max-sources 3`)
- Per-source timeout (`--src-timeout 10`)
- Advanced filtering: country, latency, anonymity, score, port, regex
- Proxy quality scoring (0–100, S/A/B/C/D/F grades)
- Live progress bar + colored histograms
- Re-check mode (`--recheck saved.txt`)
- Single proxy verify (`--verify 1.2.3.4:8080`)
- Bulk verify from file (`--bulk list.txt`)
- Rotation simulator (`--rotation`)
- Session archive (JSON) + debug report
- Multi-type duplicate analysis

```bash
# Examples
python examples/proxy_suite.py --all --elite-only --max-lat 1000
python examples/proxy_suite.py --types http socks5 --format json
python examples/proxy_suite.py --all --max-sources 3 --src-timeout 10
python examples/proxy_suite.py --verify 1.2.3.4:8080 --type http
python examples/proxy_suite.py --list-sources
```

---

## Contributing

```bash
git clone https://github.com/cruciblelab/Crucible-proxychecker
cd crucible-proxy
pip install -e ".[dev,toml]"
pytest tests/ -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

[MIT](LICENSE)
