# Contributing to PaddockPulse

Thanks for helping improve PaddockPulse. Keep changes small and focused.

## Development setup

```bash
git clone https://github.com/bluzername/paddock-pulse.git
cd paddock-pulse
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt ruff
cp .env.example .env   # add the API keys you need
```

## Checks

CI runs the same two commands on every push and pull request:

```bash
ruff check .               # syntax errors and undefined names
python -m compileall -q .  # every module byte-compiles
```

`make lint` runs both. There is no automated test suite yet; if you add one,
put it under `tests/` and wire it into `.github/workflows/ci.yml`.

## Guidelines

- Never commit API keys. Read them from the environment (see `.env.example`).
- Add new model ids to `paddock_pulse/config.py`, not inline in modules.
- Every new import needs a matching line in `requirements.txt`.
- Use conventional commit messages: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`, `ci:`.

## Reporting issues

Include the command you ran, the provider and model in use (`python run_all.py --key-debug`
prints masked key diagnostics), your Python version and the full error output.
