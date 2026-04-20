from __future__ import annotations

import zipfile
import tarfile
import rarfile

from pathlib import Path
from typing import Iterable, List, Set, Tuple
from types import FunctionType

from helper import endswith_any, safe_join
from config import Formats


def is_zip_path(path_or_url: str) -> bool:
    return endswith_any(
        path_or_url, Formats.zip_extensions)


def is_rar_path(path_or_url: str) -> bool:
    return endswith_any(
        path_or_url, Formats.rar_extensions)


def is_tar_path(path_or_url: str) -> bool:
    return endswith_any(
        path_or_url, Formats.tar_extensions)


def zip_or_rar_contains_matching_files(
        zip_path: Path,
        allowed_extensions: Iterable[str],
        file_open_func: FunctionType) -> bool:
    
    allowed = archive_internal_extensions(allowed_extensions)
    try:
        with file_open_func(zip_path, "r") as zf:
            for name in zf.namelist():
                if matching_allowed_extensions(name, allowed):
                    return True
    except zipfile.BadZipFile or rarfile.BadRarFile:
        return False
    return False


def extract_matching_files_from_zip_or_rar(
        path: Path,
        extract_dir: Path,
        allowed_extensions: Iterable[str],
        file_open_func: FunctionType) -> List[str]:

    extracted_paths: List[str] = []
    allowed = archive_internal_extensions(allowed_extensions)
    extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        with file_open_func(path, "r") as zf:
            for member in zf.infolist():
                if member.is_dir():
                    continue
                if not matching_allowed_extensions(member.filename, allowed):
                    continue

                target_path = safe_join(extract_dir, member.filename)
                target_path.parent.mkdir(parents=True, exist_ok=True)

                with zf.open(member) as src, open(target_path, "wb") as dst:
                    dst.write(src.read())

                extracted_paths.append(str(target_path))
    except zipfile.BadZipFile or rarfile.BadRarFile:
        return []

    return extracted_paths


def tar_contains_matching_files(
        tar_path: Path,
        allowed_extensions: Iterable[str]) -> bool:
    
    allowed = archive_internal_extensions(allowed_extensions)
    try:
        with tarfile.open(tar_path, "r:*") as tf:
            for member in tf.getmembers():
                if member.isfile() and matching_allowed_extensions(member.name, allowed):
                    return True
    except tarfile.TarError:
        return False
    return False


def extract_matching_files_from_tar(
        tar_path: Path,
        extract_dir: Path,
        allowed_extensions: Iterable[str]) -> List[str]:

    extracted_paths: List[str] = []
    allowed = archive_internal_extensions(allowed_extensions)
    extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        with tarfile.open(tar_path, "r:*") as tf:
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                if not matching_allowed_extensions(member.name, allowed):
                    continue

                target_path = safe_join(extract_dir, member.name)
                target_path.parent.mkdir(parents=True, exist_ok=True)

                src = tf.extractfile(member)
                if src is None:
                    continue

                with src, open(target_path, "wb") as dst:
                    dst.write(src.read())

                extracted_paths.append(str(target_path))
    except tarfile.TarError:
        return []

    return extracted_paths


def matching_allowed_extensions(
        filename: str,
        allowed_extensions: Iterable[str]) -> List[str]:

    lower = filename.lower()
    return [
        ext for ext in allowed_extensions
        if ext.lower() != ".zip" and lower.endswith(ext.lower())
    ]


def archive_internal_extensions(allowed_extensions: Iterable[str]) -> Tuple[str, ...]:
    archive_exts = {ext.lower() for ext in Formats.archive_extensions}
    return tuple(
        ext for ext in allowed_extensions
        if ext.lower() not in archive_exts
    )


def archive_contains_matching_files(
        archive_path: Path,
        allowed_extensions: Iterable[str]) -> bool:

    path_str = str(archive_path).lower()

    if is_zip_path(path_str):
        return zip_or_rar_contains_matching_files(archive_path, allowed_extensions, zipfile.ZipFile)
    
    if is_rar_path(path_str):
        return zip_or_rar_contains_matching_files(archive_path, allowed_extensions, rarfile.RarFile)

    if is_tar_path(path_str):
        return tar_contains_matching_files(archive_path, allowed_extensions)
    
    return False


def extract_matching_files_from_archive(
        archive_path: Path,
        extract_dir: Path,
        allowed_extensions: Iterable[str]) -> List[str]:

    path_str = str(archive_path).lower()

    if is_zip_path(path_str):
        return extract_matching_files_from_zip_or_rar(archive_path,
                                                      extract_dir,
                                                      allowed_extensions,
                                                      zipfile.ZipFile)
    
    if is_zip_path(path_str):
        return extract_matching_files_from_zip_or_rar(archive_path,
                                                      extract_dir,
                                                      allowed_extensions,
                                                      rarfile.RarFile)

    if is_tar_path(path_str):
        return extract_matching_files_from_tar(archive_path, extract_dir, allowed_extensions)
    return []


def detect_contained_file_types(
        extracted_paths: List[str],
        allowed_extensions: Iterable[str]) -> List[str]:

    archive_exts = {ext.lower() for ext in Formats.archive_extensions}
    detected: Set[str] = set()

    for path in extracted_paths:
        lower_path = path.lower()
        for ext in allowed_extensions:
            if ext.lower() in archive_exts:
                continue
            if lower_path.endswith(ext.lower()):
                detected.add(ext)

    return sorted(detected, key=lambda x: (len(x), x))
