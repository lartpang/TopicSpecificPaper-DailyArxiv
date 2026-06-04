# Daily ArXiv

[![](https://img.shields.io/github/contributors/lartpang/TopicSpecificPaper-DailyArxiv.svg?style=for-the-badge)](https://github.com/lartpang/TopicSpecificPaper-DailyArxiv/graphs/contributors) [![](https://img.shields.io/github/forks/lartpang/TopicSpecificPaper-DailyArxiv.svg?style=for-the-badge)](https://github.com/lartpang/TopicSpecificPaper-DailyArxiv/network/members) [![](https://img.shields.io/github/stars/lartpang/TopicSpecificPaper-DailyArxiv.svg?style=for-the-badge)](https://github.com/lartpang/TopicSpecificPaper-DailyArxiv/stargazers) [![](https://img.shields.io/github/issues/lartpang/TopicSpecificPaper-DailyArxiv.svg?style=for-the-badge)](https://github.com/lartpang/TopicSpecificPaper-DailyArxiv/issues)

Please give us a star if you find this repository useful.

## Usage

### 1. Local Run

Install dependencies and execute the crawling script:

```bash
pip install -r requirements.txt
python daily_arxiv.py
```

This will:
- Fetch papers from arXiv based on keywords defined in `daily_arxiv.py`
- Generate `arxiv-daily.json` (paper data) and `index.html` (visualization page)

### 2. Local Preview

The generated `index.html` loads `arxiv-daily.json` with `fetch`, so preview it through a local web server:

```bash
python -m http.server
```

Then open `http://localhost:8000` in your browser.

### 3. GitHub Actions (Automated)

A GitHub Actions workflow (`.github/workflows/arxiv-daily.yml`) is configured to run daily at UTC 02:17 (Beijing 10:17), ensuring arXiv's latest daily submission batch has been published while avoiding the busiest exact-hour trigger time. It automatically fetches the latest papers and commits updates. You can also manually trigger it from the Actions tab via `workflow_dispatch`.

### Customization

Edit the `keywords` dictionary in `daily_arxiv.py` to adjust search topics. In GitHub Actions, tune `ARXIV_MAX_RESULTS_PER_KEYWORD`, `ARXIV_PAGE_SIZE`, `ARXIV_DELAY_SECONDS`, and retry/backoff environment variables in `.github/workflows/arxiv-daily.yml` if arXiv rate limits requests.
