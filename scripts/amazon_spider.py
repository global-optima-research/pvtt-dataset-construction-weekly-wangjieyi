#!/usr/bin/env python3
"""
Amazon Product Video & Image Spider
=====================================
Collects product videos and images from Amazon for PVTT dataset.
Runs LOCALLY (residential IP avoids Amazon bot detection), then
uploads results to the server via launch_spider.py.

Strategy:
  1. Search Amazon for product keywords → collect ASINs
  2. Fetch each product detail page → extract image gallery + video URLs
  3. Download media (videos are the priority for PVTT)
  4. Save metadata in a format compatible with pvtt_pipeline.py

Usage:
  python amazon_spider.py --keyword "gold necklace" --category necklace --max-products 20
  python amazon_spider.py --batch          # run all predefined categories
  python amazon_spider.py --status         # check progress
  python amazon_spider.py --upload         # sync results to server via SSH

Output (local):  ./amazon_data/{category}/...
Output (server): /data/wangjieyi/pvtt-dataset/amazon/{category}/...
"""

import os
import re
import json
import time
import random
import hashlib
import logging
import argparse
import sys
from pathlib import Path
from datetime import datetime
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

# ─── Config ──────────────────────────────────────────────────

# Default: local output; --upload syncs to server
BASE_OUTPUT = os.environ.get(
    "SPIDER_OUTPUT",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "amazon_data"),
)
REMOTE_OUTPUT = "/data/wangjieyi/pvtt-dataset/amazon"

# Categories aligned with PVTT evaluation dataset
BATCH_CATEGORIES = {
    "necklace":   ["gold necklace", "silver pendant necklace", "pearl necklace",
                   "choker necklace", "diamond pendant necklace", "layered necklace"],
    "bracelet":   ["charm bracelet", "gold bangle bracelet", "beaded bracelet",
                   "tennis bracelet", "cuff bracelet women", "chain bracelet gold"],
    "earring":    ["drop earrings", "stud earrings gold", "hoop earrings silver",
                   "dangle earrings women", "pearl earrings", "clip on earrings"],
    "watch":      ["men automatic watch", "women dress watch", "sport digital watch",
                   "luxury watch men", "chronograph watch", "minimalist watch women"],
    "handbag":    ["leather crossbody bag", "women tote handbag", "clutch purse evening",
                   "shoulder bag women", "mini crossbody bag", "hobo bag leather"],
    "sunglasses": ["polarized sunglasses", "aviator sunglasses", "cat eye sunglasses",
                   "oversized sunglasses women", "sport sunglasses men", "round sunglasses retro"],
    "ring":       ["engagement ring", "gold band ring", "silver stackable ring",
                   "cocktail ring women", "signet ring men", "wedding band set"],
}

MAX_PRODUCTS_PER_KEYWORD = 20

# Request settings
REQUEST_TIMEOUT = 20
MIN_DELAY = 1.5      # seconds between requests
MAX_DELAY = 3.5
MAX_RETRIES = 3

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(BASE_OUTPUT, f"spider_{datetime.now():%Y%m%d_%H%M%S}.log"),
            encoding="utf-8",
        ) if os.path.isdir(BASE_OUTPUT) or not os.makedirs(BASE_OUTPUT, exist_ok=True) else logging.StreamHandler(),
    ],
)
log = logging.getLogger("amazon_spider")


# ─── HTTP helpers ────────────────────────────────────────────

class AmazonSession:
    """Manages a requests session with rotation and retry."""

    def __init__(self):
        self.session = requests.Session()
        self._rotate_ua()
        self.session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Cache-Control": "max-age=0",
        })
        self.request_count = 0

    def _rotate_ua(self):
        self.session.headers["User-Agent"] = random.choice(USER_AGENTS)

    def _delay(self):
        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    def get(self, url, **kwargs):
        """GET with retry, rotation, and politeness delay."""
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)

        for attempt in range(MAX_RETRIES):
            self._delay()
            self.request_count += 1

            # Rotate UA every 10 requests
            if self.request_count % 10 == 0:
                self._rotate_ua()

            try:
                resp = self.session.get(url, **kwargs)

                if resp.status_code == 200:
                    return resp
                elif resp.status_code == 503:
                    # CAPTCHA or rate limit
                    log.warning(f"  503 (rate limited), backing off... attempt {attempt+1}")
                    time.sleep(10 + random.uniform(5, 15))
                elif resp.status_code == 404:
                    return None
                else:
                    log.warning(f"  HTTP {resp.status_code} for {url[:80]}")

            except requests.exceptions.RequestException as e:
                log.warning(f"  Request error: {e}, attempt {attempt+1}")
                time.sleep(5)

        log.error(f"  Failed after {MAX_RETRIES} retries: {url[:80]}")
        return None


