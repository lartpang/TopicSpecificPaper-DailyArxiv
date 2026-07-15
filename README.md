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
- Fetch new Preprints.org DOI metadata through the Crossref REST API, then apply equivalent topic rules locally. The script does not scrape Preprints.org pages.
- Merge exact cross-source title matches within each topic while preserving both arXiv and Preprints.org identifiers and links.
- Keep a rolling 180-day archive in `arxiv-daily.json` and generate `index.html`.
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

The job is capped at 30 minutes. arXiv requests are serial and at least four seconds apart; transient errors are retried briefly per topic. A failure for one topic preserves its existing records and leaves that topic due for the fallback run.

For Crossref's polite API pool, create a repository Actions variable named `CROSSREF_MAILTO` containing a monitored contact email. Without it, the public pool is used. Crossref normally requires only one request per run for the three-day overlap window.

### Customization

Edit `ARXIV_KEYWORDS` and `matches_preprint_topics()` together when changing topics. Relevant environment variables are:

- `PAPER_RETENTION_DAYS` (default `180`) controls the rolling archive.
- `JSON_MAX_SIZE_MIB` (default `45`) refuses an oversized generated file before GitHub's 100 MiB hard limit.
- `FORCE_FETCH=1` bypasses the same-day state check.
- `ARXIV_MAX_RESULTS_PER_KEYWORD`, `ARXIV_PAGE_SIZE`, and retry/backoff variables tune arXiv access.
- `CROSSREF_LOOKBACK_DAYS` controls the overlap used to catch delayed Crossref deposits.

The existing Git history still contains older snapshots. Shrinking clone size requires a separate, one-time history rewrite and force push; the daily workflow intentionally does not perform that destructive operation.
