# PVTT Dataset Construction - Directory Structure Plan

> Status: PLANNED (not yet reorganized)
> Date: 2026-03-14
> Note: Do NOT reorganize while Amazon spider is actively running.

## Current Structure (as of 2026-03-14)

```
01-dataset-construction/
  README.md                          # Project overview and pipeline docs
  DIRECTORY_STRUCTURE.md             # This file (reorganization plan)

  # Active spider + data (DO NOT MOVE)
  amazon_spider.py                   # Amazon product spider (ACTIVE)
  amazon_data/                       # Amazon collected data (ACTIVE, spider writing)

  # Platform spiders
  etsy_spider.py                     # Etsy spider (blocked by Datadome)
  etsy_data/                         # Etsy data (small, blocked)

  # Tools
  pvtt_pipeline.py                   # Main orchestrator pipeline
  upload_to_server.py                # Upload data to server
  generate_dataset_report.py         # Report generator
  generate_charts.py                 # Chart generator for reports
  build_notebook.py                  # Notebook/report builder

  # Reports
  platform_analysis_report.md        # Multi-platform analysis (12 platforms)
  pvtt_dataset_report.html           # Dataset report (HTML)
  pvtt_dataset_report.md             # Dataset report (Markdown)

  # Server
  server-scripts/                    # Server-side processing scripts

  # Legacy
  ecommerce-scraper/                 # Old pipeline version (deprecated)
  data_pipeline.py                   # Old/duplicate pipeline script
  launch_spider.py                   # Old spider launcher
  __pycache__/                       # Python cache
```

## Planned Structure (post-reorganization)

```
01-dataset-construction/
  README.md                          # Updated project overview
  DIRECTORY_STRUCTURE.md             # This file

  pipelines/                         # Platform-specific collection pipelines
    amazon/
      amazon_spider.py               # Amazon product spider
      README.md                      # Amazon pipeline docs
    etsy/
      etsy_spider.py                 # Etsy spider (blocked by Datadome)
      README.md                      # Etsy pipeline docs
    tiktok/
      README.md                      # TikTok Shop pipeline (planned, Apify)
    ebay/
      README.md                      # eBay pipeline (planned, Browse API)
    taobao/
      README.md                      # Taobao pipeline (planned, 3rd party)

  data/                              # All collected data
    amazon/                          # Amazon data (from amazon_data/)
    etsy/                            # Etsy data (from etsy_data/)
    tiktok/                          # TikTok Shop data (planned)
    ebay/                            # eBay data (planned)
    taobao/                          # Taobao data (planned)

  tools/                             # Shared pipeline tools
    pvtt_pipeline.py                 # Main orchestrator
    upload_to_server.py              # Server upload utility
    generate_dataset_report.py       # Report generator
    generate_charts.py               # Chart generator
    build_notebook.py                # Notebook builder

  reports/                           # All generated reports
    platform_analysis_report.md      # Platform analysis report
    pvtt_dataset_report.html         # Dataset report (HTML)
    pvtt_dataset_report.md           # Dataset report (Markdown)

  server-scripts/                    # Server-side scripts (unchanged)

  _archive/                          # Deprecated files
    ecommerce-scraper/               # Old pipeline version
    data_pipeline.py                 # Old duplicate pipeline
    launch_spider.py                 # Old launcher
```

## Unified Data Format

All platform pipelines should output data in the following unified format:

```
{platform}_data/
  {category}/                        # e.g., bracelet, earring, handbag, necklace, ring, sunglasses, watch
    {PRODUCT_ID}.json                # Product metadata (JSON)
    media/
      images/
        {PRODUCT_ID}_01.jpg          # Product image 1
        {PRODUCT_ID}_02.jpg          # Product image 2
        ...
      videos/
        {PRODUCT_ID}.mp4             # Product video
```

### Metadata JSON Schema

Each `{PRODUCT_ID}.json` should contain:

```json
{
  "product_id": "B0XXXXXX",
  "platform": "amazon",
  "title": "Product Title",
  "category": "bracelet",
  "price": "29.99",
  "currency": "USD",
  "brand": "Brand Name",
  "rating": 4.5,
  "review_count": 123,
  "url": "https://www.amazon.com/dp/B0XXXXXX",
  "images": [
    "media/images/B0XXXXXX_01.jpg",
    "media/images/B0XXXXXX_02.jpg"
  ],
  "videos": [
    "media/videos/B0XXXXXX.mp4"
  ],
  "has_video": true,
  "scrape_date": "2026-03-14",
  "metadata": {}
}
```

## Migration Steps

When the Amazon spider finishes running:

1. Create the new directory structure (`pipelines/`, `data/`, `tools/`, `reports/`, `_archive/`)
2. Move `amazon_spider.py` to `pipelines/amazon/`
3. Move `amazon_data/` to `data/amazon/`
4. Move `etsy_spider.py` to `pipelines/etsy/`
5. Move `etsy_data/` to `data/etsy/`
6. Move tool scripts to `tools/`
7. Move report files to `reports/`
8. Move deprecated files to `_archive/`
9. Update all import paths and file references in scripts
10. Update `pvtt_pipeline.py` paths
11. Test that all scripts work with new paths
12. Delete `__pycache__/`

## Platform Pipeline Status

| Platform | Status | Method | Pipeline File | Data Dir |
|----------|--------|--------|---------------|----------|
| Amazon | **In Progress** | Custom spider (requests + residential IP) | `amazon_spider.py` | `amazon_data/` |
| Etsy | **Blocked** | Blocked by Datadome CAPTCHA | `etsy_spider.py` | `etsy_data/` |
| TikTok Shop | **Planned** | Apify TikTok Shop Scraper ($2/1K) | - | - |
| eBay | **Planned** | eBay Browse API (free) | - | - |
| Taobao | **Planned** | 3rd party data service | - | - |