# ─── Search: keyword → ASINs ─────────────────────────────────

def search_amazon(session: AmazonSession, keyword: str,
                  max_pages: int = 3, max_results: int = 50) -> list:
    """
    Search Amazon and extract ASINs from results.
    Returns: list of {'asin': str, 'title': str, 'url': str, 'thumbnail': str}
    """
    results = []
    seen_asins = set()

    for page in range(1, max_pages + 1):
        if len(results) >= max_results:
            break

        search_url = (
            f"https://www.amazon.com/s?k={quote_plus(keyword)}"
            f"&page={page}&ref=sr_pg_{page}"
        )
        log.info(f"  Search page {page}: {keyword}")

        resp = session.get(search_url)
        if not resp:
            break

        soup = BeautifulSoup(resp.text, "html.parser")

        # Amazon search results are in data-asin attributes
        items = soup.find_all("div", attrs={"data-asin": True})
        page_count = 0

        for item in items:
            asin = item.get("data-asin", "").strip()
            if not asin or asin in seen_asins:
                continue

            # Extract title
            title_el = item.find("span", class_="a-text-normal") or item.find("h2")
            title = title_el.get_text(strip=True) if title_el else ""

            # Extract thumbnail
            img_el = item.find("img", class_="s-image")
            thumbnail = img_el.get("src", "") if img_el else ""

            # Check for video badge (indicates product has video)
            has_video_badge = bool(
                item.find("span", string=re.compile(r"video", re.I))
                or item.find("div", class_=re.compile(r"video", re.I))
            )

            if title:
                seen_asins.add(asin)
                results.append({
                    "asin": asin,
                    "title": title,
                    "url": f"https://www.amazon.com/dp/{asin}",
                    "thumbnail": thumbnail,
                    "has_video_hint": has_video_badge,
                })
                page_count += 1

        log.info(f"    Found {page_count} products on page {page} (total: {len(results)})")

        if page_count == 0:
            break

    return results[:max_results]


# ─── Product detail: ASIN → images + videos ──────────────────

def extract_product_media(session: AmazonSession, asin: str) -> dict:
    """
    Fetch a product detail page and extract all media.
    Returns: {
        'asin', 'title', 'price', 'images': [url...],
        'video_urls': [url...], 'video_metadata': [...]
    }
    """
    url = f"https://www.amazon.com/dp/{asin}"
    resp = session.get(url)
    if not resp:
        return None

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    media = {
        "asin": asin,
        "url": url,
        "title": "",
        "price": "",
        "images": [],
        "video_urls": [],
    }

    # ── Title ──
    title_el = soup.find("span", id="productTitle")
    if title_el:
        media["title"] = title_el.get_text(strip=True)

    # ── Price ──
    price_el = (
        soup.find("span", class_="a-price-whole")
        or soup.find("span", id="priceblock_ourprice")
        or soup.find("span", class_="a-offscreen")
    )
    if price_el:
        media["price"] = price_el.get_text(strip=True)

    # ── Images: from 'colorImages' JSON in page source ──
    images = _extract_images_from_html(html)
    media["images"] = images

    # ── Videos: from multiple possible sources ──
    videos = _extract_videos_from_html(html, asin)
    media["video_urls"] = videos

    log.info(f"    {asin}: {len(images)} images, {len(videos)} videos")
    return media


