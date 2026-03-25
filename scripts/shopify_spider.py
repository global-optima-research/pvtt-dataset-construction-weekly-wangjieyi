#!/usr/bin/env python3
"""
Shopify Store Product Video & Image Spider
============================================
Collects product videos and images from Shopify independent stores for PVTT dataset.

Strategy:
  Shopify exposes /products.json (paginated, no auth required) for most stores.
  Products may contain images directly, and videos embedded in HTML descriptions
  or via the Storefront API media endpoint.

Usage:
  python shopify_spider.py --discover                    # find stores with videos
  python shopify_spider.py --store mystore.com --category necklace
  python shopify_spider.py --batch                       # crawl all known stores
  python shopify_spider.py --status                      # show progress
"""

import os
import re
import json
import time
import random
import logging
import argparse
import sys
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests

# ─── Config ──────────────────────────────────────────────────

BASE_OUTPUT = os.environ.get(
    "SPIDER_OUTPUT",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shopify_data"),
)

# Shopify stores known to have product videos in jewelry / fashion / accessories
# Format: {"domain": {"categories": [...], "note": "..."}}
# These are discovered via --discover or added manually
KNOWN_STORES = {
    # Jewelry
    "mejuri.com":           {"categories": ["necklace", "bracelet", "earring", "ring"], "note": "Fine jewelry, many product videos"},
    "kendrascott.com":      {"categories": ["necklace", "bracelet", "earring", "ring"], "note": "Fashion jewelry"},
    "gorjana.com":          {"categories": ["necklace", "bracelet", "earring", "ring"], "note": "Gold jewelry"},
    "analuisa.com":         {"categories": ["necklace", "bracelet", "earring", "ring"], "note": "Sustainable jewelry"},
    "missoma.com":          {"categories": ["necklace", "bracelet", "earring", "ring"], "note": "Demi-fine jewelry"},
    "vitaly.com":           {"categories": ["necklace", "bracelet", "ring"],            "note": "Streetwear jewelry"},
    "jaxxon.com":           {"categories": ["necklace", "bracelet", "ring"],            "note": "Men's chains"},
    # Watches
    "mvmtwatches.com":      {"categories": ["watch"],       "note": "Affordable fashion watches"},
    "filippoloreti.com":    {"categories": ["watch"],       "note": "Italian watches"},
    # Sunglasses
    "goodr.com":            {"categories": ["sunglasses"],  "note": "Sport sunglasses"},
    "blenders.com":         {"categories": ["sunglasses"],  "note": "Lifestyle sunglasses"},
    # Bags
    "dagnedover.com":       {"categories": ["handbag"],     "note": "Premium bags"},
    "beistravel.com":       {"categories": ["handbag"],     "note": "Travel bags"},
}

# Category mapping: Shopify product_type / tags → our categories
CATEGORY_KEYWORDS = {
    "necklace":   ["necklace", "pendant", "chain", "choker", "lariat"],
    "bracelet":   ["bracelet", "bangle", "cuff", "anklet"],
    "earring":    ["earring", "stud", "hoop", "huggie", "ear cuff"],
    "ring":       ["ring", "band", "signet"],
    "watch":      ["watch", "timepiece"],
    "sunglasses": ["sunglasses", "sunnies", "shades", "eyewear"],
    "handbag":    ["bag", "handbag", "tote", "clutch", "purse", "crossbody", "backpack"],
    "cosmetics":  ["lipstick", "foundation", "mascara", "blush", "concealer", "eyeshadow",
                   "skincare", "serum", "moisturizer", "cleanser", "primer", "bronzer",
                   "highlighter", "perfume", "fragrance", "makeup", "cosmetic", "beauty"],
}

MAX_PAGES = 10          # /products.json pages per store
PRODUCTS_PER_PAGE = 250  # Shopify max
REQUEST_TIMEOUT = 20
MIN_DELAY = 0.5
MAX_DELAY = 1.5

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("shopify_spider")


# ─── HTTP helpers ────────────────────────────────────────────

