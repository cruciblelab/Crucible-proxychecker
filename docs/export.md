# Export Formats

Export validated proxies into proxy-client config formats:

```python
from crucible_proxy import Session

s = Session(types=["socks5"], elite=True)
s.run()

# Clash YAML
s.export("clash", "proxies-clash.yaml")

# v2ray JSON
s.export("v2ray", "proxies-v2ray.json")

# Shadowsocks-style list
s.export("shadowsocks", "proxies-ss.txt")

# Plain host:port
s.export("txt", "proxies.txt")
```

Without a path, `export()` returns the string directly.