def _extract_images_from_html(html: str) -> list:
    """Extract high-res image URLs from Amazon product page HTML."""
    images = []
    seen = set()

    # Method 1: 'colorImages' JSON blob (most reliable)
    # Pattern: 'colorImages': {'initial': [{'hiRes': 'url', ...}, ...]}
    m = re.search(r"'colorImages'\s*:\s*\{[^}]*'initial'\s*:\s*(\[.+?\])\s*\}", html, re.DOTALL)
    if m:
        try:
            img_data = json.loads(m.group(1).replace("'", '"'))
            for item in img_data:
                url = item.get("hiRes") or item.get("large") or ""
                if url and url not in seen:
                    seen.add(url)
                    images.append(url)
        except (json.JSONDecodeError, AttributeError):
            pass

    # Method 2: 'imageGalleryData' JSON
    m2 = re.search(r'"imageGalleryData"\s*:\s*(\[.+?\])', html, re.DOTALL)
    if m2 and not images:
        try:
            gallery = json.loads(m2.group(1))
            for item in gallery:
                url = item.get("mainUrl") or item.get("thumbUrl") or ""
                if url and url not in seen:
                    seen.add(url)
                    images.append(url)
        except (json.JSONDecodeError, AttributeError):
            pass

    # Method 3: data-old-hires or data-a-dynamic-image attributes
    if not images:
        soup = BeautifulSoup(html, "html.parser")
        for img in soup.find_all("img"):
            hires = img.get("data-old-hires", "")
            if hires and "images-amazon.com" in hires and hires not in seen:
                seen.add(hires)
                images.append(hires)

            # data-a-dynamic-image is a JSON dict of {url: [w, h]}
            dyn = img.get("data-a-dynamic-image", "")
            if dyn:
                try:
                    dyn_dict = json.loads(dyn)
                    for img_url in dyn_dict:
                        if "images-amazon.com" in img_url and img_url not in seen:
                            seen.add(img_url)
                            images.append(img_url)
                except json.JSONDecodeError:
                    pass

    return images


def _extract_videos_from_html(html: str, asin: str) -> list:
    """Extract video URLs from Amazon product page."""
    videos = []
    seen = set()

    # Method 1: Look for video URLs in script tags
    # Amazon embeds video data in various JS variables
    video_patterns = [
        # Direct .mp4 URLs from Amazon video CDN
        r'(https?://[^"\'\s]+\.amazon\.com/[^"\'\s]*\.mp4[^"\'\s]*)',
        # Video manifest / streaming URLs
        r'"url"\s*:\s*"(https?://[^"]+\.mp4[^"]*)"',
        r"'url'\s*:\s*'(https?://[^']+\.mp4[^']*)'",
        # Video in data attributes
        r'data-video-url="(https?://[^"]+)"',
        r'videoUrl["\s:]+["\'](https?://[^"\']+)["\']',
    ]

    for pattern in video_patterns:
        for m in re.finditer(pattern, html):
            url = m.group(1)
            if url not in seen and ".mp4" in url:
                seen.add(url)
                videos.append(url)

    # Method 2: Amazon's video widget data
    # Pattern: "videos": [{"url": "...", "title": "..."}, ...]
    m = re.search(r'"videos"\s*:\s*(\[\{.+?\}\])', html, re.DOTALL)
    if m:
        try:
            vid_data = json.loads(m.group(1))
            for v in vid_data:
                url = v.get("url", "") or v.get("videoUrl", "")
                if url and url not in seen:
                    seen.add(url)
                    videos.append(url)
        except (json.JSONDecodeError, AttributeError):
            pass

    # Method 3: A+ content videos
    m2 = re.search(r'"videoMediaCentralAssets"\s*:\s*(\[.+?\])', html, re.DOTALL)
    if m2:
        try:
            assets = json.loads(m2.group(1))
            for asset in assets:
                url = asset.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    videos.append(url)
        except (json.JSONDecodeError, AttributeError):
            pass

    return videos


# ─── Download media ──────────────────────────────────────────

