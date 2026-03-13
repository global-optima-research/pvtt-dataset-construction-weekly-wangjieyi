#!/usr/bin/env python3
"""
生成自包含的 Jupyter Notebook 可视化报告。
图表在生成时渲染并嵌入 notebook，GitHub 可直接预览。
"""
import json
import base64
import io
import os
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ─── 配置 ──────────────────────────────────────────
plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 12,
    "axes.titlesize": 15,
    "axes.titleweight": "bold",
    "figure.facecolor": "white",
})

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "amazon_data"
OUTPUT_NB = SCRIPT_DIR.parent / "week03_dataset_report.ipynb"

ALL_CATEGORIES = ["necklace", "bracelet", "earring", "watch", "sunglasses", "handbag", "ring"]
COLORS = ["#4CAF50", "#2196F3", "#FF9800", "#9C27B0", "#F44336", "#00BCD4", "#795548"]


# ─── 数据扫描 ──────────────────────────────────────
def scan_data():
    stats = {}
    for cat in ALL_CATEGORIES:
        cat_dir = DATA_DIR / cat
        if not cat_dir.is_dir():
            stats[cat] = dict(products=0, images=0, videos=0, size_mb=0,
                              with_video=0, no_images=0, keywords_done=0, keywords_total=3)
            continue
        jsons = list(cat_dir.glob("*.json"))
        img_dir = cat_dir / "media" / "images"
        vid_dir = cat_dir / "media" / "videos"
        imgs = list(img_dir.glob("*")) if img_dir.exists() else []
        vids = list(vid_dir.glob("*")) if vid_dir.exists() else []
        cat_bytes = sum(f.stat().st_size for f in cat_dir.rglob("*") if f.is_file())
        with_video = no_images = 0
        keywords = set()
        vid_sizes = []
        img_sizes = []
        for jf in jsons:
            try:
                d = json.loads(jf.read_text(encoding="utf-8"))
                if d.get("keyword"): keywords.add(d["keyword"])
                if d.get("video_urls"): with_video += 1
                if not d.get("images"): no_images += 1
            except: pass
        for v in vids: vid_sizes.append(v.stat().st_size)
        for im in imgs: img_sizes.append(im.stat().st_size)
        stats[cat] = dict(
            products=len(jsons), images=len(imgs), videos=len(vids),
            size_mb=cat_bytes/1024/1024, with_video=with_video, no_images=no_images,
            keywords_done=len(keywords), keywords_total=3,
            vid_sizes=vid_sizes, img_sizes=img_sizes,
        )
    return stats


# ─── 图表渲染为 base64 PNG ───────────────────────────
def fig_to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def render_summary(stats):
    tp = sum(stats[c]["products"] for c in ALL_CATEGORIES)
    ti = sum(stats[c]["images"] for c in ALL_CATEGORIES)
    tv = sum(stats[c]["videos"] for c in ALL_CATEGORIES)
    tm = sum(stats[c]["size_mb"] for c in ALL_CATEGORIES)
    cd = sum(1 for c in ALL_CATEGORIES if stats[c]["keywords_done"] == 3)
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.5))
    fig.suptitle("PVTT 数据集采集总览", fontsize=16, fontweight="bold", y=1.02)
    metrics = [
        ("产品数", str(tp), f"目标: 420", "#4CAF50"),
        ("图片数", str(ti), f"avg {ti/max(tp,1):.1f}/产品", "#2196F3"),
        ("视频数", str(tv), f"{tv/max(tp,1)*100:.0f}% 含视频", "#FF9800"),
        ("数据量", f"{tm:.0f} MB", f"{cd}/7 类别完成", "#9C27B0"),
    ]
    for ax, (title, value, subtitle, color) in zip(axes, metrics):
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.text(0.5, 0.7, value, ha="center", va="center", fontsize=32, fontweight="bold", color=color)
        ax.text(0.5, 0.35, title, ha="center", va="center", fontsize=14, color="#333")
        ax.text(0.5, 0.15, subtitle, ha="center", va="center", fontsize=11, color="#888")
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values(): s.set_visible(False)
    return fig_to_b64(fig)


