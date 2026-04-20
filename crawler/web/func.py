from __future__ import annotations

import requests
import re
import time

from bs4 import BeautifulSoup
from collections import deque
from typing import Tuple, Set, List, Optional, Iterable, Dict, Deque
from urllib.parse import urljoin, urlparse
from pathlib import Path

from .playwright import PlaywrightRenderer
from config import Defaults, Formats, WebConfig
from dataclass import HtmlPage, SiteConfig, CandidateFile, CrawlTask
from helper import (
    clean_text,
    get_parser,
    is_archive_path,
    filename_from_content_disposition,
    url_matches_extensions,
    canonical_host,
    normalize_url,
    is_candidate_download_link,
    print_progress,
    sanitize_filename,
    dataset_stem_from_url,
    build_dataset_name
)
from archive import (
    archive_contains_matching_files,
    extract_matching_files_from_archive,
    detect_contained_file_types
)


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": Defaults.user_agent})
    return session


def host_allowed(url: str, seed_url: str) -> bool:
    candidate_host = canonical_host(urlparse(url).netloc)
    seed_host = canonical_host(urlparse(seed_url).netloc)
    return candidate_host == seed_host or \
        candidate_host.endswith("." + seed_host) or \
        seed_host.endswith("." + candidate_host)


def fetch_html_with_requests(session: requests.Session,
                             url: str) -> Optional[HtmlPage]:
    
    try:
        response = session.get(url,
                               timeout=Defaults.request_timeout,
                               allow_redirects=True)
        response.raise_for_status()
    except requests.RequestException:
        return None

    content_type = response.headers.get("Content-Type", "").lower()
    if "html" not in content_type and "xml" not in content_type:
        return None
    return HtmlPage(url=response.url, html=response.text, fetched_via="requests")


def extract_links(
        html: str,
        base_url: str,
        visited_links: Optional[Set[str]] = None) -> List[Tuple[str, str]]:
    
    soup = BeautifulSoup(html, get_parser())
    links: List[Tuple[str, str]] = []

    if visited_links is None:
        visited_links = set()

    for a in soup.find_all("a", href=True):
        href = normalize_url(urljoin(base_url, a["href"]))
        text = clean_text(a.get_text(" ", strip=True))
        
        if href and href not in visited_links:
            links.append((text, href))

    return links


def looks_like_html_page(url: str) -> bool:
    path = urlparse(url).path.lower()
    if not path:
        return True
    if path.endswith("/"):
        return True
    if re.search(r"\.(html?|php|aspx?|jsp|cfm)$", path):
        return True
    return "." not in Path(path).name


def download_and_extract_archive_if_relevant(
    session: requests.Session,
    candidate: CandidateFile,
    destination_dir: Path) -> Tuple[bool, str, Optional[float], List[str]]:

    success, archive_path_str, size_mb = download_dataset_file(session, candidate, destination_dir)
    if not success or not archive_path_str:
        return False, "", size_mb, []

    archive_path = Path(archive_path_str)
    if not is_archive_path(str(archive_path)):
        return success, archive_path_str, size_mb, []

    if not archive_contains_matching_files(archive_path, candidate.site.extensions):
        return False, archive_path_str, size_mb, []

    extract_dir = destination_dir / f"{archive_path.name}__extracted"
    extracted = extract_matching_files_from_archive(
        archive_path,
        extract_dir,
        candidate.site.extensions,
    )

    return bool(extracted), archive_path_str, size_mb, extracted


def extension_matches_response(
    response: requests.Response,
    extensions: Iterable[str],
    request_url: str) -> bool:

    extensions = tuple(ext.lower() for ext in extensions)

    filename = filename_from_content_disposition(response.headers.get("Content-Disposition", ""))
    if filename:
        lower_name = filename.lower()
        if any(lower_name.endswith(ext) for ext in extensions):
            return True

    final_url = response.url.lower()
    if any(final_url.endswith(ext) for ext in extensions):
        return True

    request_url = request_url.lower()
    if any(request_url.endswith(ext) for ext in extensions):
        return True

    content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
    inferred_exts = Formats.content_type_extension_map.get(content_type, [])
    return any(ext in [e.lower() for e in inferred_exts] for ext in extensions)


def head_or_get_validate(
    session: requests.Session,
    url: str,
    allowed_extensions: Iterable[str]) -> Tuple[bool, Optional[int]]:

    try:
        head = session.head(url, timeout=Defaults.request_timeout, allow_redirects=True)
        if head.ok and extension_matches_response(head, allowed_extensions, url):
            size = head.headers.get("Content-Length")
            return True, int(size) if size and size.isdigit() else None
    except requests.RequestException:
        pass

    try:
        resp = session.get(url, timeout=Defaults.request_timeout, allow_redirects=True, stream=True)
        resp.raise_for_status()
        try:
            is_match = extension_matches_response(resp, allowed_extensions, url)
            size = resp.headers.get("Content-Length")
            return is_match, int(size) if size and size.isdigit() else None
        finally:
            resp.close()
    except requests.RequestException:
        return False, None


