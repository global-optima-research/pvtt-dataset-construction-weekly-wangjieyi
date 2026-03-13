"""
数据集索引与元信息管理系统
- 统一索引: 整合所有平台 metadata
- 与 pvtt-benchmark 标注格式兼容
- 支持按品类/平台/视角/分辨率查询
- 统计报告

使用方法:
  python dataset_index.py --build          # 构建索引
  python dataset_index.py --stats          # 查看统计
  python dataset_index.py --export-pvtt    # 导出 pvtt-benchmark 格式
"""

import os
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 品类 ID 前缀映射
# ─────────────────────────────────────────────

CATEGORY_PREFIX = {
    "手表":   "WAT",
    "珠宝":   "JEW",
    "箱包":   "BAG",
    "化妆品": "BEA",
    "jewelry": "JEW",
    "watch":   "WAT",
    "handbag": "BAG",
    "cosmetics": "BEA",
    # 扩展品类
    "home":    "HOME",
    "fashion": "FASH",
    "electronics": "ELEC",
    "toys":    "TOYS",
    "clothing": "CLOT",
}


def get_category_prefix(category: str) -> str:
    """获取品类 ID 前缀"""
    cat_lower = category.lower().strip()
    for key, prefix in CATEGORY_PREFIX.items():
        if key.lower() in cat_lower or cat_lower in key.lower():
            return prefix
    return category[:4].upper()


# ─────────────────────────────────────────────
# 索引构建
# ─────────────────────────────────────────────

def build_unified_index(data_dir: str, processed_dir: str = "",
                        output_path: str = "./dataset_index.json") -> dict:
    """
    构建统一数据索引

    整合:
    1. data/ 下各平台的原始 metadata JSON
    2. processed/videos/ 下的视频片段索引
    3. processed/images/ 下的图片索引

    输出: 统一索引 JSON
    """
    index = {
        "version": "1.0",
        "created": datetime.now().isoformat(),
        "data_dir": data_dir,
        "processed_dir": processed_dir,
        "products": [],   # 产品级索引
        "clips": [],      # 视频片段索引
        "images": [],     # 图片索引
        "stats": {},
    }

    product_counter = defaultdict(int)
    data_path = Path(data_dir)

    # ── 步骤 1: 扫描原始 metadata ──
    for platform_dir in sorted(data_path.iterdir()):
        if not platform_dir.is_dir():
            continue
        platform = platform_dir.name

        for category_dir in sorted(platform_dir.iterdir()):
            if not category_dir.is_dir():
                continue
            category = category_dir.name
            prefix = get_category_prefix(category)

            for json_file in sorted(category_dir.glob("*.json")):
                if json_file.name.startswith("_"):
                    continue

                try:
                    with open(json_file, encoding="utf-8") as f:
                        meta = json.load(f)
                except Exception:
                    continue

                # 生成统一产品 ID
                product_counter[prefix] += 1
                product_id = f"{prefix}{product_counter[prefix]:04d}"

                # 提取原始平台 ID
                original_id = (
                    meta.get("item_id") or meta.get("asin") or
                    meta.get("listing_id") or meta.get("note_id") or
                    meta.get("product_id") or meta.get("video_id") or
                    json_file.stem
                )

                # 统计媒体数量
                images = meta.get("images", [])
                has_video = bool(
                    meta.get("video_url") or meta.get("videos")
                )
                video_count = 1 if meta.get("video_url") else 0
                videos_list = meta.get("videos", [])
                if isinstance(videos_list, list):
                    video_count += len(videos_list)

                product = {
                    "product_id": product_id,
                    "original_id": str(original_id),
                    "platform": platform,
                    "category": category,
                    "category_prefix": prefix,
                    "title": meta.get("title", ""),
                    "price": meta.get("price", ""),
                    "source_url": meta.get("url", meta.get("product_url", "")),
                    "image_count": len(images),
                    "video_count": video_count,
                    "has_video": has_video,
                    "metadata_path": str(json_file),
                }
                index["products"].append(product)

    # ── 步骤 2: 整合处理后的视频片段索引 ──
    if processed_dir:
        clips_index_path = os.path.join(processed_dir, "videos", "clips_index.json")
        if os.path.exists(clips_index_path):
            with open(clips_index_path, encoding="utf-8") as f:
                clips_data = json.load(f)
            index["clips"] = clips_data.get("clips", [])

        # ── 步骤 3: 整合处理后的图片索引 ──
        images_index_path = os.path.join(processed_dir, "images", "images_index.json")
        if os.path.exists(images_index_path):
            with open(images_index_path, encoding="utf-8") as f:
                images_data = json.load(f)
            index["images"] = images_data.get("images", [])

    # ── 步骤 4: 计算统计 ──
    index["stats"] = compute_stats(index)

    # 保存索引
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    logger.info(f"统一索引已保存: {output_path}")
    return index


# ─────────────────────────────────────────────
# 统计计算
# ─────────────────────────────────────────────

def compute_stats(index: dict) -> dict:
    """计算数据集统计信息"""
    products = index["products"]
    clips = index.get("clips", [])
    images = index.get("images", [])

    stats = {
        "total_products": len(products),
        "total_clips": len(clips),
        "total_images": len(images),
        "products_with_video": sum(1 for p in products if p.get("has_video")),
        "by_platform": defaultdict(int),
        "by_category": defaultdict(lambda: {
            "products": 0, "with_video": 0, "total_images": 0,
        }),
    }

    for p in products:
        stats["by_platform"][p["platform"]] += 1
        cat = p["category"]
        stats["by_category"][cat]["products"] += 1
        if p.get("has_video"):
            stats["by_category"][cat]["with_video"] += 1
        stats["by_category"][cat]["total_images"] += p.get("image_count", 0)

    # Convert defaultdicts to regular dicts for JSON serialization
    stats["by_platform"] = dict(stats["by_platform"])
    stats["by_category"] = {k: dict(v) for k, v in stats["by_category"].items()}

    return stats


