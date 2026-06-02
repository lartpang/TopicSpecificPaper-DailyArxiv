import datetime
import json
import os
import sys
from collections import defaultdict
from string import Template
from typing import TYPE_CHECKING, Dict, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

if TYPE_CHECKING:
    from arxiv import Result


class ArXivPaper:
    def __init__(self, paper_item: "Result") -> None:
        self.paper_id = paper_item.get_short_id()

        self.paper_key = self.paper_id.split("v")[0]  # eg: 2108.09112v1 -> 2108.09112
        self.paper_title = paper_item.title
        self.paper_url = paper_item.entry_id
        self.paper_abstract = paper_item.summary.replace("\n", " ")
        self.paper_authors = [str(author) for author in paper_item.authors]

        self.primary_category = paper_item.primary_category
        self.publish_time = str(paper_item.published.date())
        self.update_time = str(paper_item.updated.date())
        self.comments = paper_item.comment

    def __repr__(self) -> str:
        return f"Time={self.update_time} title={self.paper_title} author={self.paper_authors[0]}"

    def to_dict(self) -> Dict[str, object]:
        return {
            "paper_id": self.paper_id,
            "paper_key": self.paper_key,
            "paper_title": self.paper_title,
            "paper_url": self.paper_url,
            "paper_abstract": self.paper_abstract,
            "paper_authors": self.paper_authors,
            "primary_category": self.primary_category,
            "publish_time": self.publish_time,
            "update_time": self.update_time,
            "comments": self.comments,
        }


def remove_obsolete_fields(paper_info: Dict[str, object]) -> Dict[str, object]:
    return {key: value for key, value in paper_info.items() if key not in {"code_url", "repo_url"}}


def update_json_file(json_path: str, papers: Dict[str, List[ArXivPaper]]) -> None:
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            json_data: Dict[str, Dict[str, Dict[str, object]]] = json.load(f)
    else:
        json_data: Dict[str, Dict[str, Dict[str, object]]] = defaultdict(dict)

    # update papers in each keywords
    for keyword, paper_items in papers.items():
        if keyword not in json_data:
            json_data[keyword] = {}

        for paper_item in paper_items:
            json_data[keyword][paper_item.paper_key] = paper_item.to_dict()

    json_data = {
        keyword: {paper_key: remove_obsolete_fields(paper_info) for paper_key, paper_info in keyword_papers.items()}
        for keyword, keyword_papers in json_data.items()
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)


