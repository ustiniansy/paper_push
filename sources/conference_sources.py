"""
Conference paper sources.

This module uses a best-effort mix of official proceedings/event pages and
snapshot-based detection to find newly available conference papers.
"""
from __future__ import annotations

import hashlib
import html
import re
import urllib3
from dataclasses import dataclass
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin

import requests

from pipeline.http_client import get_retry_session
from pipeline.runtime_utils import ProgressBar


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@dataclass
class VenueConfig:
    key: str
    display_name: str
    parser: str
    urls: List[str]


@dataclass
class VenueFetchResult:
    venue_name: str
    status: str
    papers: List[Dict]
    detail: str = ""


def _year_candidates() -> Tuple[int, int]:
    year = datetime.now().year
    return year, year + 1


def _default_venues() -> List[VenueConfig]:
    year, prev = _year_candidates()
    return [
        VenueConfig(
            key="CVPR",
            display_name="CVPR",
            parser="cvf",
            urls=[
                f"https://openaccess.thecvf.com/CVPR{year}?day=all",
                f"https://openaccess.thecvf.com/CVPR{prev}?day=all",
            ],
        ),
        VenueConfig(
            key="ICCV",
            display_name="ICCV",
            parser="cvf",
            urls=[
                f"https://openaccess.thecvf.com/ICCV{year}?day=all",
                f"https://openaccess.thecvf.com/ICCV{prev}?day=all",
            ],
        ),
        VenueConfig(
            key="WACV",
            display_name="WACV",
            parser="cvf",
            urls=[
                f"https://openaccess.thecvf.com/WACV{year}?day=all",
                f"https://openaccess.thecvf.com/WACV{prev}?day=all",
            ],
        ),
        VenueConfig(
            key="ACL",
            display_name="ACL",
            parser="acl_event",
            urls=[
                f"https://aclanthology.org/events/acl-{year}/",
                f"https://aclanthology.org/events/acl-{prev}/",
            ],
        ),
        VenueConfig(
            key="EMNLP",
            display_name="EMNLP",
            parser="acl_event",
            urls=[
                f"https://aclanthology.org/events/emnlp-{year}/",
                f"https://aclanthology.org/events/emnlp-{prev}/",
            ],
        ),
        VenueConfig(
            key="NAACL",
            display_name="NAACL",
            parser="acl_event",
            urls=[
                f"https://aclanthology.org/events/naacl-{year}/",
                f"https://aclanthology.org/events/naacl-{prev}/",
            ],
        ),
        VenueConfig(
            key="NeurIPS",
            display_name="NeurIPS",
            parser="neurips",
            urls=[
                f"https://neurips.cc/virtual/{year}/papers.html?filter=titles",
                f"https://neurips.cc/virtual/{prev}/papers.html?filter=titles",
                f"https://proceedings.neurips.cc/paper_files/paper/{year}",
                f"https://proceedings.neurips.cc/paper_files/paper/{prev}",
                f"https://papers.nips.cc/paper_files/paper/{year}",
                f"https://papers.nips.cc/paper_files/paper/{prev}",
            ],
        ),
        VenueConfig(
            key="AAAI",
            display_name="AAAI",
            parser="aaai_archive",
            urls=[
                "https://ojs.aaai.org/index.php/AAAI/issue/archive",
                "https://auld.aaai.org/Library/AAAI/",
            ],
        ),
        VenueConfig(
            key="ICLR",
            display_name="ICLR",
            parser="generic_virtual",
            urls=[
                f"https://openreview.net/group?id=ICLR.cc/{year}/Conference",
                f"https://openreview.net/group?id=ICLR.cc/{prev}/Conference",
                f"https://iclr.cc/virtual/{year}/papers.html?filter=titles",
                f"https://iclr.cc/virtual/{prev}/papers.html?filter=titles",
                f"https://iclr.cc/Conferences/{year}/AcceptedPapersFinal",
                f"https://iclr.cc/Conferences/{prev}/AcceptedPapersFinal",
            ],
        ),
        VenueConfig(
            key="ICML",
            display_name="ICML",
            parser="pmlr",
            urls=[
                "https://proceedings.mlr.press/v267/",
                "https://proceedings.mlr.press/v235/",
                f"https://icml.cc/virtual/{year}/papers.html?filter=titles",
                f"https://icml.cc/virtual/{prev}/papers.html?filter=titles",
            ],
        ),
        VenueConfig(
            key="ACMMM",
            display_name="ACM MM",
            parser="generic_virtual",
            urls=[
                f"https://{year}.acmmm.org/program/accepted-papers/",
                f"https://{prev}.acmmm.org/program/accepted-papers/",
            ],
        ),
    ]


