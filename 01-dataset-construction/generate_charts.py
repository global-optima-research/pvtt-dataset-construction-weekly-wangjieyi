#!/usr/bin/env python3
"""
PVTT 数据集可视化图表生成器
生成 PNG 图表用于周报和 GitHub 展示
"""
import json
import os
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ─── 配置 ─────────────────────────────────────────────────
plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 12,
    "axes.titlesize": 15,
    "axes.titleweight": "bold",
    "figure.facecolor": "white",
    "savefig.dpi": 150,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.3,
})

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "amazon_data"
CHART_DIR = SCRIPT_DIR / "charts"
CHART_DIR.mkdir(exist_ok=True)

# 调色板
COLORS = ["#4CAF50", "#2196F3", "#FF9800", "#9C27B0", "#F44336", "#00BCD4", "#795548"]
COLOR_DONE = "#4CAF50"
COLOR_PARTIAL = "#FF9800"
COLOR_TODO = "#E0E0E0"

# 完整类别列表（保持顺序）
ALL_CATEGORIES = ["necklace", "bracelet", "earring", "watch", "sunglasses", "handbag", "ring"]


# ─── 数据采集 ──────────────────────────────────────────────
def scan_data():
    stats = {}
    for cat in ALL_CATEGORIES:
        cat_dir = DATA_DIR / cat
        if not cat_dir.is_dir():
            stats[cat] = {"products": 0, "images": 0, "videos": 0,
                          "size_mb": 0, "with_video": 0, "no_images": 0,
                          "keywords_done": 0, "keywords_total": 3}
            continue

        jsons = list(cat_dir.glob("*.json"))
        img_dir = cat_dir / "media" / "images"
        vid_dir = cat_dir / "media" / "videos"
        imgs = list(img_dir.glob("*")) if img_dir.exists() else []
        vids = list(vid_dir.glob("*")) if vid_dir.exists() else []
        cat_bytes = sum(f.stat().st_size for f in cat_dir.rglob("*") if f.is_file())

        with_video = 0
        no_images = 0
        keywords = set()
        for jf in jsons:
            try:
                d = json.loads(jf.read_text(encoding="utf-8"))
                if d.get("keyword"):
                    keywords.add(d["keyword"])
                if d.get("video_urls"):
                    with_video += 1
                if not d.get("images"):
                    no_images += 1
            except Exception:
                pass

        stats[cat] = {
            "products": len(jsons), "images": len(imgs), "videos": len(vids),
            "size_mb": cat_bytes / 1024 / 1024, "with_video": with_video,
            "no_images": no_images, "keywords_done": len(keywords), "keywords_total": 3,
        }
    return stats


# ─── 图表 1: 各类别产品数量柱状图 ──────────────────────────
def chart_products_by_category(stats):
    cats = ALL_CATEGORIES
    values = [stats[c]["products"] for c in cats]
    colors = [COLORS[i % len(COLORS)] for i in range(len(cats))]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(cats, values, color=colors, edgecolor="white", linewidth=1.2)

    for bar, val in zip(bars, values):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                    str(val), ha="center", va="bottom", fontweight="bold", fontsize=13)

    ax.set_title("各类别已采集产品数量")
    ax.set_ylabel("产品数")
    ax.set_ylim(0, max(values) * 1.2 if max(values) > 0 else 10)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    path = CHART_DIR / "01_products_by_category.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  [1/6] {path.name}")


# ─── 图表 2: 各类别视频 & 图片数量分组柱状图 ───────────────
def chart_media_by_category(stats):
    cats = ALL_CATEGORIES
    images = [stats[c]["images"] for c in cats]
    videos = [stats[c]["videos"] for c in cats]

    x = range(len(cats))
    width = 0.35
    fig, ax = plt.subplots(figsize=(10, 5))
    bars1 = ax.bar([i - width/2 for i in x], images, width, label="图片", color="#2196F3")
    bars2 = ax.bar([i + width/2 for i in x], videos, width, label="视频", color="#FF9800")

    for bar, val in zip(bars1, images):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                    str(val), ha="center", va="bottom", fontsize=10)
    for bar, val in zip(bars2, videos):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                    str(val), ha="center", va="bottom", fontsize=10)

    ax.set_title("各类别图片与视频采集量")
    ax.set_ylabel("数量")
    ax.set_xticks(list(x))
    ax.set_xticklabels(cats)
    ax.legend()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    path = CHART_DIR / "02_media_by_category.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  [2/6] {path.name}")


# ─── 图表 3: 数据量占比饼图 ───────────────────────────────
def chart_size_pie(stats):
    cats = [c for c in ALL_CATEGORIES if stats[c]["size_mb"] > 0]
    sizes = [stats[c]["size_mb"] for c in cats]
    labels = [f"{c}\n({s:.0f} MB)" for c, s in zip(cats, sizes)]
    colors = [COLORS[ALL_CATEGORIES.index(c) % len(COLORS)] for c in cats]

    fig, ax = plt.subplots(figsize=(8, 6))
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors, autopct="%1.1f%%",
        startangle=90, pctdistance=0.75,
        wedgeprops={"edgecolor": "white", "linewidth": 2},
    )
    for t in autotexts:
        t.set_fontsize(11)
        t.set_fontweight("bold")

    ax.set_title("各类别数据量占比（总计 {:.0f} MB）".format(sum(sizes)))

    path = CHART_DIR / "03_size_distribution.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  [3/6] {path.name}")


