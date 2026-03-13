"""
图片处理模块
- 多角度产品图筛选
- 白底图标准化
- RGBA 透明底图生成 (使用 rembg)
- 统一分辨率和格式

使用方法:
  python image_processor.py --input data/ --output processed/images/
  python image_processor.py --single image.jpg --output processed/images/ --remove-bg
"""

import os
import json
import logging
import argparse
from pathlib import Path
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)

# 标准输出分辨率
DEFAULT_SIZE = (1024, 1024)


# ─────────────────────────────────────────────
# 图片质量检查
# ─────────────────────────────────────────────

def check_image_quality(image_path: str,
                        min_width: int = 200,
                        min_height: int = 200) -> Optional[dict]:
    """
    检查图片质量, 过滤低质量图片

    返回: 图片信息 dict 或 None (不合格)
    """
    try:
        with Image.open(image_path) as img:
            w, h = img.size
            if w < min_width or h < min_height:
                return None

            return {
                "width": w,
                "height": h,
                "mode": img.mode,
                "format": img.format,
                "aspect_ratio": round(w / h, 2),
            }
    except Exception as e:
        logger.warning(f"无法打开图片 {image_path}: {e}")
        return None


def is_white_background(image_path: str, threshold: float = 0.6,
                        white_value: int = 240) -> bool:
    """
    粗略判断图片是否为白底
    通过检查边缘像素的白色占比

    threshold: 白色像素占比阈值
    white_value: RGB 各通道超过此值视为白色
    """
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            w, h = img.size

            # 采样四边各 5px 的像素
            border = 5
            border_pixels = []

            for x in range(w):
                for y in range(min(border, h)):
                    border_pixels.append(img.getpixel((x, y)))
                for y in range(max(0, h - border), h):
                    border_pixels.append(img.getpixel((x, y)))
            for y in range(border, h - border):
                for x in range(min(border, w)):
                    border_pixels.append(img.getpixel((x, y)))
                for x in range(max(0, w - border), w):
                    border_pixels.append(img.getpixel((x, y)))

            if not border_pixels:
                return False

            white_count = sum(
                1 for r, g, b in border_pixels
                if r >= white_value and g >= white_value and b >= white_value
            )

            ratio = white_count / len(border_pixels)
            return ratio >= threshold

    except Exception:
        return False


# ─────────────────────────────────────────────
# 白底标准化
# ─────────────────────────────────────────────

def standardize_white_bg(image_path: str, output_path: str,
                         target_size: tuple = DEFAULT_SIZE) -> bool:
    """
    将图片标准化为白底正方形图 (居中, 保持比例)
    """
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")

            # 创建白底画布
            canvas = Image.new("RGB", target_size, (255, 255, 255))

            # 缩放图片 (保持比例, 留边距)
            margin = int(target_size[0] * 0.05)
            max_w = target_size[0] - 2 * margin
            max_h = target_size[1] - 2 * margin

            img.thumbnail((max_w, max_h), Image.LANCZOS)

            # 居中粘贴
            paste_x = (target_size[0] - img.width) // 2
            paste_y = (target_size[1] - img.height) // 2
            canvas.paste(img, (paste_x, paste_y))

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            canvas.save(output_path, "JPEG", quality=95)
            return True

    except Exception as e:
        logger.warning(f"白底标准化失败 {image_path}: {e}")
        return False


# ─────────────────────────────────────────────
# RGBA 透明底图生成
# ─────────────────────────────────────────────

def remove_background(image_path: str, output_path: str,
                      target_size: Optional[tuple] = None) -> bool:
    """
    使用 rembg 去除背景, 生成 RGBA 透明底 PNG

    需要: pip install rembg
    """
    try:
        from rembg import remove as rembg_remove
    except ImportError:
        logger.error("请安装 rembg: pip install rembg")
        return False

    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            result = rembg_remove(img)  # 返回 RGBA

            if target_size:
                # 缩放到目标尺寸 (保持比例, 透明背景)
                result.thumbnail(target_size, Image.LANCZOS)
                canvas = Image.new("RGBA", target_size, (0, 0, 0, 0))
                paste_x = (target_size[0] - result.width) // 2
                paste_y = (target_size[1] - result.height) // 2
                canvas.paste(result, (paste_x, paste_y))
                result = canvas

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            result.save(output_path, "PNG")
            return True

    except Exception as e:
        logger.warning(f"去背景失败 {image_path}: {e}")
        return False


# ─────────────────────────────────────────────
# 批量处理
# ─────────────────────────────────────────────