def json_to_html(
    json_path: str,
    html_path: str = "index.html",
    title: str = "Daily ArXiv Papers",
):
    current_date = str(datetime.date.today()).replace("-", ".")

    assert os.path.exists(json_path), f"{json_path} does not exist"
    json_url = os.path.relpath(json_path, start=os.path.dirname(html_path) or ".").replace(os.sep, "/")

    html_template = Template("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>$title</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        :root {
            --ink: #17181c;
            --muted: #5f6470;
            --quiet: #858b96;
            --paper: #ffffff;
            --surface: #f5f6f8;
            --line: #d9dde5;
            --line-strong: #b9c0cb;
            --accent: #1b4f8f;
            --accent-soft: #e8eef7;
            --accent-strong: #163c6f;
            --radius: 6px;
            --font-sans: "Inter", "Source Sans 3", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            --font-serif: "Iowan Old Style", "Charter", "Palatino Linotype", Georgia, "Times New Roman", serif;
            --font-mono: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
        }
        * {
            box-sizing: border-box;
        }
        body {
            background:
                linear-gradient(180deg, #fbfbfc 0, var(--surface) 240px),
                var(--surface);
            color: var(--ink);
            font-family: var(--font-sans);
            font-size: 0.9rem;
            line-height: 1.42;
        }
        .navbar {
            background: rgba(255, 255, 255, 0.95) !important;
            border-bottom: 1px solid var(--line);
            padding: 0.42rem 0;
            backdrop-filter: blur(10px);
        }
        .navbar .container {
            max-width: 1180px;
        }
        .navbar-brand {
            display: inline-flex;
            align-items: baseline;
            gap: 0.55rem;
            color: var(--ink) !important;
            font-family: var(--font-serif);
            font-size: 1.18rem;
            font-weight: 700;
            line-height: 1;
            padding: 0;
        }
        .brand-mark {
            border: 1px solid var(--line-strong);
            border-radius: 4px;
            color: var(--accent-strong);
            font-family: var(--font-mono);
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            padding: 0.12rem 0.28rem;
            text-transform: uppercase;
        }
        .navbar-text {
            color: var(--muted) !important;
            font-family: var(--font-mono);
            font-size: 0.72rem;
            font-variant-numeric: tabular-nums;
        }
        .page-shell {
            max-width: 1180px;
        }
        .toolbar-wrap {
            align-items: center;
            background: var(--paper);
            border: 1px solid var(--line);
            border-radius: var(--radius);
            display: grid;
            gap: 0.65rem;
            grid-template-columns: minmax(0, 1fr) auto;
            margin-bottom: 0.65rem;
            padding: 0.55rem 0.7rem;
        }
        .control-row {
            align-items: center;
            display: grid;
            gap: 0.45rem;
            grid-template-columns: auto minmax(180px, 260px) auto minmax(220px, 360px);
        }
        .control-label {
            color: var(--quiet);
            font-family: var(--font-mono);
            font-size: 0.68rem;
            font-weight: 700;
            text-transform: uppercase;
        }
        .toolbar-wrap .form-select,
        .toolbar-wrap .form-control {
            background-color: #fbfcfd;
            border-color: var(--line);
            border-radius: 4px;
            color: var(--ink);
            font-size: 0.82rem;
            min-height: 2rem;
            padding-bottom: 0.28rem;
            padding-top: 0.28rem;
        }
        .toolbar-wrap .form-select:focus,
        .toolbar-wrap .form-control:focus {
            background-color: var(--paper);
            border-color: var(--accent);
            box-shadow: 0 0 0 3px rgba(27, 79, 143, 0.12);
        }
        .result-info {
            color: var(--muted);
            font-family: var(--font-mono);
            font-size: 0.72rem;
            font-variant-numeric: tabular-nums;
            text-align: right;
            white-space: nowrap;
        }
        .paper-list {
            background: var(--paper);
            border: 1px solid var(--line);
            border-radius: var(--radius);
            min-height: 44vh;
            overflow: hidden;
        }
        .paper-card {
            background: var(--paper);
            border: 0;
            border-bottom: 1px solid var(--line);
            display: grid;
            gap: 0.9rem;
            grid-template-columns: minmax(7.2rem, 9rem) minmax(0, 1fr);
            margin: 0;
            padding: 0.72rem 0.82rem;
            transition: background-color 0.12s;
        }
        .paper-card:last-child {
            border-bottom: 0;
        }
        .paper-card:hover {
            background: #fbfcff;
        }
        .paper-arxiv-panel {
            align-content: start;
            color: var(--quiet);
            display: grid;
            font-family: var(--font-mono);
            font-size: 0.72rem;
            gap: 0.22rem;
            justify-items: start;
            line-height: 1.35;
            overflow-wrap: anywhere;
            padding-top: 0.08rem;
        }
        .arxiv-id {
            color: var(--ink);
            font-weight: 700;
        }
        .arxiv-link {
            color: var(--accent);
            font-weight: 700;
            text-decoration: none;
        }
        .arxiv-link:hover {
            color: var(--accent-strong);
            text-decoration: underline;
            text-decoration-thickness: 1px;
            text-underline-offset: 2px;
        }
        .paper-content {
            min-width: 0;
        }
        .badge-cat {
            background: var(--accent-soft);
            border: 1px solid #d3deef;
            border-radius: 3px;
            color: var(--accent-strong);
            font-weight: 700;
            padding: 0.04rem 0.34rem;
            white-space: nowrap;
        }
        .badge-date {
            color: var(--muted);
            white-space: nowrap;
        }
        .paper-card .card-title {
            color: var(--ink);
            font-family: var(--font-serif);
            font-size: 1.02rem;
            font-weight: 700;
            line-height: 1.22;
            margin: 0 0 0.2rem;
        }
        .paper-authors {
            color: var(--muted);
            font-size: 0.8rem;
            line-height: 1.35;
            margin: 0;
        }
        .paper-comments {
            background: #fafafa;
            border-left: 2px solid var(--line-strong);
            color: #4d535d;
            font-size: 0.78rem;
            line-height: 1.38;
            margin: 0.34rem 0 0;
            padding: 0.14rem 0 0.14rem 0.48rem;
        }
        details.abstract {
            border-top: 1px dotted var(--line-strong);
            margin-top: 0.42rem;
            padding-top: 0.32rem;
        }
        details.abstract summary {
            align-items: center;
            color: var(--accent);
            cursor: pointer;
            display: inline-flex;
            font-family: var(--font-mono);
            font-size: 0.7rem;
            font-weight: 700;
            gap: 0.28rem;
            text-transform: uppercase;
            user-select: none;
        }
        details.abstract summary::-webkit-details-marker {
            display: none;
        }
        details.abstract summary::before {
            align-items: center;
            background: var(--accent-soft);
            border-radius: 3px;
            color: var(--accent);
            content: "+";
            display: inline-flex;
            font-size: 0.72rem;
            font-weight: 700;
            height: 15px;
            justify-content: center;
            line-height: 1;
            width: 15px;
        }
        details.abstract[open] summary::before {
            content: "\\2212";
        }
        details.abstract p {
            color: #3f4550;
            font-family: var(--font-serif);
            font-size: 0.88rem;
            line-height: 1.5;
            margin: 0.42rem 0 0;
        }
        .pagination-bar {
            gap: 0.28rem;
        }
        .pagination-bar .btn-page {
            background: var(--paper);
            border: 1px solid var(--line);
            border-radius: 4px;
            color: var(--muted);
            font-family: var(--font-mono);
            font-size: 0.75rem;
            font-weight: 700;
            min-height: 1.9rem;
            min-width: 2.15rem;
            padding: 0.24rem 0.55rem;
        }
        .pagination-bar .btn-page:hover:not(:disabled) {
            background: var(--accent-soft);
            border-color: var(--accent);
            color: var(--accent);
        }
        .pagination-bar .btn-page:disabled {
            opacity: 0.4;
        }
        .pagination-bar .page-info {
            color: var(--muted);
            font-family: var(--font-mono);
            font-size: 0.74rem;
            font-variant-numeric: tabular-nums;
            padding: 0 0.35rem;
        }
        .loading-spinner {
            align-items: center;
            color: var(--muted);
            display: flex;
            font-family: var(--font-mono);
            font-size: 0.78rem;
            gap: 0.55rem;
            justify-content: center;
            padding: 3rem 0;
        }
        .loading-spinner .spinner {
            animation: spin 0.7s linear infinite;
            border: 2px solid var(--line);
            border-radius: 50%;
            border-top-color: var(--accent);
            height: 18px;
            width: 18px;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .empty-state {
            color: var(--muted);
            padding: 3rem 1rem;
            text-align: center;
        }
        .empty-state p {
            font-size: 0.88rem;
            margin: 0;
        }
        @media (max-width: 820px) {
            .toolbar-wrap {
                grid-template-columns: 1fr;
            }
            .control-row {
                grid-template-columns: auto minmax(0, 1fr);
            }
            .result-info {
                text-align: left;
            }
            .paper-card {
                grid-template-columns: 1fr;
                gap: 0.42rem;
                padding: 0.62rem 0.68rem;
            }
            .paper-arxiv-panel {
                display: flex;
                flex-wrap: wrap;
                font-size: 0.68rem;
                gap: 0.25rem 0.5rem;
                padding: 0;
            }
        }
        @media (max-width: 480px) {
            body {
                font-size: 0.86rem;
            }
            .navbar .container {
                align-items: flex-start;
                flex-direction: column;
                gap: 0.22rem;
            }
            .navbar-brand {
                font-size: 1.05rem;
            }
            .control-row {
                grid-template-columns: 1fr;
                gap: 0.28rem;
            }
            .control-label {
                margin-top: 0.12rem;
            }
        }
    </style>
</head>
<body>
    <nav class="navbar sticky-top">
        <div class="container">
            <a class="navbar-brand" href="#"><span class="brand-mark">arXiv</span><span>$title</span></a>
            <span class="navbar-text">Updated $current_date</span>
        </div>
    </nav>

    <main class="container page-shell py-2 py-md-3">
        <section class="toolbar-wrap" aria-label="Paper filters">
            <div class="control-row">
                <label class="control-label" for="topicSelect">Topic</label>
                <select id="topicSelect" class="form-select" aria-label="Select topic"></select>
                <label class="control-label" for="searchInput">Search</label>
                <input id="searchInput" class="form-control" type="search" placeholder="Title, author, abstract&hellip;" aria-label="Search papers">
            </div>
            <div id="resultInfo" class="result-info"></div>
        </section>

        <div id="loading" class="loading-spinner">
            <div class="spinner"></div>
            <span>Loading papers&hellip;</span>
        </div>
        <div id="paperList" class="paper-list"></div>
        <div id="pagination" class="d-flex flex-wrap align-items-center justify-content-center mt-3 pagination-bar"></div>
    </main>

    <script>
        const DATA_URL = "$json_url";
        const PAGE_SIZE = 45;

        const state = {
            rawData: {},
            topics: [],
            papersByTopic: {},
            currentTopic: "",
            currentPage: 1,
            query: "",
            filteredPapers: [],
        };

        const elements = {
            topicSelect: document.getElementById("topicSelect"),
            searchInput: document.getElementById("searchInput"),
            loading: document.getElementById("loading"),
            paperList: document.getElementById("paperList"),
            pagination: document.getElementById("pagination"),
            resultInfo: document.getElementById("resultInfo"),
        };

        function escapeHtml(value) {
            return String(value ?? "")
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#39;");
        }

        function safeUrl(value) {
            try {
                const url = new URL(value, window.location.href);
                return ["http:", "https:"].includes(url.protocol) ? url.href : "#";
            } catch {
                return "#";
            }
        }

        function normalizePaper(paperKey, paperInfo) {
            const authors = Array.isArray(paperInfo.paper_authors) ? paperInfo.paper_authors : [];
            const paper = {
                key: paperKey,
                id: paperInfo.paper_id || paperKey,
                title: paperInfo.paper_title || "",
                url: paperInfo.paper_url || "",
                abstract: paperInfo.paper_abstract || "",
                authors,
                category: paperInfo.primary_category || "",
                publishTime: paperInfo.publish_time || "",
                updateTime: paperInfo.update_time || "",
                comments: paperInfo.comments || "",
            };
            paper.searchText = [
                paper.title,
                paper.abstract,
                paper.category,
                paper.publishTime,
                paper.updateTime,
                paper.comments,
                authors.join(" "),
            ].join(" ").toLowerCase();
            return paper;
        }

        function prepareTopic(topic) {
            if (state.papersByTopic[topic]) return;
            const topicData = state.rawData[topic] || {};
            state.papersByTopic[topic] = Object.entries(topicData)
                .map(([paperKey, paperInfo]) => normalizePaper(paperKey, paperInfo))
                .sort((a, b) => {
                    const c = b.publishTime.localeCompare(a.publishTime);
                    return c || b.updateTime.localeCompare(a.updateTime);
                });
        }

        function renderTopicSelect() {
            elements.topicSelect.innerHTML = state.topics.map((topic) => {
                const count = Object.keys(state.rawData[topic] || {}).length;
                return '<option value="' + escapeHtml(topic) + '">' + escapeHtml(topic) + ' (' + count + ')</option>';
            }).join("");
        }

        function setTopic(topic) {
            state.currentTopic = topic;
            state.currentPage = 1;
            elements.topicSelect.value = topic;
            prepareTopic(topic);
            applyFilter();
            window.scrollTo(0, 0);
        }

        function applyFilter() {
            const term = state.query.trim().toLowerCase();
            const papers = state.papersByTopic[state.currentTopic] || [];
            state.filteredPapers = term ? papers.filter((p) => p.searchText.includes(term)) : papers;
            render();
        }

        function renderPaper(paper) {
            const authorText = paper.authors.join(", ");
            const authorsHtml = authorText ? '<p class="paper-authors">' + escapeHtml(authorText) + '</p>' : "";
            const commentsHtml = paper.comments ? '<p class="paper-comments">' + escapeHtml(paper.comments) + '</p>' : "";
            const categoryHtml = paper.category ? '<span class="badge-cat">' + escapeHtml(paper.category) + '</span>' : "";
            const dateHtml = paper.publishTime ? '<span class="badge-date">' + escapeHtml(paper.publishTime) + '</span>' : "";

            return '<article class="paper-card">'
                + '<div class="paper-arxiv-panel">'
                + dateHtml
                + '<span class="arxiv-id">' + escapeHtml(paper.id) + '</span>'
                + categoryHtml
                + '<a href="' + escapeHtml(safeUrl(paper.url)) + '" class="arxiv-link" target="_blank" rel="noopener">arXiv Abs</a>'
                + '</div>'
                + '<div class="paper-content">'
                + '<h2 class="card-title">' + escapeHtml(paper.title) + '</h2>'
                + authorsHtml
                + commentsHtml
                + '<details class="abstract">'
                + '<summary>Abstract</summary>'
                + '<p>' + escapeHtml(paper.abstract) + '</p>'
                + '</details>'
                + '</div>'
                + '</article>';
        }

        function renderPagination(totalPages) {
            if (totalPages <= 1) {
                elements.pagination.innerHTML = "";
                return;
            }
            const prevDisabled = state.currentPage === 1;
            const nextDisabled = state.currentPage === totalPages;
            elements.pagination.innerHTML = ""
                + '<button class="btn-page" data-page="1"' + (prevDisabled ? " disabled" : "") + '>&#171;</button>'
                + '<button class="btn-page" data-page="' + (state.currentPage - 1) + '"' + (prevDisabled ? " disabled" : "") + '>&#8249;</button>'
                + '<span class="page-info">' + state.currentPage + ' / ' + totalPages + '</span>'
                + '<button class="btn-page" data-page="' + (state.currentPage + 1) + '"' + (nextDisabled ? " disabled" : "") + '>&#8250;</button>'
                + '<button class="btn-page" data-page="' + totalPages + '"' + (nextDisabled ? " disabled" : "") + '>&#187;</button>';
        }

        function render() {
            const total = state.filteredPapers.length;
            const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
            state.currentPage = Math.min(Math.max(state.currentPage, 1), totalPages);
            const start = (state.currentPage - 1) * PAGE_SIZE;
            const end = Math.min(start + PAGE_SIZE, total);
            const currentPapers = state.filteredPapers.slice(start, start + PAGE_SIZE);
            elements.resultInfo.textContent = total ? (start + 1) + "-" + end + " of " + total + " papers" : "0 papers";

            if (!total) {
                elements.paperList.innerHTML = '<div class="empty-state"><p>No papers found matching your search.</p></div>';
                elements.pagination.innerHTML = "";
                return;
            }
            elements.paperList.innerHTML = currentPapers.map(renderPaper).join("");
            renderPagination(totalPages);
        }

        function showError(error) {
            elements.loading.outerHTML = '<div class="empty-state"><p>Failed to load papers. Serve this page through a local web server (e.g., <code>python -m http.server</code>).</p><p class="mt-2 text-muted" style="font-size:0.8rem">' + escapeHtml(error.message) + '</p></div>';
        }

        async function init() {
            try {
                const res = await fetch(DATA_URL);
                if (!res.ok) throw new Error(res.status + " " + res.statusText);
                state.rawData = await res.json();
                state.topics = Object.keys(state.rawData);
                renderTopicSelect();
                elements.loading.style.display = "none";
                if (state.topics.length) {
                    setTopic(state.topics[0]);
                } else {
                    elements.paperList.innerHTML = '<div class="empty-state"><p>No papers available.</p></div>';
                }
            } catch (error) {
                showError(error);
            }
        }

        let searchTimer = null;
        elements.searchInput.addEventListener("input", (e) => {
            window.clearTimeout(searchTimer);
            searchTimer = window.setTimeout(() => {
                state.query = e.target.value;
                state.currentPage = 1;
                applyFilter();
            }, 120);
        });

        elements.topicSelect.addEventListener("change", (e) => setTopic(e.target.value));

        elements.pagination.addEventListener("click", (e) => {
            const btn = e.target.closest("button[data-page]");
            if (!btn || btn.disabled) return;
            state.currentPage = Number(btn.dataset.page);
            render();
            window.scrollTo(0, 0);
        });

        init();
    </script>
</body>
</html>""")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_template.substitute(title=title, current_date=current_date, json_url=json_url))
    print(f"HTML file generated at {html_path}")


def get_papers(keywords: Dict[str, str], max_results_per_keyword=10) -> Dict[str, List[ArXivPaper]]:
    import arxiv

    # Construct the default API client.
    client = arxiv.Client(page_size=200, delay_seconds=3, num_retries=5)

    counts = 0
    papers: Dict[str, List[ArXivPaper]] = {}
    for keyword, query in keywords.items():
        print(f"Keyword: {keyword}")
        search = arxiv.Search(
            query=query,
            max_results=max_results_per_keyword,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )

        keyword_specific_papers = []
        for result in client.results(search):
            paper = ArXivPaper(result)
            keyword_specific_papers.append(paper)

            counts += 1
            print(f"{counts} {paper}")
        papers[keyword] = keyword_specific_papers
    return papers


def main():
    json_file = "arxiv-daily.json"
    html_file = "index.html"
    keywords = {
        # Comprehensive Topics
        "Dataset": '(cat:cs.CV OR cat:cs.LG OR cat:cs.AI OR cat:eess.IV) AND (ti:Benchmark OR ti:Dataset OR ti:"Data Set" OR abs:"benchmark dataset" OR abs:"new dataset" OR abs:"large-scale dataset")',
        "Evaluation": '(cat:cs.CV OR cat:cs.LG OR cat:cs.AI OR cat:eess.IV) AND (ti:Evaluation OR ti:Benchmarking OR abs:"evaluation protocol" OR abs:"evaluation benchmark" OR abs:"benchmarking")',
        "Rethinking": '(cat:cs.CV OR cat:cs.LG OR cat:cs.AI OR cat:cs.NE OR cat:eess.IV) AND ti:Rethinking',
        "Survey": '(cat:cs.CV OR cat:cs.LG OR cat:cs.AI OR cat:cs.NE OR cat:eess.IV) AND (ti:Survey OR ti:Review OR ti:"A Survey" OR ti:"A Review")',
        # Special Architecture
        "Spiking Network": '(cat:cs.CV OR cat:cs.LG OR cat:cs.AI OR cat:cs.NE OR cat:eess.IV) AND (ti:"Spiking Neural Network" OR abs:"Spiking Neural Network" OR ti:"Spiking Neural Networks" OR abs:"Spiking Neural Networks" OR ti:"Spiking Neuron" OR abs:"Spiking Neuron" OR (all:SNN AND all:spiking))',
        "Recurrent Network": '(cat:cs.CV OR cat:cs.LG OR cat:cs.AI OR cat:cs.NE) AND (ti:"Recurrent Neural Network" OR abs:"Recurrent Neural Network" OR ti:"Recurrent Network" OR abs:"recurrent network" OR ti:"Recursive Neural Network" OR abs:"recursive neural network" OR ti:RNN OR abs:RNN)',
        # Context Dependent Understanding
        "Salient Object Detection": '(cat:cs.CV OR cat:eess.IV) AND (ti:"Salient Object Detection" OR abs:"Salient Object Detection" OR ti:"Video Salient Object Detection" OR abs:"Video Salient Object Detection" OR ti:"Saliency Detection")',
        "Camouflaged Object Detection": '(cat:cs.CV OR cat:eess.IV) AND (ti:"Camouflaged Object Detection" OR abs:"Camouflaged Object Detection" OR ti:"Video Camouflaged Object Detection" OR abs:"Video Camouflaged Object Detection")',
        "Change Detection": '(cat:cs.CV OR cat:eess.IV) AND (ti:"Change Detection" OR abs:"Change Detection" OR ti:"Semantic Change Detection" OR abs:"Semantic Change Detection") AND (all:"remote sensing" OR all:image OR all:video OR all:segmentation)',
        # Remote Sense Segmentation
        "Infrared Small Target Detection": '(cat:cs.CV OR cat:eess.IV) AND (ti:"Infrared Small Target Detection" OR abs:"Infrared Small Target Detection" OR ti:"Infrared Small Target" OR abs:"Infrared Small Target" OR all:IRSTD)',  # "ISTD" will incorrectly crawl the papers about segmentation dataset ISTD
    }

    papers = get_papers(keywords, max_results_per_keyword=200)
    update_json_file(json_file, papers)
    json_to_html(json_file, html_file)


if __name__ == "__main__":
    main()
