import datetime
import hashlib
import html
import http.client
import json
import os
import re
import sys
import time
import unicodedata
from collections import defaultdict
from string import Template
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple, Union
from urllib import error, parse, request

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
        self.source = "arxiv"

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
            "source": self.source,
        }


class PreprintsPaper:
    def __init__(
        self,
        paper_id: str,
        title: str,
        url: str,
        abstract: str,
        authors: List[str],
        category: str,
        publish_time: str,
        update_time: str,
    ) -> None:
        self.paper_id = paper_id
        self.paper_key = re.sub(r"\.v\d+$", "", paper_id.lower())
        self.paper_title = title
        self.paper_url = url
        self.paper_abstract = clean_markup(abstract)
        self.paper_authors = authors
        self.primary_category = category or "Preprints.org"
        self.publish_time = publish_time
        self.update_time = update_time or publish_time
        self.comments = "Preprints.org"
        self.source = "preprints.org"

    def __repr__(self) -> str:
        return f"Time={self.publish_time} title={self.paper_title}"

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
            "source": self.source,
        }


Paper = Union[ArXivPaper, PreprintsPaper]


ARXIV_KEYWORDS = {
    # Comprehensive Topics
    "Dataset": '(cat:cs.CV OR cat:cs.LG OR cat:cs.AI OR cat:eess.IV) AND (ti:Benchmark OR ti:Dataset OR ti:"Data Set" OR abs:"benchmark dataset" OR abs:"new dataset" OR abs:"large-scale dataset")',
    "Evaluation": '(cat:cs.CV OR cat:cs.LG OR cat:cs.AI OR cat:eess.IV) AND (ti:Evaluation OR ti:Benchmarking OR abs:"evaluation protocol" OR abs:"evaluation benchmark" OR abs:"benchmarking")',
    "Rethinking": '(cat:cs.CV OR cat:cs.LG OR cat:cs.AI OR cat:cs.NE OR cat:eess.IV) AND ti:Rethinking',
    "Survey": '(cat:cs.CV OR cat:cs.LG OR cat:cs.AI OR cat:cs.NE OR cat:eess.IV) AND (ti:Survey OR ti:Review OR ti:"A Survey" OR ti:"A Review")',
    "Feature Coding": '(cat:cs.CV OR cat:cs.LG OR cat:cs.AI OR cat:cs.MM OR cat:eess.IV OR cat:eess.SP) AND (all:"feature coding" OR all:"feature compression" OR all:"deep feature compression" OR all:"intermediate feature compression" OR all:"feature map compression" OR all:"feature tensor compression" OR all:"semantic feature coding" OR all:"feature codec")',
    "Gaussian Splatting": '(cat:cs.CV OR cat:cs.GR OR cat:cs.LG OR cat:cs.AI OR cat:eess.IV) AND (all:"Gaussian Splatting" OR all:"Gaussian Splat" OR all:3DGS)',
    # Special Architecture
    "Spiking Network": '(cat:cs.CV OR cat:cs.LG OR cat:cs.AI OR cat:cs.NE OR cat:eess.IV) AND (ti:"Spiking Neural Network" OR abs:"Spiking Neural Network" OR ti:"Spiking Neural Networks" OR abs:"Spiking Neural Networks" OR ti:"Spiking Neuron" OR abs:"Spiking Neuron" OR (all:SNN AND all:spiking))',
    "Recurrent Network": '(cat:cs.CV OR cat:cs.LG OR cat:cs.AI OR cat:cs.NE) AND (ti:"Recurrent Neural Network" OR abs:"Recurrent Neural Network" OR ti:"Recurrent Network" OR abs:"recurrent network" OR ti:"Recursive Neural Network" OR abs:"recursive neural network" OR ti:RNN OR abs:RNN)',
    # Context Dependent Understanding
    "Salient Object Detection": '(cat:cs.CV OR cat:eess.IV) AND (ti:"Salient Object Detection" OR abs:"Salient Object Detection" OR ti:"Video Salient Object Detection" OR abs:"Video Salient Object Detection" OR ti:"Saliency Detection")',
    "Camouflaged Object Detection": '(cat:cs.CV OR cat:eess.IV) AND (ti:"Camouflaged Object Detection" OR abs:"Camouflaged Object Detection" OR ti:"Video Camouflaged Object Detection" OR abs:"Video Camouflaged Object Detection")',
    "Change Detection": '(cat:cs.CV OR cat:eess.IV) AND (ti:"Change Detection" OR abs:"Change Detection" OR ti:"Semantic Change Detection" OR abs:"Semantic Change Detection") AND (all:"remote sensing" OR all:image OR all:video OR all:segmentation)',
    # Remote Sense Segmentation
    "Infrared Small Target Detection": '(cat:cs.CV OR cat:eess.IV) AND (ti:"Infrared Small Target Detection" OR abs:"Infrared Small Target Detection" OR ti:"Infrared Small Target" OR abs:"Infrared Small Target" OR all:IRSTD)',
}

LOCALLY_FILTERED_TOPICS = {"Feature Coding", "Gaussian Splatting"}
KNOWN_SOURCES = ("arxiv", "preprints.org")
PREPRINTS_CROSSREF_URL = "https://api.crossref.org/prefixes/10.20944/works"
PREPRINTS_OPENALEX_URL = "https://api.openalex.org/works"
PREPRINTS_DOI_PATTERN = re.compile(r"10\.20944/preprints\d{6}\.\d+(?:\.v\d+)?", re.IGNORECASE)
PREPRINTS_MANUSCRIPT_PATTERN = re.compile(
    r"(?:https?://(?:www\.)?preprints\.org/)?(?:manuscript/)?(\d{6}\.\d+)(?:/v(\d+))?",
    re.IGNORECASE,
)


def remove_obsolete_fields(paper_info: Dict[str, object]) -> Dict[str, object]:
    return {key: value for key, value in paper_info.items() if key not in {"code_url", "repo_url"}}


def normalized_paper_title(title: object) -> str:
    normalized = unicodedata.normalize("NFKC", str(title or "")).casefold()
    return "".join(character for character in normalized if character.isalnum())


def paper_sources(paper_info: Dict[str, object]) -> List[str]:
    raw_sources = paper_info.get("sources")
    candidates = raw_sources if isinstance(raw_sources, list) else str(paper_info.get("source") or "arxiv").split("+")
    present = {str(source).lower() for source in candidates}
    sources = [source for source in KNOWN_SOURCES if source in present]
    return sources or ["arxiv"]


def add_source_metadata(paper_info: Dict[str, object]) -> Dict[str, object]:
    result = remove_obsolete_fields(dict(paper_info))
    sources = paper_sources(result)
    raw_urls = result.get("source_urls")
    raw_ids = result.get("source_ids")
    source_urls = dict(raw_urls) if isinstance(raw_urls, dict) else {}
    source_ids = dict(raw_ids) if isinstance(raw_ids, dict) else {}

    if len(sources) == 1:
        source = sources[0]
        source_urls.setdefault(source, str(result.get("paper_url") or ""))
        source_ids.setdefault(source, str(result.get("paper_id") or result.get("paper_key") or ""))

    result["source"] = "+".join(sources)
    result["sources"] = sources
    result["source_urls"] = {source: str(source_urls.get(source) or "") for source in sources}
    result["source_ids"] = {source: str(source_ids.get(source) or "") for source in sources}
    return result


def compact_source_metadata(paper_info: Dict[str, object]) -> Dict[str, object]:
    result = dict(paper_info)
    sources = paper_sources(result)
    if len(sources) == 1:
        result["source"] = sources[0]
        result.pop("sources", None)
        result.pop("source_urls", None)
        result.pop("source_ids", None)
    return result


