# Quick Start

## Library — Session API (easiest)

```python
from crucible_proxy import Session

session = Session(
    types       = ["http", "socks5"],
    workers     = 300,
    elite       = True,
    max_latency = 1000,
)

# Different return shapes:
results = session.run()          # {"http": [...], "socks5": [...]}
flat    = session.live_only()    # [CheckResult, ...]
strings = session.to_list()      # ["1.2.3.4:8080", ...]
top10   = session.best(10)       # top 10 by quality score
fast10  = session.fastest(10)    # 10 lowest-latency
```

## CLI

```bash
crucible-proxy --all
crucible-proxy --type socks5 --output-format json
```