def download_media(session: AmazonSession, media: dict, category: str) -> dict:
    """Download images and videos for a product."""
    asin = media["asin"]
    cat_dir = os.path.join(BASE_OUTPUT, category)
    images_dir = os.path.join(cat_dir, "media", "images")
    videos_dir = os.path.join(cat_dir, "media", "videos")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(videos_dir, exist_ok=True)

    stats = {"images_downloaded": 0, "videos_downloaded": 0, "images_skipped": 0}

    # Download images (limit to first 8 — usually the best angles)
    for idx, img_url in enumerate(media.get("images", [])[:8]):
        save_path = os.path.join(images_dir, f"{asin}_{idx:02d}.jpg")
        if os.path.exists(save_path) and os.path.getsize(save_path) > 1000:
            stats["images_skipped"] += 1
            continue
        if _download_file(session, img_url, save_path):
            stats["images_downloaded"] += 1

    # Download videos — Amazon uses HLS streams, need ffmpeg
    for idx, vid_url in enumerate(media.get("video_urls", [])):
        suffix = f"_v{idx:02d}" if idx > 0 else ""
        save_path = os.path.join(videos_dir, f"{asin}{suffix}.mp4")
        if os.path.exists(save_path) and os.path.getsize(save_path) > 10000:
            continue
        if _download_hls_video(vid_url, save_path):
            stats["videos_downloaded"] += 1

    return stats


def _download_file(session: AmazonSession, url: str, save_path: str) -> bool:
    """Download a single file with retry."""
    for attempt in range(2):
        try:
            resp = session.session.get(
                url, timeout=60, stream=True,
                headers={"Referer": "https://www.amazon.com/"}
            )
            if resp.status_code != 200:
                continue
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            if os.path.getsize(save_path) > 1000:
                return True
            else:
                os.remove(save_path)
        except Exception:
            pass
        time.sleep(1)
    return False


