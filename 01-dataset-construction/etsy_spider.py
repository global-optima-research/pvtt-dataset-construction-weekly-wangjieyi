#!/usr/bin/env python3
"""
Etsy Product Video & Image Spider
====================================
Collects product videos and images from Etsy for PVTT dataset.
Uses DrissionPage (real Chrome) to bypass Datadome anti-bot.
Runs LOCALLY. Output format matches amazon_spider.py for pipeline compatibility.

Usage:
  python etsy_spider.py --keyword "gold necklace" --category necklace --max-products 20
  python etsy_spider.py --batch
  python etsy_spider.py --status

Output: ./etsy_data/{category}/
          *.json                    # Product metadata
          media/images/{id}_XX.jpg  # Product images
          media/videos/{id}.mp4     # Product videos
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
from urllib.parse import quote_plus

import requests
from DrissionPage import ChromiumPage, ChromiumOptions

# ─── Config ──────────────────────────────────────────────────

BASE_OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "etsy_data")

BATCH_CATEGORIES = {
    "necklace":   ["gold necklace", "silver pendant necklace", "pearl necklace", "handmade necklace"],
    "bracelet":   ["charm bracelet", "beaded bracelet", "gold bangle", "handmade bracelet"],
    "earring":    ["drop earrings", "hoop earrings", "stud earrings gold", "handmade earrings"],
    "ring":       ["engagement ring", "gold ring", "silver stackable ring", "handmade ring"],
    "watch":      ["vintage watch", "handmade watch", "leather strap watch"],
    "handbag":    ["leather handbag", "crossbody bag handmade", "tote bag leather"],
    "sunglasses": ["vintage sunglasses", "handmade sunglasses", "retro sunglasses"],
}

MAX_PRODUCTS_PER_KEYWORD = 20
MIN_DELAY = 2.0
MAX_DELAY = 4.0

os.makedirs(BASE_OUTPUT, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("etsy_spider")


# ─── Browser Session ────────────────────────────────────────

def create_browser(headless=True):
    """Create a ChromiumPage with stealth settings."""
    co = ChromiumOptions()
    if headless:
        co.headless()
    co.set_argument("--disable-blink-features=AutomationControlled")
    co.set_argument("--no-sandbox")
    co.set_argument("--disable-gpu")
    co.set_argument("--lang=en-US")
    co.set_argument("--window-size=1920,1080")
    page = ChromiumPage(co)
    return page


def _delay():
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


# ─── Search: keyword → listing IDs ──────────────────────────

def search_etsy(page, keyword, max_pages=3, max_results=50):
    """Search Etsy and extract listing IDs using real browser."""
    results = []
    seen = set()

    for pg in range(1, max_pages + 1):
        if len(results) >= max_results:
            break

        search_url = (
            f"https://www.etsy.com/search?q={quote_plus(keyword)}"
            f"&ref=pagination&page={pg}"
        )
        log.info(f"  Search page {pg}: {keyword}")

        try:
            page.get(search_url)
            _delay()

            # Wait for listings to load
            page.wait.doc_loaded(timeout=15)
            time.sleep(2)  # Extra wait for JS rendering

            html = page.html
        except Exception as e:
            log.warning(f"  Failed to load search page {pg}: {e}")
            break

        # Parse with BeautifulSoup for consistency
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        # Method 1: data-listing-id divs
        listings = soup.find_all("div", attrs={"data-listing-id": True})
        for item in listings:
            lid = item.get("data-listing-id", "").strip()
            if not lid or lid in seen:
                continue
            seen.add(lid)

            title_el = item.find("h3") or item.find("h2") or item.find("p")
            title = title_el.get_text(strip=True) if title_el else ""

            link_el = item.find("a", href=re.compile(r"/listing/"))
            url = link_el.get("href", "") if link_el else f"https://www.etsy.com/listing/{lid}"
            if url.startswith("/"):
                url = "https://www.etsy.com" + url

            img_el = item.find("img")
            thumb = img_el.get("src", "") if img_el else ""

            if title:
                results.append({
                    "listing_id": lid,
                    "title": title[:120],
                    "url": url.split("?")[0],
                    "thumbnail": thumb,
                })

        # Method 2: listing links (fallback)
        if not listings:
            for a in soup.find_all("a", href=re.compile(r"/listing/\d+")):
                href = a.get("href", "")
                m = re.search(r"/listing/(\d+)", href)
                if m:
                    lid = m.group(1)
                    if lid not in seen:
                        seen.add(lid)
                        title_el = a.find("h3") or a.find("h2") or a
                        title = title_el.get_text(strip=True) if title_el else ""
                        if title and len(title) > 5:
                            results.append({
                                "listing_id": lid,
                                "title": title[:120],
                                "url": f"https://www.etsy.com/listing/{lid}",
                                "thumbnail": "",
                            })

        log.info(f"    Found listings on page {pg} (total: {len(results)})")

        if not listings and not soup.find("a", href=re.compile(r"/listing/\d+")):
            break

    return results[:max_results]


# ─── Product detail: listing → images + videos ──────────────

def extract_listing_media(page, listing_id, url):
    """Fetch Etsy listing page and extract media using browser."""
    try:
        page.get(url)
        _delay()
        page.wait.doc_loaded(timeout=15)
        time.sleep(2)
        html = page.html
    except Exception as e:
        log.warning(f"    Failed to load listing {listing_id}: {e}")
        return None

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    media = {
        "listing_id": listing_id,
        "url": url,
        "platform": "etsy",
        "title": "",
        "price": "",
        "images": [],
        "video_urls": [],
    }

    # Title
    title_el = soup.find("h1", {"data-buy-box-listing-title": True}) or soup.find("h1")
    if title_el:
        media["title"] = title_el.get_text(strip=True)

    # Price
    price_el = soup.find("div", {"data-buy-box-region": "price"})
    if price_el:
        p = price_el.find("p") or price_el
        media["price"] = p.get_text(strip=True)[:30]
    if not media["price"]:
        price_el2 = soup.find("p", class_=re.compile(r"wt-text-title-larger"))
        if price_el2:
            media["price"] = price_el2.get_text(strip=True)[:30]

    # Images from structured data (JSON-LD)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            ld = json.loads(script.string)
            if isinstance(ld, dict) and ld.get("@type") == "Product":
                imgs = ld.get("image", [])
                if isinstance(imgs, str):
                    imgs = [imgs]
                media["images"].extend(imgs)
        except (json.JSONDecodeError, TypeError):
            pass

    # Images from page
    if not media["images"]:
        for img in soup.find_all("img", src=re.compile(r"etsystatic\.com.*il_")):
            src = img.get("src", "")
            hires = re.sub(r'il_\d+x\d+', 'il_1588xN', src)
            if hires not in media["images"]:
                media["images"].append(hires)

    # Alternative: carousel images
    if not media["images"]:
        for img in soup.find_all("img"):
            src = img.get("data-src", "") or img.get("src", "")
            if "etsystatic.com" in src and "il_" in src:
                hires = re.sub(r'il_\d+x\d+', 'il_1588xN', src)
                if hires not in media["images"]:
                    media["images"].append(hires)

    # Videos: <video> tags
    video_urls = []
    for video in soup.find_all("video"):
        for source in video.find_all("source"):
            src = source.get("src", "")
            if src and src not in video_urls:
                video_urls.append(src)
        poster = video.get("src", "") or video.get("data-src", "")
        if poster and ".mp4" in poster and poster not in video_urls:
            video_urls.append(poster)

    # Videos in script data
    for pattern in [
        r'"video_url"\s*:\s*"(https?://[^"]+\.mp4[^"]*)"',
        r'"videoUrl"\s*:\s*"(https?://[^"]+\.mp4[^"]*)"',
        r'"url"\s*:\s*"(https?://[^"]*etsystatic[^"]*\.mp4[^"]*)"',
        r'(https?://v\.etsystatic\.com/[^"\'\s]+\.mp4[^"\'\s]*)',
    ]:
        for m in re.finditer(pattern, html):
            u = m.group(1)
            if u not in video_urls:
                video_urls.append(u)

    # Video from JSON-like listing_video data
    m = re.search(r'"listing_video"\s*:\s*\{([^}]+)\}', html)
    if m:
        try:
            vid_json = "{" + m.group(1) + "}"
            vid_data = json.loads(vid_json)
            for key in ["video_url", "url", "playlist_url"]:
                if vid_data.get(key):
                    video_urls.append(vid_data[key])
        except (json.JSONDecodeError, TypeError):
            pass

    media["video_urls"] = video_urls
    log.info(f"    {listing_id}: {len(media['images'])} images, {len(video_urls)} videos")
    return media


# ─── Download (uses plain requests for CDN) ──────────────────

def download_media(media, category):
    """Download images and videos for a listing."""
    lid = media["listing_id"]
    cat_dir = os.path.join(BASE_OUTPUT, category)
    images_dir = os.path.join(cat_dir, "media", "images")
    videos_dir = os.path.join(cat_dir, "media", "videos")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(videos_dir, exist_ok=True)

    stats = {"images_downloaded": 0, "videos_downloaded": 0, "images_skipped": 0}

    # Images (max 10)
    for idx, img_url in enumerate(media.get("images", [])[:10]):
        save_path = os.path.join(images_dir, f"{lid}_{idx:02d}.jpg")
        if os.path.exists(save_path) and os.path.getsize(save_path) > 1000:
            stats["images_skipped"] += 1
            continue
        if _download_file(img_url, save_path):
            stats["images_downloaded"] += 1

    # Videos
    for idx, vid_url in enumerate(media.get("video_urls", [])):
        suffix = f"_v{idx:02d}" if idx > 0 else ""
        save_path = os.path.join(videos_dir, f"{lid}{suffix}.mp4")
        if os.path.exists(save_path) and os.path.getsize(save_path) > 10000:
            continue
        if _download_file(vid_url, save_path):
            stats["videos_downloaded"] += 1

    return stats


def _download_file(url, save_path):
    """Download file using plain requests (CDN doesn't need browser)."""
    for attempt in range(2):
        try:
            resp = requests.get(
                url, timeout=60, stream=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
                    "Referer": "https://www.etsy.com/",
                }
            )
            if resp.status_code != 200:
                continue
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            if os.path.getsize(save_path) > 500:
                return True
            else:
                os.remove(save_path)
        except Exception:
            pass
        time.sleep(1)
    return False


