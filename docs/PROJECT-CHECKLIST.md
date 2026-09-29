# PROJECT-CHECKLIST — reuse for your other 6 projects (advanced level)

Copy this file to each repo and tick. TurboQuant already passes all.

## 1. License & legal
- [ ] `LICENSE` (MIT/Apache-2.0) with year + holder
- [ ] `pyproject.toml:license` + `classifiers` match `LICENSE`
- [ ] `THIRD-PARTY-NOTICES.md` for optional deps + binaries
- [ ] `CITATION.cff` (version = code version)
- [ ] No secrets in git (`.gitignore`: `.env`, `*.pem`, `*.key`)

## 2. Community
- [ ] `README.md`: install, quickstart, docs index, community, license
- [ ] `CONTRIBUTING.md`: setup, tests, code rules, PR, version triple
- [ ] `CODE_OF_CONDUCT.md` (Covenant)
- [ ] `SECURITY.md`: supported versions, report path, boundaries, hardening
- [ ] `SUPPORT.md`: where to ask, response expectations
- [ ] `.github/PULL_REQUEST_TEMPLATE.md`
- [ ] `.github/ISSUE_TEMPLATE/bug_report.yml` + `feature_request.yml`

## 3. Docs (every inquiry answered once)
- [ ] `docs/ARCHITECTURE.md` (diagram + layers + decisions)
- [ ] `docs/API.md` (endpoints + params + headers + errors)
- [ ] `docs/CONFIGURATION.md` (env vars table + precedence + prod recipe)
- [ ] `docs/FAQ.md` (concepts, limits, bindings, versions)
- [ ] `docs/TROUBLESHOOTING.md` (exception table + HTTP codes + debug recipe)
- [ ] `docs/FORMAT.md` or protocol spec if binary format exists
- [ ] `docs/PERFORMANCE.md` with measured numbers (device, date, command)
- [ ] `docs/ROADMAP.md` (next + non-goals)
- [ ] `docs/GLOSSARY.md`
- [ ] `docs/PUBLISHING.md` (tag → CI → registry)

## 4. Engineering
- [ ] `CHANGELOG.md` (Keep a Changelog, Unreleased section)
- [ ] Version triple enforced by test (`__init__` = `pyproject` = `package.json`)
- [ ] CI matrix covers min supported version (`3.9`) + runs full extras (`[max,secure]`) + `-rs` to surface skips
- [ ] `release.yml` (tag → build → publish, trusted publishing)
- [ ] `Dockerfile` non-root (`USER app`) + `HEALTHCHECK` + `.dockerignore`
- [ ] No `str(e)` to HTTP clients (generic + server log)
- [ ] Caps on all untrusted lengths (`header_len`, manifest, decompress output)
- [ ] `pytest -q` green before every merge

## 5. Advanced bar
- [ ] Threat model written (auth? CORS? caps? path oracle?)
- [ ] Measured `PERFORMANCE.md`, not estimates
- [ ] Native/spec docs for other languages (`FORMAT.md` + bindings matrix)
- [ ] `CITATION.cff` + badges (CI, license) in README