def render_products_bar(stats):
    cats = ALL_CATEGORIES
    vals = [stats[c]["products"] for c in cats]
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(cats, vals, color=[COLORS[i] for i in range(len(cats))], edgecolor="white", linewidth=1.2)
    for b, v in zip(bars, vals):
        if v > 0: ax.text(b.get_x()+b.get_width()/2, b.get_height()+1, str(v), ha="center", fontweight="bold", fontsize=13)
    ax.set_title("各类别已采集产品数量"); ax.set_ylabel("产品数")
    ax.set_ylim(0, max(vals)*1.2 if max(vals)>0 else 10)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    return fig_to_b64(fig)


def render_media_grouped(stats):
    cats = ALL_CATEGORIES
    images = [stats[c]["images"] for c in cats]
    videos = [stats[c]["videos"] for c in cats]
    x = range(len(cats)); w = 0.35
    fig, ax = plt.subplots(figsize=(10, 5))
    b1 = ax.bar([i-w/2 for i in x], images, w, label="图片", color="#2196F3")
    b2 = ax.bar([i+w/2 for i in x], videos, w, label="视频", color="#FF9800")
    for b, v in zip(b1, images):
        if v > 0: ax.text(b.get_x()+b.get_width()/2, b.get_height()+2, str(v), ha="center", fontsize=10)
    for b, v in zip(b2, videos):
        if v > 0: ax.text(b.get_x()+b.get_width()/2, b.get_height()+2, str(v), ha="center", fontsize=10)
    ax.set_title("各类别图片与视频采集量"); ax.set_ylabel("数量")
    ax.set_xticks(list(x)); ax.set_xticklabels(cats); ax.legend()
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    return fig_to_b64(fig)


def render_size_pie(stats):
    cats = [c for c in ALL_CATEGORIES if stats[c]["size_mb"] > 0]
    sizes = [stats[c]["size_mb"] for c in cats]
    labels = [f"{c}\n({s:.0f} MB)" for c, s in zip(cats, sizes)]
    colors = [COLORS[ALL_CATEGORIES.index(c)] for c in cats]
    fig, ax = plt.subplots(figsize=(8, 6))
    wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%",
        startangle=90, pctdistance=0.75, wedgeprops={"edgecolor":"white","linewidth":2})
    for t in autotexts: t.set_fontsize(11); t.set_fontweight("bold")
    ax.set_title("各类别数据量占比（总计 {:.0f} MB）".format(sum(sizes)))
    return fig_to_b64(fig)


def render_progress(stats):
    cats = ALL_CATEGORIES
    done = [stats[c]["keywords_done"] for c in cats]
    total = [stats[c]["keywords_total"] for c in cats]
    pct = [d/t*100 if t>0 else 0 for d,t in zip(done, total)]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.barh(cats, [100]*len(cats), color="#E0E0E0", height=0.6)
    bar_colors = ["#4CAF50" if p==100 else "#FF9800" if p>0 else "#E0E0E0" for p in pct]
    ax.barh(cats, pct, color=bar_colors, height=0.6)
    for i, (p,d,t) in enumerate(zip(pct,done,total)):
        ax.text(max(p,5)+2, i, f"{d}/{t} 关键词" + (" ✓" if p==100 else ""), va="center", fontsize=11)
    ax.set_xlim(0, 120); ax.set_title("各类别爬取进度"); ax.set_xlabel("完成百分比 (%)")
    ax.invert_yaxis(); ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    return fig_to_b64(fig)


def render_extraction_pie(stats):
    with_both = only_img = only_vid = nothing = 0
    for cat_dir in DATA_DIR.iterdir():
        if not cat_dir.is_dir() or cat_dir.name.startswith("."): continue
        for jf in cat_dir.glob("*.json"):
            try:
                d = json.loads(jf.read_text(encoding="utf-8"))
                hi, hv = bool(d.get("images")), bool(d.get("video_urls"))
                if hi and hv: with_both += 1
                elif hi: only_img += 1
                elif hv: only_vid += 1
                else: nothing += 1
            except: nothing += 1
    vals = [with_both, only_img, only_vid, nothing]
    labels = ["图片+视频", "仅图片", "仅视频", "均无"]
    colors = ["#4CAF50", "#2196F3", "#FF9800", "#E0E0E0"]
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.pie(vals, labels=labels, colors=colors,
           autopct=lambda p: f"{p:.1f}%\n({int(p*sum(vals)/100)})",
           startangle=90, wedgeprops={"edgecolor":"white","linewidth":2})
    ax.set_title(f"产品媒体提取成功率（共 {sum(vals)} 产品）")
    return fig_to_b64(fig)


