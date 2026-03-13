"""
主调度脚本
统一协调各平台采集任务，监控进度，生成报告

使用方法:
  python main.py --phase metadata    # 第一阶段: 采集 metadata（URL列表）
  python main.py --phase download    # 第二阶段: 批量下载媒体文件
  python main.py --phase report      # 查看进度报告
  python main.py --platform tiktok --category 手表  # 单平台单品类测试
"""

import argparse
import logging
import json
import os
import sys
from datetime import datetime
from config import CATEGORIES, TARGET_PER_CATEGORY_PER_PLATFORM, OUTPUT_BASE

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"scraper_{datetime.now().strftime('%Y%m%d')}.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 平台采集任务分发
# ─────────────────────────────────────────────

def run_metadata_collection(platform_filter: str = None, category_filter: str = None):
    """
    第一阶段: 采集所有平台商品 metadata（不下载媒体文件，只保存 URL）
    这一步相对轻量，可以快速建立 URL 列表
    """
    from scrapers.taobao_scraper import scrape_taobao_category
    from scrapers.amazon_etsy_scraper import scrape_amazon_category, scrape_etsy_category
    from scrapers.tiktok_xhs_scraper import scrape_tiktok_category, scrape_xiaohongshu_category
    
    # 平台配置：(采集函数, 使用的关键词语言)
    platform_scrapers = {
        "taobao":      (scrape_taobao_category,      "zh"),
        "amazon":      (scrape_amazon_category,       "en"),
        "etsy":        (scrape_etsy_category,         "en"),
        "tiktok":      (scrape_tiktok_category,       "en"),
        "xiaohongshu": (scrape_xiaohongshu_category,  "zh"),
    }
    
    total_collected = 0
    summary = {}
    
    for platform, (scraper_func, lang) in platform_scrapers.items():
        if platform_filter and platform != platform_filter:
            continue
        
        summary[platform] = {}
        
        for category_name, keywords in CATEGORIES.items():
            if category_filter and category_name != category_filter:
                continue
            
            keyword = keywords[lang]
            # 中文平台用第一个关键词，英文平台用英文关键词
            kw = keyword.split()[0]
            
            logger.info(f"\n{'='*50}")
            logger.info(f"开始采集: [{platform}] [{category_name}] 关键词: {kw}")
            logger.info(f"{'='*50}")
            
            try:
                results = scraper_func(kw, TARGET_PER_CATEGORY_PER_PLATFORM, category_name)
                summary[platform][category_name] = len(results)
                total_collected += len(results)
                logger.info(f"✓ [{platform}][{category_name}] 完成: {len(results)} 条")
            except Exception as e:
                logger.error(f"✗ [{platform}][{category_name}] 失败: {e}")
                summary[platform][category_name] = 0
    
    # 保存采集汇总
    summary_file = os.path.join(OUTPUT_BASE, "collection_summary.json")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_collected": total_collected,
            "by_platform": summary
        }, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n{'='*50}")
    logger.info(f"Metadata 采集完成! 共 {total_collected} 条")
    logger.info(f"汇总保存至: {summary_file}")
    
    return summary


def run_media_download(platform_filter: str = None, category_filter: str = None):
    """
    第二阶段: 批量下载媒体文件
    基于第一阶段保存的 metadata JSON，下载实际图片和视频
    """
    from media_downloader import download_platform_media
    from pathlib import Path
    
    platforms = ["taobao", "amazon", "etsy", "tiktok", "xiaohongshu"]
    
    for platform in platforms:
        if platform_filter and platform != platform_filter:
            continue
        
        platform_dir = os.path.join(OUTPUT_BASE, platform)
        if not os.path.exists(platform_dir):
            continue
        
        for category_name in CATEGORIES.keys():
            if category_filter and category_name != category_filter:
                continue
            
            category_dir = os.path.join(platform_dir, category_name)
            if not os.path.exists(category_dir):
                continue
            
            logger.info(f"\n[下载] [{platform}][{category_name}]")
            stats = download_platform_media(platform, category_name)
            logger.info(f"✓ [{platform}][{category_name}] 下载完成: {stats}")


def run_report():
    """生成进度报告"""
    from media_downloader import generate_download_report
    
    report = generate_download_report()
    
    print("\n" + "="*60)
    print("📊 数据采集进度报告")
    print("="*60)
    
    total_meta = 0
    total_images = 0
    total_videos = 0
    
    for platform, categories in report.items():
        print(f"\n🏪 {platform.upper()}")
        for category, stats in categories.items():
            print(f"   {category}: metadata={stats['metadata']}, "
                  f"图片={stats['images_downloaded']}, "
                  f"视频={stats['videos_downloaded']}")
            total_meta += stats['metadata']
            total_images += stats['images_downloaded']
            total_videos += stats['videos_downloaded']
    
    print(f"\n{'='*60}")
    print(f"📦 总计: {total_meta} 条 metadata")
    print(f"🖼️  图片: {total_images} 张已下载")
    print(f"🎬 视频: {total_videos} 个已下载")
    print(f"目标: 10,000 条 | 完成度: {total_meta/100:.1f}%")
    print("="*60)
    
    return report


# ─────────────────────────────────────────────
# 快速测试单个平台
# ─────────────────────────────────────────────

def quick_test():
    """
    快速测试：每个平台只跑5条，验证 API key 是否有效
    建议在正式采集前先跑这个
    """
    logger.info("=== 快速测试模式（每平台5条）===")
    
    from scrapers.taobao_scraper import scrape_taobao_category
    from scrapers.amazon_etsy_scraper import scrape_amazon_category, scrape_etsy_category
    from scrapers.tiktok_xhs_scraper import scrape_tiktok_category, scrape_xiaohongshu_category
    
    tests = [
        ("淘宝", lambda: scrape_taobao_category("手表", 5, "TEST_手表")),
        ("Amazon", lambda: scrape_amazon_category("watch", 5, "TEST_watch")),
        ("Etsy", lambda: scrape_etsy_category("jewelry", 5, "TEST_jewelry")),
        ("TikTok", lambda: scrape_tiktok_category("watch", 5, "TEST_watch")),
        ("小红书", lambda: scrape_xiaohongshu_category("手表", 5, "TEST_手表")),
    ]
    
    for name, test_func in tests:
        print(f"\n测试 {name}...")
        try:
            results = test_func()
            print(f"  ✓ {name}: {len(results)} 条 (期望5条)")
            if results:
                sample = results[0]
                print(f"    示例: 图片={len(sample.get('images', []))}张, "
                      f"视频={'有' if sample.get('video_url') or sample.get('videos') else '无'}")
        except Exception as e:
            print(f"  ✗ {name}: 失败 - {e}")
            print(f"    → 检查 API Key 或网络连接")


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="电商平台媒体采集工具")
    parser.add_argument("--phase", choices=["metadata", "download", "report", "test"],
                       default="metadata", help="执行阶段")
    parser.add_argument("--platform", help="过滤平台: taobao/amazon/etsy/tiktok/xiaohongshu")
    parser.add_argument("--category", help="过滤品类: 手表/珠宝/箱包/化妆品")
    args = parser.parse_args()
    
    os.makedirs(OUTPUT_BASE, exist_ok=True)
    
    if args.phase == "test":
        quick_test()
    elif args.phase == "metadata":
        run_metadata_collection(args.platform, args.category)
    elif args.phase == "download":
        run_media_download(args.platform, args.category)
    elif args.phase == "report":
        run_report()