def detect_candidate_files(
    session: requests.Session,
    site: SiteConfig,
    source_page_url: str,
    links: List[Tuple[str, str]],
    current_depth: int = 0,
    scanned_candidates: int = 0,
    accepted_candidates: int = 0) -> Tuple[List[CandidateFile], int, int]:
    
    candidates: List[CandidateFile] = list()
    
    for link_text, href in links:
        scanned_candidates += 1
        
        if not host_allowed(href, site.start_url):
            pass

        if url_matches_extensions(href, site.extensions) or is_archive_path(href):
            accepted_candidates += 1
            candidates.append(
                CandidateFile(site=site,
                              source_page_url=source_page_url,
                              file_url=href,
                              link_text=link_text))

        elif is_candidate_download_link(link_text, href):
            is_match, _ = head_or_get_validate(session, href, site.extensions)
            if is_match:
                accepted_candidates += 1
                candidates.append(
                    CandidateFile(site=site,
                                  source_page_url=source_page_url,
                                  file_url=href,
                                  link_text=link_text))

        print_progress(scanned_candidates, accepted_candidates, current_depth, href)

    return candidates, scanned_candidates, accepted_candidates


def should_try_playwright(page: Optional[HtmlPage],
                          links: List[Tuple[str, str]]) -> bool:
    
    if page is None:
        return True
    if len(links) <= 2:
        return True
    html_lower = page.html.lower()
    return any(marker in html_lower for marker in WebConfig.js_markers)


def fetch_page(
    session: requests.Session,
    url: str,
    renderer: Optional[PlaywrightRenderer],
    use_playwright_fallback: bool) -> Optional[HtmlPage]:

    page = fetch_html_with_requests(session, url)
    links: List[Tuple[str, str]] = []
    if page is not None:
        links = extract_links(page.html, page.url)
        if not (use_playwright_fallback and renderer and \
                renderer.available() and \
                should_try_playwright(page, links)):
            return page

    if use_playwright_fallback and renderer and renderer.available():
        rendered = renderer.fetch(url)
        if rendered is not None:
            return rendered
    return page


def discover_candidates_for_site(
    session: requests.Session,
    site: SiteConfig,
    max_pages: int,
    max_depth: int,
    renderer: Optional[PlaywrightRenderer],
    use_playwright_fallback: bool) -> List[CandidateFile]:
    
    queue: Deque[CrawlTask] = deque([CrawlTask(site.start_url, 0)])
    visited_pages: Set[str] = set()
    visited_links: Set[str] = set()
    seen_files: Set[str] = set()
    found: List[CandidateFile] = []
    scanned_candidates = 0
    accepted_candidates = 0

    while queue and len(visited_pages) < max_pages:
        task = queue.popleft()
        current_url = normalize_url(task.url)

        if not current_url or current_url in visited_pages:
            continue
        if task.depth > max_depth:
            continue
        if not host_allowed(current_url, site.start_url):
            continue

        visited_pages.add(current_url)
        page = fetch_page(
            session=session,
            url=current_url,
            renderer=renderer,
            use_playwright_fallback=use_playwright_fallback,
        )
        time.sleep(Defaults.crawl_sleep_seconds)
        
        if page is None:
            continue

        links = extract_links(page.html, page.url, visited_links)
        candidates, scanned_candidates, accepted_candidates = \
            detect_candidate_files(session,
                                   site,
                                   page.url,
                                   links,
                                   task.depth,
                                   scanned_candidates,
                                   accepted_candidates)
        
        for candidate in candidates:
            normalized_candidate_url = normalize_url(candidate.file_url)
                        
            if normalized_candidate_url not in seen_files:
                seen_files.add(normalized_candidate_url)
                candidate.file_url = normalized_candidate_url
                found.append(candidate)

        if task.depth < max_depth:
            for _, href in links:
                if href in visited_links:
                    continue
                
                visited_links.add(href)

                if not host_allowed(href, site.start_url):
                    continue
                if looks_like_html_page(href):
                    queue.append(CrawlTask(href, task.depth + 1))

    return found


def best_filename_from_url_or_headers(response: requests.Response,
                                      original_url: str) -> str:
    
    filename = filename_from_content_disposition(response.headers.get("Content-Disposition", ""))
    if filename:
        return sanitize_filename(filename)

    path_name = Path(urlparse(response.url or original_url).path).name
    if path_name:
        return sanitize_filename(path_name)

    return "downloaded_file"


