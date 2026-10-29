# Contributing

Thank you for your help. Small, focused pull requests are easiest to review.

## Good first contributions

- **Camera reports**: open a [Camera works](../../issues/new?template=camera_works.md) issue, or add a row to the table in the README.
- Bug fixes with a clear way to reproduce them.
- Documentation fixes.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt ruff pytest
.venv/bin/ruff check .
.venv/bin/pytest -q
.venv/bin/python cam.py --once   # with a real camera
```

## Rules

- Keep it small. Use the standard library or an installed package before you add a dependency.
- `common.py` and `timelapse.py` use only the standard library. Keep it that way: `timelapse.py snap` runs every minute.
- Errors in optional features (Telegram, faces, TV) must never stop the recording.
- Never commit config files, clips, face photos, logs, tokens or camera passwords.
- By contributing, you agree that your work is licensed under the [AGPL-3.0](LICENSE).

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md).