def merge_paper_records(first: Dict[str, object], second: Dict[str, object]) -> Dict[str, object]:
    first = add_source_metadata(first)
    second = add_source_metadata(second)
    first_sources = paper_sources(first)
    second_sources = paper_sources(second)
    sources = [source for source in KNOWN_SOURCES if source in set(first_sources + second_sources)]

    # arXiv remains the canonical record when available because its identifier is stable
    # and existing archive keys already use it.
    if "arxiv" in second_sources and (
        "arxiv" not in first_sources or (len(first_sources) > 1 and second_sources == ["arxiv"])
    ):
        base, other = second, first
    else:
        base, other = first, second
    merged = dict(base)

    for field in ("paper_title", "primary_category", "comments"):
        if not merged.get(field) and other.get(field):
            merged[field] = other[field]
    if len(str(other.get("paper_abstract") or "")) > len(str(merged.get("paper_abstract") or "")):
        merged["paper_abstract"] = other.get("paper_abstract")
    if len(other.get("paper_authors") or []) > len(merged.get("paper_authors") or []):
        merged["paper_authors"] = other.get("paper_authors")

    publish_dates = [str(value) for value in (first.get("publish_time"), second.get("publish_time")) if value]
    update_dates = [str(value) for value in (first.get("update_time"), second.get("update_time")) if value]
    if publish_dates:
        merged["publish_time"] = min(publish_dates)
    if update_dates:
        merged["update_time"] = max(update_dates)

    source_urls = dict(first.get("source_urls") or {})
    source_urls.update(dict(second.get("source_urls") or {}))
    source_ids = dict(first.get("source_ids") or {})
    source_ids.update(dict(second.get("source_ids") or {}))
    merged["source"] = "+".join(sources)
    merged["sources"] = sources
    merged["source_urls"] = {source: str(source_urls.get(source) or "") for source in sources}
    merged["source_ids"] = {source: str(source_ids.get(source) or "") for source in sources}
    return merged


def merge_cross_source_duplicates(
    keyword_papers: Dict[str, Dict[str, object]],
) -> Tuple[Dict[str, Dict[str, object]], int]:
    merged_papers = {key: add_source_metadata(info) for key, info in keyword_papers.items()}
    title_groups: Dict[str, List[str]] = defaultdict(list)
    for paper_key, paper_info in merged_papers.items():
        normalized_title = normalized_paper_title(paper_info.get("paper_title"))
        if normalized_title:
            title_groups[normalized_title].append(paper_key)

    merge_count = 0
    for paper_keys in title_groups.values():
        existing_keys = [key for key in paper_keys if key in merged_papers]
        mixed_keys = [key for key in existing_keys if set(paper_sources(merged_papers[key])) == set(KNOWN_SOURCES)]
        arxiv_keys = [key for key in existing_keys if paper_sources(merged_papers[key]) == ["arxiv"]]
        preprint_keys = [key for key in existing_keys if paper_sources(merged_papers[key]) == ["preprints.org"]]

        if mixed_keys:
            canonical_key = mixed_keys[0]
            canonical = merged_papers[canonical_key]
            for duplicate_key in arxiv_keys + preprint_keys + mixed_keys[1:]:
                canonical = merge_paper_records(canonical, merged_papers.pop(duplicate_key))
                merge_count += 1
            merged_papers[canonical_key] = canonical
        elif len(arxiv_keys) == 1 and len(preprint_keys) == 1:
            canonical_key = arxiv_keys[0]
            merged_papers[canonical_key] = merge_paper_records(
                merged_papers[canonical_key], merged_papers.pop(preprint_keys[0])
            )
            merge_count += 1

    return merged_papers, merge_count


def get_env_int(name: str, default: int, minimum: int = 1) -> int:
    value = os.getenv(name)
    if value is None:
        return default

    try:
        parsed = int(value)
    except ValueError:
        print(f"Invalid {name}={value!r}; using default {default}.", file=sys.stderr)
        return default

    if parsed < minimum:
        print(f"Invalid {name}={parsed}; using minimum {minimum}.", file=sys.stderr)
        return minimum
    return parsed


def get_http_status(error: Exception) -> Optional[int]:
    status = getattr(error, "status", None) or getattr(error, "status_code", None)
    if isinstance(status, int):
        return status

    message = str(error)
    for status_code in (429, 500, 502, 503, 504):
        if f"HTTP {status_code}" in message:
            return status_code
    return None


def describe_request_error(exception: Exception) -> str:
    details = str(exception)
    if isinstance(exception, error.HTTPError):
        akamai_reference = exception.headers.get("Akamai-GRN")
        if akamai_reference:
            details = f"{details} (Akamai-GRN: {akamai_reference})"
    return details


def clean_markup(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())


