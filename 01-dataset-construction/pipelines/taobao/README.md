# Taobao/Tmall Pipeline

> PVTT Dataset Construction - Taobao/Tmall Data Collection

## Platform Overview

| Field | Details |
|-------|---------|
| **Platform** | Taobao/Tmall (淘宝/天猫) |
| **Status** | Planned |
| **Collection Method** | 3rd party data service (China local vendors) |
| **Priority** | P2 (highest quality videos, requires budget) |
| **Estimated Cost** | CNY 100-250 (~$15-35) for 500+ products |

## Collection Method

### Primary: 3rd Party Data Service (Recommended)

Chinese local data service vendors offer the most reliable and cost-effective access to Taobao data:

- **Price**: CNY 0.01-0.05 per product record (bulk pricing)
- **Coverage**: Full data fields including video URLs
- **Compliance**: Vendors handle platform access; researchers purchase processed data
- **Budget estimate**: CNY 100-250 for 500+ products with complete metadata, images, and video URLs

### Why NOT Self-Scraping

Taobao has the most aggressive anti-bot system among all platforms evaluated:

| Mechanism | Severity | Details |
|-----------|----------|---------|
| Behavioral fingerprinting | Extreme | Mouse trajectory, scroll patterns, click intervals analyzed by AI |
| Dynamic signatures | Extreme | Cookie expires every ~10 minutes, API signatures rotate frequently |
| IP detection | Extreme | Ultra-low frequency threshold, data center IPs instantly blocked |
| Slider/CAPTCHA | High | Triggered at very low request rates |
| Login gating | High | Most product details and videos require login |

**Tested and failed**:
- `requests` / `curl_cffi`: Signature validation fails immediately
- `DrissionPage` / `Selenium`: Cookie expires too fast, constant re-login needed
- Full anti-detection browser + proxy pool + CAPTCHA solver needed for any scale

### Why NOT Official API

**Taobao Open Platform** (https://open.taobao.com/):
- Requires **business license** (企业资质) -- individual/academic developers cannot get product data API access
- International version (https://open.taobao.global/) has lower registration barrier but limited data scope
- API calls are free once approved, but approval is the bottleneck
- No academic research program available

### Alternative: Paid Scraping Services

| Service | Price | Notes |
|---------|-------|-------|
| Oxylabs Taobao Scraper API | $49/month ($1.6/1K results) | Product details, images, pricing |
| ZenRows | Custom pricing | Taobao-specific scraper |
| Crawlbase | Custom pricing | CAPTCHA bypass, proxy rotation |
| RapidAPI | Per-call pricing | Taobao/Tmall Scraper V2 |
| Apify | **Deprecated** (Taobao Tmall Scraper Pro taken down) | No longer available |

## Data Format

Output must conform to the unified PVTT data format:

```
taobao_data/
  {category}/                        # bracelet, earring, handbag, necklace, ring, sunglasses, watch
    {PRODUCT_ID}.json                # Product metadata
    media/
      images/
        {PRODUCT_ID}_01.jpg
        {PRODUCT_ID}_02.jpg
        ...
      videos/
        {PRODUCT_ID}.mp4
```

### Metadata JSON

```json
{
  "product_id": "TB_XXXXXXXXXXXX",
  "platform": "taobao",
  "title": "产品标题 / Product Title",
  "category": "necklace",
  "price": "199.00",
  "currency": "CNY",
  "brand": "品牌名",
  "rating": 4.8,
  "review_count": 5678,
  "url": "https://item.taobao.com/item.htm?id=XXXXXXXXXXXX",
  "images": [
    "media/images/TB_XXXXXXXXXXXX_01.jpg",
    "media/images/TB_XXXXXXXXXXXX_02.jpg"
  ],
  "videos": [
    "media/videos/TB_XXXXXXXXXXXX.mp4"
  ],
  "has_video": true,
  "scrape_date": "2026-03-14",
  "metadata": {
    "shop_name": "店铺名称",
    "monthly_sales": 2345,
    "material": "925纯银",
    "tmall": true
  }
}
```

## Estimated Data Volume

| Category | Est. Products | Est. Videos | Notes |
|----------|--------------|-------------|-------|
| bracelet | 80+ | 65+ | Very high video rate |
| earring | 80+ | 65+ | Professional model videos |
| handbag | 60+ | 50+ | High quality brand videos |
| necklace | 80+ | 65+ | 360-degree display common |
| ring | 60+ | 50+ | Detail close-ups |
| sunglasses | 60+ | 50+ | Model wearing videos |
| watch | 80+ | 65+ | Brand flagship stores |
| **Total** | **500+** | **410+** | |

**Video coverage**: ~70-80% (jewelry/accessories category has near-universal main video)
**Video quality**: 1080p MP4, professionally produced, model wearing demonstrations
**Video duration**: 15-60 seconds, product showcase style
**Video style**: 360-degree rotation, wearing demos, detail close-ups -- ideal for PVTT template transfer

## Why Taobao Data is Valuable for PVTT

1. **Highest video quality** across all evaluated platforms
2. **Professional production**: Standard white-background images + scene images + model videos
3. **Jewelry specialization**: Chinese e-commerce has the most developed jewelry video ecosystem
4. **Video style match**: Product showcase videos (rotation, wearing, close-up) are exactly what PVTT needs for template transfer
5. **Landscape orientation**: 16:9 horizontal videos (unlike TikTok's 9:16), directly usable for PVTT
6. **Chinese language data**: Adds bilingual diversity to the dataset (reviewer bonus for cross-lingual generalization)

## Legal Considerations

- **Chinese Data Protection Laws**: Strictly protected by Cybersecurity Law, Data Security Law, and Personal Information Protection Law
- **Taobao TOS**: Explicitly prohibits unauthorized scraping
- **Academic exemption**: Less clear than US Fair Use doctrine
- **Recommended approach**: Purchase data through compliant 3rd party services to avoid direct scraping risks
- **Paper compliance**: Clearly annotate data source and academic-only usage in publications

## Next Steps

1. Complete Amazon data expansion first (P0 priority)
2. Research and contact Chinese local data service vendors for quotes
3. Request sample data (10-20 products) to validate quality and format
4. If quality meets requirements, purchase 500+ products across all categories
5. Build format conversion script to match unified PVTT data format
6. Can potentially bundle with JD.com (京东) data from same vendor for additional coverage
