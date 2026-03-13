# PVTT Dataset Construction

> Product Video Template Transfer (PVTT) - Multi-Platform E-Commerce Dataset Collection
> Target: CVPR 2027
> Last updated: 2026-03-14

## Overview

This module handles the collection, processing, and curation of e-commerce product video data for the PVTT project. The goal is to build a large-scale dataset of product showcase videos and images across multiple categories (jewelry, accessories) from multiple e-commerce platforms.

**Target scale**: 1000+ products, 500+ videos across 7 categories and 5+ platforms.

## Current Status (2026-03-14)

### Data Collected

| Platform | Products | Images | Videos | Size | Status |
|----------|----------|--------|--------|------|--------|
| **Amazon** | 603+ | 3,304+ | 593+ | 3.8 GB | **Active** (spider running, expanding to 800+) |
| **Etsy** | small | small | 0 | ~MB | Blocked (Datadome CAPTCHA) |
| **TikTok Shop** | - | - | - | - | Planned |
| **eBay** | - | - | - | - | Planned |
| **Taobao** | - | - | - | - | Planned |

### Amazon Data Breakdown

7 categories: bracelet (133), earring (127+), handbag (38+), necklace (122), ring (62+), sunglasses (64+), watch (57+)
*(Spider still running — expanding handbag, sunglasses, watch, ring with additional keywords)*

### Server Pipeline

Full processing pipeline tested: 53 videos -> 87 clips -> 87 standardized (1280x720, 24fps, H.264)
- Server: `wangjieyi@111.17.197.107` (RTX-5090-32G-X8)
- Data location: `/data/wangjieyi/pvtt-dataset/amazon_data/`

## Directory Structure

See [DIRECTORY_STRUCTURE.md](DIRECTORY_STRUCTURE.md) for the full planned reorganization.

### Current Layout

```
01-dataset-construction/
  README.md                          # This file
  DIRECTORY_STRUCTURE.md             # Planned directory reorganization

  # === Active Spider (DO NOT MOVE while running) ===
  amazon_spider.py                   # Amazon product spider
  amazon_data/                       # Amazon collected data (active)

  # === Platform Spiders ===
  etsy_spider.py                     # Etsy spider (blocked by Datadome)
  etsy_data/                         # Etsy data

  # === Pipeline Documentation ===
  pipelines/
    tiktok/README.md                 # TikTok Shop pipeline (planned, Apify)
    ebay/README.md                   # eBay pipeline (planned, Browse API)
    taobao/README.md                 # Taobao pipeline (planned, 3rd party)

  # === Tools ===
  pvtt_pipeline.py                   # Main orchestrator (crawl -> upload -> process -> report -> push)
  upload_to_server.py                # Upload data to RTX-5090 server
  generate_dataset_report.py         # Generate dataset reports
  generate_charts.py                 # Generate charts for reports
  build_notebook.py                  # Build report notebooks

  # === Reports ===
  platform_analysis_report.md        # 12-platform analysis report
  pvtt_dataset_report.html           # Dataset report (HTML)
  pvtt_dataset_report.md             # Dataset report (Markdown)

  # === Server ===
  server-scripts/                    # Server-side processing scripts

  # === Legacy (to be archived) ===
  ecommerce-scraper/                 # Old pipeline version
  data_pipeline.py                   # Old duplicate pipeline
  launch_spider.py                   # Old spider launcher
```

## Platform Strategy

### Tier 1: Active / In Progress

| Platform | Method | Cost | Video Rate | Notes |
|----------|--------|------|------------|-------|
| **Amazon** | Custom spider (requests + residential IP) | Free | ~40-60% | Must run locally (server gets 503) |

### Tier 2: Planned (Next Steps)

| Platform | Method | Cost | Video Rate | Notes |
|----------|--------|------|------------|-------|
| **eBay** | Browse API (official, free) | Free | ~10-20% | Register dev account, mainly images |
| **TikTok Shop** | Apify Scraper | ~$2/1K products | ~90% | Portrait videos need crop/resize |
| **Etsy** | Open API v3 (images only) | Free | ~10-15% | Videos blocked by Datadome |

### Tier 3: Future (Budget Dependent)

