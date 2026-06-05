# Contributing

## Setup

```bash
git clone https://github.com/cruciblelab/Crucible-proxychecker
cd crucible-proxychecker
pip install -e ".[dev,toml]"
```

## Running tests

```bash
pytest tests/ -v
pytest tests/ -v --cov=crucible_proxy --cov-report=term-missing
```

## Linting & type checking

```bash
ruff check crucible_proxy/ tests/
mypy crucible_proxy/ --ignore-missing-imports
```

## Adding proxy sources

Edit `crucible_proxy/constants.py` → `PROXY_SOURCES`.
Sources must return a plain-text list of `host:port` lines (one per line).
The fetcher handles `scheme://`, `user@host:port`, and `#` comments automatically.

## Releasing (maintainers)

1. Update `version` in `pyproject.toml` and `crucible_proxy/__init__.py`
2. Add an entry in `CHANGELOG.md`
3. `git tag v7.0.0 && git push origin v7.1.0`

CI will build and publish to PyPI automatically via the OIDC trusted publisher.
