import datetime
import json
import os
from collections import defaultdict
from typing import Dict, List

import arxiv
import requests
from arxiv import Result


class ArXivPaper:
    base_url = "https://arxiv.paperswithcode.com/api/v0/papers/"

    def __init__(self, paper_item: Result) -> None:
        self.paper_id = paper_item.get_short_id()
        self.code_url = self.base_url + self.paper_id

        self.paper_key = self.paper_id.split("v")[0]  # eg: 2108.09112v1 -> 2108.09112
        self.paper_title = paper_item.title
        self.paper_url = paper_item.entry_id
        self.paper_abstract = paper_item.summary.replace("\n", " ")
        self.paper_authors = [str(author) for author in paper_item.authors]

        self.primary_category = paper_item.primary_category
        self.publish_time = str(paper_item.published.date())
        self.update_time = str(paper_item.updated.date())
        self.comments = paper_item.comment
        self.repo_url = self.get_repo_url()

    def get_repo_url(self) -> str:
        repo_url = "#"
        try:
            r = requests.get(self.code_url).json()
            if "official" in r and r["official"]:
                repo_url = r["official"]["url"]
        except Exception as e:
            print(f"exception: {e} with id: {self.paper_key}")
        return repo_url

    def __repr__(self) -> str:
        return f"Time={self.update_time} title={self.paper_title} author={self.paper_authors[0]}"

    def to_dict(self) -> Dict[str, str]:
        return {
            "paper_id": self.paper_id,
            "code_url": self.code_url,
            "paper_key": self.paper_key,
            "paper_title": self.paper_title,
            "paper_url": self.paper_url,
            "paper_abstract": self.paper_abstract,
            "paper_authors": self.paper_authors,
            "primary_category": self.primary_category,
            "publish_time": self.publish_time,
            "update_time": self.update_time,
            "comments": self.comments,
            "repo_url": self.repo_url,
        }


def update_json_file(json_path: str, papers: Dict[str, List[ArXivPaper]]) -> None:
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            json_data: Dict[str, Dict[str, Dict[str, str]]] = json.load(f)
    else:
        json_data: Dict[str, Dict[str, Dict[str, str]]] = defaultdict(dict)

    # update papers in each keywords
    for keyword, paper_items in papers.items():
        if keyword not in json_data:
            json_data[keyword] = {}

        for paper_item in paper_items:
            # NOTE: updated by the latest code information
            json_data[keyword][paper_item.paper_key] = paper_item.to_dict()

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2)