def maybe_add_extension(
        filename: str,
        response: requests.Response,
        allowed_extensions: Iterable[str]) -> str:
    
    if Path(filename).suffix:
        return filename

    content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
    inferred = Formats.content_type_extension_map.get(content_type, [])
    allowed = [ext for ext in allowed_extensions if ext in inferred]
    if allowed:
        return filename + allowed[0]

    allowed = list(allowed_extensions)
    if allowed:
        return filename + allowed[0]

    return filename


def download_dataset_file(
    session: requests.Session,
    candidate: CandidateFile,
    destination_dir: Path) -> Tuple[bool, str, Optional[float]]:
    
    destination_dir.mkdir(parents=True, exist_ok=True)

    try:
        response = session.get(
            candidate.file_url,
            timeout=Defaults.request_timeout,
            allow_redirects=True,
            stream=True)
        response.raise_for_status()
    except requests.RequestException:
        return False, "", None

    try:
        if not extension_matches_response(response, candidate.site.extensions, candidate.file_url):
            return False, "", None

        filename = best_filename_from_url_or_headers(response, candidate.file_url)
        filename = maybe_add_extension(filename, response, candidate.site.extensions)
        output_path = destination_dir / sanitize_filename(filename)
        temp_path = output_path.with_suffix(output_path.suffix + ".part")

        total_bytes = 0
        with open(temp_path, "wb") as handle:
            for chunk in response.iter_content(chunk_size=Defaults.download_chunk_size):
                if not chunk:
                    continue
                handle.write(chunk)
                total_bytes += len(chunk)

        temp_path.replace(output_path)
        size_mb = round(total_bytes / (1024 * 1024), 3)
        return True, str(output_path.resolve()), size_mb
    finally:
        response.close()


def download_document_page(
    session: requests.Session,
    source_page_url: str,
    destination_dir: Path,
    repository_name: str,
    dataset_stem: str) -> str:

    destination_dir.mkdir(parents=True, exist_ok=True)
    try:
        response = session.get(source_page_url,
                               timeout=Defaults.request_timeout,
                               allow_redirects=True)
        response.raise_for_status()
    except requests.RequestException:
        return ""

    content_type = response.headers.get("Content-Type", "").lower()
    if "html" not in content_type and "xml" not in content_type:
        return ""

    slug = sanitize_filename(f"{repository_name}__{dataset_stem}__document", default="document")
    output_path = destination_dir / f"{slug}.html"
    try:
        with open(output_path,
                  "w",
                  encoding=response.encoding or "utf-8",
                  errors="replace") as handle:
            
            handle.write(response.text)
        return str(output_path.resolve())
    except OSError:
        return ""


def process_site(
    session: requests.Session,
    site: SiteConfig,
    download_root: Path,
    max_pages_per_site: int,
    max_depth: int,
    renderer: Optional[PlaywrightRenderer],
    use_playwright_fallback: bool) -> List[Dict[str, str]]:

    site_slug = sanitize_filename(site.repository, default="site")
    site_root = download_root / site_slug
    data_dir = site_root / "data"
    docs_dir = site_root / "documents"

    rows: List[Dict[str, str]] = []
    candidates = discover_candidates_for_site(
        session=session,
        site=site,
        max_pages=max_pages_per_site,
        max_depth=max_depth,
        renderer=renderer,
        use_playwright_fallback=use_playwright_fallback,
    )

    for candidate in candidates:
        dataset_name = build_dataset_name(site.repository, candidate.file_url)
        dataset_stem = sanitize_filename(dataset_stem_from_url(candidate.file_url),
                                         default="dataset")

        if is_archive_path(candidate.file_url):
            success, download_path, size_mb, extracted_paths = \
                download_and_extract_archive_if_relevant(session, candidate, data_dir)
        else:
            success, download_path, size_mb = download_dataset_file(session, candidate, data_dir)
            extracted_paths = []

        document_path = download_document_page(
            session,
            candidate.source_page_url,
            docs_dir,
            site.repository,
            dataset_stem)

        extension = ""
        lower_url = candidate.file_url.lower()

        for ext in sorted(site.extensions, key=len, reverse=True):
            if lower_url.endswith(ext.lower()):
                extension = ext
                break
        if not extension and download_path:
            lower_download = download_path.lower()
            for ext in sorted(site.extensions, key=len, reverse=True):
                if lower_download.endswith(ext.lower()):
                    extension = ext
                    break
        if not extension and download_path:
            extension = Path(download_path).suffix

        contained_file_types = detect_contained_file_types(
            extracted_paths,
            candidate.site.extensions,
        )

        rows.append(
            {
                "Dataset Name": dataset_name,
                "Category": site.category,
                "Size": f"{size_mb:.3f}" if size_mb is not None else "",
                "Data Storage Type": extension,
                "Accessible?": "Yes" if success else "No",
                "Download Path": download_path,
                "Document Path": document_path,
                "Extracted Paths": "; ".join(extracted_paths),
                "Contained File Types": ", ".join(contained_file_types),
            }
        )

    return rows