def render_video_size_hist(stats):
    all_sizes = []
    for c in ALL_CATEGORIES:
        all_sizes.extend(stats[c].get("vid_sizes", []))
    if not all_sizes:
        return None
    sizes_mb = [s/1024/1024 for s in all_sizes if s > 0]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.hist(sizes_mb, bins=20, color="#FF9800", edgecolor="white", linewidth=1)
    ax.axvline(sum(sizes_mb)/len(sizes_mb), color="#F44336", linestyle="--", linewidth=2, label=f"均值: {sum(sizes_mb)/len(sizes_mb):.1f} MB")
    ax.set_title(f"视频大小分布（共 {len(sizes_mb)} 个视频）")
    ax.set_xlabel("视频大小 (MB)"); ax.set_ylabel("数量"); ax.legend()
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    return fig_to_b64(fig)


# ─── Notebook 构建 ─────────────────────────────────
def make_md_cell(source):
    return {"cell_type": "markdown", "metadata": {}, "source": source.strip().split("\n")}

def make_code_cell_with_image(b64_png, code_comment=""):
    """创建一个带预渲染图片输出的代码 cell"""
    return {
        "cell_type": "code",
        "execution_count": 1,
        "metadata": {},
        "source": [f"# {code_comment}\n"] if code_comment else [""],
        "outputs": [{
            "output_type": "display_data",
            "data": {"image/png": b64_png, "text/plain": ["<Figure>"]},
            "metadata": {}
        }]
    }


