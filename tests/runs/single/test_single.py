
from crawler.main import parse_args, run
from crawler.config import CrawlConfig

test_defaults = CrawlConfig(
    config_url="tests/runs/single/HCDA - REAL DATA GATHERING.xlsx",
    limit_sites=1,
    max_pages_per_site=5,
    download_dir="test_downloads")

args = parse_args(defaults=test_defaults)
cfg = CrawlConfig(**vars(args))
exit_code = run(cfg=cfg)
