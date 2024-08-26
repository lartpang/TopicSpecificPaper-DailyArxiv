import datetime
import json
import os
from collections import defaultdict
from typing import Dict, List, Tuple

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


def update_json_file(json_path, papers: Dict[str, List[ArXivPaper]]) -> None:
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            json_data: Dict[str, Dict[str, Dict[str, str]]] = json.load(f)
    else:
        json_data: Dict[str, Dict[str, Dict[str, str]]] = defaultdict(dict)

    # update papers in each keywords
    for keyword, paper_items in papers.items():
        for paper_item in paper_items:
            # NOTE: updated by the latest code information
            json_data[keyword][paper_item.paper_key] = paper_item.to_dict()

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2)


def json_to_md(json_path, markdown_path, title="Daily ArXiv", show_badge=True, show_toc=True):
    current_date = str(datetime.date.today())
    current_date = current_date.replace("-", ".")

    assert os.path.exists(json_path), f"{json_path} does not exist"
    with open(json_path, "r", encoding="utf-8") as f:
        data: Dict[str, Dict[str, Dict[str, str]]] = json.load(f)

    # convert data into the string list
    title_line = f"# {title}"
    lines = [title_line]
    lines.append(f"> Updated on {current_date}")

    if show_badge:
        lines.append(
            "[![](https://img.shields.io/github/contributors/lartpang/TopicSpecificPaper-DailyArxiv.svg?style=for-the-badge)](https://github.com/lartpang/TopicSpecificPaper-DailyArxiv/graphs/contributors) "
            "[![](https://img.shields.io/github/forks/lartpang/TopicSpecificPaper-DailyArxiv.svg?style=for-the-badge)](https://github.com/lartpang/TopicSpecificPaper-DailyArxiv/network/members) "
            "[![](https://img.shields.io/github/stars/lartpang/TopicSpecificPaper-DailyArxiv.svg?style=for-the-badge)](https://github.com/lartpang/TopicSpecificPaper-DailyArxiv/stargazers) "
            "[![](https://img.shields.io/github/issues/lartpang/TopicSpecificPaper-DailyArxiv.svg?style=for-the-badge)](https://github.com/lartpang/TopicSpecificPaper-DailyArxiv/issues) "
        )

    if show_toc:
        toc_strings = ["**Table of Contents**"]
        for keyword in data.keys():
            toc_strings.append(f"- [{keyword}](#{keyword.replace(' ', '-')})")
        lines.append("\n".join(toc_strings))

    for keyword, day_content in data.items():
        # the head of each part
        section_lines = [f"## {keyword}"]
        section_lines.append(" Publish Date | Title | Abstract | Authors | Links ")
        section_lines.append(":-------------|:------|:---------|:------- |:------")

        sorted_by = "publish_time"  # use the publish_time string as the key to sort
        day_content: Tuple[str, Dict[str, str]] = sorted(
            day_content.items(), key=lambda item: item[1][sorted_by.replace("-", "")], reverse=True
        )
        for paper_key, paper_info in day_content:
            print(paper_key, paper_info["paper_title"])
            paper_line_splits = [
                paper_info["publish_time"],
                paper_info["paper_title"],
                f"<details><summary>...</summary>{paper_info['paper_abstract']}</details>",
                ", ".join(paper_info["paper_authors"]),
                f"[{paper_info['paper_id']}]({paper_info['paper_url']}), [Code]({paper_info['repo_url']})",
            ]
            section_lines.append("|".join(paper_line_splits))

        # Add: back to top
        top_info = title_line.replace(" ", "-").replace(".", "")
        section_lines.append(f"<p align=right>(<a href={top_info}>back to top</a>)</p>")
        lines.append("\n".join(section_lines))

    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(lines))
    print("finished")


def get_papers(keywords: Dict[str, str], max_results_per_keyword=10) -> Dict[str, List[ArXivPaper]]:
    # Construct the default API client.
    client = arxiv.Client(page_size=500, delay_seconds=5, num_retries=5)

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
            print(f"id={counts} {paper}")
        papers[keyword] = keyword_specific_papers
    return papers


def main():
    json_file = "arxiv-daily.json"
    md_file = "README.md"
    keywords = {
        "Spiking Neural Network": '"Spiking Neural Network"OR"Spiking Neural Networks"OR"Spiking Neuron"',
    }

    papers = get_papers(keywords, max_results_per_keyword=500)
    update_json_file(json_file, papers)
    json_to_md(json_file, md_file)


if __name__ == "__main__":
    main()
