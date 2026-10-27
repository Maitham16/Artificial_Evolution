# Artificial Evolution documentation website

**Production:** https://maitham16.github.io/Artificial_Evolution/

MkDocs Material publishes the original V1/V2 documentation without editing its source files. New landing pages and tutorials are under `pages/`; `hooks.py` imports existing guides as virtual pages and resolves links only in generated output. The applications and their Python dependencies are separate.

From the repository root:

```bash
python3.13 -m venv .cache/website/venv
.cache/website/venv/bin/python -m pip install -r v2/website/requirements.txt
.cache/website/venv/bin/mkdocs serve --config-file v2/website/mkdocs.yml
```

Preview: http://127.0.0.1:8000/Artificial_Evolution/

Production checks:

```bash
.cache/website/venv/bin/mkdocs build --strict --config-file v2/website/mkdocs.yml
.cache/website/venv/bin/python v2/website/check_site.py
python3 v2/tools/verify_original.py
```

Build output stays under ignored `.cache/website/site/`. Automatic build/check/deployment is defined in the new [Pages workflow](../../.github/workflows/pages.yml). The existing application CI workflow remains unchanged. See the [website development guide](pages/development/website.md) for content ownership, SEO, deployment permissions and troubleshooting.
