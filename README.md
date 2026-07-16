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
- Fetch daily Preprints.org additions from its [official RSS feed](https://www.preprints.org/rss) and apply all topic rules locally. Historical backfills use the official [OAI-PMH endpoint](https://www.preprints.org/oaipmh) instead of Crossref or page scraping.
- Merge exact cross-source title matches within each topic while preserving both arXiv and Preprints.org identifiers and links.
- Keep a rolling 180-day arXiv archive and five-year Preprints.org archive in `arxiv-daily.json`, then generate `index.html`.
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

The job is capped at 180 minutes so a manually requested OAI-PMH history backfill can finish. arXiv requests are serial and at least four seconds apart; transient errors are retried briefly per topic. A failure for one source preserves its existing records and leaves that source due for the fallback run.

For a five-year Preprints.org history import, manually run the workflow with `preprints_backfill_days` set to `1826`. Scheduled runs leave it at `0` and make one RSS request.

### Customization

Edit `ARXIV_KEYWORDS` and `matches_preprint_topics()` together when changing topics. Relevant environment variables are:

- `PAPER_RETENTION_DAYS` (default `180`) controls arXiv retention.
- `PREPRINT_RETENTION_DAYS` (default `1826`) controls the five-year Preprints.org archive.
- `JSON_MAX_SIZE_MIB` (default `45`) refuses an oversized generated file before GitHub's 100 MiB hard limit.
- `FORCE_FETCH=1` bypasses the same-day state check.
- `ARXIV_MAX_RESULTS_PER_KEYWORD`, `ARXIV_PAGE_SIZE`, and retry/backoff variables tune arXiv access.
- `PREPRINTS_BACKFILL_DAYS` selects an OAI-PMH history window; `0` uses the daily RSS path.
- `PREPRINTS_OAI_DELAY_SECONDS` (default `1`) spaces OAI-PMH resumption-token pages.

The existing Git history still contains older snapshots. Shrinking clone size requires a separate, one-time history rewrite and force push; the daily workflow intentionally does not perform that destructive operation.
