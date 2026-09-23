# Public deployment

The site is designed to deploy from `main` through GitHub Pages.

## One-time repository setting

GitHub Pages must be enabled for this repository with **Source: GitHub Actions**.

The workflow cannot enable the Pages site itself with the repository's current Actions integration permissions; GitHub returns `Resource not accessible by integration` when `actions/configure-pages` attempts to create the site.

After Pages is enabled once, the existing workflow `.github/workflows/pages.yml` can deploy automatically on every push to `main`.

Expected site URL:

`https://mapkepp.github.io/vseyasvetnaya-gramota-reference/`

Expected API entry point:

`https://mapkepp.github.io/vseyasvetnaya-gramota-reference/api/v1/index.json`

## Data integrity

The canonical catalog is `data/bukovy.json`. The public API is generated from it by `scripts/build-api.py`.

`scripts/validate-bukovy.py` verifies:

- stable unique entry IDs;
- unique source image numbers;
- coverage counters;
- local-image references;
- exact synchronization of `api/v1/bukovy.json`;
- API endpoint declarations.

The validator runs automatically in `.github/workflows/validate-bukovy.yml`.

## Recovery artifact workflow

`.github/workflows/harvest-historical-bukovnik.yml` is a manual, read-only workflow. It runs `scripts/recover-historical-six-pages.py`, stores archived HTML/images plus SHA-256 hashes as a 14-day Actions artifact, and does **not** write to `data/bukovy.json` or promote recovery candidates into the canonical catalog.

The recovery API is published separately at `api/v1/recovery.json`; its candidate count is intentionally not interpreted as a one-to-one count of the 79 unfilled canonical positions.