def json_to_html(
    json_path: str,
    html_path: str = "index.html",
    title: str = "Daily ArXiv Papers",
):
    current_date = str(datetime.date.today())
    current_date = current_date.replace("-", ".")

    assert os.path.exists(json_path), f"{json_path} does not exist"
    with open(json_path, "r", encoding="utf-8") as f:
        data: Dict[str, Dict[str, Dict[str, str]]] = json.load(f)

    # Generate navigation HTML with dropdown
    nav_html = f"""
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary sticky-top">
        <div class="container">
            <a class="navbar-brand" href="#">{title}</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarContent">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarContent">
                <div class="d-flex align-items-center ms-auto">
                    <div class="dropdown me-3">
                        <button class="btn btn-outline-light dropdown-toggle" type="button"
                                id="topicDropdown" data-bs-toggle="dropdown" aria-expanded="false">
                            Select Topic
                        </button>
                        <ul class="dropdown-menu" aria-labelledby="topicDropdown">
    """

    # Add dropdown items
    for i, keyword in enumerate(data.keys()):
        active = "active" if i == 0 else ""
        nav_html += f"""
                            <li><a class="dropdown-item {active}" href="#" onclick="showTopic('{keyword}')">{keyword}</a></li>
        """

    nav_html += f"""
                        </ul>
                    </div>
                    <span class="navbar-text">
                        Updated on {current_date}
                    </span>
                </div>
            </div>
        </div>
    </nav>
    """

    # Generate tab content HTML (all abstracts collapsed)
    content_html = []
    for i, (keyword, day_content) in enumerate(data.items()):
        display = "" if i == 0 else "display: none;"
        paper_items = []

        sorted_papers = sorted(day_content.items(), key=lambda item: item[1]["publish_time"], reverse=True)

        for paper_key, paper_info in sorted_papers:
            # 只有当repo_url存在且不为空时才生成代码链接
            code_link = (
                f"""
                <a href="{paper_info["repo_url"]}" class="btn btn-sm btn-success ms-2" target="_blank">
                    <i class="fas fa-code"></i> Code
                </a>
            """
                if paper_info.get("repo_url", "#") != "#"
                else ""
            )

            paper_items.append(f"""
            <div class="card mb-3">
                <div class="card-body">
                    <h5 class="card-title">{paper_info["paper_title"]}</h5>
                    <div class="d-flex flex-wrap gap-2 mb-2 text-muted">
                        <small>{paper_info["publish_time"]}</small>
                        <small><i>{", ".join(paper_info["paper_authors"])}</i></small>
                    </div>

                    <button class="btn btn-sm btn-outline-primary mb-2"
                            type="button"
                            data-bs-toggle="collapse"
                            data-bs-target="#abstract-{paper_key.replace(".", "-")}">
                        <i class="fas fa-align-left"></i> Show Abstract
                    </button>

                    <div class="collapse" id="abstract-{paper_key.replace(".", "-")}">
                        <div class="card card-body bg-light mb-2">
                            {paper_info["paper_abstract"]}
                        </div>
                    </div>

                    <div class="paper-actions">
                        <a href="{paper_info["paper_url"]}" class="btn btn-sm btn-primary" target="_blank">
                            <i class="fas fa-file-alt"></i> arXiv
                        </a>
                        {code_link}
                    </div>
                </div>
            </div>
            """)

        content_html.append(f"""
        <div id="{keyword}" class="topic-content container mt-4" style="{display}">
            <h2 class="mb-4">{keyword}</h2>
            {"".join(paper_items)}
        </div>
        """)

    # Complete HTML template with Bootstrap
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- Font Awesome -->
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .topic-content {{
            padding-top: 20px;
        }}
        .navbar {{
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }}
        .paper-actions {{
            margin-top: 10px;
        }}
    </style>
</head>
<body>
    {nav_html}

    {"".join(content_html)}

    <!-- Bootstrap JS Bundle with Popper -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>

    <script>
        // Show selected topic and hide others
        function showTopic(topicName) {{
            // Hide all topic contents
            document.querySelectorAll('.topic-content').forEach(content => {{
                content.style.display = 'none';
            }});

            // Show selected topic
            document.getElementById(topicName).style.display = '';

            // Update dropdown button text
            document.getElementById('topicDropdown').textContent = topicName;

            // Scroll to top
            window.scrollTo(0, 0);
        }}
    </script>
</body>
</html>"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_template)
    print(f"HTML file generated at {html_path}")


def get_papers(keywords: Dict[str, str], max_results_per_keyword=10) -> Dict[str, List[ArXivPaper]]:
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
            print(counts, paper)
        papers[keyword] = keyword_specific_papers
    return papers


def main():
    json_file = "arxiv-daily.json"
    html_file = "index.html"
    keywords = {
        "Rethinking": '"Rethinking"',
        "Survey": '"Survey"OR"Review"',
        "Spiking Neural Network": '"Spiking Neural Network"OR"Spiking Neural Networks"OR"Spiking Neuron"OR"SNN"',
        "Infrared Small Target Detection": '"Infrared Small Target Detection"OR"IRSTD"',  # "ISTD" will incorrectly crawl the papers about segmentation dataset ISTD
        "Salient Object Detection": '"Salient Object Detection"OR"Video Salient Object Detection"',
        "Camouflaged Object Detection": '"Camouflaged Object Detection"OR"Video Camouflaged Object Detection"',
        "Change Detection": '"Change Detection"',
    }

    papers = get_papers(keywords, max_results_per_keyword=200)
    update_json_file(json_file, papers)
    json_to_html(json_file, html_file)


if __name__ == "__main__":
    main()
