# Contributing

Thanks for helping improve CondenseIt.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp config.example.yaml config.yaml
```

Run checks:

```bash
ruff check src tests
pytest tests/
```

## Pull requests

- Keep changes focused on one concern when possible.
- Add or update tests for behavior you change.
- Run `ruff` and `pytest` before opening a PR.

## Security

Please report sensitive issues privately (see `SECURITY.md`).
