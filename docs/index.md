# Crucible Proxychecker

Fast, multi-source proxy scraper and validator — CLI tool and Python library.

Scrapes proxies from **67 free sources**, validates them concurrently, and reports
anonymity level (Elite / Anonymous / Transparent), country, city, ASN, and latency.

## Install

```bash
pip install crucible-proxychecker
```

## 30-second example

```python
from crucible_proxy import Session

session = Session(types=["http", "socks5"], elite=True, max_latency=1000)
proxies = session.to_list()   # ['1.2.3.4:8080', ...]
```

See [Quick Start](quickstart.md) for more.