def normalized_date(value: object) -> str:
    text = str(value or "").strip()
    return text[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", text) else ""


def extract_preprints_doi(*values: str) -> str:
    joined = " ".join(values)
    match = PREPRINTS_DOI_PATTERN.search(joined)
    if match:
        return match.group(0).lower()
    manuscript_match = PREPRINTS_MANUSCRIPT_PATTERN.search(joined)
    if not manuscript_match:
        return ""
    version = f".v{manuscript_match.group(2)}" if manuscript_match.group(2) else ""
    return f"10.20944/preprints{manuscript_match.group(1)}{version}".lower()


def preprints_url_from_doi(doi: str) -> str:
    match = re.match(r"10\.20944/preprints(\d{6}\.\d+)(?:\.v(\d+))?", doi, re.IGNORECASE)
    if not match:
        return f"https://doi.org/{doi}" if doi else ""
    version = f"/v{match.group(2)}" if match.group(2) else ""
    return f"https://www.preprints.org/manuscript/{match.group(1)}{version}"


def fetch_json(
    url: str,
    params: Dict[str, object],
    provider: str,
    attempts: int = 3,
    user_agent: str = "DailyArxiv/3.0 (https://github.com/lartpang/DailyArxiv)",
) -> Dict[str, object]:
    target_url = f"{url}?{parse.urlencode(params)}"
    max_response_bytes = min(get_env_int("HTTP_MAX_RESPONSE_MIB", 64), 256) * 1024 * 1024
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json",
    }
    for attempt in range(1, attempts + 1):
        try:
            with request.urlopen(request.Request(target_url, headers=headers), timeout=60) as response:
                content_length = str(response.headers.get("Content-Length") or "").strip()
                if content_length.isdigit() and int(content_length) > max_response_bytes:
                    raise ValueError(f"{provider} response exceeds HTTP_MAX_RESPONSE_MIB")
                response_body = response.read(max_response_bytes + 1)
                if len(response_body) > max_response_bytes:
                    raise ValueError(f"{provider} response exceeds HTTP_MAX_RESPONSE_MIB")
                payload = json.loads(response_body.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError(f"{provider} returned a non-object JSON response")
                return payload
        except error.HTTPError as exc:
            retryable = exc.code == 429 or 500 <= exc.code <= 599
            if not retryable or attempt == attempts:
                raise
            retry_after = exc.headers.get("Retry-After")
            wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else 10 * attempt
        except (error.URLError, OSError, http.client.HTTPException, json.JSONDecodeError, UnicodeDecodeError):
            if attempt == attempts:
                raise
            wait_seconds = 10 * attempt
        print(f"Warning: {provider} request failed; retrying in {wait_seconds} seconds.", file=sys.stderr)
        time.sleep(wait_seconds)
    raise RuntimeError(f"{provider} request failed")


def crossref_date(item: Dict[str, object], *fields: str) -> str:
    for field in fields:
        value = item.get(field)
        if not isinstance(value, dict):
            continue
        direct_date = normalized_date(value.get("date-time"))
        if direct_date:
            return direct_date
        date_parts = value.get("date-parts")
        if isinstance(date_parts, list) and date_parts and isinstance(date_parts[0], list):
            parts = date_parts[0]
            if parts:
                try:
                    year = int(parts[0])
                    month = int(parts[1]) if len(parts) > 1 else 1
                    day = int(parts[2]) if len(parts) > 2 else 1
                    return datetime.date(year, month, day).isoformat()
                except (TypeError, ValueError):
                    continue
    return ""


def parse_crossref_preprint(item: Dict[str, object]) -> Optional[PreprintsPaper]:
    doi = extract_preprints_doi(str(item.get("DOI") or ""))
    if not doi or PREPRINTS_DOI_PATTERN.fullmatch(doi) is None:
        return None
    raw_titles = item.get("title")
    titles = raw_titles if isinstance(raw_titles, list) else []
    title = clean_markup(str(titles[0])) if titles else ""
    if not title:
        return None
    raw_authors = item.get("author")
    authors = []
    if isinstance(raw_authors, list):
        for author in raw_authors:
            if not isinstance(author, dict):
                continue
            name = " ".join(
                str(author.get(part) or "").strip() for part in ("given", "family")
            ).strip()
            if name:
                authors.append(name)
    category = str(item.get("group-title") or item.get("subtype") or "Preprints.org")
    publish_time = crossref_date(item, "posted", "published", "issued", "created")
    update_time = crossref_date(item, "deposited", "indexed", "created") or publish_time
    return PreprintsPaper(
        paper_id=doi,
        title=title,
        url=preprints_url_from_doi(doi),
        abstract=clean_markup(str(item.get("abstract") or "")),
        authors=authors,
        category=category,
        publish_time=publish_time,
        update_time=update_time,
    )


def openalex_abstract(inverted_index: object) -> str:
    if not isinstance(inverted_index, dict):
        return ""
    positioned_words = []
    for word, positions in inverted_index.items():
        if not isinstance(positions, list):
            continue
        for position in positions:
            if isinstance(position, int):
                positioned_words.append((position, str(word)))
    return " ".join(word for _, word in sorted(positioned_words))


def parse_openalex_preprint(item: Dict[str, object]) -> Optional[PreprintsPaper]:
    doi = extract_preprints_doi(str(item.get("doi") or ""))
    if not doi or PREPRINTS_DOI_PATTERN.fullmatch(doi) is None:
        return None
    title = clean_markup(str(item.get("display_name") or item.get("title") or ""))
    if not title:
        return None
    raw_authorships = item.get("authorships")
    authors = []
    if isinstance(raw_authorships, list):
        for authorship in raw_authorships:
            if not isinstance(authorship, dict) or not isinstance(authorship.get("author"), dict):
                continue
            name = str(authorship["author"].get("display_name") or "").strip()
            if name:
                authors.append(name)
    primary_topic = item.get("primary_topic")
    category = (
        str(primary_topic.get("display_name") or "Preprints.org")
        if isinstance(primary_topic, dict)
        else "Preprints.org"
    )
    publish_time = normalized_date(item.get("publication_date"))
    update_time = normalized_date(item.get("updated_date")) or publish_time
    return PreprintsPaper(
        paper_id=doi,
        title=title,
        url=preprints_url_from_doi(doi),
        abstract=openalex_abstract(item.get("abstract_inverted_index")),
        authors=authors,
        category=category,
        publish_time=publish_time,
        update_time=update_time,
    )


def preprint_version(paper: PreprintsPaper) -> int:
    version_match = re.search(r"\.v(\d+)$", paper.paper_id, re.IGNORECASE)
    return int(version_match.group(1)) if version_match else 0


def merge_preprint_provider_records(
    first: PreprintsPaper,
    second: PreprintsPaper,
) -> PreprintsPaper:
    first_rank = (preprint_version(first), first.update_time)
    second_rank = (preprint_version(second), second.update_time)
    base, other = (second, first) if second_rank > first_rank else (first, second)
    publish_dates = [date for date in (first.publish_time, second.publish_time) if date]
    update_dates = [date for date in (first.update_time, second.update_time) if date]
    category = base.primary_category
    if category == "Preprints.org" and other.primary_category != "Preprints.org":
        category = other.primary_category
    return PreprintsPaper(
        paper_id=base.paper_id,
        title=base.paper_title or other.paper_title,
        url=base.paper_url or other.paper_url,
        abstract=max((first.paper_abstract, second.paper_abstract), key=len),
        authors=max((first.paper_authors, second.paper_authors), key=len),
        category=category,
        publish_time=min(publish_dates, default=""),
        update_time=max(update_dates, default=""),
    )


def deduplicate_preprint_versions(
    papers: Dict[str, List[PreprintsPaper]],
) -> Dict[str, List[PreprintsPaper]]:
    deduplicated: Dict[str, List[PreprintsPaper]] = {}
    for topic, topic_papers in papers.items():
        latest: Dict[str, PreprintsPaper] = {}
        for paper in topic_papers:
            current = latest.get(paper.paper_key)
            latest[paper.paper_key] = (
                merge_preprint_provider_records(current, paper) if current else paper
            )
        deduplicated[topic] = list(latest.values())
    return deduplicated


def matches_preprint_topics(title: str, abstract: str) -> List[str]:
    title_text = " ".join(title.lower().split())
    all_text = f"{title_text} {' '.join(abstract.lower().split())}"

    def title_has(*terms: str) -> bool:
        return any(term in title_text for term in terms)

    def text_has(*terms: str) -> bool:
        return any(term in all_text for term in terms)

    matches = []
    if title_has("benchmark", "dataset", "data set") or text_has(
        "benchmark dataset", "new dataset", "large-scale dataset"
    ):
        matches.append("Dataset")
    if title_has("evaluation", "benchmarking") or text_has(
        "evaluation protocol", "evaluation benchmark", "benchmarking"
    ):
        matches.append("Evaluation")
    if title_has("rethinking"):
        matches.append("Rethinking")
    if title_has("survey", "review"):
        matches.append("Survey")
    feature_phrases = (
        "feature coding",
        "feature compression",
        "deep feature compression",
        "intermediate feature compression",
        "feature map compression",
        "feature tensor compression",
        "semantic feature coding",
        "feature codec",
    )
    feature_in_title = any(term in title_text for term in feature_phrases)
    feature_in_abstract = any(term in abstract.lower() for term in feature_phrases)
    representation_only = "representation learning" in title_text and not feature_in_title
    coding_context = text_has(
        "rate-distortion",
        "bitrate",
        "bitstream",
        "bandwidth",
        "transmission",
        "transmitted",
        "communication",
        "quantiz",
        "codec",
        "encoder",
        "decoder",
        "encode",
        "decode",
        "symbol stream",
        "bottleneck",
        "data volume",
        "memory-constrained",
        "compression module",
        "compresses",
        "compressed feature",
        "compression ratio",
    )
    if not representation_only and (feature_in_title or (feature_in_abstract and coding_context)):
        matches.append("Feature Coding")
    if text_has("gaussian splatting", "gaussian splat") or re.search(r"\b3dgs\b", all_text):
        matches.append("Gaussian Splatting")
    if text_has("spiking neural network", "spiking neural networks", "spiking neuron") or (
        re.search(r"\bsnn\b", all_text) and "spiking" in all_text
    ):
        matches.append("Spiking Network")
    if text_has("recurrent neural network", "recurrent network", "recursive neural network") or re.search(
        r"\brnn\b", all_text
    ):
        matches.append("Recurrent Network")
    if text_has("salient object detection", "video salient object detection", "saliency detection"):
        matches.append("Salient Object Detection")
    if text_has("camouflaged object detection", "video camouflaged object detection"):
        matches.append("Camouflaged Object Detection")
    if text_has("change detection", "semantic change detection") and text_has(
        "remote sensing", "image", "video", "segmentation"
    ):
        matches.append("Change Detection")
    if text_has("infrared small target detection", "infrared small target") or re.search(r"\birstd\b", all_text):
        matches.append("Infrared Small Target Detection")
    return matches


def paper_archive_date(paper_info: Dict[str, object]) -> str:
    if "preprints.org" in paper_sources(paper_info):
        return str(paper_info.get("publish_time") or paper_info.get("update_time") or "")
    return max(str(paper_info.get("publish_time", "")), str(paper_info.get("update_time", "")))


def paper_is_retained(
    topic: str,
    paper_info: Dict[str, object],
    arxiv_cutoff: str,
    preprint_cutoff: Optional[str] = None,
) -> bool:
    cutoff = preprint_cutoff if preprint_cutoff and "preprints.org" in paper_sources(paper_info) else arxiv_cutoff
    if paper_archive_date(paper_info) < cutoff:
        return False
    if topic in LOCALLY_FILTERED_TOPICS:
        return topic in matches_preprint_topics(
            str(paper_info.get("paper_title", "")), str(paper_info.get("paper_abstract", ""))
        )
    if "preprints.org" not in paper_sources(paper_info):
        return True
    return topic in matches_preprint_topics(
        str(paper_info.get("paper_title", "")), str(paper_info.get("paper_abstract", ""))
    )


def load_sharded_archive(data_dir: str) -> Dict[str, Dict[str, Dict[str, object]]]:
    manifest_path = os.path.join(data_dir, "topics.json")
    if not os.path.exists(manifest_path):
        return {}
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("topics"), list):
        raise ValueError("Invalid data/topics.json manifest")

    archive = {}
    for topic_info in manifest["topics"]:
        if not isinstance(topic_info, dict):
            raise ValueError("Invalid topic entry in data/topics.json")
        topic = topic_info.get("name")
        chunks = topic_info.get("chunks")
        count = topic_info.get("count")
        if not isinstance(topic, str) or not isinstance(chunks, list) or not isinstance(count, int):
            raise ValueError("Invalid topic metadata in data/topics.json")
        topic_data = {}
        for filename in chunks:
            if not isinstance(filename, str):
                raise ValueError(f"Invalid chunk path for topic {topic}")
            chunk_name = os.path.basename(filename.replace("/", os.sep))
            legacy_name = f"{os.path.basename(os.path.normpath(data_dir))}/{chunk_name}"
            if filename.replace("\\", "/") not in {chunk_name, legacy_name}:
                raise ValueError(f"Invalid chunk path for topic {topic}")
            chunk_path = os.path.join(data_dir, chunk_name)
            with open(chunk_path, "r", encoding="utf-8") as f:
                entries = json.load(f)
            if not isinstance(entries, list):
                raise ValueError(f"Invalid chunk data for topic {topic}")
            for entry in entries:
                if (
                    not isinstance(entry, list)
                    or len(entry) != 2
                    or not isinstance(entry[0], str)
                    or not isinstance(entry[1], dict)
                    or entry[0] in topic_data
                ):
                    raise ValueError(f"Invalid or duplicate paper entry for topic {topic}")
                topic_data[entry[0]] = entry[1]
        if len(topic_data) != count:
            raise ValueError(f"Topic count mismatch for {topic}: expected {count}, loaded {len(topic_data)}")
        archive[topic] = topic_data
    return archive


