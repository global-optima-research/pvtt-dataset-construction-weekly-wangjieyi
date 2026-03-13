#!/usr/bin/env python3
"""
Generate PVTT Dataset Report (HTML + Markdown) with playable video.
Videos are referenced via relative paths — open the HTML from the same directory.
"""

import json
import os
import glob
import base64
from io import BytesIO
from datetime import datetime
from pathlib import Path
from collections import defaultdict

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    print("WARNING: OpenCV not installed. Video thumbnails unavailable.")

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("WARNING: Pillow not installed.")

# ── Config ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "amazon_data"
OUTPUT_DIR = Path(__file__).parent
CATEGORIES = ["bracelet", "earring", "handbag", "necklace", "ring", "sunglasses", "watch"]
SAMPLES_PER_CATEGORY = 3
REPORT_DATE = datetime.now().strftime("%Y-%m-%d")

CAT_COLORS = {
    "bracelet": "#4E79A7", "earring": "#F28E2B", "handbag": "#E15759",
    "necklace": "#76B7B2", "ring": "#59A14F", "sunglasses": "#EDC948", "watch": "#B07AA1",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_products(category):
    products = []
    for jf in sorted((DATA_DIR / category).glob("*.json")):
        try:
            with open(jf, encoding="utf-8") as f:
                products.append(json.load(f))
        except Exception:
            pass
    return products


def count_media(category):
    img_dir = DATA_DIR / category / "media" / "images"
    vid_dir = DATA_DIR / category / "media" / "videos"
    imgs = list(img_dir.glob("*.jpg")) + list(img_dir.glob("*.png")) if img_dir.exists() else []
    vids = list(vid_dir.glob("*.mp4")) if vid_dir.exists() else []
    return len(imgs), len(vids)


def get_dir_size_mb(category):
    total = 0
    for dirpath, _, filenames in os.walk(str(DATA_DIR / category)):
        for f in filenames:
            try: total += os.path.getsize(os.path.join(dirpath, f))
            except OSError: pass
    return total / (1024 * 1024)


def get_product_images(category, asin):
    img_dir = DATA_DIR / category / "media" / "images"
    return sorted(glob.glob(str(img_dir / f"{asin}_*.jpg")) + glob.glob(str(img_dir / f"{asin}_*.png")))


def get_product_videos(category, asin):
    vid_dir = DATA_DIR / category / "media" / "videos"
    return sorted(glob.glob(str(vid_dir / f"{asin}.mp4")) + glob.glob(str(vid_dir / f"{asin}_v*.mp4")))


def make_thumb_b64(img_path, width=160):
    if not HAS_PIL:
        return None
    try:
        img = Image.open(img_path)
        ratio = width / img.width
        img = img.resize((width, int(img.height * ratio)), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def get_video_info(path):
    info = {"duration": 0, "width": 0, "height": 0, "fps": 0, "size_mb": 0}
    try: info["size_mb"] = os.path.getsize(path) / (1024 * 1024)
    except OSError: pass
    if not HAS_CV2:
        return info
    try:
        cap = cv2.VideoCapture(path)
        if cap.isOpened():
            info["fps"] = cap.get(cv2.CAP_PROP_FPS) or 0
            info["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            info["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            if info["fps"] > 0:
                info["duration"] = frames / info["fps"]
        cap.release()
    except Exception:
        pass
    return info


def extract_poster_b64(video_path, width=320):
    if not HAS_CV2 or not HAS_PIL:
        return None
    try:
        cap = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, min(10, total - 1))
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return None
        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        ratio = width / img.width
        img = img.resize((width, int(img.height * ratio)), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def rel(path):
    """Get relative path from OUTPUT_DIR."""
    return os.path.relpath(path, str(OUTPUT_DIR)).replace("\\", "/")


# ── Collect Data ──────────────────────────────────────────────────────────────

print("Scanning data...")
stats = {}
products_all = {}

for cat in CATEGORIES:
    print(f"  {cat}...")
    prods = load_products(cat)
    n_img, n_vid = count_media(cat)
    size = get_dir_size_mb(cat)
    with_title = sum(1 for p in prods if p.get("title"))
    with_video = sum(1 for p in prods if p.get("download_stats", {}).get("videos_downloaded", 0) > 0)
    with_images = sum(1 for p in prods if p.get("download_stats", {}).get("images_downloaded", 0) > 0)
    keywords = list(set(p.get("keyword", "") for p in prods if p.get("keyword")))

    stats[cat] = dict(n_prods=len(prods), with_title=with_title, with_video=with_video,
                       with_images=with_images, n_img=n_img, n_vid=n_vid, size_mb=size, keywords=keywords)
    products_all[cat] = prods

T = lambda key: sum(s[key] for s in stats.values())
tot_prods = T("n_prods"); tot_img = T("n_img"); tot_vid = T("n_vid")
tot_size = T("size_mb"); tot_w_vid = T("with_video"); tot_w_img = T("with_images")
print(f"\n  Total: {tot_prods} products, {tot_img} images, {tot_vid} videos, {tot_size:.0f} MB")

# Select samples — prefer products with video + images
samples = {}
for cat in CATEGORIES:
    cands = [p for p in products_all[cat]
             if p.get("title") and p.get("download_stats", {}).get("images_downloaded", 0) > 0]
    cands.sort(key=lambda p: (p.get("download_stats", {}).get("videos_downloaded", 0),
                               p.get("download_stats", {}).get("images_downloaded", 0)), reverse=True)
    samples[cat] = cands[:SAMPLES_PER_CATEGORY]

# Video analysis
print("Analyzing videos...")
vid_infos = []
for cat in CATEGORIES:
    vdir = DATA_DIR / cat / "media" / "videos"
    if vdir.exists():
        for vf in sorted(vdir.glob("*.mp4")):
            vi = get_video_info(str(vf))
            vi.update(path=str(vf), category=cat, filename=vf.name)
            vid_infos.append(vi)

avg_dur = sum(v["duration"] for v in vid_infos) / max(len(vid_infos), 1)
max_dur = max((v["duration"] for v in vid_infos), default=0)
min_dur = min((v["duration"] for v in vid_infos if v["duration"] > 0), default=0)
tot_vid_size = sum(v["size_mb"] for v in vid_infos)
res_counts = defaultdict(int)
for v in vid_infos:
    if v["width"]: res_counts[f"{v['width']}x{v['height']}"] += 1
top_res = sorted(res_counts.items(), key=lambda x: -x[1])[:5]
max_chart = max(max(s["n_vid"], s["n_img"]) for s in stats.values())

# ── HTML ──────────────────────────────────────────────────────────────────────

print("Generating HTML...")
h = []
h.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PVTT Dataset Report</title>
<style>
:root {{ --bg:#f8f9fa; --card:#fff; --text:#212529; --muted:#6c757d; --border:#dee2e6; --accent:#4E79A7; --red:#E15759; }}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);line-height:1.6;padding:1.5rem}}
.container{{max-width:1300px;margin:0 auto}}
h1{{font-size:2rem;color:var(--accent);margin-bottom:.2rem}}
h2{{font-size:1.35rem;margin:2rem 0 1rem;padding-bottom:.4rem;border-bottom:2px solid var(--accent)}}
h3{{font-size:1.05rem;margin:1.5rem 0 .5rem;color:var(--muted)}}
.sub{{color:var(--muted);margin-bottom:2rem}}

/* Stat cards */
.sg{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.8rem;margin-bottom:1.5rem}}
.sc{{background:var(--card);border-radius:8px;padding:1rem;box-shadow:0 1px 3px rgba(0,0,0,.08);text-align:center}}
.sc .v{{font-size:1.7rem;font-weight:700;color:var(--accent)}}
.sc .l{{font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}}
.sc.red .v{{color:var(--red)}}

/* Table */
table{{width:100%;border-collapse:collapse;margin:1rem 0;background:var(--card);border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
th,td{{padding:.55rem .7rem;text-align:left;border-bottom:1px solid var(--border);font-size:.88rem}}
th{{background:var(--accent);color:#fff;font-weight:600;font-size:.78rem;text-transform:uppercase;letter-spacing:.04em}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:#f1f3f5}}
.trow td{{font-weight:700;background:#e9ecef;border-top:2px solid var(--accent)}}

/* Chart */
.cc{{background:var(--card);border-radius:8px;padding:1.2rem;box-shadow:0 1px 3px rgba(0,0,0,.08);margin:1rem 0 1.5rem}}
.cr{{display:flex;align-items:center;margin:.35rem 0}}
.cl{{width:90px;font-size:.8rem;font-weight:600;text-align:right;padding-right:.8rem;text-transform:capitalize}}
.cb{{flex:1;display:flex;flex-direction:column;gap:2px}}
.b{{height:16px;border-radius:3px;display:flex;align-items:center;padding-left:5px;font-size:.7rem;color:#fff;font-weight:600;min-width:25px}}
.bv{{opacity:.9}}.bi{{opacity:.5}}
.cleg{{display:flex;gap:1.2rem;margin-top:.8rem;font-size:.8rem}}
.cli{{display:flex;align-items:center;gap:.3rem}}
.csw{{width:12px;height:12px;border-radius:3px}}

/* Product */
.cat-sec{{margin:1.5rem 0}}
.pcard{{background:var(--card);border-radius:8px;overflow:hidden;box-shadow:0 2px 6px rgba(0,0,0,.1);border-left:4px solid var(--accent);margin-bottom:1.2rem}}
.pbody{{padding:1rem 1.2rem}}
.ptitle{{font-weight:600;font-size:.92rem;margin-bottom:.3rem}}
.pmeta{{font-size:.78rem;color:var(--muted);margin-bottom:.5rem}}
.pmeta span{{margin-right:.7rem}}
.badge{{display:inline-block;padding:.1rem .4rem;border-radius:4px;font-size:.7rem;font-weight:600;margin-right:.2rem}}
.bv-badge{{background:#d4edda;color:#155724}}.bi-badge{{background:#cce5ff;color:#004085}}.bk-badge{{background:#fff3cd;color:#856404}}

/* Media */
.msec{{margin-top:.7rem}}
.msec h4{{font-size:.78rem;color:var(--muted);margin-bottom:.3rem;text-transform:uppercase;letter-spacing:.03em}}
.igrid{{display:flex;gap:4px;flex-wrap:wrap}}
.igrid img{{height:85px;width:auto;border-radius:4px;object-fit:cover;cursor:pointer;transition:transform .2s;border:1px solid #eee}}
.igrid img:hover{{transform:scale(1.8);z-index:10;position:relative;box-shadow:0 4px 12px rgba(0,0,0,.3)}}

/* Video player */
.vgrid{{display:flex;gap:12px;flex-wrap:wrap;margin-top:.4rem}}
.vcard{{border-radius:6px;overflow:hidden;background:#000;width:300px;box-shadow:0 2px 8px rgba(0,0,0,.2)}}
.vcard video{{width:100%;display:block;max-height:220px}}
.vinfo{{background:#1a1a2e;color:#fff;padding:.4rem .6rem;font-size:.72rem}}
.vinfo .vn{{font-weight:600;margin-bottom:1px}}
.vinfo .vm{{opacity:.7}}

footer{{margin-top:2.5rem;padding-top:.8rem;border-top:1px solid var(--border);color:var(--muted);font-size:.78rem;text-align:center}}
</style>
</head>
<body>
<div class="container">

<h1>PVTT Dataset Report</h1>
<p class="sub">Product Video Template Transfer &mdash; Amazon Scraped Data &mdash; {REPORT_DATE}</p>

<!-- Summary -->
<h2>Summary</h2>
<div class="sg">
  <div class="sc"><div class="v">{tot_prods}</div><div class="l">Products</div></div>
  <div class="sc red"><div class="v">{tot_vid}</div><div class="l">Videos</div></div>
  <div class="sc"><div class="v">{tot_img}</div><div class="l">Images</div></div>
  <div class="sc"><div class="v">{tot_size:.0f} MB</div><div class="l">Total Size</div></div>
  <div class="sc"><div class="v">{len(CATEGORIES)}</div><div class="l">Categories</div></div>
  <div class="sc"><div class="v">{tot_w_vid/tot_prods*100:.0f}%</div><div class="l">Video Rate</div></div>
</div>

<!-- Video Stats -->
<h2>Video Analysis</h2>
<div class="sg">
  <div class="sc red"><div class="v">{tot_vid}</div><div class="l">Total Videos</div></div>
  <div class="sc red"><div class="v">{avg_dur:.1f}s</div><div class="l">Avg Duration</div></div>
  <div class="sc red"><div class="v">{min_dur:.1f}s–{max_dur:.1f}s</div><div class="l">Duration Range</div></div>
  <div class="sc red"><div class="v">{tot_vid_size:.0f} MB</div><div class="l">Video Size</div></div>
  <div class="sc"><div class="v" style="font-size:1rem">{'<br>'.join(f'{r}: {c}' for r,c in top_res[:3])}</div><div class="l">Top Resolutions</div></div>
</div>

<!-- Category Table -->
<h2>Category Breakdown</h2>
<table>
<thead><tr><th>Category</th><th>Products</th><th>w/ Title</th><th>w/ Video</th><th>Images</th><th>Videos</th><th>Size (MB)</th><th>Keywords</th></tr></thead>
<tbody>
""")

for cat in CATEGORIES:
    s = stats[cat]; kw = ", ".join(s["keywords"]) if s["keywords"] else "-"
    h.append(f'<tr><td style="text-transform:capitalize;font-weight:600;color:{CAT_COLORS[cat]}">{cat}</td>'
             f'<td>{s["n_prods"]}</td><td>{s["with_title"]}</td><td>{s["with_video"]}</td>'
             f'<td>{s["n_img"]}</td><td>{s["n_vid"]}</td><td>{s["size_mb"]:.1f}</td>'
             f'<td style="font-size:.75rem">{kw}</td></tr>')

h.append(f'<tr class="trow"><td>Total</td><td>{tot_prods}</td><td>{T("with_title")}</td>'
         f'<td>{tot_w_vid}</td><td>{tot_img}</td><td>{tot_vid}</td><td>{tot_size:.1f}</td><td></td></tr>')
h.append("</tbody></table>")

# Chart
h.append('<h2>Distribution</h2><div class="cc">')
for cat in CATEGORIES:
    s = stats[cat]; c = CAT_COLORS[cat]
    vp = s["n_vid"]/max_chart*100 if max_chart else 0
    ip = s["n_img"]/max_chart*100 if max_chart else 0
    h.append(f'<div class="cr"><div class="cl" style="color:{c}">{cat}</div><div class="cb">'
             f'<div class="b bv" style="width:{max(vp,3):.1f}%;background:{c}">{s["n_vid"]} vid</div>'
             f'<div class="b bi" style="width:{max(ip,3):.1f}%;background:{c}">{s["n_img"]} img</div>'
             f'</div></div>')
h.append('<div class="cleg"><div class="cli"><div class="csw" style="background:#555;opacity:.9"></div>Videos</div>'
         '<div class="cli"><div class="csw" style="background:#555;opacity:.5"></div>Images</div></div></div>')

# ── Sample Products ───────────────────────────────────────────────────────────
h.append("<h2>Sample Products</h2>")
h.append('<p style="color:var(--muted);font-size:.85rem;margin-bottom:1rem">'
         'Top 3 products per category (sorted by video availability). '
         'Click play to watch videos directly.</p>')

vid_count = 0
for cat in CATEGORIES:
    color = CAT_COLORS[cat]; ss = stats[cat]
    h.append(f'<div class="cat-sec"><h3 style="color:{color};text-transform:capitalize;'
             f'border-left:4px solid {color};padding-left:.5rem">'
             f'{cat} &mdash; {ss["n_prods"]} products, {ss["n_vid"]} videos</h3>')

    if not samples[cat]:
        h.append('<p style="color:#999;font-style:italic">No sample products available.</p>')
    else:
        for p in samples[cat]:
            asin = p.get("asin", "?")
            title = p.get("title", "Untitled")
            price = p.get("price", "N/A")
            kw = p.get("keyword", "")
            ds = p.get("download_stats", {})
            ni = ds.get("images_downloaded", 0)
            nv = ds.get("videos_downloaded", 0)

            imgs = get_product_images(cat, asin)[:6]
            vids = get_product_videos(cat, asin)

            # Images as base64 thumbnails
            img_html = ""
            for im in imgs:
                b64 = make_thumb_b64(im, width=150)
                if b64:
                    img_html += f'<img src="data:image/jpeg;base64,{b64}" alt="{asin}"/>'

            # Videos as relative-path <video> tags with poster
            vid_html = ""
            for vf in vids[:3]:
                vi = get_video_info(vf)
                dur = f"{vi['duration']:.1f}s" if vi["duration"] else "?"
                res = f"{vi['width']}x{vi['height']}" if vi["width"] else "?"
                sz = f"{vi['size_mb']:.1f}MB"
                vname = os.path.basename(vf)
                vrel = rel(vf)

                poster_b64 = extract_poster_b64(vf, width=300)
                poster = f'poster="data:image/jpeg;base64,{poster_b64}"' if poster_b64 else ""

                vid_html += f"""<div class="vcard">
<video controls preload="metadata" {poster}><source src="{vrel}" type="video/mp4">Browser does not support video.</video>
<div class="vinfo"><div class="vn">{vname}</div><div class="vm">{dur} &middot; {res} &middot; {sz}</div></div>
</div>"""
                vid_count += 1

            h.append(f'<div class="pcard" style="border-left-color:{color}"><div class="pbody">')
            h.append(f'<div class="ptitle">{title}</div>')
            h.append(f'<div class="pmeta"><span><b>ASIN:</b> {asin}</span><span><b>Price:</b> {price}</span></div>')
            h.append(f'<div class="pmeta"><span class="badge bk-badge">{kw}</span>'
                     f'<span class="badge bi-badge">{ni} imgs</span>'
                     f'<span class="badge bv-badge">{nv} vids</span></div>')

            if img_html:
                h.append(f'<div class="msec"><h4>Images</h4><div class="igrid">{img_html}</div></div>')
            if vid_html:
                h.append(f'<div class="msec"><h4>Videos</h4><div class="vgrid">{vid_html}</div></div>')

            h.append("</div></div>")

    h.append("</div>")

# Quality
no_title = tot_prods - T("with_title")
no_media = tot_prods - T("with_images")
h.append(f"""
<h2>Data Quality</h2>
<table>
<thead><tr><th>Metric</th><th>Value</th><th>Notes</th></tr></thead>
<tbody>
<tr><td>Products missing title</td><td>{no_title}</td><td>Page load failed during scraping</td></tr>
<tr><td>Products missing images</td><td>{no_media}</td><td>No images downloaded</td></tr>
<tr><td>Products with video</td><td>{tot_w_vid} ({tot_w_vid/tot_prods*100:.1f}%)</td><td>Video availability rate</td></tr>
<tr><td>Avg images/product</td><td>{tot_img/max(tot_w_img,1):.1f}</td><td>Among products with media</td></tr>
<tr><td>Avg video duration</td><td>{avg_dur:.1f}s</td><td>Range: {min_dur:.1f}s – {max_dur:.1f}s</td></tr>
<tr><td>Videos in report</td><td>{vid_count}</td><td>Playable via relative path (open HTML from its directory)</td></tr>
</tbody></table>

<footer>PVTT Dataset Report &mdash; {REPORT_DATE} &mdash; Product Video Template Transfer (CVPR 2027)<br>
<span style="font-size:.7rem">Open this HTML from <code>01-dataset-construction/</code> directory for videos to play correctly.</span>
</footer>
</div>
</body>
</html>""")

html_out = "\n".join(h)
html_path = OUTPUT_DIR / "pvtt_dataset_report.html"
html_path.write_text(html_out, encoding="utf-8")
print(f"\nHTML: {html_path} ({len(html_out)//1024} KB)")
print(f"  {vid_count} playable videos (relative paths)")

# ── Markdown ──────────────────────────────────────────────────────────────────

print("Generating Markdown...")
m = []
m.append(f"# PVTT Dataset Report\n\n**Product Video Template Transfer** — Amazon Scraped Data — {REPORT_DATE}\n")

m.append("## Summary\n\n| Metric | Value |\n|--------|-------|\n"
         f"| Products | {tot_prods} |\n| Videos | {tot_vid} |\n| Images | {tot_img} |\n"
         f"| Total Size | {tot_size:.0f} MB |\n| Categories | {len(CATEGORIES)} |\n"
         f"| Video Rate | {tot_w_vid/tot_prods*100:.1f}% ({tot_w_vid} products) |\n")

m.append("## Video Statistics\n\n| Metric | Value |\n|--------|-------|\n"
         f"| Total Videos | {tot_vid} |\n| Avg Duration | {avg_dur:.1f}s |\n"
         f"| Duration Range | {min_dur:.1f}s – {max_dur:.1f}s |\n"
         f"| Total Video Size | {tot_vid_size:.0f} MB |\n")
for r, c in top_res[:3]:
    m.append(f"| Resolution {r} | {c} videos |")
m.append("")

m.append("\n## Category Breakdown\n\n| Category | Products | w/ Title | w/ Video | Images | Videos | Size (MB) |"
         "\n|----------|----------|----------|----------|--------|--------|-----------|")
for cat in CATEGORIES:
    s = stats[cat]
    m.append(f"| {cat.capitalize()} | {s['n_prods']} | {s['with_title']} | {s['with_video']} | {s['n_img']} | {s['n_vid']} | {s['size_mb']:.1f} |")
m.append(f"| **Total** | **{tot_prods}** | **{T('with_title')}** | **{tot_w_vid}** | **{tot_img}** | **{tot_vid}** | **{tot_size:.1f}** |\n")

m.append("## Sample Products\n")
for cat in CATEGORIES:
    m.append(f"### {cat.capitalize()}\n")
    for p in samples[cat]:
        asin = p.get("asin", "?")
        title = p.get("title", "Untitled")
        price = p.get("price", "N/A")
        kw = p.get("keyword", "")
        ds = p.get("download_stats", {})
        m.append(f"**{title}**")
        m.append(f"- ASIN: `{asin}` | Price: {price} | Keyword: _{kw}_")
        m.append(f"- Media: {ds.get('images_downloaded',0)} images, {ds.get('videos_downloaded',0)} videos")

        imgs = get_product_images(cat, asin)[:3]
        if imgs:
            m.append("- " + " ".join(f"![{asin}]({rel(i)})" for i in imgs))

        vids = get_product_videos(cat, asin)
        for vf in vids[:2]:
            vi = get_video_info(vf)
            dur = f"{vi['duration']:.1f}s" if vi["duration"] else "?"
            m.append(f"- Video: [{os.path.basename(vf)}]({rel(vf)}) ({dur}, {vi['size_mb']:.1f}MB)")
        m.append("")

m.append("## Data Quality\n\n| Metric | Value |\n|--------|-------|\n"
         f"| Missing title | {no_title} |\n| Missing images | {no_media} |\n"
         f"| Video rate | {tot_w_vid/tot_prods*100:.1f}% |\n"
         f"| Avg images/product | {tot_img/max(tot_w_img,1):.1f} |\n"
         f"| Avg video duration | {avg_dur:.1f}s |\n")

m.append("## Directory Structure\n\n```\namazon_data/")
for cat in CATEGORIES:
    s = stats[cat]
    m.append(f"  {cat}/\n    *.json              ({s['n_prods']} files)"
             f"\n    media/images/       ({s['n_img']} files)"
             f"\n    media/videos/       ({s['n_vid']} files)")
m.append("```\n\n---\n*PVTT Dataset Report — Product Video Template Transfer (CVPR 2027)*\n")

md_out = "\n".join(m)
md_path = OUTPUT_DIR / "pvtt_dataset_report.md"
md_path.write_text(md_out, encoding="utf-8")
print(f"MD:   {md_path} ({len(md_out)//1024} KB)")
print("Done!")
