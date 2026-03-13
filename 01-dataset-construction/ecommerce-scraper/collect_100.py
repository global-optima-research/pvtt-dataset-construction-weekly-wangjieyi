"""
快速采集 100 个产品展示视频
聚焦 TikTok (视频) + Amazon (图片)

策略:
  - TikTok Shop 搜索 → 商品详情 → 推广视频 URL → 下载
  - TikTok 关键词视频搜索 → 直接获取视频 URL → 下载
  - Amazon 免费 Actor → 多角度产品图片
  - 4 品类 × 25 = 100 个视频

使用方法:
  python collect_100.py                    # 采集全部
  python collect_100.py --category watch   # 只采集手表
  python collect_100.py --download-only    # 仅下载已采集 URL
"""

import os
import sys
import json
import time
import logging
import argparse
import hashlib
import requests
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"collect100_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)

# ─── API Keys ───
from config import SCRAPECREATORS_KEY, APIFY_TOKEN

SC_BASE = "https://api.scrapecreators.com/v1"
APIFY_BASE = "https://api.apify.com/v2"

OUTPUT_DIR = "./data"

# 品类关键词: 每个品类多组关键词, 增加覆盖面
CATEGORIES = {
    "watch": [
        "luxury watch", "smart watch review", "watch unboxing",
        "men watch", "women watch", "automatic watch",
    ],
    "jewelry": [
        "jewelry", "necklace", "bracelet showcase",
        "ring", "earrings", "handmade jewelry",
    ],
    "handbag": [
        "handbag", "luxury bag", "shoulder bag review",
        "leather bag", "designer bag", "tote bag",
    ],
    "cosmetics": [
        "lipstick review", "foundation", "eyeshadow palette",
        "makeup tutorial", "skincare", "perfume",
    ],
}

TARGET_PER_CATEGORY = 25  # 4 × 25 = 100


# ─────────────────────────────────────────────
# TikTok 视频采集
# ─────────────────────────────────────────────

def tiktok_keyword_search(keyword: str, amount: int = 30) -> list:
    """TikTok 关键词视频搜索 (直接返回视频 URL)"""
    url = f"{SC_BASE}/tiktok/search/top"
    headers = {"x-api-key": SCRAPECREATORS_KEY}
    params = {"query": keyword, "amount": amount}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        # ScrapeCreators returns {success, credits_remaining, items, cursor}
        items = data.get("items", data.get("videos", data.get("data", [])))
        logger.info(f"  Got {len(items)} results, credits remaining: {data.get('credits_remaining', '?')}")
        return items
    except Exception as e:
        logger.warning(f"TikTok search failed for '{keyword}': {e}")
        return []


def tiktok_shop_search(keyword: str, amount: int = 50) -> list:
    """TikTok Shop 商品搜索"""
    url = f"{SC_BASE}/tiktok/shop/search"
    headers = {"x-api-key": SCRAPECREATORS_KEY}
    params = {"query": keyword, "amount": min(amount, 200)}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data.get("products", [])
    except Exception as e:
        logger.warning(f"TikTok shop search failed for '{keyword}': {e}")
        return []


def tiktok_product_detail(product_url: str) -> dict:
    """获取 TikTok Shop 商品详情 (含推广视频)"""
    url = f"{SC_BASE}/tiktok/product"
    headers = {"x-api-key": SCRAPECREATORS_KEY}
    params = {
        "url": product_url,
        "get_related_videos": "true",
        "region": "US",
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=90)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"TikTok product detail failed: {e}")
        return {}


def extract_video_url(video_item: dict) -> str:
    """从 TikTok 视频数据中提取下载 URL

    ScrapeCreators 返回的视频 URL 结构:
      video.play_addr / download_addr / download_no_watermark_addr
      每个都是 dict: {url_list: [url1, ...], uri: ..., data_size: ...}
    """
    video = video_item.get("video", {})
    if not isinstance(video, dict):
        return ""

    # 优先无水印下载 > play_addr_h264 > play_addr > download_addr
    for field in ["download_no_watermark_addr", "play_addr_h264", "play_addr", "download_addr"]:
        addr = video.get(field)
        if isinstance(addr, dict):
            url_list = addr.get("url_list", [])
            if isinstance(url_list, list) and url_list:
                return url_list[0]
        elif isinstance(addr, str) and addr.startswith("http"):
            return addr

    # 兜底: 旧格式兼容
    return (
        video.get("downloadAddr", "") or
        video.get("playAddr", "") or
        video_item.get("video_url", "") or
        ""
    )


