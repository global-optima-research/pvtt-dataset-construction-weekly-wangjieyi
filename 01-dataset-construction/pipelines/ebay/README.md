# eBay Pipeline

> PVTT Dataset Construction - eBay Data Collection

## Platform Overview

| Field | Details |
|-------|---------|
| **Platform** | eBay |
| **Status** | Planned |
| **Collection Method** | eBay Browse API (official, free) |
| **Priority** | P1 (free API, immediate access) |
| **Estimated Cost** | $0 (fully free API) |

## Collection Method

### Primary: eBay Browse API

- **Documentation**: https://developer.ebay.com/api-docs/buy/browse/overview.html
- **Cost**: Completely free
- **Registration**: Free eBay Developer Program account
- **Authentication**: OAuth 2.0 (Client Credentials Grant for public data)
- **Rate limits**:
  - Default: 5,000 requests/day
  - After Application Growth Check (free): up to 1.5 million requests/day
  - No documented QPS limit (but use reasonable intervals)

### Key API Endpoints

| Endpoint | Purpose | Notes |
|----------|---------|-------|
| `search` | Search items by keyword/category | Main discovery endpoint |
| `searchByImage` | Reverse image search | Find similar products |
| `getItem` | Get item details | Full product info |
| `getItemsByItemGroup` | Get item variants | Group items |

### Data Available via API

- Listing title, description, price, category, condition
- Images: `imageUrl` with `height`/`width` (full resolution)
- Seller info, ratings, review counts
- Item specifics (brand, material, etc.)
- Use `fieldgroups` parameter (COMPACT/PRODUCT) to control response detail

### Video Limitations

- Browse API does **not directly return video URLs** in the response
- Videos must be parsed from the item description HTML
- eBay Media API exists but is primarily for **seller-side** upload/management, not buyer-side batch download
- Workaround: Parse `getItem` description field for embedded video elements

### Alternative Methods

- **curl_cffi**: Can fetch some data directly from web pages
- **Playwright**: Needed for search results pages (JS-rendered)
- **Bright Data**: $1.50/1000 requests (unnecessary given free API)

## Anti-Bot Protection

| Mechanism | Severity | Notes |
|-----------|----------|-------|
| JavaScript rendering | Medium | Search pages need JS execution |
| Rate limiting | Low | Temporary blocks on high frequency |
| CAPTCHA | None | No strong CAPTCHA (no Datadome/Akamai) |

**Conclusion**: eBay's anti-bot is mild. The official Browse API is the best approach -- free, stable, fully supported.

## Data Format

Output must conform to the unified PVTT data format:

```
ebay_data/
  {category}/                        # bracelet, earring, handbag, necklace, ring, sunglasses, watch
    {PRODUCT_ID}.json                # Product metadata
    media/
      images/
        {PRODUCT_ID}_01.jpg
        {PRODUCT_ID}_02.jpg
        ...
      videos/
        {PRODUCT_ID}.mp4             # If available (rare for jewelry)
```

### Metadata JSON

```json
{
  "product_id": "EBAY_XXXXXXXXXXXX",
  "platform": "ebay",
  "title": "Product Title",
  "category": "bracelet",
  "price": "34.99",
  "currency": "USD",
  "brand": "Brand Name",
  "rating": null,
  "review_count": null,
  "url": "https://www.ebay.com/itm/XXXXXXXXXXXX",
  "images": ["media/images/EBAY_XXXXXXXXXXXX_01.jpg"],
  "videos": [],
  "has_video": false,
  "scrape_date": "2026-03-14",
  "metadata": {
    "condition": "New",
    "seller": "seller_username",
    "seller_feedback_score": 9876,
    "item_specifics": {
      "Material": "Sterling Silver",
      "Style": "Chain"
    }
  }
}
```

## Estimated Data Volume

| Category | Est. Products | Est. Videos | Notes |
|----------|--------------|-------------|-------|
| bracelet | 30+ | 3-5 | Low video rate for jewelry |
| earring | 30+ | 2-4 | Mostly individual sellers |
| handbag | 30+ | 5-8 | Slightly more videos |
| necklace | 30+ | 3-5 | |
| ring | 30+ | 2-4 | |
| sunglasses | 25+ | 3-5 | Brand items may have videos |
| watch | 25+ | 5-8 | Watch sellers more likely to add videos |
| **Total** | **200+** | **23-39** | |

**Video coverage**: ~10-20% overall, ~5-10% for jewelry specifically
**Video quality**: Variable (seller-uploaded, non-standardized)
**Image quality**: Medium (seller-uploaded, inconsistent)

## Important Notes

- eBay jewelry listings are heavily **secondhand/vintage/collectible** -- different from Amazon's new retail products
- Video rate is very low for jewelry category
- **Primary value is as an image data supplement**, not a video source
- Image quality varies significantly between sellers
- Browse API is the most cost-effective entry point (completely free)
- 5,000 requests/day is sufficient for hundreds of products; Growth Check enables 1.5M/day

## Legal Considerations

- eBay API License Agreement explicitly allows developer access to data via API
- API usage is **fully compliant**
- Direct web scraping should respect robots.txt
- Academic research usage carries very low legal risk
- Must comply with data protection regulations (GDPR for EU listings)

## Next Steps

1. Register eBay Developer Program account (free): https://developer.ebay.com/
2. Create application and obtain API keys
3. Apply for Application Growth Check (free) to increase rate limits
4. Build Browse API client targeting jewelry categories
5. Implement image download pipeline matching unified data format
6. Parse item descriptions for embedded videos where available
