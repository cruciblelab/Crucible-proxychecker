# Session API

The `Session` class wraps fetching, validation, filtering, and saving into one
configurable object.

## Construction

```python
from crucible_proxy import Session

# Direct
s = Session(types=["http"], elite=True)

# From dict
s = Session.from_dict({"types": ["socks5"], "workers": 300})

# From JSON file
s = Session.from_json("config.json")
```

## Callbacks

Bring your own functions for full control:

```python
def on_alive(result):
    print(f"Found: {result.proxy} ({result.country})")

def on_progress(checked, total):
    print(f"{checked}/{total}")

s = Session(types=["http"], on_alive=on_alive, on_progress=on_progress)
s.run()
```

## Async

```python
results = await Session(types=["http"]).run_async()
```

## Filters

| Filter | Type | Description |
|--------|------|-------------|
| `elite` | bool | ELITE only |
| `anonymous` | bool | ELITE + ANONYMOUS |
| `max_latency` / `min_latency` | float | Latency bounds (ms) |
| `min_score` / `max_score` | float | Quality score 0–100 |
| `countries` / `exclude_countries` | list[str] | Country codes |
| `cities` | list[str] | City name substrings |
| `exclude_asn` | list[str] | ASN substrings to drop |
| `ports` / `exclude_ports` | list[int] | Port allow / deny |