def _download_hls_video(hls_url: str, save_path: str, resolution="720") -> bool:
    """
    Download an HLS video stream.
    Amazon product videos are served as HLS (.m3u8) manifests.
    Strategy:
      1. Try ffmpeg if available (best: proper remux to mp4)
      2. Fallback: pure-Python TS segment download + concatenation
    """
    import subprocess

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    headers = {"Referer": "https://www.amazon.com/",
               "User-Agent": random.choice(USER_AGENTS)}

    try:
        # Fetch master manifest
        resp = requests.get(hls_url, timeout=15, headers=headers)
        if resp.status_code != 200:
            log.warning(f"    HLS manifest fetch failed: {resp.status_code}")
            return False

        manifest = resp.text
        stream_url = hls_url  # default: this IS the stream

        # If master playlist, pick the best quality sub-playlist
        if "#EXT-X-STREAM-INF" in manifest:
            best_url = None
            best_bandwidth = 0
            next_is_url = False

            for line in manifest.strip().split("\n"):
                line = line.strip()
                if line.startswith("#EXT-X-STREAM-INF"):
                    bw_match = re.search(r"BANDWIDTH=(\d+)", line)
                    bw = int(bw_match.group(1)) if bw_match else 0
                    next_is_url = True
                elif next_is_url and not line.startswith("#") and line:
                    next_is_url = False
                    full_url = line if line.startswith("http") else urljoin(hls_url, line)
                    if f"hls{resolution}" in line:
                        best_url = full_url
                        break
                    elif bw > best_bandwidth:
                        best_bandwidth = bw
                        best_url = full_url

            if not best_url:
                log.warning("    No suitable HLS stream found in manifest")
                return False
            stream_url = best_url

        # Method 1: Try ffmpeg if available
        try:
            result = subprocess.run(
                ["ffmpeg", "-y",
                 "-headers", "Referer: https://www.amazon.com/\r\n",
                 "-i", stream_url,
                 "-c", "copy", "-movflags", "+faststart",
                 save_path],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0 and os.path.getsize(save_path) > 10000:
                size_mb = os.path.getsize(save_path) / (1024 * 1024)
                log.info(f"    Video (ffmpeg): {os.path.basename(save_path)} ({size_mb:.1f}MB)")
                return True
        except FileNotFoundError:
            pass  # ffmpeg not installed, use fallback

        # Method 2: Pure-Python — download TS segments + concatenate
        return _download_hls_segments(stream_url, save_path, headers)

    except Exception as e:
        log.warning(f"    HLS download error: {e}")
        if os.path.exists(save_path):
            os.remove(save_path)
        return False


def _download_hls_segments(stream_url: str, save_path: str, headers: dict) -> bool:
    """Download HLS TS segments and concatenate into a single file."""
    try:
        resp = requests.get(stream_url, timeout=15, headers=headers)
        if resp.status_code != 200:
            return False

        manifest = resp.text
        base_url = stream_url.rsplit("/", 1)[0] + "/"

        # Collect segment URLs
        segment_urls = []
        for line in manifest.strip().split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                seg_url = line if line.startswith("http") else urljoin(base_url, line)
                segment_urls.append(seg_url)

        if not segment_urls:
            log.warning("    No segments found in HLS playlist")
            return False

        # Download and concatenate all TS segments
        with open(save_path, "wb") as out_f:
            for seg_url in segment_urls:
                seg_resp = requests.get(seg_url, timeout=30, headers=headers)
                if seg_resp.status_code == 200:
                    out_f.write(seg_resp.content)

        if os.path.getsize(save_path) > 10000:
            size_mb = os.path.getsize(save_path) / (1024 * 1024)
            log.info(f"    Video (ts-concat): {os.path.basename(save_path)} ({size_mb:.1f}MB)")
            return True
        else:
            os.remove(save_path)
            return False

    except Exception as e:
        log.warning(f"    TS segment download error: {e}")
        if os.path.exists(save_path):
            os.remove(save_path)
        return False


# ─── Orchestration ───────────────────────────────────────────

def crawl_category(keyword: str, category: str,
                   max_products: int = MAX_PRODUCTS_PER_KEYWORD) -> dict:
    """
    Full crawl for one keyword: search → detail → download.
    Returns stats dict.
    """
    session = AmazonSession()
    cat_dir = os.path.join(BASE_OUTPUT, category)
    os.makedirs(cat_dir, exist_ok=True)

    stats = {
        "keyword": keyword,
        "category": category,
        "products_found": 0,
        "products_scraped": 0,
        "products_with_video": 0,
        "total_images": 0,
        "total_videos": 0,
    }

    # Step 1: Search
    log.info(f"\n{'='*60}")
    log.info(f"Crawling: [{category}] \"{keyword}\" (max {max_products})")
    log.info(f"{'='*60}")

    search_results = search_amazon(session, keyword, max_pages=3, max_results=max_products)
    stats["products_found"] = len(search_results)

    if not search_results:
        log.warning("  No search results. Amazon may be blocking. Try again later.")
        return stats

    # Step 2: Fetch detail pages + extract media
    for idx, item in enumerate(search_results):
        asin = item["asin"]
        log.info(f"\n  [{idx+1}/{len(search_results)}] {asin}: {item['title'][:60]}")

        # Skip if already scraped
        meta_path = os.path.join(cat_dir, f"{asin}.json")
        if os.path.exists(meta_path):
            log.info(f"    Already scraped, skipping")
            stats["products_scraped"] += 1
            continue

        media = extract_product_media(session, asin)
        if not media:
            continue

        media["platform"] = "amazon"
        media["category"] = category
        media["keyword"] = keyword
        media["scraped_at"] = datetime.now().isoformat()

        # Step 3: Download media
        dl_stats = download_media(session, media, category)
        stats["total_images"] += dl_stats["images_downloaded"]
        stats["total_videos"] += dl_stats["videos_downloaded"]

        if media["video_urls"]:
            stats["products_with_video"] += 1

        # Save metadata
        media["download_stats"] = dl_stats
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(media, f, ensure_ascii=False, indent=2)

        stats["products_scraped"] += 1

    log.info(f"\n  Category '{category}' complete: {stats}")
    return stats


def run_batch():
    """Run all predefined categories."""
    log.info("=" * 60)
    log.info("Amazon Batch Crawl - All Categories")
    log.info("=" * 60)

    all_stats = []
    start = datetime.now()

    for category, keywords in BATCH_CATEGORIES.items():
        for keyword in keywords:
            stats = crawl_category(keyword, category)
            all_stats.append(stats)

    elapsed = (datetime.now() - start).total_seconds()

    # Summary
    total_products = sum(s["products_scraped"] for s in all_stats)
    total_with_video = sum(s["products_with_video"] for s in all_stats)
    total_images = sum(s["total_images"] for s in all_stats)
    total_videos = sum(s["total_videos"] for s in all_stats)

    log.info(f"\n{'='*60}")
    log.info(f"BATCH COMPLETE in {elapsed:.0f}s ({elapsed/60:.1f}min)")
    log.info(f"  Products scraped:    {total_products}")
    log.info(f"  Products with video: {total_with_video}")
    log.info(f"  Images downloaded:   {total_images}")
    log.info(f"  Videos downloaded:   {total_videos}")
    log.info(f"{'='*60}")

    # Save summary
    summary_path = os.path.join(BASE_OUTPUT, "crawl_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": elapsed,
            "stats": all_stats,
            "totals": {
                "products": total_products,
                "with_video": total_with_video,
                "images": total_images,
                "videos": total_videos,
            }
        }, f, ensure_ascii=False, indent=2)

    return all_stats