class ShopifySession:
    """Manages requests session for Shopify stores."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.request_count = 0

    def get(self, url, **kwargs):
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
        self.request_count += 1

        for attempt in range(3):
            try:
                resp = self.session.get(url, **kwargs)
                if resp.status_code == 200:
                    return resp
                elif resp.status_code == 429:
                    wait = 10 + random.uniform(5, 15)
                    log.warning(f"  429 rate limited, waiting {wait:.0f}s...")
                    time.sleep(wait)
                elif resp.status_code == 404:
                    return None
                else:
                    log.warning(f"  HTTP {resp.status_code}: {url[:80]}")
                    if attempt < 2:
                        time.sleep(3)
            except requests.exceptions.RequestException as e:
                log.warning(f"  Request error: {e}")
                if attempt < 2:
                    time.sleep(3)

        return None

    def get_binary(self, url, save_path, **kwargs):
        """Download a binary file (image/video)."""
        kwargs.setdefault("timeout", 120)
        kwargs.setdefault("stream", True)
        try:
            resp = self.session.get(url, **kwargs)
            if resp.status_code != 200:
                return False
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            return os.path.getsize(save_path) > 1000
        except Exception as e:
            log.warning(f"  Download error: {e}")
            if os.path.exists(save_path):
                os.remove(save_path)
            return False


# ─── Shopify API ─────────────────────────────────────────────

def fetch_products(session: ShopifySession, store_domain: str) -> list:
    """
    Fetch all products from a Shopify store via /products.json.
    Returns list of product dicts.
    """
    all_products = []
    base_url = f"https://{store_domain}/products.json"

    for page in range(1, MAX_PAGES + 1):
        url = f"{base_url}?limit={PRODUCTS_PER_PAGE}&page={page}"
        log.info(f"  Fetching page {page}: {store_domain}")

        resp = session.get(url)
        if not resp:
            break

        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError):
            log.warning(f"  Invalid JSON response from {store_domain}")
            break

        products = data.get("products", [])
        if not products:
            break

        all_products.extend(products)
        log.info(f"    Got {len(products)} products (total: {len(all_products)})")

        if len(products) < PRODUCTS_PER_PAGE:
            break  # last page

    return all_products


def classify_product(product: dict) -> str | None:
    """
    Map a Shopify product to one of our categories based on
    product_type, tags, and title.
    Returns category name or None.
    """
    searchable = " ".join([
        product.get("product_type", ""),
        product.get("title", ""),
        " ".join(product.get("tags", [])) if isinstance(product.get("tags"), list) else product.get("tags", ""),
    ]).lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in searchable:
                return category
    return None


def _clean_video_url(url: str) -> str:
    """Clean up video URLs: unescape JSON slashes, add scheme, etc."""
    # Unescape JSON-escaped forward slashes
    url = url.replace("\\/", "/")
    # Handle protocol-relative URLs
    if url.startswith("//"):
        url = "https:" + url
    # Remove leading backslashes before //
    if url.startswith("\\//") or url.startswith("\\\\/\\\\/"):
        url = url.replace("\\", "")
        if url.startswith("//"):
            url = "https:" + url
    return url


def extract_videos_from_description(html_body: str) -> list:
    """
    Extract video URLs embedded in the product description HTML.
    Shopify merchants often embed videos via:
      - <video> tags with <source src="...">
      - YouTube/Vimeo iframes
      - Shopify CDN hosted videos
    """
    if not html_body:
        return []

    videos = []
    seen = set()

    # Direct video source URLs (Shopify CDN, etc.)
    for pattern in [
        r'<source[^>]+src="([^"]+\.mp4[^"]*)"',
        r'<video[^>]+src="([^"]+\.mp4[^"]*)"',
        r'(https?://cdn\.shopify\.com/[^"\s]+\.mp4[^"\s]*)',
        r'(https?://[^"\s]+\.shopify\.com/[^"\s]+/files/[^"\s]+\.mp4)',
    ]:
        for m in re.finditer(pattern, html_body, re.I):
            url = _clean_video_url(m.group(1))
            if url not in seen:
                seen.add(url)
                videos.append({"url": url, "source": "description_html"})

    # YouTube embeds → we just record the ID, not download
    for m in re.finditer(
        r'(?:youtube\.com/embed/|youtu\.be/|youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})',
        html_body,
    ):
        yt_id = m.group(1)
        yt_url = f"https://www.youtube.com/watch?v={yt_id}"
        if yt_url not in seen:
            seen.add(yt_url)
            videos.append({"url": yt_url, "source": "youtube_embed"})

    # Vimeo embeds
    for m in re.finditer(r'vimeo\.com/(?:video/)?(\d+)', html_body):
        vimeo_url = f"https://vimeo.com/{m.group(1)}"
        if vimeo_url not in seen:
            seen.add(vimeo_url)
            videos.append({"url": vimeo_url, "source": "vimeo_embed"})

    return videos


def extract_media_from_product_page(session: ShopifySession,
                                     store_domain: str, handle: str) -> list:
    """
    Fetch the product page HTML and look for video/media not in /products.json.
    Shopify's product JSON doesn't include videos; they're in the page HTML
    or loaded via Storefront API.
    """
    url = f"https://{store_domain}/products/{handle}"
    resp = session.get(url, headers={"Accept": "text/html"})
    if not resp:
        return []

    html = resp.text
    videos = []
    seen = set()

    # Look for Shopify media (model/video) in page scripts
    # Shopify themes often embed media data in JSON-LD or script tags
    for pattern in [
        r'"sources":\s*\[\s*\{[^}]*"url"\s*:\s*"([^"]+\.mp4[^"]*)"',
        r'"src"\s*:\s*"(https?://cdn\.shopify\.com/[^"]+\.mp4[^"]*)"',
        r'"url"\s*:\s*"((?:https?:)?(?:\\?/\\?/)[^"]*\.mp4[^"]*)"',
        r'(https?://cdn\.shopify\.com/videos/[^"\s]+\.mp4)',
        # Escaped Shopify CDN video URLs (common in JSON-in-HTML)
        r'"url"\s*:\s*"(\\?/\\?/[^"]*\.mp4[^"]*)"',
    ]:
        for m in re.finditer(pattern, html):
            url = _clean_video_url(m.group(1).replace("\\u0026", "&"))
            if url not in seen and ".mp4" in url:
                seen.add(url)
                videos.append({"url": url, "source": "product_page"})

    # Also check for external video URLs in script data
    for m in re.finditer(
        r'"external_id"\s*:\s*"([^"]+)"[^}]*"host"\s*:\s*"youtube"', html
    ):
        yt_id = m.group(1)
        yt_url = f"https://www.youtube.com/watch?v={yt_id}"
        if yt_url not in seen:
            seen.add(yt_url)
            videos.append({"url": yt_url, "source": "youtube_product_media"})

    return videos


# ─── Store discovery ─────────────────────────────────────────

def check_store(session: ShopifySession, domain: str) -> dict | None:
    """
    Check if a domain is a Shopify store and has product videos.
    Returns store info dict or None.
    """
    # Test /products.json
    url = f"https://{domain}/products.json?limit=5"
    resp = session.get(url)
    if not resp:
        return None

    try:
        data = resp.json()
    except (json.JSONDecodeError, ValueError):
        return None

    products = data.get("products", [])
    if not products:
        return None

    info = {
        "domain": domain,
        "is_shopify": True,
        "sample_products": len(products),
        "has_images": any(p.get("images") for p in products),
        "videos_in_description": 0,
        "categories_detected": set(),
    }

    # Check a few products for videos
    for product in products[:5]:
        body_html = product.get("body_html", "")
        vids = extract_videos_from_description(body_html)
        info["videos_in_description"] += len(vids)

        cat = classify_product(product)
        if cat:
            info["categories_detected"].add(cat)

    info["categories_detected"] = list(info["categories_detected"])
    return info


def discover_stores(session: ShopifySession):
    """Test all known stores and report which have video content."""
    log.info("=" * 60)
    log.info("Shopify Store Discovery")
    log.info("=" * 60)

    results = []
    for domain, meta in KNOWN_STORES.items():
        log.info(f"\nChecking: {domain} ({meta['note']})")
        info = check_store(session, domain)

        if info:
            info["expected_categories"] = meta["categories"]
            results.append(info)
            log.info(f"  [OK] Shopify store confirmed | "
                     f"images: {info['has_images']} | "
                     f"desc videos: {info['videos_in_description']} | "
                     f"categories: {info['categories_detected']}")
        else:
            log.info(f"  [FAIL] Not accessible or not Shopify")

    # Also check product pages for a couple stores to find video media
    for result in results[:3]:
        domain = result["domain"]
        log.info(f"\nDeep-checking product pages on {domain}...")
        url = f"https://{domain}/products.json?limit=3"
        resp = session.get(url)
        if resp:
            products = resp.json().get("products", [])
            for p in products[:3]:
                handle = p.get("handle", "")
                if handle:
                    page_videos = extract_media_from_product_page(session, domain, handle)
                    if page_videos:
                        log.info(f"  Found {len(page_videos)} videos on product page: {handle}")
                        result["page_videos_found"] = True

    # Save discovery results
    os.makedirs(BASE_OUTPUT, exist_ok=True)
    discovery_path = os.path.join(BASE_OUTPUT, "store_discovery.json")
    with open(discovery_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "stores": results,
        }, f, ensure_ascii=False, indent=2)

    log.info(f"\n{'='*60}")
    log.info(f"Discovery complete: {len(results)}/{len(KNOWN_STORES)} stores accessible")
    log.info(f"Results saved to: {discovery_path}")
    log.info(f"{'='*60}")

    return results


# ─── Crawl a single store ────────────────────────────────────

def crawl_store(session: ShopifySession, store_domain: str,
                target_category: str = None) -> dict:
    """
    Crawl a Shopify store: fetch products → classify → download media.
    """
    log.info(f"\n{'='*60}")
    log.info(f"Crawling: {store_domain}")
    if target_category:
        log.info(f"  Filtering for category: {target_category}")
    log.info(f"{'='*60}")

    stats = {
        "store": store_domain,
        "products_total": 0,
        "products_matched": 0,
        "products_with_video": 0,
        "images_downloaded": 0,
        "videos_downloaded": 0,
        "videos_youtube": 0,
    }

    # Fetch all products
    products = fetch_products(session, store_domain)
    stats["products_total"] = len(products)

    if not products:
        log.warning(f"  No products found on {store_domain}")
        return stats

    for idx, product in enumerate(products):
        handle = product.get("handle", "")
        title = product.get("title", "")
        product_id = str(product.get("id", handle))

        # Classify
        category = classify_product(product)
        if not category:
            continue
        if target_category and category != target_category:
            continue

        stats["products_matched"] += 1

        # Prepare output dirs
        cat_dir = os.path.join(BASE_OUTPUT, category)
        images_dir = os.path.join(cat_dir, "media", "images")
        videos_dir = os.path.join(cat_dir, "media", "videos")
        os.makedirs(images_dir, exist_ok=True)
        os.makedirs(videos_dir, exist_ok=True)

        # Skip if already scraped
        meta_path = os.path.join(cat_dir, f"{store_domain}_{handle}.json")
        if os.path.exists(meta_path):
            log.info(f"  [{idx+1}] {handle} — already scraped, skipping")
            continue

        log.info(f"  [{idx+1}/{len(products)}] {handle} → {category}: {title[:50]}")

        # Collect all video sources
        all_videos = []

        # 1. Videos from description HTML
        desc_videos = extract_videos_from_description(product.get("body_html", ""))
        all_videos.extend(desc_videos)

        # 2. Videos from product page HTML (slower, but catches Shopify media)
        page_videos = extract_media_from_product_page(session, store_domain, handle)
        # Deduplicate
        seen_urls = {v["url"] for v in all_videos}
        for v in page_videos:
            if v["url"] not in seen_urls:
                all_videos.append(v)
                seen_urls.add(v["url"])

        # Download images (from /products.json — always available)
        images = product.get("images", [])
        downloaded_images = []
        for img_idx, img in enumerate(images[:8]):
            img_url = img.get("src", "")
            if not img_url:
                continue
            # Shopify CDN: request specific size (1024px wide)
            img_url = re.sub(r'(\.\w+)\?', r'_1024x\1?', img_url)
            save_path = os.path.join(
                images_dir, f"{store_domain}_{handle}_{img_idx:02d}.jpg"
            )
            if os.path.exists(save_path) and os.path.getsize(save_path) > 1000:
                downloaded_images.append(save_path)
                continue
            if session.get_binary(img_url, save_path):
                downloaded_images.append(save_path)
                stats["images_downloaded"] += 1

        # Download videos (only direct MP4s; skip YouTube/Vimeo)
        downloaded_videos = []
        for vid_idx, vid in enumerate(all_videos):
            vid_url = _clean_video_url(vid["url"])

            if "youtube.com" in vid_url or "youtu.be" in vid_url:
                stats["videos_youtube"] += 1
                continue
            if "vimeo.com" in vid_url:
                continue

            suffix = f"_v{vid_idx:02d}" if vid_idx > 0 else ""
            save_path = os.path.join(
                videos_dir, f"{store_domain}_{handle}{suffix}.mp4"
            )
            if os.path.exists(save_path) and os.path.getsize(save_path) > 10000:
                downloaded_videos.append(save_path)
                continue

            log.info(f"    Downloading video: {vid_url[:80]}")
            if session.get_binary(vid_url, save_path):
                downloaded_videos.append(save_path)
                stats["videos_downloaded"] += 1

        if all_videos:
            stats["products_with_video"] += 1

        # Save metadata
        meta = {
            "platform": "shopify",
            "store": store_domain,
            "handle": handle,
            "product_id": product_id,
            "title": title,
            "product_type": product.get("product_type", ""),
            "tags": product.get("tags", []),
            "category": category,
            "vendor": product.get("vendor", ""),
            "price": _get_price(product),
            "images": [img.get("src", "") for img in images],
            "video_urls": [v["url"] for v in all_videos],
            "video_sources": all_videos,
            "images_downloaded": len(downloaded_images),
            "videos_downloaded": len(downloaded_videos),
            "scraped_at": datetime.now().isoformat(),
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    log.info(f"\n  Store complete: {stats}")
    return stats


def _get_price(product: dict) -> str:
    """Extract price from Shopify product variants."""
    variants = product.get("variants", [])
    if variants:
        return variants[0].get("price", "")
    return ""


# ─── Batch crawl ─────────────────────────────────────────────

def run_batch():
    """Crawl all known stores."""
    log.info("=" * 60)
    log.info("Shopify Batch Crawl - All Known Stores")
    log.info("=" * 60)

    session = ShopifySession()
    all_stats = []
    start = datetime.now()

    for domain, meta in KNOWN_STORES.items():
        for category in meta["categories"]:
            stats = crawl_store(session, domain, target_category=category)
            all_stats.append(stats)

    elapsed = (datetime.now() - start).total_seconds()

    total_matched = sum(s["products_matched"] for s in all_stats)
    total_with_video = sum(s["products_with_video"] for s in all_stats)
    total_images = sum(s["images_downloaded"] for s in all_stats)
    total_videos = sum(s["videos_downloaded"] for s in all_stats)

    log.info(f"\n{'='*60}")
    log.info(f"BATCH COMPLETE in {elapsed:.0f}s ({elapsed/60:.1f}min)")
    log.info(f"  Products matched:    {total_matched}")
    log.info(f"  Products with video: {total_with_video}")
    log.info(f"  Images downloaded:   {total_images}")
    log.info(f"  Videos downloaded:   {total_videos}")
    log.info(f"{'='*60}")

    # Save summary
    os.makedirs(BASE_OUTPUT, exist_ok=True)
    summary_path = os.path.join(BASE_OUTPUT, "crawl_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": elapsed,
            "stats": all_stats,
            "totals": {
                "products_matched": total_matched,
                "with_video": total_with_video,
                "images": total_images,
                "videos": total_videos,
            }
        }, f, ensure_ascii=False, indent=2)

    return all_stats


# ─── Status ──────────────────────────────────────────────────

def show_status():
    """Show current crawl progress."""
    print(f"\n{'='*60}")
    print(f"  Shopify Spider - Status")
    print(f"  Output: {BASE_OUTPUT}")
    print(f"{'='*60}")

    if not os.path.isdir(BASE_OUTPUT):
        print("  No data yet.")
        return

    total_meta = 0
    total_images = 0
    total_videos = 0

    for cat_dir in sorted(Path(BASE_OUTPUT).iterdir()):
        if not cat_dir.is_dir():
            continue
        category = cat_dir.name
        meta_count = len(list(cat_dir.glob("*.json")))
        img_dir = cat_dir / "media" / "images"
        vid_dir = cat_dir / "media" / "videos"
        img_count = len(list(img_dir.glob("*"))) if img_dir.exists() else 0
        vid_count = len(list(vid_dir.glob("*"))) if vid_dir.exists() else 0

        total_meta += meta_count
        total_images += img_count
        total_videos += vid_count

        print(f"  {category:15s} | products: {meta_count:4d} | "
              f"images: {img_count:4d} | videos: {vid_count:3d}")

    print(f"  {'─'*55}")
    print(f"  {'TOTAL':15s} | products: {total_meta:4d} | "
          f"images: {total_images:4d} | videos: {total_videos:3d}")
    print(f"{'='*60}")


# ─── CLI ─────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Shopify Store Product Video & Image Spider",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--store", help="Store domain (e.g., mejuri.com)")
    parser.add_argument("--category", help="Filter for specific category")
    parser.add_argument("--batch", action="store_true",
                        help="Crawl all known stores")
    parser.add_argument("--discover", action="store_true",
                        help="Test known stores for video availability")
    parser.add_argument("--status", action="store_true", help="Show progress")
    parser.add_argument("--output", help="Override output directory")

    args = parser.parse_args()

    if args.output:
        BASE_OUTPUT = args.output

    if args.status:
        show_status()
    elif args.discover:
        session = ShopifySession()
        discover_stores(session)
    elif args.batch:
        run_batch()
    elif args.store:
        session = ShopifySession()
        crawl_store(session, args.store, target_category=args.category)
    else:
        parser.print_help()