def _normalize_venue_keys(selected_venues: Optional[Iterable[str]]) -> Optional[set[str]]:
    if not selected_venues:
        return None
    normalized = {str(item).strip().upper() for item in selected_venues if str(item).strip()}
    return normalized or None


def _clean_text(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _looks_like_paper_title(title: str) -> bool:
    lowered = title.lower()
    banned = (
        "video/poster/slides",
        "poster",
        "slides",
        "session",
        "schedule",
        "program",
        "welcome",
        "call for papers",
        "proceedings of",
    )
    if len(title) < 12:
        return False
    return not any(item in lowered for item in banned)


def _uid(venue: str, stable_id: str) -> str:
    digest = hashlib.md5(stable_id.encode("utf-8")).hexdigest()[:16]
    return f"conf:{venue}:{digest}"


def _venue_slug(venue_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", venue_name.strip().upper()).strip("-")
    return slug or "CONF"


def _get(url: str, timeout: int) -> str:
    try:
        resp = get_retry_session().get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except requests.exceptions.SSLError:
        resp = get_retry_session().get(url, timeout=timeout, verify=False)
        resp.raise_for_status()
        return resp.text


def _extract_acl_event_papers(base_url: str, html_text: str) -> List[Dict]:
    pattern = re.compile(
        r'href=(["\']?)(/[^ >"\']*\d{4}\.[^ >"\']+/)\1[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    papers: Dict[str, Dict] = {}
    for _, href, title_html in pattern.findall(html_text):
        if href.startswith("/volumes/") or href.rstrip("/").endswith(".0"):
            continue
        title = _clean_text(title_html)
        if not _looks_like_paper_title(title):
            continue
        full_url = urljoin(base_url, href)
        stable_id = href.strip("/")
        papers[stable_id] = {
            "arxiv_id": _uid("ACL", stable_id),
            "title": title,
            "abstract": "",
            "authors": [],
            "url": full_url,
            "source": "conference",
            "venue": "",
            "upvotes": 0,
        }
    return list(papers.values())


def _extract_neurips_papers(base_url: str, html_text: str) -> List[Dict]:
    pattern = re.compile(
        r'<a href="([^"]*(?:/paper_files/paper/\d{4}/hash/[^"]+-Abstract-Conference\.html|/virtual/\d{4}/poster/[^"]+))">(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    papers = []
    seen = set()
    for href, title_html in pattern.findall(html_text):
        title = _clean_text(title_html)
        if not _looks_like_paper_title(title):
            continue
        full_url = urljoin(base_url, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        papers.append(
            {
                "arxiv_id": _uid("NeurIPS", full_url),
                "title": title,
                "abstract": "",
                "authors": [],
                "url": full_url,
                "source": "conference",
                "venue": "NeurIPS",
                "upvotes": 0,
            }
        )
    return papers


def _extract_pmlr_papers(base_url: str, html_text: str) -> List[Dict]:
    pattern = re.compile(
        r'<div class="paper">.*?<p class="title">(.*?)</p>.*?<p class="links">.*?<a href="([^"]+)">abs</a>',
        re.IGNORECASE | re.DOTALL,
    )
    papers = []
    seen = set()
    for title_html, href in pattern.findall(html_text):
        title = _clean_text(title_html)
        if not _looks_like_paper_title(title):
            continue
        full_url = urljoin(base_url, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        papers.append(
            {
                "arxiv_id": _uid("ICML", full_url),
                "title": title,
                "abstract": "",
                "authors": [],
                "url": full_url,
                "source": "conference",
                "venue": "ICML",
                "upvotes": 0,
            }
        )
    return papers


def _extract_cvf_papers(base_url: str, html_text: str) -> List[Dict]:
    pattern = re.compile(
        r'<dt class="ptitle">.*?<a href="([^"]+)">(.*?)</a>\s*</dt>',
        re.IGNORECASE | re.DOTALL,
    )
    papers = []
    seen = set()
    for href, title_html in pattern.findall(html_text):
        title = _clean_text(title_html)
        if not _looks_like_paper_title(title):
            continue
        full_url = urljoin(base_url, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        papers.append(
            {
                "arxiv_id": _uid("CVF", full_url),
                "title": title,
                "abstract": "",
                "authors": [],
                "url": full_url,
                "source": "conference",
                "venue": "",
                "upvotes": 0,
            }
        )
    return papers


def _extract_generic_anchor_papers(base_url: str, html_text: str) -> List[Dict]:
    pattern = re.compile(r'<a href="([^"]+)".*?>(.*?)</a>', re.IGNORECASE | re.DOTALL)
    papers = []
    seen = set()
    for href, title_html in pattern.findall(html_text):
        title = _clean_text(title_html)
        if not _looks_like_paper_title(title):
            continue
        if any(skip in href.lower() for skip in ("login", "register", "program", "schedule", "workshop", "sponsor")):
            continue
        full_url = urljoin(base_url, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        papers.append(
            {
                "arxiv_id": _uid("GENERIC", full_url),
                "title": title,
                "abstract": "",
                "authors": [],
                "url": full_url,
                "source": "conference",
                "venue": "",
                "upvotes": 0,
            }
        )
    return papers


def _extract_aaai_archive_papers(base_url: str, html_text: str) -> List[Dict]:
    issue_pattern = re.compile(r'href="([^"]*(?:issue/view|contents\.php)[^"]*)"', re.IGNORECASE)
    issue_urls = [urljoin(base_url, href) for href in issue_pattern.findall(html_text)]
    if not issue_urls:
        return []
    issue_url = issue_urls[0]
    issue_html = _get(issue_url, 30)
    pattern = re.compile(r'href="([^"]*(?:article/view|index\.php/AAAI/article/view)[^"]*)".*?>(.*?)</a>', re.IGNORECASE | re.DOTALL)
    papers = []
    seen = set()
    for href, title_html in pattern.findall(issue_html):
        title = _clean_text(title_html)
        if not _looks_like_paper_title(title):
            continue
        full_url = urljoin(issue_url, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        papers.append(
            {
                "arxiv_id": _uid("AAAI", full_url),
                "title": title,
                "abstract": "",
                "authors": [],
                "url": full_url,
                "source": "conference",
                "venue": "AAAI",
                "upvotes": 0,
            }
        )
    return papers


def _fetch_abstract(url: str, parser: str, timeout: int) -> str:
    try:
        html_text = _get(url, timeout)
    except Exception:
        return ""

    patterns = {
        "cvf": [
            r'<div id="abstract"[^>]*>\s*(.*?)\s*</div>',
            r'<div class="abstract"[^>]*>\s*(.*?)\s*</div>',
        ],
        "acl_event": [
            r'<div class="acl-abstract"[^>]*>\s*(.*?)\s*</div>',
            r'<div id="abstract"[^>]*>\s*(.*?)\s*</div>',
        ],
        "neurips": [
            r'<h4>Abstract</h4>\s*<p>(.*?)</p>',
            r'<div class="abstract">(.*?)</div>',
        ],
        "aaai_archive": [
            r'<section class="item abstract"[^>]*>.*?<p>(.*?)</p>',
            r'<meta name="citation_abstract" content="(.*?)"',
        ],
        "pmlr": [
            r'<div id="abstract"[^>]*>\s*(.*?)\s*</div>',
            r'<meta name="description" content="(.*?)"',
        ],
        "generic_virtual": [
            r'<div[^>]+class="abstract"[^>]*>(.*?)</div>',
            r'<meta name="description" content="(.*?)"',
        ],
    }

    for pattern in patterns.get(parser, patterns["generic_virtual"]):
        match = re.search(pattern, html_text, re.IGNORECASE | re.DOTALL)
        if match:
            return _clean_text(match.group(1))
    return ""


def _apply_venue(papers: List[Dict], venue_name: str, parser: str, timeout: int) -> List[Dict]:
    venue_slug = _venue_slug(venue_name)
    for paper in papers:
        paper["venue"] = venue_name
        digest = paper["arxiv_id"].split(":")[-1]
        paper["arxiv_id"] = f"conf:{venue_slug}:{digest}"
        paper["detail_parser"] = parser
    return papers


def _is_not_released_error(exc: Exception) -> bool:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        if exc.response.status_code == 404:
            return True
    message = str(exc).lower()
    markers = (
        "404 client error",
        "not found for url",
        "accepted papers",
        "no accepted papers",
    )
    return any(marker in message for marker in markers)


def _fetch_from_url(venue: VenueConfig, timeout: int) -> VenueFetchResult:
    last_error: Optional[Exception] = None
    for index, url in enumerate(venue.urls, 1):
        try:
            print(f"[ConferenceSource] {venue.display_name}: 尝试 {index}/{len(venue.urls)} -> {url}")
            html_text = _get(url, timeout)
            if venue.parser == "cvf":
                papers = _apply_venue(_extract_cvf_papers(url, html_text), venue.display_name, venue.parser, timeout)
                print(f"[ConferenceSource] {venue.display_name}: 抓到 {len(papers)} 篇")
                return VenueFetchResult(venue.display_name, "published", papers)
            if venue.parser == "acl_event":
                papers = _apply_venue(_extract_acl_event_papers(url, html_text), venue.display_name, venue.parser, timeout)
                print(f"[ConferenceSource] {venue.display_name}: 抓到 {len(papers)} 篇")
                return VenueFetchResult(venue.display_name, "published", papers)
            if venue.parser == "neurips":
                papers = _apply_venue(_extract_neurips_papers(url, html_text), venue.display_name, venue.parser, timeout)
                print(f"[ConferenceSource] {venue.display_name}: 抓到 {len(papers)} 篇")
                return VenueFetchResult(venue.display_name, "published", papers)
            if venue.parser == "aaai_archive":
                papers = _apply_venue(_extract_aaai_archive_papers(url, html_text), venue.display_name, venue.parser, timeout)
                print(f"[ConferenceSource] {venue.display_name}: 抓到 {len(papers)} 篇")
                return VenueFetchResult(venue.display_name, "published", papers)
            if venue.parser == "pmlr":
                papers = _apply_venue(_extract_pmlr_papers(url, html_text), venue.display_name, venue.parser, timeout)
                print(f"[ConferenceSource] {venue.display_name}: 抓到 {len(papers)} 篇")
                return VenueFetchResult(venue.display_name, "published", papers)
            papers = _apply_venue(_extract_generic_anchor_papers(url, html_text), venue.display_name, venue.parser, timeout)
            print(f"[ConferenceSource] {venue.display_name}: 抓到 {len(papers)} 篇")
            return VenueFetchResult(venue.display_name, "published", papers)
        except Exception as exc:
            last_error = exc
            print(f"[ConferenceSource] {venue.display_name}: 本次尝试失败: {exc}")
            continue
    if last_error:
        if _is_not_released_error(last_error):
            return VenueFetchResult(venue.display_name, "not_released", [], str(last_error))
        return VenueFetchResult(venue.display_name, "failed", [], str(last_error))
    return VenueFetchResult(venue.display_name, "not_released", [], "")


def fetch_conference_papers(
    timeout: int = 30,
    selected_venues: Optional[Iterable[str]] = None,
    max_workers: int = 6,
) -> Tuple[List[Dict], Dict[str, int], List[str], List[str]]:
    all_papers: List[Dict] = []
    venue_counts: Dict[str, int] = {}
    errors: List[str] = []
    not_released: List[str] = []
    selected = _normalize_venue_keys(selected_venues)
    venues = [venue for venue in _default_venues() if not selected or venue.key.upper() in selected]
    if not venues:
        return [], {}, ["conference_monitor.venues does not match any supported venue"], []

    print(f"[ConferenceSource] 开始抓取 {len(venues)} 个会议源，max_workers={max_workers}")
    progress = ProgressBar("conference-source-fetch", len(venues))
    worker_count = max(1, min(max_workers, len(venues)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_map = {
            executor.submit(_fetch_from_url, venue, timeout): venue
            for venue in venues
        }
        for future in as_completed(future_map):
            venue = future_map[future]
            try:
                result = future.result()
                if result.status == "published":
                    if not result.papers:
                        print(f"[ConferenceSource] {venue.display_name}: 未抓到论文")
                        progress.advance(detail=f"{venue.display_name}: 0 papers")
                        continue
                    venue_counts[venue.display_name] = len(result.papers)
                    all_papers.extend(result.papers)
                    progress.advance(detail=f"{venue.display_name}: {len(result.papers)} papers")
                    continue
                if result.status == "not_released":
                    not_released.append(venue.display_name)
                    print(f"[ConferenceSource] {venue.display_name}: 未发布")
                    progress.advance(detail=f"{venue.display_name}: not released")
                    continue
                errors.append(f"{venue.display_name}: {result.detail}")
                print(f"[ConferenceSource] {venue.display_name}: 最终失败")
                progress.advance(detail=f"{venue.display_name}: failed")
            except Exception as exc:
                errors.append(f"{venue.display_name}: {exc}")
                print(f"[ConferenceSource] {venue.display_name}: 最终失败")
                progress.advance(detail=f"{venue.display_name}: failed")

    unique: Dict[str, Dict] = {}
    for paper in all_papers:
        unique[paper["arxiv_id"]] = paper
    progress.finish(
        detail=f"unique={len(unique)} errors={len(errors)} not_released={len(not_released)}"
    )
    print(
        f"[ConferenceSource] 抓取完成，成功会议 {len(venue_counts)} 个，"
        f"唯一论文 {len(unique)} 篇，未发布 {len(not_released)} 个，失败 {len(errors)} 个"
    )
    return list(unique.values()), venue_counts, errors, not_released


def enrich_conference_papers(papers: List[Dict], timeout: int = 30):
    """Populate abstracts for conference papers in-place."""
    progress = ProgressBar("conference-abstract-enrich", len(papers))
    for paper in papers:
        if paper.get("abstract"):
            progress.advance(detail="cached")
            continue
        parser = paper.get("detail_parser", "generic_virtual")
        paper["abstract"] = _fetch_abstract(paper["url"], parser, timeout)
        progress.advance(detail=paper.get("venue", "Unknown"))
    progress.finish()
