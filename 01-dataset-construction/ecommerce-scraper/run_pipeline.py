"""
数据采集 & 处理统一管线

完整流程:
  1. 采集 Metadata (从各平台获取产品 URL)
  2. 批量下载媒体 (图片 + 视频)
  3. 视频处理 (镜头分割 + 标准化 720p/24fps/2-4s)
  4. 图片处理 (白底标准化 + RGBA 透明底)
  5. 构建索引 (统一元信息管理)

使用方法:
  # 完整流程
  python run_pipeline.py --all

  # 分步执行
  python run_pipeline.py --step scrape          # 步骤1+2: 采集+下载
  python run_pipeline.py --step video           # 步骤3: 视频处理
  python run_pipeline.py --step image           # 步骤4: 图片处理
  python run_pipeline.py --step index           # 步骤5: 构建索引

  # 仅查看当前进度
  python run_pipeline.py --status

  # 指定平台/品类
  python run_pipeline.py --step scrape --platform etsy --category 珠宝
"""

import os
import sys
import logging
import argparse
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            encoding="utf-8"
        ),
    ]
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────

DATA_DIR = "./data"              # 原始采集数据
PROCESSED_DIR = "./processed"    # 处理后数据
INDEX_PATH = "./dataset_index.json"
PVTT_EXPORT_DIR = "./pvtt_export/annotations"

# 视频标准化参数
VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
VIDEO_FPS = 24

# 图片标准化参数
IMAGE_SIZE = 1024


# ─────────────────────────────────────────────
# 步骤函数
# ─────────────────────────────────────────────

def step_scrape(platform: str = None, category: str = None):
    """步骤 1+2: 采集 Metadata + 下载媒体"""
    from main import run_metadata_collection, run_media_download

    logger.info("\n" + "="*60)
    logger.info("步骤 1: 采集 Metadata")
    logger.info("="*60)
    run_metadata_collection(platform, category)

    logger.info("\n" + "="*60)
    logger.info("步骤 2: 下载媒体文件")
    logger.info("="*60)
    run_media_download(platform, category)


def step_video():
    """步骤 3: 视频处理 (镜头分割 + 标准化)"""
    from video_processor import process_all_videos

    logger.info("\n" + "="*60)
    logger.info("步骤 3: 视频处理")
    logger.info("="*60)

    output_dir = os.path.join(PROCESSED_DIR, "videos")
    process_all_videos(
        DATA_DIR, output_dir,
        target_w=VIDEO_WIDTH, target_h=VIDEO_HEIGHT,
        target_fps=VIDEO_FPS,
    )


def step_image(generate_rgba: bool = True):
    """步骤 4: 图片处理 (白底标准化 + RGBA)"""
    from image_processor import process_all_images

    logger.info("\n" + "="*60)
    logger.info("步骤 4: 图片处理")
    logger.info("="*60)

    output_dir = os.path.join(PROCESSED_DIR, "images")
    process_all_images(
        DATA_DIR, output_dir,
        generate_rgba=generate_rgba,
        target_size=(IMAGE_SIZE, IMAGE_SIZE),
    )


def step_index():
    """步骤 5: 构建统一索引"""
    from dataset_index import build_unified_index, print_stats, export_pvtt_format

    logger.info("\n" + "="*60)
    logger.info("步骤 5: 构建索引")
    logger.info("="*60)

    index = build_unified_index(DATA_DIR, PROCESSED_DIR, INDEX_PATH)
    print_stats(index)

    # 同时导出 PVTT 格式
    export_pvtt_format(index, PVTT_EXPORT_DIR)


def show_status():
    """显示当前数据集状态"""
    from main import run_report
    from dataset_index import print_stats

    print("\n" + "="*60)
    print("  数据采集 & 处理 - 当前状态")
    print("="*60)

    # 采集进度
    run_report()

    # 索引统计
    if os.path.exists(INDEX_PATH):
        import json
        with open(INDEX_PATH, encoding="utf-8") as f:
            index = json.load(f)
        print_stats(index)
    else:
        print("\n  索引尚未构建, 请运行: python run_pipeline.py --step index")

    # 处理后文件统计
    print("\n  --- 处理后文件 ---")
    for subdir in ["videos", "images"]:
        p = os.path.join(PROCESSED_DIR, subdir)
        if os.path.exists(p):
            from pathlib import Path
            file_count = sum(1 for _ in Path(p).rglob("*") if _.is_file())
            print(f"    {subdir}: {file_count} 个文件")
        else:
            print(f"    {subdir}: (未创建)")


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="电商产品数据采集 & 处理统一管线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_pipeline.py --all                  # 完整流程
  python run_pipeline.py --step scrape          # 只采集
  python run_pipeline.py --step video           # 只处理视频
  python run_pipeline.py --step image           # 只处理图片
  python run_pipeline.py --step index           # 只建索引
  python run_pipeline.py --status               # 查看进度
  python run_pipeline.py --step scrape --platform etsy
        """
    )
    parser.add_argument("--all", action="store_true",
                        help="执行完整管线 (采集→下载→视频→图片→索引)")
    parser.add_argument("--step",
                        choices=["scrape", "video", "image", "index"],
                        help="执行单个步骤")
    parser.add_argument("--status", action="store_true",
                        help="查看当前进度")
    parser.add_argument("--platform",
                        help="指定平台 (taobao/amazon/etsy/tiktok/xiaohongshu)")
    parser.add_argument("--category",
                        help="指定品类 (手表/珠宝/箱包/化妆品)")
    parser.add_argument("--no-rgba", action="store_true",
                        help="跳过 RGBA 透明底生成")

    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.all:
        logger.info("开始完整管线...")
        start = datetime.now()

        step_scrape(args.platform, args.category)
        step_video()
        step_image(generate_rgba=not args.no_rgba)
        step_index()

        elapsed = (datetime.now() - start).total_seconds()
        logger.info(f"\n完整管线结束, 总耗时: {elapsed/60:.1f} 分钟")
    elif args.step:
        if args.step == "scrape":
            step_scrape(args.platform, args.category)
        elif args.step == "video":
            step_video()
        elif args.step == "image":
            step_image(generate_rgba=not args.no_rgba)
        elif args.step == "index":
            step_index()
    else:
        parser.print_help()
