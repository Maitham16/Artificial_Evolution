---
title: Build and publish the documentation website
description: Develop the isolated MkDocs Material site, preview locally, validate source preservation, links, SEO and sitemap, and deploy through GitHub Pages Actions.
---

# Develop this website

The site lives in `v2/website/`. It reads the existing root and V1/V2 Markdown files without editing them. A MkDocs hook publishes virtual pages, resolves internal links, adds descriptive metadata and copies referenced media into the build. The published source manifest records each imported file's SHA-256.

## Install isolated documentation dependencies

From the repository root:

```bash
python3.13 -m venv .cache/website/venv
.cache/website/venv/bin/python -m pip install -r v2/website/requirements.txt
.cache/website/venv/bin/python -m pip check
```

This environment is separate from the applications' `.venv`; the root requirements remain unchanged. The requirements file pins the website build dependencies, including MkDocs Material. Godot and Blender are not required to build documentation.

## Preview locally

```bash
.cache/website/venv/bin/mkdocs serve --config-file v2/website/mkdocs.yml
```

Open **http://127.0.0.1:8000/Artificial_Evolution/**. The project prefix matches the production GitHub Pages path. Original documentation directories are watched for rebuilding alongside the website pages.

## Build and check

```bash
.cache/website/venv/bin/mkdocs build --strict --config-file v2/website/mkdocs.yml
.cache/website/venv/bin/python v2/website/check_site.py
python3 v2/tools/verify_original.py
```

Output goes to ignored `.cache/website/site/`. The checker verifies internal HTML/media links and anchors, descriptive metadata, canonical URLs, Open Graph data, XML sitemap coverage and source hashes. It also checks homepage reachability, title uniqueness, image alt attributes and every gallery-manifest output, including unembedded previews. The original-preservation tool still checks every original application/documentation hash. Its explicit non-V2 additions are the Pages workflow and scoped `results/.gitattributes` report-classification metadata; these never exempt original files from hash checks.

For repository Markdown/example checks and optional published HTTP/media checks, follow the [documentation audit](audit.md). Those network checks classify temporary failures separately and do not submit URLs to search engines.

## Edit content in the right place

| Content | Source |
| --- | --- |
| Homepage, tutorial, FAQ, download page and website development guide | `v2/website/pages/` |
| Existing V1 user/reproducibility/release guides | Original files under `docs/` |
| Complete V1 research record | Verbatim archived README block in root `README.md` |
| Existing V2 guides | Original files under `v2/docs/` |
| V2 overview | `v2/README.md` |
| Navigation, canonical site root and Markdown extensions | `v2/website/mkdocs.yml` |
| Source routing and generated presentation | `v2/website/hooks.py` |
| Theme and share metadata | `v2/website/overrides/main.html` |
| Responsive styles | `v2/website/pages/assets/stylesheets/extra.css` |

Source edits should follow the repository's preservation policy and requested task scope. Do not edit generated HTML or copy application logic into website code. Existing CLI examples remain commands to run from the repository root, even when displayed on nested website pages.

The site's own styles and Material assets are local, with system fonts and no web-font request. Mermaid is initialized on diagram pages by Material's built-in integration; that feature loads its diagram runtime from Material's configured upstream CDN. Videos have no autoplay and use `preload="none"`; images have dimensions where available and lazy loading outside the homepage hero. Respect reduced-motion settings in added effects.

## Automatic deployment

`.github/workflows/pages.yml` builds and checks documentation on relevant pull requests and pushes. Only a successful build on `master` (or a manual run on `master`) can deploy. Pull requests never receive Pages deployment permissions. The existing application test workflow is unchanged.

The workflow uses GitHub's Pages artifact/deployment actions, with commit-pinned action versions, read-only build permissions and a separate deployment job using `pages: write` and OIDC. Repository **Settings → Pages → Source** must be **GitHub Actions**. The production address is:

**https://maitham16.github.io/Artificial_Evolution/**

The canonical URL, Open Graph URLs, robots sitemap reference and XML sitemap all use this exact project prefix. When moving the site to another URL, update `site_url`, the robots sitemap line and the checker's default expectation together.

## Build failures

Treat strict build warnings as failures: fix stale routes, missing files or anchors in the publication layer without weakening preservation checks. Run the checker after custom template or link changes. For a deployment permission error, check Pages source and the `github-pages` environment's branch rules; do not add a personal token to the workflow.

Website tooling references: [MkDocs configuration](https://www.mkdocs.org/user-guide/configuration/), [Material navigation](https://squidfunk.github.io/mkdocs-material/setup/setting-up-navigation/), [GitHub Pages custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
