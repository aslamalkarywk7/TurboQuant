# Pull request

## What / why
-
-

## Evidence
- `pytest tests -q -rs` output:
- `bench` / `cert` output (if codec/transform change):
- `file:line` touched:

## Checklist
- [ ] Tests green, new round-trip + corrupt-input tests if codec/transform/API
- [ ] Docs updated (`README.md` + `docs/*` + `CHANGELOG.md` Unreleased)
- [ ] No new base dependency (optional extras only)
- [ ] Security considered (caps, filename sanitize, no `str(e)` to clients)
- [ ] Version triple still matches (`__init__` = `pyproject` = `package.json`)
