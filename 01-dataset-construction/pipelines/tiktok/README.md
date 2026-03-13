# TikTok Shop Pipeline

> PVTT Dataset Construction - TikTok Shop Data Collection

## Platform Overview

| Field | Details |
|-------|---------|
| **Platform** | TikTok Shop |
| **Status** | Planned |
| **Collection Method** | Apify TikTok Shop Scraper (3rd party service) |
| **Priority** | P1 (low cost, high video coverage) |
| **Estimated Cost** | ~$2/1000 products (Apify free tier covers ~2500 products) |

## Collection Method

### Primary: Apify TikTok Shop Scraper

- **Service**: [Apify TikTok Shop Scraper](https://apify.com/store)
- **Pricing**: $2/1000 results (pay-per-result) or $20/month flat
- **Alternative**: sovereigntaylor variant at $1.80/1000 products
- **Free tier**: $5/month credit (~2500 products)
- **Data fields**: Title, price, discount, sales count, rating, images, variants, seller info

### Alternative Methods

1. **TikTok Research API** (academic channel)
   - Free for US/EU non-profit universities
   - Requires faculty endorsement letter
   - Supports querying TikTok Shop product and shop info
   - Apply at: https://developers.tiktok.com/products/research-api/
   - Note: Researchers report incomplete/inconsistent data delivery (SAGE 2025)

2. **Bright Data TikTok Scraper**: $2.50/1000 requests (more stable, built-in anti-bot bypass)

3. **Direct scraping** (not recommended)
   - Encrypted request headers require reverse engineering
   - Real-time fraud scoring system detects automation
   - Must use US residential proxies
   - Signature algorithms change frequently

## Anti-Bot Protection

| Mechanism | Severity | Notes |
|-----------|----------|-------|
| Encrypted headers | High | Custom encryption, needs reverse engineering |
| Behavioral detection | High | Real-time fraud scoring |
| IP restrictions | High | Data center IPs blocked, US residential proxy required |
| Regional restrictions | Medium | TikTok Shop US requires US IP |

**Conclusion**: Self-scraping is impractical. Apify or Bright Data is the recommended approach.

## Data Format

Output must conform to the unified PVTT data format:

```
tiktok_data/
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
  "product_id": "TT_XXXXXXXX",
  "platform": "tiktok",
  "title": "Product Title",
  "category": "bracelet",
  "price": "19.99",
  "currency": "USD",
  "brand": "Seller Name",
  "rating": 4.7,
  "review_count": 456,
  "url": "https://shop.tiktok.com/...",
  "images": ["media/images/TT_XXXXXXXX_01.jpg"],
  "videos": ["media/videos/TT_XXXXXXXX.mp4"],
  "has_video": true,
  "scrape_date": "2026-03-14",
  "metadata": {
    "sold_count": 1200,
    "discount_percentage": 30,
    "shop_name": "Shop Name",
    "shop_rating": 4.8
  }
}
```

## Estimated Data Volume

| Category | Est. Products | Est. Videos | Notes |
|----------|--------------|-------------|-------|
| bracelet | 50+ | 45+ | Popular category on TikTok Shop |
| earring | 50+ | 45+ | High engagement |
| handbag | 40+ | 35+ | Fashion category |
| necklace | 50+ | 45+ | Popular |
| ring | 40+ | 35+ | Growing category |
| sunglasses | 40+ | 35+ | Seasonal peaks |
| watch | 30+ | 25+ | Moderate volume |
| **Total** | **300+** | **265+** | |

**Video coverage**: ~90%+ (TikTok is natively a video platform)
**Video quality**: 720p-1080p, short-form style (9:16 portrait orientation)
**Video duration**: 15-60 seconds

## Important Notes

- TikTok videos are predominantly **portrait (9:16)** orientation -- post-processing crop/resize needed for PVTT
- Video style leans toward influencer/sales content rather than traditional product showcase
- Jewelry is a hot category on TikTok Shop (GMV $1.2B in 2025, +94% YoY)
- 2026 update: US TikTok operations transferred to USDS joint venture (Oracle-managed), data access policies may change

## Legal Considerations

- Public data scraping is generally legal in the US (hiQ v. LinkedIn precedent)
- TikTok TOS prohibits unauthorized automated access
- Using Apify (3rd party service) reduces direct legal exposure
- Academic research purpose provides additional protection
- Recommend applying for TikTok Research API for full compliance

## Next Steps

1. Register Apify free account
2. Test TikTok Shop Scraper with 50-100 products using free credits
3. Validate video quality and relevance for PVTT
4. If successful, expand to 300+ products across all categories
5. Build post-processing script for portrait-to-landscape conversion