# ─── Crawl category ─────────────────────────────────────────

def crawl_category(keyword, category, max_products=MAX_PRODUCTS_PER_KEYWORD, page=None):
    """Crawl a single keyword + category. Optionally reuse an existing browser page."""
    log.info(f"\n{'='*60}")
    log.info(f"Crawling: [etsy/{category}] \"{keyword}\" (max {max_products})")
    log.info(f"{'='*60}")

    own_page = False
    if page is None:
        page = create_browser(headless=True)
        own_page = True

    cat_dir = os.path.join(BASE_OUTPUT, category)
    os.makedirs(cat_dir, exist_ok=True)

    # Check existing
    existing = set()
    for f in os.listdir(cat_dir):
        if f.endswith(".json"):
            existing.add(f.replace(".json", ""))

    # Search
    results = search_etsy(page, keyword, max_pages=3, max_results=max_products)
    log.info(f"  Found {len(results)} listings")

    total_stats = {
        "keyword": keyword, "category": category, "platform": "etsy",
        "products_found": len(results), "products_scraped": 0,
        "products_with_video": 0, "total_images": 0, "total_videos": 0,
    }

    for i, result in enumerate(results[:max_products]):
        lid = result["listing_id"]
        log.info(f"\n  [{i+1}/{min(len(results), max_products)}] {lid}: {result['title'][:60]}")

        # Skip existing
        if lid in existing:
            log.info(f"    Already scraped, skipping")
            total_stats["products_scraped"] += 1
            continue

        # Extract media
        media = extract_listing_media(page, lid, result["url"])
        if not media:
            log.warning(f"    Failed to extract media")
            continue

        # Download
        dl_stats = download_media(media, category)

        # Save metadata (compatible format with amazon_spider)
        meta = {
            "listing_id": lid,
            "asin": lid,  # Compatibility: use listing_id as asin
            "platform": "etsy",
            "url": media["url"],
            "title": media["title"] or result["title"],
            "price": media["price"],
            "keyword": keyword,
            "category": category,
            "images": media["images"],
            "video_urls": media["video_urls"],
            "download_stats": dl_stats,
            "scraped_at": datetime.now().isoformat(),
        }

        json_path = os.path.join(cat_dir, f"{lid}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        total_stats["products_scraped"] += 1
        total_stats["total_images"] += dl_stats["images_downloaded"]
        total_stats["total_videos"] += dl_stats["videos_downloaded"]
        if dl_stats["videos_downloaded"] > 0:
            total_stats["products_with_video"] += 1

    if own_page:
        try:
            page.quit()
        except Exception:
            pass

    log.info(f"\n  Category '{category}' complete: {total_stats}")
    return total_stats


def run_batch():
    """Run all categories with a shared browser instance."""
    log.info("Starting batch crawl (all categories)...")
    page = create_browser(headless=True)
    all_stats = []
    try:
        for cat, keywords in BATCH_CATEGORIES.items():
            for kw in keywords:
                stats = crawl_category(kw, cat, MAX_PRODUCTS_PER_KEYWORD, page=page)
                all_stats.append(stats)
    finally:
        try:
            page.quit()
        except Exception:
            pass

    # Summary
    total_products = sum(s["products_scraped"] for s in all_stats)
    total_images = sum(s["total_images"] for s in all_stats)
    total_videos = sum(s["total_videos"] for s in all_stats)
    log.info(f"\n{'='*60}")
    log.info(f"BATCH COMPLETE: {total_products} products, {total_images} images, {total_videos} videos")
    log.info(f"{'='*60}")
    return all_stats


def show_status():
    """Show current Etsy data status."""
    print(f"\nEtsy Data: {BASE_OUTPUT}")
    print(f"{'─'*60}")
    total_p = total_i = total_v = 0
    total_bytes = 0
    base = Path(BASE_OUTPUT)
    if not base.exists():
        print("  No data yet.")
        return
    for d in sorted(base.iterdir()):
        if not d.is_dir():
            continue
        np = len(list(d.glob("*.json")))
        ni = len(list((d / "media" / "images").glob("*"))) if (d / "media" / "images").exists() else 0
        nv = len(list((d / "media" / "videos").glob("*"))) if (d / "media" / "videos").exists() else 0
        sz = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
        total_p += np; total_i += ni; total_v += nv; total_bytes += sz
        print(f"  {d.name:15s} {np:3d} products  {ni:4d} imgs  {nv:3d} vids  {sz/1024/1024:7.1f} MB")
    print(f"  {'─'*60}")
    print(f"  {'TOTAL':15s} {total_p:3d} products  {total_i:4d} imgs  {total_v:3d} vids  {total_bytes/1024/1024:7.1f} MB")


# ─── Main ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Etsy Product Spider for PVTT")
    parser.add_argument("--keyword", "-k", help="Search keyword")
    parser.add_argument("--category", "-c", help="Product category")
    parser.add_argument("--max-products", "-m", type=int, default=MAX_PRODUCTS_PER_KEYWORD)
    parser.add_argument("--batch", action="store_true", help="Run all categories")
    parser.add_argument("--status", action="store_true", help="Show progress")
    parser.add_argument("--headful", action="store_true", help="Show browser window (for debugging)")
    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.batch:
        run_batch()
    elif args.keyword and args.category:
        page = create_browser(headless=not args.headful)
        try:
            crawl_category(args.keyword, args.category, args.max_products, page=page)
        finally:
            try:
                page.quit()
            except Exception:
                pass
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
