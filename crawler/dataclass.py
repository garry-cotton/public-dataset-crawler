from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class SiteConfig:
    category: str
    repository: str
    start_url: str
    extensions: Tuple[str, ...]


@dataclass(frozen=True)
class CrawlTask:
    url: str
    depth: int


@dataclass
class CandidateFile:
    site: SiteConfig
    source_page_url: str
    file_url: str
    link_text: str = ""


@dataclass
class HtmlPage:
    url: str
    html: str
    fetched_via: str = "requests"