def collect_tiktok_videos(category: str, keywords: list,
                          target: int = 25) -> list:
    """
    采集单个品类的 TikTok 视频

    返回: [{video_url, title, category, source, ...}, ...]
    """
    results = []
    save_dir = os.path.join(OUTPUT_DIR, "tiktok", category)
    os.makedirs(save_dir, exist_ok=True)

    # 策略 1: 关键词视频搜索 (直接得到视频URL, 最快)
    for kw in keywords:
        if len(results) >= target:
            break

        logger.info(f"[TikTok] Searching videos: '{kw}'")
        videos = tiktok_keyword_search(kw, amount=30)

        for vid in videos:
            if len(results) >= target:
                break

            video_url = extract_video_url(vid)
            if not video_url:
                continue

            vid_id = vid.get("id", hashlib.md5(video_url.encode()).hexdigest()[:12])

            # 去重
            existing_urls = {r["video_url"] for r in results}
            if video_url in existing_urls:
                continue

            media = {
                "video_id": str(vid_id),
                "title": vid.get("desc", "") or vid.get("title", ""),
                "platform": "tiktok",
                "category": category,
                "source_type": "keyword_search",
                "search_keyword": kw,
                "video_url": video_url,
                "cover_url": vid.get("video", {}).get("cover", ""),
                "author": vid.get("author", {}).get("nickname", vid.get("author", {}).get("unique_id", "")),
                "likes": (vid.get("statistics") or vid.get("stats") or {}).get("digg_count", (vid.get("statistics") or vid.get("stats") or {}).get("diggCount", 0)),
                "views": (vid.get("statistics") or vid.get("stats") or {}).get("play_count", (vid.get("statistics") or vid.get("stats") or {}).get("playCount", 0)),
                "tiktok_url": vid.get("url", ""),
                "collected_at": datetime.now().isoformat(),
            }

            results.append(media)

            meta_file = os.path.join(save_dir, f"vid_{vid_id}.json")
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(media, f, ensure_ascii=False, indent=2)

        time.sleep(1)

    # 策略 2: Shop 商品搜索 → 推广视频 (质量更高但更慢)
    if len(results) < target:
        for kw in keywords[:2]:  # 只用前2个关键词
            if len(results) >= target:
                break

            logger.info(f"[TikTok Shop] Searching: '{kw}'")
            products = tiktok_shop_search(kw, amount=20)

            for product in products[:10]:  # 每个关键词最多10个商品
                if len(results) >= target:
                    break

                # seo_url 是 dict: {canonical_url: "https://...", slug: "...", ...}
                seo = product.get("seo_url")
                if isinstance(seo, dict):
                    product_url = seo.get("canonical_url", "")
                elif isinstance(seo, str):
                    product_url = seo
                else:
                    product_url = ""

                if not product_url:
                    pid = product.get("product_id", "")
                    product_url = f"https://www.tiktok.com/shop/pdp/{pid}"

                try:
                    detail = tiktok_product_detail(product_url)
                    related_vids = detail.get("related_videos", [])

                    for rv in related_vids[:3]:
                        if len(results) >= target:
                            break

                        video_url = extract_video_url(rv)
                        if not video_url:
                            continue

                        existing_urls = {r["video_url"] for r in results}
                        if video_url in existing_urls:
                            continue

                        vid_id = rv.get("id", hashlib.md5(video_url.encode()).hexdigest()[:12])

                        media = {
                            "video_id": str(vid_id),
                            "title": rv.get("desc", "") or product.get("title", ""),
                            "platform": "tiktok",
                            "category": category,
                            "source_type": "shop_related_video",
                            "product_id": product.get("product_id", ""),
                            "search_keyword": kw,
                            "video_url": video_url,
                            "cover_url": rv.get("video", {}).get("cover", ""),
                            "author": rv.get("author", {}).get("nickname", ""),
                            "likes": rv.get("stats", {}).get("diggCount", 0),
                            "views": rv.get("stats", {}).get("playCount", 0),
                            "collected_at": datetime.now().isoformat(),
                        }

                        results.append(media)

                        meta_file = os.path.join(save_dir, f"shop_{vid_id}.json")
                        with open(meta_file, "w", encoding="utf-8") as f:
                            json.dump(media, f, ensure_ascii=False, indent=2)

                except Exception as e:
                    logger.warning(f"Shop detail failed: {e}")

                time.sleep(2)

    logger.info(f"[TikTok/{category}] Collected {len(results)} videos")
    return results


