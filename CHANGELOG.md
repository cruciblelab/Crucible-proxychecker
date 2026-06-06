# Changelog

All notable changes are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [7.0.0] — 2025-06-06

### Added
- **Unified config system** (`crucible_proxy.config`): three-tier priority (CLI → env vars → TOML file → defaults)
- **`--generate-config`** flag — prints a fully-commented TOML template to stdout
- **JSON and CSV output formats** (`--output-format json|csv`)
- **Debug report** (`--debug-report`) — machine-readable JSON with dead proxies + error messages
- **`--log-file PATH`** — write logs to file in addition to stderr
- **`--no-color`** flag + `CRUCIBLE_NO_COLOR` env var
- **`--retries`** flag exposed in CLI (was only an internal constant)
- `CRUCIBLE_*` environment variables for all settings
- `write_debug_report()` public API function
- 46 additional proxy sources (67 total across all protocols)
- `[project.optional-dependencies]` in `pyproject.toml`: `toml`, `dev`
- OIDC trusted-publisher PyPI publish job in CI

### Changed
- Version bumped to `7.0.0` (breaking: `save_results` signature now accepts `fmt` and `output_dir` kwargs)
- `cli.py` fully rewritten to consume `Config` object
- `output.py` rewritten with format dispatch and debug report support
- `requirements.txt` now generated from `pyproject.toml`

### Fixed
- Global `_SESSION` removed from `fetcher.py` → test isolation + concurrent safety
- `_detect_anonymity` removed from `__all__` and public imports
- IP detection uses `ipaddress` module (handles IPv6 + edge cases)
- `httpbin.org` URL now overridable via `CRUCIBLE_ANONYMITY_CHECK_URL`
- `proxy_checker.py` docstring artefact `(v6)` removed

---

## [6.0.0] — 2025-06-05

### Added
- Multi-source fetching with deduplication
- Concurrent validation with `ThreadPoolExecutor`
- Anonymity detection (Elite / Anonymous / Transparent)
- Country detection via ip-api
- Colorized CLI output with progress bar
- TXT output (simple + detailed)