# ─── 图表 4: 爬取进度条 ──────────────────────────────────
def chart_crawl_progress(stats):
    cats = ALL_CATEGORIES
    done = [stats[c]["keywords_done"] for c in cats]
    total = [stats[c]["keywords_total"] for c in cats]
    pct = [d / t * 100 if t > 0 else 0 for d, t in zip(done, total)]

    fig, ax = plt.subplots(figsize=(10, 4.5))

    # 背景条（总量）
    ax.barh(cats, [100] * len(cats), color=COLOR_TODO, height=0.6)
    # 前景条（完成量）
    bar_colors = [COLOR_DONE if p == 100 else COLOR_PARTIAL if p > 0 else COLOR_TODO for p in pct]
    ax.barh(cats, pct, color=bar_colors, height=0.6)

    for i, (p, d, t) in enumerate(zip(pct, done, total)):
        label = f"{d}/{t} 关键词" + (" ✓" if p == 100 else "")
        ax.text(max(p, 5) + 2, i, label, va="center", fontsize=11)

    ax.set_xlim(0, 120)
    ax.set_title("各类别爬取进度")
    ax.set_xlabel("完成百分比 (%)")
    ax.invert_yaxis()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    path = CHART_DIR / "04_crawl_progress.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  [4/6] {path.name}")


# ─── 图表 5: 媒体提取成功率 ──────────────────────────────
def chart_extraction_success(stats):
    total = sum(stats[c]["products"] for c in ALL_CATEGORIES)
    with_both = 0
    only_img = 0
    only_vid = 0
    nothing = 0

    for cat_dir in DATA_DIR.iterdir():
        if not cat_dir.is_dir() or cat_dir.name.startswith("."):
            continue
        for jf in cat_dir.glob("*.json"):
            try:
                d = json.loads(jf.read_text(encoding="utf-8"))
                has_img = bool(d.get("images"))
                has_vid = bool(d.get("video_urls"))
                if has_img and has_vid:
                    with_both += 1
                elif has_img:
                    only_img += 1
                elif has_vid:
                    only_vid += 1
                else:
                    nothing += 1
            except Exception:
                nothing += 1

    labels = ["图片+视频", "仅图片", "仅视频", "均无"]
    values = [with_both, only_img, only_vid, nothing]
    colors = ["#4CAF50", "#2196F3", "#FF9800", "#E0E0E0"]

    fig, ax = plt.subplots(figsize=(7, 6))
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, colors=colors, autopct=lambda p: f"{p:.1f}%\n({int(p*sum(values)/100)})",
        startangle=90, wedgeprops={"edgecolor": "white", "linewidth": 2},
    )
    for t in autotexts:
        t.set_fontsize(10)

    ax.set_title(f"产品媒体提取成功率（共 {sum(values)} 产品）")

    path = CHART_DIR / "05_extraction_success.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  [5/6] {path.name}")


# ─── 图表 6: Pipeline 概览（文字信息图）──────────────────
def chart_pipeline_summary(stats):
    total_products = sum(stats[c]["products"] for c in ALL_CATEGORIES)
    total_images = sum(stats[c]["images"] for c in ALL_CATEGORIES)
    total_videos = sum(stats[c]["videos"] for c in ALL_CATEGORIES)
    total_mb = sum(stats[c]["size_mb"] for c in ALL_CATEGORIES)
    cats_done = sum(1 for c in ALL_CATEGORIES if stats[c]["keywords_done"] == 3)

    fig, axes = plt.subplots(1, 4, figsize=(14, 3.5))
    fig.suptitle("PVTT 数据集采集总览", fontsize=16, fontweight="bold", y=1.02)

    metrics = [
        ("产品数", str(total_products), f"目标: 420", "#4CAF50"),
        ("图片数", str(total_images), f"avg {total_images/max(total_products,1):.1f}/产品", "#2196F3"),
        ("视频数", str(total_videos), f"{total_videos/max(total_products,1)*100:.0f}% 含视频", "#FF9800"),
        ("数据量", f"{total_mb:.0f} MB", f"{cats_done}/7 类别完成", "#9C27B0"),
    ]

    for ax, (title, value, subtitle, color) in zip(axes, metrics):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.text(0.5, 0.7, value, ha="center", va="center",
                fontsize=32, fontweight="bold", color=color)
        ax.text(0.5, 0.35, title, ha="center", va="center",
                fontsize=14, color="#333")
        ax.text(0.5, 0.15, subtitle, ha="center", va="center",
                fontsize=11, color="#888")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

    path = CHART_DIR / "06_summary_dashboard.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  [6/6] {path.name}")


# ─── 主入口 ──────────────────────────────────────────────
def main():
    print("PVTT 数据集可视化图表生成")
    print("=" * 40)
    print(f"数据目录: {DATA_DIR}")
    print(f"输出目录: {CHART_DIR}")
    print()

    stats = scan_data()

    print("生成图表:")
    chart_products_by_category(stats)
    chart_media_by_category(stats)
    chart_size_pie(stats)
    chart_crawl_progress(stats)
    chart_extraction_success(stats)
    chart_pipeline_summary(stats)

    print(f"\n完成! 共生成 6 张图表 → {CHART_DIR}/")


if __name__ == "__main__":
    main()