def show_status():
    """Show current crawl progress."""
    print(f"\n{'='*60}")
    print(f"  Amazon Spider - Status")
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

        print(f"  {category:15s} | meta: {meta_count:4d} | "
              f"images: {img_count:4d} | videos: {vid_count:3d}")

    print(f"  {'─'*50}")
    print(f"  {'TOTAL':15s} | meta: {total_meta:4d} | "
          f"images: {total_images:4d} | videos: {total_videos:3d}")
    print(f"{'='*60}")


def upload_to_server():
    """Upload local amazon_data/ to server via SSH (paramiko SFTP)."""
    try:
        import paramiko
    except ImportError:
        print("pip install paramiko  (needed for upload)")
        return

    if not os.path.isdir(BASE_OUTPUT):
        print("No local data to upload.")
        return

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("111.17.197.107", username="wangjieyi", password="wangjieyi@hkust", timeout=15)
    sftp = ssh.open_sftp()

    # Ensure remote dirs exist
    def sftp_makedirs(remote_path):
        dirs_to_make = []
        while remote_path and remote_path != "/":
            try:
                sftp.stat(remote_path)
                break
            except FileNotFoundError:
                dirs_to_make.append(remote_path)
                remote_path = os.path.dirname(remote_path)
        for d in reversed(dirs_to_make):
            sftp.mkdir(d)

    uploaded = 0
    skipped = 0

    for root, dirs, files in os.walk(BASE_OUTPUT):
        for fname in files:
            local_path = os.path.join(root, fname)
            rel_path = os.path.relpath(local_path, BASE_OUTPUT)
            # Convert Windows backslashes to forward slashes
            rel_path = rel_path.replace("\\", "/")
            remote_path = f"{REMOTE_OUTPUT}/{rel_path}"

            # Skip if remote file exists and is same size
            try:
                remote_stat = sftp.stat(remote_path)
                local_size = os.path.getsize(local_path)
                if remote_stat.st_size == local_size:
                    skipped += 1
                    continue
            except (FileNotFoundError, IOError):
                pass

            remote_dir = os.path.dirname(remote_path)
            sftp_makedirs(remote_dir)

            print(f"  Uploading: {rel_path}")
            sftp.put(local_path, remote_path)
            uploaded += 1

    sftp.close()
    ssh.close()
    print(f"\nUpload complete: {uploaded} files uploaded, {skipped} skipped (already exist)")


# ─── CLI ─────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Amazon Product Video & Image Spider",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--keyword", help="Search keyword (e.g., 'gold necklace')")
    parser.add_argument("--category", help="Product category name")
    parser.add_argument("--max-products", type=int, default=MAX_PRODUCTS_PER_KEYWORD,
                        help=f"Max products per keyword (default: {MAX_PRODUCTS_PER_KEYWORD})")
    parser.add_argument("--batch", action="store_true",
                        help="Run all predefined categories")
    parser.add_argument("--status", action="store_true", help="Show progress")
    parser.add_argument("--upload", action="store_true",
                        help="Upload local results to server via SSH")
    parser.add_argument("--output", help="Override output directory")

    args = parser.parse_args()

    if args.output:
        BASE_OUTPUT = args.output

    os.makedirs(BASE_OUTPUT, exist_ok=True)

    if args.status:
        show_status()
    elif args.upload:
        upload_to_server()
    elif args.batch:
        run_batch()
    elif args.keyword and args.category:
        crawl_category(args.keyword, args.category, args.max_products)
    else:
        parser.print_help()
