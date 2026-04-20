from __future__ import annotations

import re

from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import unquote, urlparse, urlsplit, urlunsplit, urldefrag, parse_qs

from config import Formats, WebConfig


def lower_name(path_or_url: str) -> str:
    return path_or_url.lower()


def endswith_any(value: str, suffixes: Iterable[str]) -> bool:
    value = value.lower()
    return any(value.endswith(sfx.lower()) for sfx in suffixes)


def is_archive_path(path_or_url: str) -> bool:
    return endswith_any(path_or_url, Formats.archive_extensions)


def clean_text(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def sanitize_filename(name: str, default: str = "file") -> str:
    name = clean_text(name)
    name = re.sub(r'[<>:"/\\|?*]+', "_", name)
    name = name.strip(" .")
    return name or default


def safe_join(base_dir: Path, member_name: str) -> Path:
    target = (base_dir / member_name).resolve()
    base_resolved = base_dir.resolve()
    if base_resolved not in target.parents and target != base_resolved:
        raise ValueError(f"Unsafe archive member path: {member_name}")
    return target


def get_parser() -> str:
    try:
        import lxml  # noqa: F401
        return "lxml"
    except Exception:
        return "html.parser"


def url_matches_extensions(url: str, extensions: Iterable[str]) -> bool:
    lowered = url.lower()
    return any(lowered.endswith(ext.lower()) for ext in extensions)


def filename_from_content_disposition(content_disposition: str) -> Optional[str]:
    if not content_disposition:
        return None
    match = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition, re.I)
    if match:
        return unquote(match.group(1).strip().strip('"'))
    match = re.search(r'filename="?([^";]+)"?', content_disposition, re.I)
    if match:
        return match.group(1).strip()
    return None


def print_progress(scanned: int, accepted: int, current_depth: int, url: str) -> None:
    short_url = compact_url(url, max_len=60)
    msg = (
        f"\r    Scanned {scanned} candidate objects, {accepted} accepted. "
        f"Current depth: {current_depth}. "
        f"Current candidate: {short_url}"
    )
    print(msg.ljust(160), end="", flush=True)


def compact_url(url: str, max_len: int = 60) -> str:
    parsed = urlparse(url)
    compact = f"{parsed.netloc}{parsed.path}"
    if len(compact) <= max_len:
        return compact
    return compact[:max_len - 3] + "..."


def dataset_stem_from_url(url: str) -> str:
    path_name = Path(urlparse(url).path).name
    if not path_name:
        return "dataset"

    lower = path_name.lower()
    for suffix in Formats.compound_suffixes:
        if lower.endswith(suffix):
            return path_name[: -len(suffix)]

    return Path(path_name).stem or "dataset"


def build_dataset_name(repository: str, file_url: str) -> str:
    stem = dataset_stem_from_url(file_url)
    return f"{repository} - {stem}"


def is_candidate_download_link(link_text: str, url: str) -> bool:
    text = (link_text + " " + url).lower()
    return any(keyword in text for keyword in WebConfig.candidate_keywords)


def normalize_url(url: str) -> str:
    url = urldefrag(url)[0].strip()
    if not url:
        return ""
    parts = list(urlsplit(url))
    query_pairs = parse_qs(parts[3], keep_blank_values=True)
    filtered = []
    for key in sorted(query_pairs):
        if key.lower().startswith("utm_") or key.lower() in {"fbclid", "gclid"}:
            continue
        for value in sorted(query_pairs[key]):
            filtered.append(f"{key}={value}")
    parts[3] = "&".join(filtered)
    url = urlunsplit(parts)
    
    if url.endswith("/"):
        url = url[:-1]

    return url


def canonical_host(host: str) -> str:
    host = host.lower().strip()
    if host.startswith("www."):
        return host[4:]
    return host