| Platform | Method | Cost | Video Rate | Notes |
|----------|--------|------|------------|-------|
| **Taobao/Tmall** | 3rd party data service | CNY 100-250 | ~70-80% | Highest quality, landscape videos |
| **JD.com** | 3rd party (bundled with Taobao) | CNY 50-100 | ~50-60% | Brand flagship store videos |

### Not Recommended

| Platform | Reason |
|----------|--------|
| AliExpress | Akamai Bot Manager, high cost |
| Xiaohongshu | Legal compliance risk (Chinese data laws) |
| Pinduoduo | Low video quality, budget products |
| Shopee | Jewelry not a strong category |
| Walmart/Target | Brand official videos (not wearing demos) |

See [platform_analysis_report.md](platform_analysis_report.md) for the full 12-platform deep analysis.

## Unified Data Format

All platform pipelines must output data in this standardized format:

```
{platform}_data/
  {category}/                        # bracelet, earring, handbag, necklace, ring, sunglasses, watch
    {PRODUCT_ID}.json                # Product metadata (JSON)
    media/
      images/
        {PRODUCT_ID}_01.jpg          # Product images
        {PRODUCT_ID}_02.jpg
      videos/
        {PRODUCT_ID}.mp4             # Product video (if available)
```

See [DIRECTORY_STRUCTURE.md](DIRECTORY_STRUCTURE.md) for the full JSON schema specification.

## Key Scripts

| Script | Purpose |
|--------|---------|
| `amazon_spider.py` | Amazon product crawler (categories, images, videos, metadata) |
| `etsy_spider.py` | Etsy product crawler (blocked by Datadome) |
| `pvtt_pipeline.py` | Main pipeline orchestrator: crawl -> upload -> process -> report -> push |
| `upload_to_server.py` | Upload collected data to RTX-5090 server via SSH |
| `generate_dataset_report.py` | Generate dataset statistics and reports |
| `generate_charts.py` | Generate visualization charts for reports |
| `build_notebook.py` | Build Jupyter-style report notebooks |

## Execution Plan

### Phase 1: Amazon Expansion (Current)
- Expand Amazon data to 600+ products across 7 categories
- More keywords per category for diversity
- Spider running in background -- do not interrupt

### Phase 2: Free Platform APIs (Next)
- Register eBay Developer Program, build Browse API client
- Register Etsy developer account, collect images via API v3
- Register Apify free account, test TikTok Shop Scraper

### Phase 3: Paid Data Sources (Future)
- Contact Chinese data service vendors for Taobao/JD quotes
- Purchase 500+ products if budget approved
- Apply for TikTok Research API (needs faculty endorsement)

## Server Upload

Data is uploaded to the server for GPU-accelerated processing:

```bash
# Upload command (run from local)
python upload_to_server.py
# Target: /data/wangjieyi/pvtt-dataset/amazon_data/
```

Server processing pipeline: shot segmentation -> standardization (1280x720, 24fps, H.264)

## GitHub Repository

- Repo: `global-optima-research/pvtt-dataset-construction-weekly-wangjieyi`
- Branch: `main`
- Push: `git push origin main` (pull first if rejected)

## Technical Survey

The original technical survey covering the PVTT dataset construction pipeline (video preprocessing, segmentation, inpainting, composition, quality filtering) is preserved below for reference. It covers:

1. Video Preprocessing and Scene Segmentation (PySceneDetect, TransNetV2, AutoShot)
2. Video Object Segmentation (SAM2, Grounded-SAM2)
3. Video Inpainting and Background Recovery (VideoPainter, ProPainter)
4. Video Object Composition (VideoAnyDoor, InsertAnywhere, GenCompositor)
5. Data Quality Assessment and Filtering (CLIP-I, DINO-I, MUSIQ, DOVER, VBench)
6. E-Commerce Video Datasets (VACE, InsViE-1M, OpenVE-3M, VIVID-10M)
7. Recommended Pipeline Configuration

For the full technical survey, see the git history of this README (version prior to 2026-03-14).

---

*Document version: 2.0 (2026-03-14)*
*Previous version: 1.0 (2026-02-11) - Full technical survey*
