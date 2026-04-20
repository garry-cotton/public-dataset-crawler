from crawler.main import main
from crawler.config import CrawlConfig

test_defaults = CrawlConfig(
    config_url="https://example.com/test-sheet",
    gid="0",
    limit_sites=1,
    max_pages_per_site=5,
    download_dir="test_downloads")

SystemExit(main())