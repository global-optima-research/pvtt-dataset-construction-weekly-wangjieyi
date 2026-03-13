"""
媒体批量下载模块
将采集到的图片和视频 URL 批量下载到本地
支持断点续传、并发下载、失败重试
"""

import os
import json
import logging
import hashlib
import time
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
import requests
from config import OUTPUT_BASE

logger = logging.getLogger(__name__)


def get_file_ext(url: str, content_type: str = "") -> str:
    """从 URL 或 Content-Type 推断文件扩展名"""
    if "video" in content_type or any(url.endswith(e) for e in [".mp4", ".mov", ".webm"]):
        return ".mp4"
    elif any(url.endswith(e) for e in [".jpg", ".jpeg"]):
        return ".jpg"
    elif url.endswith(".png"):
        return ".png"
    elif url.endswith(".webp"):
        return ".webp"
    else:
        return ".jpg"  # 默认图片


def url_to_filename(url: str) -> str:
    """将 URL 哈希为文件名（避免路径过长问题）"""
    return hashlib.md5(url.encode()).hexdigest()[:16]


def download_file(url: str, save_path: str, retries: int = 3) -> bool:
    """
    下载单个文件（同步版本）
    支持断点续传：如果文件已存在且大小>0则跳过
    """
    if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
        return True  # 已下载，跳过
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.google.com/",
    }
    
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, timeout=30, stream=True)
            resp.raise_for_status()
            
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return True
            
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)   # 指数退避
            else:
                logger.warning(f"下载失败 {url[:60]}...: {e}")
                return False
    
    return False


async def download_file_async(session: aiohttp.ClientSession, url: str, save_path: str) -> bool:
    """下载单个文件（异步版本，用于并发下载）"""
    if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
        return True
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }
    
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as resp:
            if resp.status == 200:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                async with aiofiles.open(save_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(8192):
                        await f.write(chunk)
                return True
    except Exception as e:
        logger.warning(f"异步下载失败 {url[:60]}: {e}")
    
    return False


async def batch_download_async(download_tasks: list, max_concurrent: int = 10) -> dict:
    """
    并发批量下载
    download_tasks: [(url, save_path), ...]
    返回: {"success": count, "failed": count, "skipped": count}
    """
    stats = {"success": 0, "failed": 0, "skipped": 0}
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def download_with_semaphore(url, path):
        async with semaphore:
            if os.path.exists(path) and os.path.getsize(path) > 0:
                stats["skipped"] += 1
                return
            result = await download_file_async(session, url, path)
            if result:
                stats["success"] += 1
            else:
                stats["failed"] += 1
    
    connector = aiohttp.TCPConnector(limit=max_concurrent)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [download_with_semaphore(url, path) for url, path in download_tasks]
        
        # 分批执行，每批100个，显示进度
        batch_size = 100
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i+batch_size]
            await asyncio.gather(*batch)
            logger.info(f"下载进度: {min(i+batch_size, len(tasks))}/{len(tasks)} "
                       f"成功:{stats['success']} 失败:{stats['failed']} 跳过:{stats['skipped']}")
    
    return stats


def download_platform_media(platform: str, category_name: str):
    """
    根据保存的 metadata JSON，批量下载某平台某品类的所有媒体文件
    
    目录结构:
    data/
      {platform}/
        {category}/
          {item_id}.json        ← metadata（已由 scraper 保存）
          media/
            images/
              {item_id}_{n}.jpg ← 图片
            videos/
              {item_id}.mp4     ← 视频
    """
    meta_dir = os.path.join(OUTPUT_BASE, platform, category_name)
    media_dir = os.path.join(OUTPUT_BASE, platform, category_name, "media")
    images_dir = os.path.join(media_dir, "images")
    videos_dir = os.path.join(media_dir, "videos")
    
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(videos_dir, exist_ok=True)
    
    download_tasks = []
    
    # 读取所有 metadata JSON
    for json_file in Path(meta_dir).glob("*.json"):
        if json_file.name.startswith("_"):
            continue  # 跳过 _index.json
        
        with open(json_file, encoding="utf-8") as f:
            meta = json.load(f)
        
        item_id = (
            meta.get("item_id") or meta.get("asin") or 
            meta.get("listing_id") or meta.get("note_id") or
            meta.get("product_id") or meta.get("video_id") or
            json_file.stem
        )
        
        # ─── 图片下载任务 ───
        images = meta.get("images", [])
        for idx, img_url in enumerate(images):
            if not img_url or not img_url.startswith("http"):
                continue
            ext = get_file_ext(img_url)
            save_path = os.path.join(images_dir, f"{item_id}_{idx:02d}{ext}")
            download_tasks.append((img_url, save_path))
        
        # ─── 视频下载任务 ───
        # 单个视频 URL
        video_url = meta.get("video_url", "")
        if video_url and video_url.startswith("http"):
            save_path = os.path.join(videos_dir, f"{item_id}.mp4")
            download_tasks.append((video_url, save_path))
        
        # 多个视频（TikTok 推广视频列表）
        videos_list = meta.get("videos", [])
        for vidx, vid in enumerate(videos_list):
            if isinstance(vid, dict):
                vid_url = vid.get("url", "")
            else:
                vid_url = vid
            if vid_url and vid_url.startswith("http"):
                save_path = os.path.join(videos_dir, f"{item_id}_v{vidx:02d}.mp4")
                download_tasks.append((vid_url, save_path))
    
    logger.info(f"[{platform}/{category_name}] 准备下载 {len(download_tasks)} 个文件")
    
    # 执行并发下载
    stats = asyncio.run(batch_download_async(download_tasks, max_concurrent=8))
    
    logger.info(f"[{platform}/{category_name}] 下载完成: {stats}")
    return stats


def generate_download_report(output_base: str = OUTPUT_BASE) -> dict:
    """
    统计当前采集进度
    返回各平台各品类的数据量统计
    """
    report = {}
    
    for platform_dir in Path(output_base).iterdir():
        if not platform_dir.is_dir():
            continue
        platform = platform_dir.name
        report[platform] = {}
        
        for category_dir in platform_dir.iterdir():
            if not category_dir.is_dir():
                continue
            category = category_dir.name
            
            metadata_count = len(list(category_dir.glob("*.json")))
            
            media_dir = category_dir / "media"
            image_count = len(list((media_dir / "images").glob("*"))) if (media_dir / "images").exists() else 0
            video_count = len(list((media_dir / "videos").glob("*"))) if (media_dir / "videos").exists() else 0
            
            report[platform][category] = {
                "metadata": metadata_count,
                "images_downloaded": image_count,
                "videos_downloaded": video_count,
            }
    
    return report