def write_sharded_archive(
    data_dir: str,
    archive: Dict[str, Dict[str, Dict[str, object]]],
    max_size_mib: int,
) -> float:
    os.makedirs(data_dir, exist_ok=True)
    topics = []
    expected_shards = set()
    pending_files = []
    chunk_size = 225
    try:
        for topic, topic_data in archive.items():
            topic_hash = hashlib.sha256(topic.encode("utf-8")).hexdigest()[:16]
            sorted_papers = sorted(
                topic_data.items(),
                key=lambda item: (
                    str(item[1].get("publish_time") or ""),
                    str(item[1].get("update_time") or ""),
                ),
                reverse=True,
            )
            chunks = []
            for chunk_index, start in enumerate(range(0, len(sorted_papers), chunk_size)):
                filename = f"topic-{topic_hash}-{chunk_index:03d}.json"
                expected_shards.add(filename)
                shard_path = os.path.join(data_dir, filename)
                shard_temp_path = f"{shard_path}.tmp"
                with open(shard_temp_path, "w", encoding="utf-8") as f:
                    json.dump(
                        sorted_papers[start : start + chunk_size],
                        f,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                pending_files.append((shard_temp_path, shard_path))
                chunks.append(filename)
            topics.append({"name": topic, "count": len(topic_data), "chunkSize": chunk_size, "chunks": chunks})

        manifest_path = os.path.join(data_dir, "topics.json")
        manifest_temp_path = f"{manifest_path}.tmp"
        with open(manifest_temp_path, "w", encoding="utf-8") as f:
            json.dump({"topics": topics}, f, ensure_ascii=False, separators=(",", ":"))
        pending_files.append((manifest_temp_path, manifest_path))

        size_bytes = sum(os.path.getsize(temp_path) for temp_path, _ in pending_files)
        size_mib = size_bytes / (1024 * 1024)
        if size_mib > max_size_mib:
            raise RuntimeError(
                f"Generated data is {size_mib:.1f} MiB, above JSON_MAX_SIZE_MIB={max_size_mib}. "
                "Reduce PAPER_RETENTION_DAYS or PREPRINT_RETENTION_DAYS before GitHub's file limits are reached."
            )

        for temp_path, final_path in pending_files:
            os.replace(temp_path, final_path)
        for filename in os.listdir(data_dir):
            if filename.startswith("topic-") and filename.endswith(".json") and filename not in expected_shards:
                os.remove(os.path.join(data_dir, filename))
        return size_mib
    except Exception:
        for temp_path, _ in pending_files:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        raise


def update_sharded_archive(
    data_dir: str,
    papers: Dict[str, List[Paper]],
    retention_days: Optional[int] = None,
    preprint_retention_days: Optional[int] = None,
    max_size_mib: Optional[int] = None,
) -> None:
    json_data = load_sharded_archive(data_dir)

    # update papers in each keywords
    for keyword, paper_items in papers.items():
        if keyword not in json_data:
            json_data[keyword] = {}

        for paper_item in paper_items:
            incoming = add_source_metadata(paper_item.to_dict())
            existing = json_data[keyword].get(paper_item.paper_key)
            if existing and len(paper_sources(existing)) > 1:
                json_data[keyword][paper_item.paper_key] = merge_paper_records(existing, incoming)
            else:
                json_data[keyword][paper_item.paper_key] = incoming

    retention_days = retention_days or get_env_int("PAPER_RETENTION_DAYS", 180)
    preprint_retention_days = preprint_retention_days or get_env_int("PREPRINT_RETENTION_DAYS", 1826)
    max_size_mib = max_size_mib or get_env_int("JSON_MAX_SIZE_MIB", 75)
    utc_today = datetime.datetime.now(datetime.timezone.utc).date()
    arxiv_cutoff = (utc_today - datetime.timedelta(days=retention_days)).isoformat()
    preprint_cutoff = (utc_today - datetime.timedelta(days=preprint_retention_days)).isoformat()
    retained_data = {}
    merged_duplicates = 0
    for keyword, keyword_papers in json_data.items():
        retained_papers = {
            paper_key: add_source_metadata(paper_info)
            for paper_key, paper_info in keyword_papers.items()
            if paper_is_retained(keyword, paper_info, arxiv_cutoff, preprint_cutoff)
        }
        merged_papers, topic_merges = merge_cross_source_duplicates(retained_papers)
        retained_data[keyword] = {
            paper_key: compact_source_metadata(paper_info) for paper_key, paper_info in merged_papers.items()
        }
        merged_duplicates += topic_merges
    json_data = retained_data

    size_mib = write_sharded_archive(data_dir, json_data, max_size_mib)
    print(
        f"Sharded archive retains {retention_days} days of arXiv and "
        f"{preprint_retention_days} days of Preprints.org data ({size_mib:.1f} MiB)."
    )
    if merged_duplicates:
        print(f"Merged {merged_duplicates} cross-source duplicate record(s) by normalized title.")


def json_to_html(
    data_dir: str,
    html_path: str = "index.html",
    title: str = "Daily ArXiv Papers",
):
    current_date = str(datetime.date.today()).replace("-", ".")

    manifest_path = os.path.join(data_dir, "topics.json")
    assert os.path.exists(manifest_path), f"{manifest_path} does not exist"
    html_dir = os.path.dirname(html_path) or "."
    data_index_url = os.path.relpath(manifest_path, start=html_dir).replace(os.sep, "/")

    html_template = Template("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="referrer" content="no-referrer">
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; font-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'">
    <title>$title</title>
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
            --arxiv: #b31b1b;
            --arxiv-strong: #8f1515;
            --preprints: #eab308;
            --preprints-strong: #a16207;
            --radius: 6px;
            --font-sans: "Inter", "Source Sans 3", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            --font-serif: "Iowan Old Style", "Charter", "Palatino Linotype", Georgia, "Times New Roman", serif;
            --font-mono: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
        }
        * {
            box-sizing: border-box;
        }
        html {
            -webkit-text-size-adjust: 100%;
        }
        body {
            background:
                linear-gradient(180deg, #fbfbfc 0, var(--surface) 240px),
                var(--surface);
            color: var(--ink);
            font-family: var(--font-sans);
            font-size: 0.9rem;
            line-height: 1.42;
            margin: 0;
        }
        .container {
            margin-left: auto;
            margin-right: auto;
            max-width: 1180px;
            padding-left: 0.75rem;
            padding-right: 0.75rem;
            width: 100%;
        }
        .sticky-top {
            position: sticky;
            top: 0;
            z-index: 10;
        }
        .navbar {
            background: rgba(255, 255, 255, 0.95) !important;
            border-bottom: 1px solid var(--line);
            padding: 0.42rem 0;
            backdrop-filter: blur(10px);
        }
        .navbar .container {
            align-items: center;
            display: flex;
            justify-content: space-between;
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
            padding-bottom: 1rem;
            padding-top: 1rem;
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
            border: 1px solid var(--line);
            border-radius: 4px;
            color: var(--ink);
            display: block;
            font-family: inherit;
            font-size: 0.82rem;
            line-height: 1.5;
            min-height: 2rem;
            padding: 0.28rem 0.5rem;
            width: 100%;
        }
        .toolbar-wrap .form-select {
            cursor: pointer;
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
            display: grid;
            gap: 0.42rem;
            min-height: 44vh;
            overflow: hidden;
            padding: 0.42rem;
        }
        .paper-card {
            --card-fill: var(--paper);
            --source-border: linear-gradient(var(--line), var(--line));
            background: linear-gradient(var(--card-fill), var(--card-fill)) padding-box,
                        var(--source-border) border-box;
            border: 2px solid transparent;
            border-radius: 4px;
            display: grid;
            gap: 0.9rem;
            grid-template-columns: minmax(7.2rem, 9rem) minmax(0, 1fr);
            margin: 0;
            padding: 0.72rem 0.82rem;
            transition: background-color 0.12s;
        }
        .paper-card.source-arxiv {
            --source-border: linear-gradient(var(--arxiv), var(--arxiv));
        }
        .paper-card.source-preprints {
            --source-border: linear-gradient(var(--preprints), var(--preprints));
        }
        .paper-card.source-mixed {
            --source-border: linear-gradient(90deg, var(--arxiv) 0 50%, var(--preprints) 50% 100%);
        }
        .paper-card:hover {
            --card-fill: #fbfcff;
        }
        .paper-source-panel {
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
        .source-row {
            align-items: center;
            display: flex;
            flex-wrap: wrap;
            gap: 0.28rem;
        }
        .source-id {
            color: var(--ink);
            font-weight: 700;
        }
        .source-link {
            border-radius: 3px;
            display: inline-block;
            font-weight: 700;
            padding: 0.06rem 0.32rem;
            text-decoration: none;
        }
        .source-link-arxiv {
            background: var(--arxiv);
            color: #fff;
        }
        .source-link-arxiv:hover {
            background: var(--arxiv-strong);
            color: #fff;
        }
        .source-link-preprints {
            background: var(--preprints);
            color: #111;
        }
        .source-link-preprints:hover {
            background: #facc15;
            color: #111;
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
            align-items: center;
            display: flex;
            flex-wrap: wrap;
            gap: 0.28rem;
            justify-content: center;
            margin-top: 1rem;
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
            .paper-source-panel {
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
            <a class="navbar-brand" href="#"><span class="brand-mark">Feeds</span><span>$title</span></a>
            <span class="navbar-text">Updated $current_date</span>
        </div>
    </nav>

    <main class="container page-shell">
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
        <div id="pagination" class="pagination-bar"></div>
    </main>

    <script>
        const DATA_INDEX_URL = "$data_index_url";
        const PAGE_SIZE = 45;

        const state = {
            topics: [],
            topicsByName: {},
            papersByTopic: {},
            chunkCache: {},
            chunkPromises: {},
            currentTopic: "",
            currentPage: 1,
            query: "",
            loadRequest: 0,
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

        function safeSourceUrl(value, source) {
            try {
                const url = new URL(value, window.location.href);
                const allowedHosts = source === "preprints.org"
                    ? ["preprints.org", "www.preprints.org", "doi.org"]
                    : ["arxiv.org", "www.arxiv.org", "export.arxiv.org"];
                if (!["http:", "https:"].includes(url.protocol) || !allowedHosts.includes(url.hostname)) {
                    return "#";
                }
                url.protocol = "https:";
                return url.href;
            } catch {
                return "#";
            }
        }

        function normalizePaper(paperKey, paperInfo) {
            const authors = Array.isArray(paperInfo.paper_authors) ? paperInfo.paper_authors : [];
            const rawSources = Array.isArray(paperInfo.sources)
                ? paperInfo.sources
                : String(paperInfo.source || "arxiv").split("+");
            const sources = ["arxiv", "preprints.org"].filter((source) => rawSources.includes(source));
            if (!sources.length) sources.push("arxiv");
            const sourceUrls = Object.assign({}, paperInfo.source_urls || {});
            const sourceIds = Object.assign({}, paperInfo.source_ids || {});
            if (sources.length === 1) {
                sourceUrls[sources[0]] ||= paperInfo.paper_url || "";
                sourceIds[sources[0]] ||= paperInfo.paper_id || paperKey;
            }
            const paper = {
                key: paperKey,
                title: paperInfo.paper_title || "",
                abstract: paperInfo.paper_abstract || "",
                authors,
                category: paperInfo.primary_category || "",
                publishTime: paperInfo.publish_time || "",
                updateTime: paperInfo.update_time || "",
                comments: paperInfo.comments || "",
                sources,
                sourceUrls,
                sourceIds,
            };
            paper.searchText = [
                paper.title,
                paper.abstract,
                paper.category,
                paper.publishTime,
                paper.updateTime,
                paper.comments,
                authors.join(" "),
                Object.values(sourceIds).join(" "),
                sources.join(" "),
            ].join(" ").toLowerCase();
            return paper;
        }

        async function loadChunk(topic, chunkIndex) {
            const topicInfo = state.topicsByName[topic];
            if (!topicInfo) throw new Error("Unknown topic: " + topic);
            const cacheKey = JSON.stringify([topic, chunkIndex]);
            if (state.chunkCache[cacheKey]) return state.chunkCache[cacheKey];
            if (state.chunkPromises[cacheKey]) return state.chunkPromises[cacheKey];
            const promise = (async () => {
                const manifestUrl = new URL(DATA_INDEX_URL, window.location.href);
                const chunkUrl = new URL(topicInfo.chunks[chunkIndex], manifestUrl).href;
                if (!chunkUrl) return [];
                const res = await fetch(chunkUrl, { cache: "no-cache" });
                if (!res.ok) throw new Error(res.status + " " + res.statusText);
                const entries = await res.json();
                if (!Array.isArray(entries)) throw new Error("Invalid topic data");
                const papers = entries.map(([paperKey, paperInfo]) => normalizePaper(paperKey, paperInfo));
                state.chunkCache[cacheKey] = papers;
                return papers;
            })();
            state.chunkPromises[cacheKey] = promise;
            try {
                return await promise;
            } finally {
                delete state.chunkPromises[cacheKey];
            }
        }

        async function loadTopic(topic) {
            if (state.papersByTopic[topic]) return state.papersByTopic[topic];
            const topicInfo = state.topicsByName[topic];
            if (!topicInfo) throw new Error("Unknown topic: " + topic);
            const chunks = await Promise.all(topicInfo.chunks.map((_, index) => loadChunk(topic, index)));
            state.papersByTopic[topic] = chunks.flat();
            return state.papersByTopic[topic];
        }

        function renderTopicSelect() {
            elements.topicSelect.innerHTML = state.topics.map((topicInfo) => {
                return '<option value="' + escapeHtml(topicInfo.name) + '">' + escapeHtml(topicInfo.name) + ' (' + topicInfo.count + ')</option>';
            }).join("");
        }

        async function setTopic(topic) {
            state.currentTopic = topic;
            state.currentPage = 1;
            elements.topicSelect.value = topic;
            window.scrollTo(0, 0);
            await refresh();
        }

        async function refresh() {
            const request = ++state.loadRequest;
            const topic = state.currentTopic;
            const topicInfo = state.topicsByName[topic];
            if (!topicInfo) return;
            elements.loading.style.display = "flex";
            elements.paperList.innerHTML = "";
            elements.pagination.innerHTML = "";
            elements.resultInfo.textContent = "";
            try {
                const term = state.query.trim().toLowerCase();
                let filteredPapers = [];
                let total = topicInfo.count;
                if (term) {
                    const papers = await loadTopic(topic);
                    filteredPapers = papers.filter((paper) => paper.searchText.includes(term));
                    total = filteredPapers.length;
                }

                const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
                state.currentPage = Math.min(Math.max(state.currentPage, 1), totalPages);
                const start = (state.currentPage - 1) * PAGE_SIZE;
                let currentPapers = filteredPapers.slice(start, start + PAGE_SIZE);
                if (!term && total) {
                    const chunkIndex = Math.floor(start / topicInfo.chunkSize);
                    const chunk = await loadChunk(topic, chunkIndex);
                    const chunkOffset = start - chunkIndex * topicInfo.chunkSize;
                    currentPapers = chunk.slice(chunkOffset, chunkOffset + PAGE_SIZE);
                }
                if (request !== state.loadRequest) return;
                render(currentPapers, total, start);
            } catch (error) {
                if (request !== state.loadRequest) return;
                elements.paperList.innerHTML = '<div class="empty-state"><p>Failed to load this topic.</p><p style="color:var(--muted);font-size:0.8rem;margin-top:0.5rem">' + escapeHtml(error.message) + '</p></div>';
                elements.pagination.innerHTML = "";
                elements.resultInfo.textContent = "";
            } finally {
                if (request === state.loadRequest) {
                    elements.loading.style.display = "none";
                }
            }
        }

        function renderPaper(paper) {
            const authorText = paper.authors.join(", ");
            const authorsHtml = authorText ? '<p class="paper-authors">' + escapeHtml(authorText) + '</p>' : "";
            const commentsHtml = paper.comments ? '<p class="paper-comments">' + escapeHtml(paper.comments) + '</p>' : "";
            const categoryHtml = paper.category ? '<span class="badge-cat">' + escapeHtml(paper.category) + '</span>' : "";
            const dateHtml = paper.publishTime ? '<span class="badge-date">' + escapeHtml(paper.publishTime) + '</span>' : "";
            const sourceClass = paper.sources.length > 1
                ? "source-mixed"
                : (paper.sources[0] === "preprints.org" ? "source-preprints" : "source-arxiv");
            const sourceRows = paper.sources.map((source) => {
                const isPreprints = source === "preprints.org";
                const label = isPreprints ? "Preprints.org" : "arXiv";
                const linkClass = isPreprints ? "source-link-preprints" : "source-link-arxiv";
                return '<div class="source-row">'
                    + '<span class="source-id">' + escapeHtml(paper.sourceIds[source] || label) + '</span>'
                    + '<a href="' + escapeHtml(safeSourceUrl(paper.sourceUrls[source], source)) + '" class="source-link ' + linkClass + '" target="_blank" rel="noopener noreferrer">' + label + '</a>'
                    + '</div>';
            }).join("");

            return '<article class="paper-card ' + sourceClass + '">'
                + '<div class="paper-source-panel">'
                + dateHtml
                + sourceRows
                + categoryHtml
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

        function render(currentPapers, total, start) {
            const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
            const end = Math.min(start + PAGE_SIZE, total);
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
            elements.loading.outerHTML = '<div class="empty-state"><p>Failed to load papers. Serve this page through a local web server (e.g., <code>python -m http.server</code>).</p><p style="color:var(--muted);font-size:0.8rem;margin-top:0.5rem">' + escapeHtml(error.message) + '</p></div>';
        }

        async function init() {
            try {
                const res = await fetch(DATA_INDEX_URL, { cache: "no-cache" });
                if (!res.ok) throw new Error(res.status + " " + res.statusText);
                const manifest = await res.json();
                state.topics = Array.isArray(manifest.topics) ? manifest.topics : [];
                state.topicsByName = Object.fromEntries(state.topics.map((topicInfo) => [topicInfo.name, topicInfo]));
                renderTopicSelect();
                if (state.topics.length) {
                    await setTopic(state.topics[0].name);
                } else {
                    elements.loading.style.display = "none";
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
                void refresh();
            }, 120);
        });

        elements.topicSelect.addEventListener("change", (e) => void setTopic(e.target.value));

        elements.pagination.addEventListener("click", (e) => {
            const btn = e.target.closest("button[data-page]");
            if (!btn || btn.disabled) return;
            state.currentPage = Number(btn.dataset.page);
            void refresh();
            window.scrollTo(0, 0);
        });

        init();
    </script>
</body>
</html>""")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_template.substitute(title=title, current_date=current_date, data_index_url=data_index_url))
    print(f"HTML file generated at {html_path}")


def get_papers(
    keywords: Dict[str, str], max_results_per_keyword: int = 100
) -> Tuple[Dict[str, List[ArXivPaper]], Set[str]]:
    import arxiv
    import requests

    page_size = get_env_int("ARXIV_PAGE_SIZE", 100)
    delay_seconds = get_env_int("ARXIV_DELAY_SECONDS", 4, minimum=3)
    client_retries = get_env_int("ARXIV_CLIENT_RETRIES", 1, minimum=0)
    keyword_retries = get_env_int("ARXIV_KEYWORD_RETRIES", 2)
    backoff_seconds = get_env_int("ARXIV_BACKOFF_SECONDS", 30)
    max_backoff_seconds = get_env_int("ARXIV_MAX_BACKOFF_SECONDS", 120)

    # GitHub-hosted runners often hit arXiv API 429/503 responses. Keep requests slow and
    # retry per keyword so one transient outage does not discard the existing archive.
    client = arxiv.Client(page_size=page_size, delay_seconds=delay_seconds, num_retries=client_retries)

    papers: Dict[str, List[ArXivPaper]] = {}
    succeeded: Set[str] = set()
    for keyword, query in keywords.items():
        print(f"Keyword: {keyword}")
        search = arxiv.Search(
            query=query,
            max_results=max_results_per_keyword,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )

        keyword_specific_papers = []
        results = []
        for attempt in range(1, keyword_retries + 1):
            try:
                results = list(client.results(search))
                succeeded.add(keyword)
                break
            except (arxiv.ArxivError, requests.RequestException) as error:
                status = get_http_status(error)
                retryable = isinstance(error, requests.RequestException) or status in {429, 500, 502, 503, 504}
                if not retryable:
                    raise

                reason = f"HTTP {status}" if status else error.__class__.__name__

                if attempt == keyword_retries:
                    print(
                        f"Warning: skipped keyword {keyword!r} after {attempt} attempts because arXiv returned "
                        f"{reason}. Existing JSON entries for this keyword will be preserved.",
                        file=sys.stderr,
                    )
                    break

                wait_seconds = min(max_backoff_seconds, backoff_seconds * (2 ** (attempt - 1)))
                print(
                    f"Warning: arXiv returned {reason} for keyword {keyword!r}; retrying in "
                    f"{wait_seconds} seconds ({attempt}/{keyword_retries}).",
                    file=sys.stderr,
                )
                time.sleep(wait_seconds)

        for result in results:
            paper = ArXivPaper(result)
            if keyword in LOCALLY_FILTERED_TOPICS and keyword not in matches_preprint_topics(
                paper.paper_title, paper.paper_abstract
            ):
                continue
            keyword_specific_papers.append(paper)
        if keyword in succeeded:
            print(f"arXiv {keyword}: fetched {len(keyword_specific_papers)} records.")
        papers[keyword] = keyword_specific_papers
    return papers, succeeded


def get_crossref_preprints(
    since_date: datetime.date,
    until_date: datetime.date,
    historical: bool = False,
) -> Tuple[List[PreprintsPaper], bool]:
    papers: List[PreprintsPaper] = []
    rows = get_env_int("CROSSREF_ROWS", 1000)
    rows = min(rows, 1000)
    max_pages = get_env_int("PREPRINTS_METADATA_MAX_PAGES", 5000)
    delay_seconds = get_env_int("PREPRINTS_METADATA_DELAY_SECONDS", 1, minimum=0)
    date_filter = "created" if historical else "update"
    cursor = "*"
    scanned_items = 0
    total_results: Optional[int] = None
    contact = os.getenv("CROSSREF_MAILTO", "").strip()
    if contact and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", contact) is None:
        print("Warning: CROSSREF_MAILTO is not a valid email address; ignoring it.", file=sys.stderr)
        contact = ""
    user_agent = "DailyArxiv/3.0 (https://github.com/lartpang/DailyArxiv)"
    if contact:
        user_agent = f"{user_agent}; mailto:{contact}"
    try:
        for page in range(1, max_pages + 1):
            filters = [
                "type:posted-content",
                f"from-{date_filter}-date:{since_date.isoformat()}",
                f"until-{date_filter}-date:{until_date.isoformat()}",
            ]
            params: Dict[str, object] = {
                "filter": ",".join(filters),
                "rows": rows,
                "cursor": cursor,
            }
            if contact:
                params["mailto"] = contact
            payload = fetch_json(
                PREPRINTS_CROSSREF_URL,
                params,
                "Crossref",
                attempts=1,
                user_agent=user_agent,
            )
            message = payload.get("message")
            if not isinstance(message, dict):
                raise ValueError("Crossref response has no message object")
            raw_items = message.get("items")
            items = raw_items if isinstance(raw_items, list) else []
            scanned_items += len(items)
            if total_results is None:
                raw_total = message.get("total-results")
                total_results = int(raw_total) if isinstance(raw_total, int) else None
            for item in items:
                if isinstance(item, dict):
                    paper = parse_crossref_preprint(item)
                    if paper is not None:
                        papers.append(paper)
            if page % 25 == 0:
                print(
                    f"Crossref: scanned {page} pages; retained "
                    f"{len(papers)} Preprints.org records...",
                    flush=True,
                )
            next_cursor = str(message.get("next-cursor") or "")
            reached_total = total_results is not None and scanned_items >= total_results
            if len(items) < rows or reached_total or not next_cursor:
                print(f"Crossref: retained {len(papers)} Preprints.org records from {page} page(s).")
                return papers, True
            cursor = next_cursor
            if delay_seconds:
                time.sleep(delay_seconds)
        raise RuntimeError(f"Crossref results exceeded PREPRINTS_METADATA_MAX_PAGES={max_pages}")
    except (error.HTTPError, error.URLError, OSError, http.client.HTTPException, RuntimeError, ValueError) as exc:
        print(
            f"Warning: Crossref Preprints.org sync failed: {describe_request_error(exc)}",
            file=sys.stderr,
        )
        return [], False


def get_openalex_preprints(
    since_date: datetime.date,
    until_date: datetime.date,
    api_key: Optional[str] = None,
) -> Tuple[List[PreprintsPaper], Optional[bool]]:
    api_key = (api_key if api_key is not None else os.getenv("OPENALEX_API_KEY", "")).strip()
    if not api_key:
        print("OpenAlex: skipped because OPENALEX_API_KEY is not configured.")
        return [], None

    papers: List[PreprintsPaper] = []
    max_pages = get_env_int("PREPRINTS_METADATA_MAX_PAGES", 5000)
    delay_seconds = get_env_int("PREPRINTS_METADATA_DELAY_SECONDS", 1, minimum=0)
    cursor = "*"
    try:
        for page in range(1, max_pages + 1):
            params: Dict[str, object] = {
                "api_key": api_key,
                "filter": ",".join(
                    (
                        "doi_starts_with:10.20944/preprints",
                        f"from_created_date:{since_date.isoformat()}",
                        f"to_created_date:{until_date.isoformat()}",
                    )
                ),
                "per-page": 100,
                "cursor": cursor,
                "select": (
                    "doi,display_name,abstract_inverted_index,authorships,publication_date,"
                    "updated_date,primary_topic"
                ),
            }
            payload = fetch_json(PREPRINTS_OPENALEX_URL, params, "OpenAlex")
            raw_results = payload.get("results")
            results = raw_results if isinstance(raw_results, list) else []
            for item in results:
                if isinstance(item, dict):
                    paper = parse_openalex_preprint(item)
                    if paper is not None:
                        papers.append(paper)
            meta = payload.get("meta")
            next_cursor = str(meta.get("next_cursor") or "") if isinstance(meta, dict) else ""
            if len(results) < 100 or not next_cursor or next_cursor == cursor:
                print(f"OpenAlex: retained {len(papers)} Preprints.org records from {page} page(s).")
                return papers, True
            cursor = next_cursor
            if delay_seconds:
                time.sleep(delay_seconds)
        raise RuntimeError(f"OpenAlex results exceeded PREPRINTS_METADATA_MAX_PAGES={max_pages}")
    except (error.HTTPError, error.URLError, OSError, http.client.HTTPException, RuntimeError, ValueError) as exc:
        print(
            f"Warning: OpenAlex Preprints.org sync failed: {describe_request_error(exc)}",
            file=sys.stderr,
        )
        return [], False


def get_preprints_metadata(
    since_date: datetime.date,
    until_date: datetime.date,
    historical: bool = False,
    openalex_api_key: Optional[str] = None,
) -> Tuple[Dict[str, List[PreprintsPaper]], bool]:
    windows = [(since_date, until_date)]
    if historical:
        windows = []
        window_start = since_date
        while window_start <= until_date:
            window_end = min(window_start + datetime.timedelta(days=365), until_date)
            windows.append((window_start, window_end))
            window_start = window_end + datetime.timedelta(days=1)

    crossref_papers: List[PreprintsPaper] = []
    crossref_succeeded = True
    window_retries = get_env_int("PREPRINTS_WINDOW_RETRIES", 3)
    window_backoff_seconds = get_env_int("PREPRINTS_WINDOW_BACKOFF_SECONDS", 15)
    for window_index, (window_start, window_end) in enumerate(windows, start=1):
        if historical:
            print(
                f"Crossref history window {window_index}/{len(windows)}: "
                f"{window_start} to {window_end}"
            )
        window_papers: List[PreprintsPaper] = []
        window_succeeded = False
        for window_attempt in range(1, window_retries + 1):
            window_papers, window_succeeded = get_crossref_preprints(
                window_start, window_end, historical=historical
            )
            if window_succeeded:
                break
            if window_attempt < window_retries:
                wait_seconds = window_backoff_seconds * window_attempt
                print(
                    f"Crossref window {window_index}/{len(windows)} failed; restarting it in "
                    f"{wait_seconds} seconds ({window_attempt}/{window_retries}).",
                    file=sys.stderr,
                )
                time.sleep(wait_seconds)
        if not window_succeeded:
            crossref_papers = []
            crossref_succeeded = False
            break
        crossref_papers.extend(window_papers)

    openalex_papers: List[PreprintsPaper] = []
    openalex_succeeded: Optional[bool] = True
    for window_index, (window_start, window_end) in enumerate(windows, start=1):
        if historical and openalex_api_key:
            print(
                f"OpenAlex history window {window_index}/{len(windows)}: "
                f"{window_start} to {window_end}"
            )
        window_papers, window_succeeded = get_openalex_preprints(
            window_start, window_end, api_key=openalex_api_key
        )
        if window_succeeded is None:
            openalex_succeeded = None
            break
        if not window_succeeded:
            openalex_papers = []
            openalex_succeeded = False
            break
        openalex_papers.extend(window_papers)

    if not crossref_succeeded and openalex_succeeded is not True:
        return {}, False

    all_papers = crossref_papers + openalex_papers
    unique_papers = deduplicate_preprint_versions({"all": all_papers}).get("all", [])
    routed: Dict[str, List[PreprintsPaper]] = defaultdict(list)
    for paper in unique_papers:
        for topic in matches_preprint_topics(paper.paper_title, paper.paper_abstract):
            routed[topic].append(paper)
    deduplicated = deduplicate_preprint_versions(dict(routed))
    print(
        f"Preprints.org metadata: merged {len(all_papers)} provider records into "
        f"{len(unique_papers)} papers; {sum(map(len, deduplicated.values()))} topic matches."
    )
    return deduplicated, True


def load_state(path: str) -> Dict[str, object]:
    if not os.path.exists(path):
        return {"arxiv": {}, "preprints": ""}
    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)
    return state if isinstance(state, dict) else {"arxiv": {}, "preprints": ""}


def save_state(path: str, state: Dict[str, object]) -> None:
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(temp_path, path)


def succeeded_today(value: object, today: datetime.date) -> bool:
    return isinstance(value, str) and value[:10] == today.isoformat()


def merge_papers(target: Dict[str, List[Paper]], incoming: Dict[str, List[Paper]]) -> None:
    for topic, paper_items in incoming.items():
        target.setdefault(topic, []).extend(paper_items)


def main():
    data_dir = "data"
    html_file = "index.html"
    state_file = ".tracker-state.json"
    now = datetime.datetime.now(datetime.timezone.utc)
    today = now.date()
    timestamp = now.isoformat().replace("+00:00", "Z")
    # Remove the optional secret before importing third-party arXiv code. It is passed
    # directly to the OpenAlex fetcher later and is never written to generated files.
    openalex_api_key = os.environ.pop("OPENALEX_API_KEY", "").strip()
    force_fetch = os.getenv("FORCE_FETCH", "").lower() in {"1", "true", "yes"}
    preprint_backfill_days = get_env_int("PREPRINTS_BACKFILL_DAYS", 0, minimum=0)
    preprint_lookback_days = get_env_int("PREPRINTS_LOOKBACK_DAYS", 3)
    preprint_retention_days = get_env_int("PREPRINT_RETENTION_DAYS", 1826)
    if preprint_backfill_days > preprint_retention_days:
        print(
            f"PREPRINTS_BACKFILL_DAYS={preprint_backfill_days} exceeds the retained history; "
            f"using {preprint_retention_days} days instead.",
            file=sys.stderr,
        )
        preprint_backfill_days = preprint_retention_days
    state = load_state(state_file)
    arxiv_state = state.setdefault("arxiv", {})
    if not isinstance(arxiv_state, dict):
        arxiv_state = {}
        state["arxiv"] = arxiv_state

    due_keywords = {
        topic: query
        for topic, query in ARXIV_KEYWORDS.items()
        if force_fetch or not succeeded_today(arxiv_state.get(topic), today)
    }
    if preprint_backfill_days:
        due_keywords = {}
    preprints_due = (
        preprint_backfill_days > 0
        or force_fetch
        or not succeeded_today(state.get("preprints"), today)
    )
    if not due_keywords and not preprints_due:
        print("All sources already succeeded today; skipping duplicate scheduled run.")
        return

    papers: Dict[str, List[Paper]] = {}
    successful_sources = 0
    if due_keywords:
        max_results_per_keyword = get_env_int("ARXIV_MAX_RESULTS_PER_KEYWORD", 100)
        arxiv_papers, succeeded_keywords = get_papers(
            due_keywords, max_results_per_keyword=max_results_per_keyword
        )
        merge_papers(papers, arxiv_papers)
        for topic in succeeded_keywords:
            arxiv_state[topic] = timestamp
        successful_sources += len(succeeded_keywords)

    if preprints_due:
        since_date = today - datetime.timedelta(
            days=preprint_backfill_days or preprint_lookback_days
        )
        preprint_papers, preprints_succeeded = get_preprints_metadata(
            since_date,
            today,
            historical=preprint_backfill_days > 0,
            openalex_api_key=openalex_api_key,
        )
        if preprints_succeeded:
            merge_papers(papers, preprint_papers)
            state["preprints"] = timestamp
            successful_sources += 1

    if not successful_sources:
        raise RuntimeError("No due source completed successfully; existing data was left unchanged.")

    update_sharded_archive(data_dir, papers)
    json_to_html(data_dir, html_file, title="Daily Research Preprints")
    save_state(state_file, state)


if __name__ == "__main__":
    main()