# ─────────────────────────────────────────────
# Amazon 图片采集
# ─────────────────────────────────────────────

def collect_amazon_images(category: str, keyword: str,
                          target: int = 25) -> list:
    """
    通过 Amazon 免费 Actor 采集产品图片 (thumbnailImage + highResolutionImages)
    """
    save_dir = os.path.join(OUTPUT_DIR, "amazon", category)
    os.makedirs(save_dir, exist_ok=True)

    results = []
    actor_id = "junglee~free-amazon-product-scraper"
    url = f"{APIFY_BASE}/acts/{actor_id}/run-sync-get-dataset-items"

    input_data = {
        "categoryUrls": [{"url": f"https://www.amazon.com/s?k={keyword}"}],
        "maxItems": target,
    }

    logger.info(f"[Amazon/{category}] Fetching {target} products for '{keyword}'...")

    try:
        resp = requests.post(
            url, params={"token": APIFY_TOKEN},
            json=input_data, timeout=600
        )

        if resp.status_code in (200, 201):
            items = resp.json()
            for item in items:
                asin = item.get("asin", "")
                if not asin:
                    continue

                # 收集所有可用图片
                images = []
                thumb = item.get("thumbnailImage", "")
                if thumb:
                    images.append(thumb)

                hi_res = item.get("highResolutionImages", [])
                if isinstance(hi_res, list):
                    for img in hi_res:
                        if isinstance(img, str) and img.startswith("http"):
                            images.append(img)
                        elif isinstance(img, dict):
                            img_url = img.get("url", "") or img.get("src", "")
                            if img_url:
                                images.append(img_url)

                gallery = item.get("galleryThumbnails", [])
                if isinstance(gallery, list):
                    for g in gallery:
                        if isinstance(g, str) and g.startswith("http"):
                            images.append(g)
                        elif isinstance(g, dict):
                            g_url = g.get("url", "") or g.get("src", "")
                            if g_url:
                                images.append(g_url)

                media = {
                    "asin": asin,
                    "title": item.get("title", ""),
                    "platform": "amazon",
                    "category": category,
                    "price": item.get("price", ""),
                    "images": images,
                    "videos_count": item.get("videosCount", 0),
                    "url": item.get("url", ""),
                    "collected_at": datetime.now().isoformat(),
                }

                results.append(media)
                meta_file = os.path.join(save_dir, f"{asin}.json")
                with open(meta_file, "w", encoding="utf-8") as f:
                    json.dump(media, f, ensure_ascii=False, indent=2)

            logger.info(f"[Amazon/{category}] Got {len(results)} products")
        else:
            logger.error(f"[Amazon] Error {resp.status_code}: {resp.text[:200]}")

    except Exception as e:
        logger.error(f"[Amazon/{category}] Failed: {e}")

    # Save index
    index_file = os.path.join(save_dir, "_index.json")
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return results


# ─────────────────────────────────────────────
# 视频下载
# ─────────────────────────────────────────────

def download_video(url: str, save_path: str, retries: int = 3) -> bool:
    """下载单个视频文件"""
    if os.path.exists(save_path) and os.path.getsize(save_path) > 10000:
        return True  # Already downloaded

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.tiktok.com/",
    }

    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, timeout=60, stream=True)
            if resp.status_code == 200:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                size = os.path.getsize(save_path)
                if size > 10000:
                    return True
                else:
                    os.remove(save_path)
            else:
                logger.warning(f"Download HTTP {resp.status_code}: {url[:60]}")
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                logger.warning(f"Download failed: {url[:60]}: {e}")

    return False


