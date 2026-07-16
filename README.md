# Daily Research Preprints

[![](https://img.shields.io/github/contributors/lartpang/TopicSpecificPaper-DailyArxiv.svg?style=for-the-badge)](https://github.com/lartpang/TopicSpecificPaper-DailyArxiv/graphs/contributors) [![](https://img.shields.io/github/forks/lartpang/TopicSpecificPaper-DailyArxiv.svg?style=for-the-badge)](https://github.com/lartpang/TopicSpecificPaper-DailyArxiv/network/members) [![](https://img.shields.io/github/stars/lartpang/TopicSpecificPaper-DailyArxiv.svg?style=for-the-badge)](https://github.com/lartpang/TopicSpecificPaper-DailyArxiv/stargazers) [![](https://img.shields.io/github/issues/lartpang/TopicSpecificPaper-DailyArxiv.svg?style=for-the-badge)](https://github.com/lartpang/TopicSpecificPaper-DailyArxiv/issues)

Please give us a star if you find this repository useful.

## Usage

### 1. Local Run

Install dependencies and execute the tracker:

```bash
pip install -r requirements.txt
python daily_arxiv.py
```

This will:

- Fetch papers from arXiv with the queries in `ARXIV_KEYWORDS`.
- Fetch Preprints.org records through Crossref and, when an API key is configured, OpenAlex. It does not request Preprints.org pages, RSS, or OAI-PMH endpoints, which avoids the site's Akamai restrictions.
- Apply all topic rules locally and merge duplicate provider records by the version-independent Preprints.org DOI.
- Merge exact cross-source title matches within each topic while preserving both arXiv and Preprints.org identifiers and links.
- Keep a rolling 180-day arXiv archive and a five-year publication-date Preprints.org archive in `arxiv-daily.json`, then generate `index.html`.
- Record per-topic/source success in `.tracker-state.json`, so a retry only calls sources that have not succeeded that UTC day.

The generated page uses an arXiv-red border for arXiv-only records and a Preprints.org-yellow border for Preprints.org-only records. Merged records use a red left half and yellow right half, with a separate themed link for each source.

### 2. Local Preview

The generated `index.html` loads `arxiv-daily.json` with `fetch`, so preview it through a local web server:

```bash
python -m http.server
```

Then open `http://localhost:8000` in your browser.

### 3. GitHub Actions (Automated)

A GitHub Actions workflow (`.github/workflows/arxiv-daily.yml`) has a primary trigger at UTC 06:17 and a fallback at UTC 16:47. GitHub may delay or drop scheduled events under load, so the second trigger provides another opportunity. It normally makes no upstream requests because the state file detects that the primary run already succeeded.

The job is capped at 120 minutes so a manual history import has enough time to finish. arXiv requests are serial and at least four seconds apart; transient errors are retried briefly per topic. Crossref and OpenAlex use cursor pagination with a one-second delay between pages. A failed provider does not fail the Preprints.org update when the other provider succeeds; if both fail, existing records and state are left unchanged for the fallback run.

The workflow pins GitHub Actions and Python packages to exact revisions, with weekly Dependabot checks for both ecosystems. Checkout credentials are not persisted while the metadata code runs; the short-lived `GITHUB_TOKEN` is exposed only to the final pull/push step through a non-persistent credential helper. API responses and the generated JSON archive also have independent size limits.

Scheduled runs query an overlapping three-day metadata window to tolerate delayed indexing. Crossref is the default provider and requires no secret. OpenAlex is an optional supplement because its current API budget is tied to an API key: create a free key in [OpenAlex settings](https://openalex.org/settings/api) and store it as the repository Actions secret `OPENALEX_API_KEY`. You may also set the repository variable `CROSSREF_MAILTO` to a monitored contact address for Crossref's polite pool.

For a five-year Preprints.org history import, manually run the workflow with `preprints_backfill_days` set to `1826`. The backfill skips arXiv for that run, splits provider history into yearly windows, merges repeated DOI versions, and enforces the final range by publication date before updating the existing archive.

### Customization

Edit `ARXIV_KEYWORDS` and `matches_preprint_topics()` together when changing topics. Relevant environment variables are:

- `PAPER_RETENTION_DAYS` (default `180`) controls arXiv retention.
- `PREPRINT_RETENTION_DAYS` (default `1826`) controls the five-year Preprints.org archive.
- `JSON_MAX_SIZE_MIB` (default `75`) refuses an oversized generated file before GitHub's 100 MiB hard limit.
- `FORCE_FETCH=1` bypasses the same-day state check.
- `ARXIV_MAX_RESULTS_PER_KEYWORD`, `ARXIV_PAGE_SIZE`, and retry/backoff variables tune arXiv access.
- `PREPRINTS_BACKFILL_DAYS` selects a historical provider window; `0` uses the daily overlap.
- `PREPRINTS_LOOKBACK_DAYS` (default `3`) controls that daily overlap.
- `PREPRINTS_METADATA_DELAY_SECONDS` (default `1`) spaces cursor pages; `PREPRINTS_METADATA_MAX_PAGES` is a safety ceiling.
- `PREPRINTS_WINDOW_RETRIES` (default `3`) and `PREPRINTS_WINDOW_BACKOFF_SECONDS` (default `15`) restart a complete date window after a cursor/network failure instead of risking a skipped page.
- `HTTP_MAX_RESPONSE_MIB` (default `64`, capped at `256`) limits each upstream JSON response.
- `OPENALEX_API_KEY` enables the optional OpenAlex supplement; `CROSSREF_MAILTO` identifies the client to Crossref.

The existing Git history still contains older snapshots. Shrinking clone size requires a separate, one-time history rewrite and force push; the daily workflow intentionally does not perform that destructive operation.