def process_all_images(input_base: str, output_base: str,
                       generate_rgba: bool = True,
                       target_size: tuple = DEFAULT_SIZE) -> dict:
    """
    批量处理所有已下载的产品图片

    扫描目录结构:
      input_base/{platform}/{category}/media/images/*.{jpg,png,webp}

    输出:
      output_base/{category}/white_bg/{product_id}_{N}.jpg    (白底图)
      output_base/{category}/rgba/{product_id}_{N}.png        (透明底图)

    返回: 处理统计
    """
    stats = {
        "total_images": 0,
        "qualified": 0,
        "white_bg_generated": 0,
        "rgba_generated": 0,
        "skipped_low_quality": 0,
        "by_category": {},
    }

    all_image_info = []
    input_path = Path(input_base)
    image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

    for platform_dir in sorted(input_path.iterdir()):
        if not platform_dir.is_dir():
            continue
        platform = platform_dir.name

        for category_dir in sorted(platform_dir.iterdir()):
            if not category_dir.is_dir():
                continue
            category = category_dir.name

            images_dir = category_dir / "media" / "images"
            if not images_dir.exists():
                continue

            white_bg_dir = os.path.join(output_base, category, "white_bg")
            rgba_dir = os.path.join(output_base, category, "rgba")
            os.makedirs(white_bg_dir, exist_ok=True)
            if generate_rgba:
                os.makedirs(rgba_dir, exist_ok=True)

            image_files = [
                f for f in images_dir.iterdir()
                if f.suffix.lower() in image_extensions
            ]

            if not image_files:
                continue

            logger.info(f"[{platform}/{category}] 发现 {len(image_files)} 张图片")

            if category not in stats["by_category"]:
                stats["by_category"][category] = {
                    "total": 0, "white_bg": 0, "rgba": 0,
                }

            for img_file in sorted(image_files):
                stats["total_images"] += 1
                stats["by_category"][category]["total"] += 1

                # 质量检查
                quality = check_image_quality(str(img_file))
                if not quality:
                    stats["skipped_low_quality"] += 1
                    continue

                stats["qualified"] += 1
                product_id = f"{platform}_{img_file.stem}"

                img_info = {
                    "image_id": product_id,
                    "source_path": str(img_file),
                    "platform": platform,
                    "category": category,
                    **quality,
                }

                # 白底图
                wb_path = os.path.join(white_bg_dir, f"{product_id}.jpg")
                if standardize_white_bg(str(img_file), wb_path, target_size):
                    stats["white_bg_generated"] += 1
                    stats["by_category"][category]["white_bg"] += 1
                    img_info["white_bg_path"] = wb_path
                    is_wb = is_white_background(str(img_file))
                    img_info["original_is_white_bg"] = is_wb

                # RGBA 透明底
                if generate_rgba:
                    rgba_path = os.path.join(rgba_dir, f"{product_id}.png")
                    if remove_background(str(img_file), rgba_path, target_size):
                        stats["rgba_generated"] += 1
                        stats["by_category"][category]["rgba"] += 1
                        img_info["rgba_path"] = rgba_path

                all_image_info.append(img_info)

    # 保存图片索引
    index_path = os.path.join(output_base, "images_index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump({
            "stats": stats,
            "images": all_image_info,
        }, f, ensure_ascii=False, indent=2)

    logger.info(f"\n{'='*50}")
    logger.info(f"图片处理完成!")
    logger.info(f"  总图片: {stats['total_images']}")
    logger.info(f"  合格: {stats['qualified']}")
    logger.info(f"  白底图: {stats['white_bg_generated']}")
    logger.info(f"  透明底图: {stats['rgba_generated']}")
    logger.info(f"  低质量跳过: {stats['skipped_low_quality']}")
    logger.info(f"  索引保存: {index_path}")

    return stats


# ─────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    parser = argparse.ArgumentParser(description="产品图片处理: 白底标准化 + 透明底")
    parser.add_argument("--input", default="./data",
                        help="输入目录 (含平台/品类/media/images/)")
    parser.add_argument("--output", default="./processed/images",
                        help="输出目录")
    parser.add_argument("--size", type=int, default=1024,
                        help="目标尺寸 (正方形, 默认1024)")
    parser.add_argument("--no-rgba", action="store_true",
                        help="跳过 RGBA 透明底生成 (加快速度)")
    parser.add_argument("--single",
                        help="处理单张图片")
    parser.add_argument("--remove-bg", action="store_true",
                        help="单张图片去背景模式")

    args = parser.parse_args()
    target_size = (args.size, args.size)

    if args.single:
        if args.remove_bg:
            out = os.path.join(args.output, Path(args.single).stem + "_rgba.png")
            ok = remove_background(args.single, out, target_size)
            print(f"{'成功' if ok else '失败'}: {out}")
        else:
            out = os.path.join(args.output, Path(args.single).stem + "_white.jpg")
            ok = standardize_white_bg(args.single, out, target_size)
            print(f"{'成功' if ok else '失败'}: {out}")
    else:
        process_all_images(
            args.input, args.output,
            generate_rgba=not args.no_rgba,
            target_size=target_size,
        )
