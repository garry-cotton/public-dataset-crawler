from dataclasses import dataclass
from typing import Optional

@dataclass
class CrawlConfig:
    config_url: str = "https://docs.google.com/spreadsheets/d/1bTd3OUsUz4t08nb-ZZEBy5L_3E8ZnFK_2L8KBlnq9l0/"
    workbook: Optional[str] = None
    sheet: str = "DataRepo1"
    gid: Optional[str] = "0"
    output_csv: str = "discovered_datasets.csv"
    download_dir: str = "crawler_downloads"
    max_pages_per_site: int = 150
    max_depth: int = 3
    limit_sites: int = 0
    playwright_fallback: bool = True
    playwright_browser: str = "chromium"
    playwright_wait_ms: int = 2500
    shutdown_on_completion: bool = False
    show_browser: bool = False


@dataclass(frozen=True)
class Defaults:
    user_agent: str = "Mozilla/5.0 (compatible; GeneralizedDatasetCrawler/1.2; +https://example.invalid)"
    request_timeout: int = 30
    download_chunk_size: int = 1024 ** 2
    crawl_sleep_seconds: float = 0.2


@dataclass(frozen=True)
class Settings:
    export_url = "https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={resolved_gid}"
    

@dataclass(frozen=True)
class WebConfig:
    candidate_keywords = [
        "download",
        "data",
        "dataset",
        "export",
        "file",
        "resource",
        "csv",
        "tsv",
        "json",
        "zip"]
    js_markers = ["__next",
        "window.__",
        "react",
        "vue",
        "angular",
        "app-root",
        'id="root"',
        'id="app"']


@dataclass(frozen=True)
class Formats:
    extension_map = {
        "csv": [".csv"],
        "tsv": [".tsv"],
        "json": [".json"],
        "xml": [".xml"],
        "zip": [".zip"],
        "gzip": [".gz", ".gzip", ".tgz"],
        "tar": [".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz"],
        "parquet": [".parquet"],
        "feather": [".feather"],
        "arrow": [".arrow"],
        "sqlite": [".sqlite", ".sqlite3", ".db"],
        "fixed-width": [".dat", ".txt", ".fwf"],
        "excel": [".xls", ".xlsx", ".xlsm"],
        "hdf5": [".h5", ".hdf5", ".hdf"],
        "hdf": [".h5", ".hdf5", ".hdf"],
        "gct": [".gct", ".gctx"],
        "mat": [".mat"],
        "numpy": [".npy", ".npz"],
        "npy": [".npy"],
        "npz": [".npz"],
        "nifti": [".nii", ".nii.gz", ".nifti"],
        "bids": [".nii", ".nii.gz", ".json", ".tsv", ".bval", ".bvec", ".bids"],
        "netcdf": [".nc", ".netcdf"],
        "grib": [".grib", ".grib2"],
        "msp": [".msp"],
        "txt": [".txt"],
        "fasta": [".fasta", ".fa", ".fna", ".ffn"],
        "fastq": [".fastq", ".fq", ".fastq.gz", ".fq.gz"],
    }

    content_type_extension_map = {
        "text/csv": [".csv"],
        "text/tab-separated-values": [".tsv"],
        "application/json": [".json"],
        "application/zip": [".zip"],
        "application/x-zip-compressed": [".zip"],
        "application/gzip": [".gz"],
        "application/x-gzip": [".gz"],
        "application/x-hdf5": [".h5", ".hdf5"],
        "application/x-netcdf": [".nc"],
        "application/x-sqlite3": [".sqlite", ".sqlite3", ".db"],
        "application/vnd.ms-excel": [".xls"],
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
        "application/octet-stream": [],
    }

    ignored_format_tokens = {
        "",
        "sparse matrix"
    }

    zip_extensions = {
        ".zip"
    }

    rar_extensions = {
        ".rar"
    }

    tar_extensions = {
        ".zip",
        ".tar",
        ".tar.gz",
        ".tgz",
        ".tar.bz2",
        ".tbz2",
        ".tar.xz"
    }

    compound_suffixes = {
        ".tar.gz",
        ".tar.bz2",
        ".tar.xz",
        ".nii.gz",
        ".fastq.gz",
        ".fq.gz"
    }

    archive_extensions = zip_extensions.union(tar_extensions)
