#!/usr/bin/env python3
"""
Generalized public dataset crawler driven by either:
- an Excel workbook, or
- a public Google Sheet URL

Config source expectations:
Excel sheet / Google Sheet tab columns:
- A: Data Category
- B: Data Repository
- C: URL
- F: Common Formats (comma-delimited)

For each site, the crawler:
1. Crawls public HTML pages under the same host/domain.
2. Detects candidate dataset files using configured extensions and lightweight heuristics.
3. Optionally falls back to Playwright for JavaScript-rendered pages.
4. Downloads each dataset file it finds.
5. Downloads the HTML page that contained the direct link as a "document" file.
6. Writes a CSV manifest with one row per discovered dataset.

Dependencies:
    pip install requests beautifulsoup4 openpyxl lxml playwright
    playwright install chromium

Examples:
    python generalized_dataset_crawler.py \
        --workbook "HCDA - REAL DATA GATHERING.xlsx" \
        --sheet DataRepo1 \
        --output-csv discovered_datasets.csv \
        --download-dir ./downloads

    python generalized_dataset_crawler.py \
        --config-url "https://docs.google.com/spreadsheets/d/.../edit?gid=1045935102#gid=1045935102" \
        --output-csv discovered_datasets.csv \
        --download-dir ./downloads

Notes on Google Sheets:
- This supports public Google Sheet URLs only.
- It accepts common URL shapes such as:
    * /edit
    * /edit#gid=...
    * /edit?gid=...
    * /view
    * /export?format=csv&gid=...
- If a gid is present, that specific tab is used.
- If no gid is present, Google will export the default/first sheet tab.
"""


from __future__ import annotations

import argparse
import os

from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .config import CrawlConfig
from .web.func import create_session, process_site
from .web.playwright import PlaywrightRenderer
from .io import load_site_configs, write_csv


def run(cfg: CrawlConfig) -> int:

    output_csv_path = Path(cfg.output_csv)
    download_root = Path(cfg.download_dir)

    session = create_session()
    configs = load_site_configs(
        workbook=cfg.workbook or None,
        config_url=cfg.config_url or None,
        sheet_name=cfg.sheet,
        gid=cfg.gid or None,
        session=session,
    )
    if cfg.limit_sites > 0:
        configs = configs[: cfg.limit_sites]

    renderer = PlaywrightRenderer(
        enabled=cfg.playwright_fallback,
        browser=cfg.playwright_browser,
        wait_ms=cfg.playwright_wait_ms,
        headless=not cfg.show_browser,
    )
    all_rows: List[Dict[str, str]] = []

    try:
        if cfg.playwright_fallback and not renderer.available():
            print("[warn] Playwright fallback requested, "
                  "but Playwright is not installed or unavailable. "
                  "Continuing without it.")

        for idx, site in enumerate(configs, start=1):
            print(f"[{idx}/{len(configs)}] Crawling {site.repository} "
                  f"({site.start_url}) with extensions {site.extensions}")
            try:
                rows = process_site(
                    session=session,
                    site=site,
                    download_root=download_root,
                    max_pages_per_site=cfg.max_pages_per_site,
                    max_depth=cfg.max_depth,
                    renderer=renderer,
                    use_playwright_fallback=cfg.playwright_fallback,
                )
                print(f"    Found {len(rows)} candidate datasets".ljust(140),
                      end="\n",
                      flush=True)
                all_rows.extend(rows)
            except Exception as exc:
                print(f"    [warn] Site failed: {exc}")
    finally:
        renderer.close()

    write_csv(all_rows, output_csv_path)
    print(f"[done] Wrote {len(all_rows)} rows to {output_csv_path.resolve()}")
    return 0


def parse_args(
        argv: Optional[Sequence[str]] = None,
        defaults: Optional[CrawlConfig] = None) -> CrawlConfig:
    
    defaults = defaults or CrawlConfig()

    parser = argparse.ArgumentParser(
        description="Generic public dataset crawler driven by Excel or public Google Sheets.")
    parser.add_argument(
        "--workbook",
        default=defaults.workbook,
        help="Path to the Excel workbook, or a public Google Sheet URL.")
    parser.add_argument(
        "--config-url",
        default=defaults.config_url,
        help="Public Google Sheet URL to use as the configuration source.")
    parser.add_argument(
        "--sheet",
        default=defaults.sheet,
        help=f"Worksheet name to read for Excel input. Default: {defaults.sheet}")
    parser.add_argument(
        "--gid",
        default=defaults.gid,
        help="Optional Google Sheet gid (tab ID). Overrides --sheet for Google Sheets.")
    parser.add_argument(
        "--output-csv",
        default=defaults.output_csv,
        help="Path to output CSV manifest.")
    parser.add_argument(
        "--download-dir",
        default=defaults.download_dir,
        help="Directory for downloaded files and document pages.")
    parser.add_argument(
        "--max-pages-per-site",
        type=int,
        default=defaults.max_pages_per_site,
        help="Maximum number of HTML pages to crawl per site.")
    parser.add_argument(
        "--max-depth",
        type=int,
        default=defaults.max_depth,
        help="Maximum crawl depth per site.")
    parser.add_argument(
        "--limit-sites",
        type=int,
        default=defaults.limit_sites,
        help="If > 0, only process the first N configured sites.")
    parser.add_argument(
        "--playwright-fallback",
        action="store_true",
        default=defaults.playwright_fallback,
        help="Use Playwright when requests-only fetches look too sparse or JS-heavy.")
    parser.add_argument(
        "--playwright-browser",
        default=defaults.playwright_browser,
        choices=["chromium", "firefox", "webkit"],
        help="Browser engine for Playwright.")
    parser.add_argument(
        "--playwright-wait-ms",
        type=int,
        default=defaults.playwright_wait_ms,
        help="Extra wait after page load in Playwright mode.")
    parser.add_argument(
        "--show-browser",
        action="store_true",
        default=defaults.show_browser,
        help="Show the Playwright browser window instead of running headless.")
    parser.add_argument(
        "--shutdown-on-completion",
        action="store_true",
        default=defaults.shutdown_on_completion,
        help="Shutdown the machine on completion of the crawl.")
    args = parser.parse_args(argv)
    return CrawlConfig(**vars(args))


def main(argv: Optional[Sequence[str]] = None) -> int:
    defaults = CrawlConfig()
    args = parse_args(argv, defaults)
    cfg = CrawlConfig(**vars(args))
    
    try:
        exit_code = run(cfg=cfg)
    except KeyboardInterrupt:
        return 130
    
    # Shutdown the machine after completing the task if required.
    if args.shutdown_on_completion:
        os.system("shutdown /s /t 30")

    return exit_code

if __name__ == "__main__":
    SystemExit(main())