def download_all_videos(category_filter: str = None):
    """下载所有已采集的 TikTok 视频"""
    tiktok_dir = Path(OUTPUT_DIR) / "tiktok"
    if not tiktok_dir.exists():
        logger.info("No TikTok data found")
        return

    total = 0
    success = 0
    failed = 0

    for cat_dir in sorted(tiktok_dir.iterdir()):
        if not cat_dir.is_dir():
            continue
        category = cat_dir.name
        if category_filter and category != category_filter:
            continue

        videos_dir = cat_dir / "media" / "videos"
        os.makedirs(videos_dir, exist_ok=True)

        for json_file in sorted(cat_dir.glob("*.json")):
            if json_file.name.startswith("_"):
                continue

            with open(json_file, encoding="utf-8") as f:
                meta = json.load(f)

            video_url = meta.get("video_url", "")
            if not video_url:
                continue

            total += 1
            vid_id = meta.get("video_id", json_file.stem)
            save_path = str(videos_dir / f"{vid_id}.mp4")

            if download_video(video_url, save_path):
                success += 1
                size_mb = os.path.getsize(save_path) / 1024 / 1024
                logger.info(f"  [{category}] Downloaded {vid_id} ({size_mb:.1f}MB)")
            else:
                failed += 1

    logger.info(f"\nDownload complete: {success}/{total} success, {failed} failed")


# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────

def collect_all(category_filter: str = None):
    """采集所有品类"""
    all_videos = []
    all_images = []

    for category, keywords in CATEGORIES.items():
        if category_filter and category != category_filter:
            continue

        logger.info(f"\n{'='*50}")
        logger.info(f"Category: {category} (target: {TARGET_PER_CATEGORY} videos)")
        logger.info(f"{'='*50}")

        # TikTok 视频
        videos = collect_tiktok_videos(category, keywords, TARGET_PER_CATEGORY)
        all_videos.extend(videos)

        # Amazon 图片 (用第一个英文关键词)
        images = collect_amazon_images(category, keywords[0], TARGET_PER_CATEGORY)
        all_images.extend(images)

    # 保存总汇总
    summary = {
        "collected_at": datetime.now().isoformat(),
        "total_videos": len(all_videos),
        "total_image_products": len(all_images),
        "by_category": {},
    }
    for cat in CATEGORIES:
        cat_vids = [v for v in all_videos if v["category"] == cat]
        cat_imgs = [i for i in all_images if i["category"] == cat]
        summary["by_category"][cat] = {
            "videos": len(cat_vids),
            "image_products": len(cat_imgs),
        }

    summary_path = os.path.join(OUTPUT_DIR, "collection_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info(f"\n{'='*50}")
    logger.info(f"Collection Summary:")
    logger.info(f"  Total videos: {len(all_videos)}")
    logger.info(f"  Total image products: {len(all_images)}")
    for cat, stats in summary["by_category"].items():
        logger.info(f"  {cat}: {stats['videos']} videos, {stats['image_products']} image products")
    logger.info(f"{'='*50}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quick collect 100 product videos")
    parser.add_argument("--category", help="Single category: watch/jewelry/handbag/cosmetics")
    parser.add_argument("--download-only", action="store_true",
                        help="Only download videos from existing metadata")
    parser.add_argument("--target", type=int, default=25,
                        help="Videos per category (default: 25)")

    args = parser.parse_args()

    if args.target != 25:
        TARGET_PER_CATEGORY = args.target

    if args.download_only:
        download_all_videos(args.category)
    else:
        # Step 1: Collect metadata (video URLs)
        collect_all(args.category)

        # Step 2: Download videos
        logger.info("\n\nStarting video downloads...")
        download_all_videos(args.category)

        logger.info("\nDone! Next steps:")
        logger.info("  1. python video_processor.py --input data/ --output processed/videos/")
        logger.info("  2. python image_processor.py --input data/ --output processed/images/")
        logger.info("  3. python dataset_index.py --build")
