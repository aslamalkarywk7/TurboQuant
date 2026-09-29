# النشر الرسمي (PyPI + npm) — خطوات المالك

## Python (PyPI)
```bash
pip install build twine
python -m pytest tests/ -q          # يجب: كل ناجح
python -m build                     # dist/*.whl + *.tar.gz
twine check dist/*
git tag v2.4.0 && git push origin v2.4.0   # الـ CI ينشر تلقائياً (trusted publishing)
# يدوياً عند الحاجة: twine upload dist/*
```
المتطلبات لمرة واحدة: مشروع `turboquant` على PyPI + OIDC publisher مربوط بالمستودع
(موثق في `.github/workflows/release.yml`)، و`version` في `pyproject.toml` = الوسم.

## Node (npm)
```bash
node --check bindings/tqz-decode.mjs
npm version 2.4.0 --no-git-tag-version   # مزامنة مع package.json
git tag npm-2.4.0  # أو نفس وسم v2.4.0 — الـ CI ينشر بـ NPM_TOKEN
```
يتطلب `NPM_TOKEN` في أسرار المستودع.

## قبل كل إصدار (قائمة فحص)
1. `python -m pytest tests/ -q` أخضر على Windows + Linux (المصفوفة في CI).
2. `CHANGELOG.md` مؤرخ، و`__version__` و`pyproject` و`package.json` متطابقة.
3. `docs/FORMAT.md` يصف أي حقل جديد (transform/codec/method).
4. المفككات الأصلية تُختبر بحزم مولّدة من نفس الإصدار (مصفوفة §المفككات في bindings/README).