# ─────────────────────────────────────────────
# PVTT Benchmark 格式导出
# ─────────────────────────────────────────────

def export_pvtt_format(index: dict, output_dir: str) -> str:
    """
    将索引导出为 pvtt-benchmark 兼容的 metadata.json 格式

    适配 pvtt-training-free-main/data/pvtt-benchmark/annotations/metadata.json
    """
    pvtt_metadata = {
        "version": "1.0",
        "created": datetime.now().strftime("%Y-%m-%d"),
        "source": "ecommerce_scraper",
        "samples": [],
    }

    for product in index["products"]:
        if not product.get("has_video"):
            continue  # 只导出有视频的产品

        sample = {
            "id": product["product_id"],
            "category": product["category"],
            "subcategory": "",
            "template_video": {
                "path": "",   # 需要手动映射
                "duration_sec": 0,
                "resolution": "",
                "fps": 24,
                "total_frames": 0,
                "source": product["platform"],
                "source_url": product.get("source_url", ""),
            },
            "source_product": {
                "image_path": "",
                "description": product.get("title", ""),
                "attributes": {},
            },
            "target_product": None,  # 需要后续配对
            "prompts": {
                "source": product.get("title", ""),
                "target": "",
            },
            "difficulty": "medium",
            "shot_type": "pure_product",
            "added_date": datetime.now().strftime("%Y-%m-%d"),
        }

        # 如果有处理后的视频片段, 链接最佳片段
        product_clips = [
            c for c in index.get("clips", [])
            if product["original_id"] in c.get("clip_id", "")
        ]
        if product_clips:
            best = product_clips[0]
            sample["template_video"]["path"] = best.get("output_path", "")
            sample["template_video"]["duration_sec"] = best.get("duration_sec", 0)
            sample["template_video"]["resolution"] = best.get("resolution", "")
            sample["template_video"]["fps"] = best.get("fps", 24)

        pvtt_metadata["samples"].append(sample)

    output_path = os.path.join(output_dir, "metadata.json")
    os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(pvtt_metadata, f, ensure_ascii=False, indent=2)

    logger.info(f"PVTT 格式导出: {len(pvtt_metadata['samples'])} 个样本 → {output_path}")
    return output_path


# ─────────────────────────────────────────────
# 报告打印
# ─────────────────────────────────────────────

def print_stats(index: dict):
    """打印数据集统计报告"""
    stats = index.get("stats", compute_stats(index))

    print(f"\n{'='*60}")
    print(f"  PVTT 数据集统计报告")
    print(f"  生成时间: {index.get('created', 'N/A')}")
    print(f"{'='*60}")

    print(f"\n  总产品数:     {stats['total_products']}")
    print(f"  含视频产品:   {stats['products_with_video']}")
    print(f"  视频片段数:   {stats['total_clips']}")
    print(f"  图片数:       {stats['total_images']}")

    print(f"\n  --- 按平台 ---")
    for platform, count in sorted(stats.get("by_platform", {}).items()):
        print(f"    {platform:15s}: {count} 个产品")

    print(f"\n  --- 按品类 ---")
    for category, cat_stats in sorted(stats.get("by_category", {}).items()):
        print(
            f"    {category:10s}: "
            f"{cat_stats['products']} 产品, "
            f"{cat_stats['with_video']} 有视频, "
            f"{cat_stats['total_images']} 张图"
        )

    total = stats['total_products']
    target = 10000
    print(f"\n  进度: {total}/{target} ({total/target*100:.1f}%)")
    print(f"{'='*60}\n")


# ─────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    parser = argparse.ArgumentParser(description="数据集索引管理")
    parser.add_argument("--build", action="store_true",
                        help="构建统一索引")
    parser.add_argument("--stats", action="store_true",
                        help="查看统计报告")
    parser.add_argument("--export-pvtt", action="store_true",
                        help="导出 pvtt-benchmark 格式")
    parser.add_argument("--data-dir", default="./data",
                        help="原始数据目录")
    parser.add_argument("--processed-dir", default="./processed",
                        help="处理后数据目录")
    parser.add_argument("--index-path", default="./dataset_index.json",
                        help="索引文件路径")
    parser.add_argument("--pvtt-output", default="./pvtt_export/annotations",
                        help="PVTT 导出目录")

    args = parser.parse_args()

    if args.build:
        index = build_unified_index(
            args.data_dir, args.processed_dir, args.index_path
        )
        print_stats(index)

    elif args.stats:
        if os.path.exists(args.index_path):
            with open(args.index_path, encoding="utf-8") as f:
                index = json.load(f)
            print_stats(index)
        else:
            print(f"索引文件不存在: {args.index_path}")
            print("请先运行: python dataset_index.py --build")

    elif args.export_pvtt:
        if os.path.exists(args.index_path):
            with open(args.index_path, encoding="utf-8") as f:
                index = json.load(f)
            export_pvtt_format(index, args.pvtt_output)
        else:
            print(f"索引文件不存在: {args.index_path}")

    else:
        parser.print_help()