def build_notebook(stats):
    # 汇总数据
    tp = sum(stats[c]["products"] for c in ALL_CATEGORIES)
    ti = sum(stats[c]["images"] for c in ALL_CATEGORIES)
    tv = sum(stats[c]["videos"] for c in ALL_CATEGORIES)
    tm = sum(stats[c]["size_mb"] for c in ALL_CATEGORIES)
    wv = sum(stats[c]["with_video"] for c in ALL_CATEGORIES)

    all_vid = []
    all_img = []
    for c in ALL_CATEGORIES:
        all_vid.extend(stats[c].get("vid_sizes", []))
        all_img.extend(stats[c].get("img_sizes", []))
    vid_mb = [s/1024/1024 for s in all_vid if s > 0]
    img_kb = [s/1024 for s in all_img if s > 0]

    cells = []

    # ── 标题 ──
    cells.append(make_md_cell("""# PVTT 数据集采集可视化报告

**项目：** Product Video Template Transfer (PVTT)
**负责人：** 王洁怡 (wangjieyi)
**更新日期：** 2026-03-09
**数据来源：** Amazon (amazon.com)"""))

    # ── 总览 ──
    cells.append(make_md_cell("---\n## 1. 总览"))
    cells.append(make_code_cell_with_image(render_summary(stats), "总览仪表盘"))

    # ── 各类别产品数量 ──
    cells.append(make_md_cell("---\n## 2. 各类别产品采集数量"))
    cells.append(make_code_cell_with_image(render_products_bar(stats), "各类别产品数量柱状图"))

    # ── 图片 & 视频 ──
    cells.append(make_md_cell("---\n## 3. 各类别图片与视频采集量"))
    cells.append(make_code_cell_with_image(render_media_grouped(stats), "图片与视频分组柱状图"))

    # ── 数据量饼图 ──
    cells.append(make_md_cell("---\n## 4. 各类别数据量占比"))
    cells.append(make_code_cell_with_image(render_size_pie(stats), "数据量占比饼图"))

    # ── 爬取进度 ──
    cells.append(make_md_cell("---\n## 5. 爬取进度"))
    cells.append(make_code_cell_with_image(render_progress(stats), "爬取进度条"))

    # ── 进度明细表 ──
    table_rows = ""
    for c in ALL_CATEGORIES:
        s = stats[c]
        status = "**已完成**" if s["keywords_done"]==3 else f"进行中 ({s['keywords_done']}/3)" if s["keywords_done"]>0 else "未开始"
        sz = f"{s['size_mb']:.0f} MB" if s['size_mb']>0 else "—"
        table_rows += f"| {c} | {s['products']} | {s['images']} | {s['videos']} | {sz} | {status} |\n"

    cells.append(make_md_cell(f"""
| 类别 | 产品数 | 图片数 | 视频数 | 数据量 | 状态 |
|------|--------|--------|--------|--------|------|
{table_rows}| **合计** | **{tp}** | **{ti}** | **{tv}** | **{tm:.0f} MB** | |"""))

    # ── 媒体提取成功率 ──
    cells.append(make_md_cell("---\n## 6. 媒体提取成功率"))
    cells.append(make_code_cell_with_image(render_extraction_pie(stats), "媒体提取成功率饼图"))
    cells.append(make_md_cell("> **说明：** 约 47% 产品未能提取到媒体，主要原因是 Amazon 反爬机制（CAPTCHA）。后续将引入 Playwright 无头浏览器提升提取率。"))

    # ── 视频大小分布 ──
    cells.append(make_md_cell("---\n## 7. 视频大小分布"))
    vid_hist = render_video_size_hist(stats)
    if vid_hist:
        cells.append(make_code_cell_with_image(vid_hist, "视频大小分布直方图"))

    # ── 数据质量指标 ──
    vid_min = f"{min(vid_mb):.2f}" if vid_mb else "—"
    vid_max = f"{max(vid_mb):.2f}" if vid_mb else "—"
    vid_avg = f"{sum(vid_mb)/len(vid_mb):.2f}" if vid_mb else "—"
    img_avg = f"{sum(img_kb)/len(img_kb):.1f}" if img_kb else "—"

    cells.append(make_md_cell(f"""---
## 8. 数据质量指标

### 视频

| 指标 | 值 |
|------|------|
| 视频格式 | MP4（HLS 流转封装） |
| 目标分辨率 | 720p |
| 最小 / 最大 | {vid_min} MB / {vid_max} MB |
| 平均大小 | {vid_avg} MB |
| 视频总数 | {len(vid_mb)} |

### 图片

| 指标 | 值 |
|------|------|
| 图片格式 | JPEG |
| 每产品上限 | 8 张 |
| 平均大小 | {img_avg} KB |
| 图片总数 | {len(img_kb)} |"""))

    # ── 已知问题 ──
    cells.append(make_md_cell("""---
## 9. 已知问题

| 问题 | 影响范围 | 原因 | 解决方案 |
|------|----------|------|----------|
| 零图片提取 | ~47% 产品 | Amazon CAPTCHA / 页面结构变化 | 引入 Playwright 无头浏览器 |
| DRM 加密视频 | 少量 watch 产品 | HLS 流 DRM 保护 | 跳过，不影响整体 |
| 频率限制 | watch 类别较严重 | HTTP 500/503 | 添加代理轮换 |
| 图片分辨率低 | 部分产品 | 未提取到 hiRes URL | 改进 colorImages 正则 |"""))

    # ── 下一步 ──
    cells.append(make_md_cell("""---
## 10. 下一步计划

- [ ] 完成剩余类别爬取（sunglasses、handbag、ring）
- [ ] 上传数据至 GPU 服务器并运行标准化处理
- [ ] 生成最终 HTML 质量报告
- [ ] 调研多平台 API 补充数据源（Pexels、Pixabay）
- [ ] 引入 Playwright 提升媒体提取成功率

---
*本报告由 `build_notebook.py` 自动生成，数据截至 2026-03-09*"""))

    # ── 组装 notebook ──
    nb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.12.0"},
        },
        "cells": cells,
    }
    return nb


def main():
    print("扫描数据...")
    stats = scan_data()
    print("生成 notebook...")
    nb = build_notebook(stats)
    with open(OUTPUT_NB, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    print(f"完成: {OUTPUT_NB}")
    print(f"  大小: {OUTPUT_NB.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
