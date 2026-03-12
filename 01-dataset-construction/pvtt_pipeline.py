#!/usr/bin/env python3
"""
PVTT Data Collection Pipeline
================================
End-to-end pipeline: crawl → upload → process → report → push to GitHub.

Usage:
  python pvtt_pipeline.py crawl                          # Crawl Amazon (LOCAL only)
  python pvtt_pipeline.py crawl -c necklace ring -m 5    # Specific categories
  python pvtt_pipeline.py upload                         # Upload data to server
  python pvtt_pipeline.py process                        # Server-side standardization
  python pvtt_pipeline.py report                         # Generate HTML+MD report
  python pvtt_pipeline.py push                           # Push report to GitHub
  python pvtt_pipeline.py status                         # Show pipeline status
  python pvtt_pipeline.py all                            # Run full pipeline

Note: 'crawl' must run locally (residential IP). Server IP gets 503 from Amazon.
"""

import os
import sys
import json
import glob
import time
import base64
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from io import BytesIO

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "amazon_data"
REPORT_HTML = SCRIPT_DIR / "pvtt_dataset_report.html"
REPORT_MD = SCRIPT_DIR / "pvtt_dataset_report.md"

# Server
SERVER_HOST = "111.17.197.107"
SERVER_USER = "wangjieyi"
SERVER_PASS = "wangjieyi@hkust"
REMOTE_DATA = "/data/wangjieyi/pvtt-dataset/amazon_data"

# GitHub (token in remote URL)
GITHUB_REPO_DIR = SCRIPT_DIR.parent  # IP-2026-Spring-push
GITHUB_BRANCH = "main"

# Categories
CATEGORIES = {
    "necklace":   ["gold necklace", "silver pendant necklace", "pearl necklace"],
    "bracelet":   ["charm bracelet", "gold bangle bracelet", "beaded bracelet"],
    "earring":    ["drop earrings", "stud earrings gold", "hoop earrings silver"],
    "watch":      ["men automatic watch", "women dress watch", "sport digital watch"],
    "handbag":    ["leather crossbody bag", "women tote handbag", "clutch purse evening"],
    "sunglasses": ["polarized sunglasses", "aviator sunglasses", "cat eye sunglasses"],
    "ring":       ["engagement ring", "gold band ring", "silver stackable ring"],
}

SAMPLES_PER_CATEGORY = 3

# ── SSH Helper ────────────────────────────────────────────────────────────────

def get_ssh():
    import paramiko
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER_HOST, username=SERVER_USER, password=SERVER_PASS,
                timeout=30, banner_timeout=60)
    return ssh


def ssh_exec(ssh, cmd, timeout=300):
    print(f"  [SSH] {cmd[:80]}...")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        for line in out.split("\n"):
            print(f"  | {line}")
    if err:
        for line in err.split("\n")[:10]:
            print(f"  ! {line}")
    return out, err


# ── Step 1: Crawl ────────────────────────────────────────────────────────────

def step_crawl(categories=None, max_products=20):
    """Run Amazon spider locally."""
    print("=" * 60)
    print("STEP 1: Crawl Amazon (LOCAL)")
    print("=" * 60)

    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        import amazon_spider as spider
    except ImportError as e:
        print(f"ERROR: {e}")
        return False

    start = time.time()
    cats = categories or list(CATEGORIES.keys())

    all_stats = []
    for cat in cats:
        if cat not in CATEGORIES:
            print(f"  WARNING: Unknown category '{cat}', skip")
            continue
        for kw in CATEGORIES[cat]:
            try:
                stats = spider.crawl_category(kw, cat, max_products)
                all_stats.append(stats)
            except Exception as e:
                print(f"  ERROR crawling '{kw}': {e}")

    elapsed = time.time() - start
    tp = sum(s.get("products_scraped", 0) for s in all_stats)
    tv = sum(s.get("total_videos", 0) for s in all_stats)
    ti = sum(s.get("total_images", 0) for s in all_stats)
    print(f"\nCrawl done in {elapsed:.0f}s: {tp} products, {tv} videos, {ti} images")
    return True


# ── Step 2: Upload ────────────────────────────────────────────────────────────

def step_upload():
    """Upload local data to server via SFTP."""
    print("\n" + "=" * 60)
    print("STEP 2: Upload to Server")
    print("=" * 60)

    if not DATA_DIR.exists():
        print("  No local data found.")
        return False

    import paramiko
    ssh = get_ssh()
    sftp = paramiko.SFTPClient.from_transport(ssh.get_transport())
    sftp.get_channel().settimeout(120)
    print(f"  Connected to {SERVER_HOST}")

    # Collect files
    files = []
    for root, _, fnames in os.walk(str(DATA_DIR)):
        for fn in fnames:
            local = os.path.join(root, fn)
            relative = os.path.relpath(local, str(DATA_DIR)).replace("\\", "/")
            remote = REMOTE_DATA + "/" + relative
            files.append((local, remote, os.path.getsize(local)))

    total_size = sum(f[2] for f in files)
    print(f"  Files: {len(files)} ({total_size/1024/1024:.0f} MB)")

    uploaded = skipped = failed = 0
    uploaded_bytes = 0
    start = time.time()

    for i, (local, remote, size) in enumerate(files):
        # Skip existing same-size files
        try:
            if sftp.stat(remote).st_size == size:
                skipped += 1
                continue
        except FileNotFoundError:
            pass

        # Create dirs
        rdir = os.path.dirname(remote)
        _sftp_mkdir_p(sftp, rdir)

        try:
            sftp.put(local, remote)
            uploaded += 1
            uploaded_bytes += size
        except Exception as e:
            print(f"  FAIL: {os.path.basename(local)} - {e}")
            failed += 1

        if (uploaded + skipped) % 50 == 0:
            elapsed = time.time() - start
            speed = uploaded_bytes / max(elapsed, 1) / 1024 / 1024
            pct = (uploaded + skipped) / len(files) * 100
            print(f"  Progress: {pct:.0f}% ({uploaded} new, {skipped} skip, {speed:.1f}MB/s)")

    elapsed = time.time() - start
    print(f"\n  Done: {uploaded} uploaded, {skipped} skipped, {failed} failed in {elapsed:.0f}s")

    sftp.close()
    ssh.close()
    return True


def _sftp_mkdir_p(sftp, remote_dir):
    dirs = []
    d = remote_dir
    while d and d != "/":
        try:
            sftp.stat(d)
            break
        except FileNotFoundError:
            dirs.append(d)
            d = os.path.dirname(d)
    for d in reversed(dirs):
        try:
            sftp.mkdir(d)
        except Exception:
            pass


# ── Step 3: Server Processing ────────────────────────────────────────────────

def step_process():
    """Run server-side processing (standardize videos)."""
    print("\n" + "=" * 60)
    print("STEP 3: Server Processing")
    print("=" * 60)

    ssh = get_ssh()

    # Check if data exists
    out, _ = ssh_exec(ssh, f"find {REMOTE_DATA} -name '*.mp4' | wc -l", timeout=30)
    vid_count = int(out.strip().split("\n")[-1]) if out.strip() else 0
    print(f"  Videos on server: {vid_count}")

    if vid_count == 0:
        print("  No videos to process. Run upload first.")
        ssh.close()
        return False

    # Run standardization: 1280x720, 24fps, H.264
    cmd = (
        f"source /data/wangjieyi/miniconda3/etc/profile.d/conda.sh && "
        f"conda activate datapipeline && "
        f"cd /data/wangjieyi/pvtt-dataset && "
        f"python -c \""
        f"import os, subprocess, json; "
        f"src='{REMOTE_DATA}'; dst='/data/wangjieyi/pvtt-dataset/processed/standardized'; "
        f"os.makedirs(dst, exist_ok=True); "
        f"vids=[]; "
        f"[vids.extend([os.path.join(r,f) for f in fs if f.endswith('.mp4')]) "
        f"  for r,_,fs in os.walk(src)]; "
        f"print(f'Found {{len(vids)}} videos to process'); "
        f"done=0; "
        f"for v in vids: "
        f"  out=os.path.join(dst, os.path.basename(v)); "
        f"  if os.path.exists(out): done+=1; continue; "
        f"  subprocess.run(['ffmpeg','-y','-i',v,'-vf','scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2','-r','24','-c:v','libx264','-preset','fast','-crf','23','-c:a','aac','-b:a','128k','-movflags','+faststart',out], capture_output=True); "
        f"  done+=1; "
        f"  if done%20==0: print(f'  Processed {{done}}/{{len(vids)}}'); "
        f"print(f'Done: {{done}} videos processed')\""
    )
    ssh_exec(ssh, cmd, timeout=1800)
    ssh.close()
    return True


# ── Step 4: Report ────────────────────────────────────────────────────────────

def step_report():
    """Generate HTML + MD dataset report."""
    print("\n" + "=" * 60)
    print("STEP 4: Generate Report")
    print("=" * 60)

    try:
        import cv2
        HAS_CV2 = True
    except ImportError:
        HAS_CV2 = False

    try:
        from PIL import Image
        HAS_PIL = True
    except ImportError:
        HAS_PIL = False

    if not DATA_DIR.exists():
        print("  No data found.")
        return False

    # Scan data
    print("  Scanning data...")
    stats = {}
    products_all = {}

    for cat_dir in sorted(DATA_DIR.iterdir()):
        if not cat_dir.is_dir():
            continue
        cat = cat_dir.name
        prods = []
        for jf in sorted(cat_dir.glob("*.json")):
            try:
                with open(jf, encoding="utf-8") as f:
                    prods.append(json.load(f))
            except Exception:
                pass

        img_dir = cat_dir / "media" / "images"
        vid_dir = cat_dir / "media" / "videos"
        imgs = list(img_dir.glob("*.jpg")) + list(img_dir.glob("*.png")) if img_dir.exists() else []
        vids = list(vid_dir.glob("*.mp4")) if vid_dir.exists() else []

        size_mb = sum(f.stat().st_size for f in cat_dir.rglob("*") if f.is_file()) / 1024 / 1024
        with_title = sum(1 for p in prods if p.get("title"))
        with_video = sum(1 for p in prods if p.get("download_stats", {}).get("videos_downloaded", 0) > 0)
        with_images = sum(1 for p in prods if p.get("download_stats", {}).get("images_downloaded", 0) > 0)
        keywords = list(set(p.get("keyword", "") for p in prods if p.get("keyword")))

        stats[cat] = dict(n_prods=len(prods), with_title=with_title, with_video=with_video,
                          with_images=with_images, n_img=len(imgs), n_vid=len(vids),
                          size_mb=size_mb, keywords=keywords)
        products_all[cat] = prods

    T = lambda k: sum(s[k] for s in stats.values())
    tot_p = T("n_prods"); tot_i = T("n_img"); tot_v = T("n_vid")
    tot_sz = T("size_mb"); tot_wv = T("with_video"); tot_wi = T("with_images")

    print(f"  {tot_p} products, {tot_i} images, {tot_v} videos, {tot_sz:.0f} MB")

    # Select samples
    samples = {}
    for cat, prods in products_all.items():
        cands = [p for p in prods if p.get("title") and
                 p.get("download_stats", {}).get("images_downloaded", 0) > 0]
        cands.sort(key=lambda p: (p.get("download_stats", {}).get("videos_downloaded", 0),
                                   p.get("download_stats", {}).get("images_downloaded", 0)), reverse=True)
        samples[cat] = cands[:SAMPLES_PER_CATEGORY]

    # Video analysis
    print("  Analyzing videos...")
    vid_infos = []
    for cat_dir in sorted(DATA_DIR.iterdir()):
        if not cat_dir.is_dir():
            continue
        vdir = cat_dir / "media" / "videos"
        if not vdir.exists():
            continue
        for vf in sorted(vdir.glob("*.mp4")):
            vi = _get_video_info(str(vf), HAS_CV2)
            vi.update(category=cat_dir.name, filename=vf.name, path=str(vf))
            vid_infos.append(vi)

    avg_dur = sum(v["duration"] for v in vid_infos) / max(len(vid_infos), 1)
    max_dur = max((v["duration"] for v in vid_infos), default=0)
    min_dur = min((v["duration"] for v in vid_infos if v["duration"] > 0), default=0)
    tot_vid_sz = sum(v["size_mb"] for v in vid_infos)
    res_c = defaultdict(int)
    for v in vid_infos:
        if v["width"]: res_c[f"{v['width']}x{v['height']}"] += 1
    top_res = sorted(res_c.items(), key=lambda x: -x[1])[:5]

    # Generate HTML
    print("  Generating HTML...")
    html = _gen_html(stats, samples, products_all, vid_infos,
                     avg_dur, min_dur, max_dur, tot_vid_sz, top_res,
                     HAS_CV2, HAS_PIL)
    REPORT_HTML.write_text(html, encoding="utf-8")
    print(f"  HTML: {REPORT_HTML} ({len(html)//1024} KB)")

    # Generate MD
    print("  Generating Markdown...")
    md = _gen_md(stats, samples, products_all, vid_infos,
                 avg_dur, min_dur, max_dur, tot_vid_sz, top_res)
    REPORT_MD.write_text(md, encoding="utf-8")
    print(f"  MD:   {REPORT_MD} ({len(md)//1024} KB)")

    return True


# ── Step 5: Push to GitHub ───────────────────────────────────────────────────

def step_push():
    """Push report + referenced media to GitHub."""
    print("\n" + "=" * 60)
    print("STEP 5: Push to GitHub")
    print("=" * 60)

    import subprocess as sp
    repo = str(GITHUB_REPO_DIR)

    # Ensure on main branch
    sp.run(["git", "checkout", GITHUB_BRANCH], cwd=repo, capture_output=True)

    # Pull latest
    r = sp.run(["git", "pull", "origin", GITHUB_BRANCH, "--no-edit"],
               cwd=repo, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  Pull warning: {r.stderr[:200]}")

    # Find referenced media in reports
    refs = set()
    for report in [REPORT_HTML, REPORT_MD]:
        if not report.exists():
            continue
        content = report.read_text(encoding="utf-8", errors="ignore")
        import re
        for m in re.finditer(r'(?:src|href|\()="?(amazon_data/[^"\s)]+)', content):
            refs.add(m.group(1))

    print(f"  Referenced media: {len(refs)} files")

    # Stage reports
    sp.run(["git", "add",
            "01-dataset-construction/pvtt_dataset_report.html",
            "01-dataset-construction/pvtt_dataset_report.md"],
           cwd=repo, capture_output=True)

    # Stage referenced media
    for ref in refs:
        full = f"01-dataset-construction/{ref}"
        sp.run(["git", "add", full], cwd=repo, capture_output=True)

    # Stage pipeline script
    sp.run(["git", "add", "01-dataset-construction/pvtt_pipeline.py"],
           cwd=repo, capture_output=True)

    # Check if anything to commit
    r = sp.run(["git", "diff", "--cached", "--stat"], cwd=repo, capture_output=True, text=True)
    if not r.stdout.strip():
        print("  Nothing new to push.")
        return True

    print(f"  Staged:\n{r.stdout.strip()[:500]}")

    # Commit
    msg = (f"Update dataset report ({datetime.now():%Y-%m-%d})\n\n"
           f"- {len(refs)} media files (videos + images)\n"
           f"- HTML report with playable videos\n"
           f"- MD report with linked media\n\n"
           f"Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>")
    sp.run(["git", "commit", "-m", msg], cwd=repo, capture_output=True)

    # Push
    print("  Pushing...")
    r = sp.run(["git", "push", "origin", GITHUB_BRANCH],
               cwd=repo, capture_output=True, text=True, timeout=600)
    if r.returncode == 0:
        print("  Push successful!")
    else:
        print(f"  Push failed: {r.stderr[:300]}")
        return False

    return True


# ── Status ────────────────────────────────────────────────────────────────────

def step_status():
    """Show pipeline status."""
    print("=" * 60)
    print("PVTT Pipeline Status")
    print("=" * 60)

    # Local
    print("\nLOCAL DATA:")
    if DATA_DIR.exists():
        total_p = total_i = total_v = 0
        total_bytes = 0
        for d in sorted(DATA_DIR.iterdir()):
            if not d.is_dir():
                continue
            np = len(list(d.glob("*.json")))
            ni = len(list((d / "media" / "images").glob("*"))) if (d / "media" / "images").exists() else 0
            nv = len(list((d / "media" / "videos").glob("*"))) if (d / "media" / "videos").exists() else 0
            sz = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
            total_p += np; total_i += ni; total_v += nv; total_bytes += sz
            print(f"  {d.name:15s} {np:3d} products  {ni:4d} imgs  {nv:3d} vids  {sz/1024/1024:7.1f} MB")
        print(f"  {'─'*60}")
        print(f"  {'TOTAL':15s} {total_p:3d} products  {total_i:4d} imgs  {total_v:3d} vids  {total_bytes/1024/1024:7.1f} MB")
    else:
        print("  No local data.")

    # Reports
    print("\nREPORTS:")
    for rp in [REPORT_HTML, REPORT_MD]:
        if rp.exists():
            print(f"  {rp.name} ({rp.stat().st_size//1024} KB, {datetime.fromtimestamp(rp.stat().st_mtime):%Y-%m-%d %H:%M})")
        else:
            print(f"  {rp.name} — not generated")

    # Server
    print("\nSERVER:")
    try:
        ssh = get_ssh()
        ssh_exec(ssh, f"echo 'Data:' && find {REMOTE_DATA} -type f | wc -l && "
                      f"echo 'Videos:' && find {REMOTE_DATA} -name '*.mp4' | wc -l && "
                      f"echo 'Size:' && du -sh {REMOTE_DATA} 2>/dev/null", timeout=15)
        ssh.close()
    except Exception as e:
        print(f"  Cannot connect: {e}")

    print("=" * 60)


# ── Report Generators (inline) ───────────────────────────────────────────────

CAT_COLORS = {
    "bracelet": "#4E79A7", "earring": "#F28E2B", "handbag": "#E15759",
    "necklace": "#76B7B2", "ring": "#59A14F", "sunglasses": "#EDC948", "watch": "#B07AA1",
}


def _get_video_info(path, has_cv2):
    info = {"duration": 0, "width": 0, "height": 0, "fps": 0, "size_mb": 0}
    try: info["size_mb"] = os.path.getsize(path) / 1024 / 1024
    except: pass
    if not has_cv2: return info
    try:
        import cv2
        cap = cv2.VideoCapture(path)
        if cap.isOpened():
            info["fps"] = cap.get(cv2.CAP_PROP_FPS) or 0
            info["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            info["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if info["fps"] > 0:
                info["duration"] = cap.get(cv2.CAP_PROP_FRAME_COUNT) / info["fps"]
        cap.release()
    except: pass
    return info


def _thumb_b64(img_path, has_pil, width=150):
    if not has_pil: return None
    try:
        from PIL import Image
        img = Image.open(img_path)
        r = width / img.width
        img = img.resize((width, int(img.height * r)), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return base64.b64encode(buf.getvalue()).decode()
    except: return None


def _poster_b64(vpath, has_cv2, has_pil, width=300):
    if not has_cv2 or not has_pil: return None
    try:
        import cv2
        from PIL import Image
        cap = cv2.VideoCapture(vpath)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, min(10, total - 1))
        ret, frame = cap.read()
        cap.release()
        if not ret: return None
        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        r = width / img.width
        img = img.resize((width, int(img.height * r)), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return base64.b64encode(buf.getvalue()).decode()
    except: return None


def _rel(path):
    return os.path.relpath(path, str(SCRIPT_DIR)).replace("\\", "/")


def _get_prod_images(cat, asin):
    d = DATA_DIR / cat / "media" / "images"
    return sorted(glob.glob(str(d / f"{asin}_*.jpg")) + glob.glob(str(d / f"{asin}_*.png")))


def _get_prod_videos(cat, asin):
    d = DATA_DIR / cat / "media" / "videos"
    return sorted(glob.glob(str(d / f"{asin}.mp4")) + glob.glob(str(d / f"{asin}_v*.mp4")))


def _gen_html(stats, samples, products_all, vid_infos,
              avg_dur, min_dur, max_dur, tot_vid_sz, top_res,
              has_cv2, has_pil):
    T = lambda k: sum(s[k] for s in stats.values())
    tot_p=T("n_prods"); tot_i=T("n_img"); tot_v=T("n_vid"); tot_sz=T("size_mb")
    tot_wv=T("with_video"); max_chart=max(max(s["n_vid"],s["n_img"]) for s in stats.values())
    date = datetime.now().strftime("%Y-%m-%d")

    h = [f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>PVTT Dataset Report</title>
<style>
:root{{--bg:#f8f9fa;--card:#fff;--text:#212529;--muted:#6c757d;--border:#dee2e6;--accent:#4E79A7;--red:#E15759}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);line-height:1.6;padding:1.5rem}}
.container{{max-width:1300px;margin:0 auto}}
h1{{font-size:2rem;color:var(--accent);margin-bottom:.2rem}}
h2{{font-size:1.35rem;margin:2rem 0 1rem;padding-bottom:.4rem;border-bottom:2px solid var(--accent)}}
h3{{font-size:1.05rem;margin:1.5rem 0 .5rem;color:var(--muted)}}
.sub{{color:var(--muted);margin-bottom:2rem}}
.sg{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.8rem;margin-bottom:1.5rem}}
.sc{{background:var(--card);border-radius:8px;padding:1rem;box-shadow:0 1px 3px rgba(0,0,0,.08);text-align:center}}
.sc .v{{font-size:1.7rem;font-weight:700;color:var(--accent)}}.sc .l{{font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}}
.sc.red .v{{color:var(--red)}}
table{{width:100%;border-collapse:collapse;margin:1rem 0;background:var(--card);border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
th,td{{padding:.55rem .7rem;text-align:left;border-bottom:1px solid var(--border);font-size:.88rem}}
th{{background:var(--accent);color:#fff;font-weight:600;font-size:.78rem;text-transform:uppercase}}
tr:last-child td{{border-bottom:none}}tr:hover td{{background:#f1f3f5}}
.trow td{{font-weight:700;background:#e9ecef;border-top:2px solid var(--accent)}}
.cc{{background:var(--card);border-radius:8px;padding:1.2rem;box-shadow:0 1px 3px rgba(0,0,0,.08);margin:1rem 0 1.5rem}}
.cr{{display:flex;align-items:center;margin:.35rem 0}}.cl{{width:90px;font-size:.8rem;font-weight:600;text-align:right;padding-right:.8rem;text-transform:capitalize}}
.cb{{flex:1;display:flex;flex-direction:column;gap:2px}}
.b{{height:16px;border-radius:3px;display:flex;align-items:center;padding-left:5px;font-size:.7rem;color:#fff;font-weight:600;min-width:25px}}
.bv{{opacity:.9}}.bi{{opacity:.5}}
.pcard{{background:var(--card);border-radius:8px;overflow:hidden;box-shadow:0 2px 6px rgba(0,0,0,.1);border-left:4px solid var(--accent);margin-bottom:1.2rem}}
.pbody{{padding:1rem 1.2rem}}.ptitle{{font-weight:600;font-size:.92rem;margin-bottom:.3rem}}
.pmeta{{font-size:.78rem;color:var(--muted);margin-bottom:.5rem}}.pmeta span{{margin-right:.7rem}}
.badge{{display:inline-block;padding:.1rem .4rem;border-radius:4px;font-size:.7rem;font-weight:600;margin-right:.2rem}}
.bv-b{{background:#d4edda;color:#155724}}.bi-b{{background:#cce5ff;color:#004085}}.bk-b{{background:#fff3cd;color:#856404}}
.msec{{margin-top:.7rem}}.msec h4{{font-size:.78rem;color:var(--muted);margin-bottom:.3rem;text-transform:uppercase}}
.igrid{{display:flex;gap:4px;flex-wrap:wrap}}
.igrid img{{height:85px;width:auto;border-radius:4px;object-fit:cover;cursor:pointer;transition:transform .2s;border:1px solid #eee}}
.igrid img:hover{{transform:scale(1.8);z-index:10;position:relative;box-shadow:0 4px 12px rgba(0,0,0,.3)}}
.vgrid{{display:flex;gap:12px;flex-wrap:wrap;margin-top:.4rem}}
.vcard{{border-radius:6px;overflow:hidden;background:#000;width:300px;box-shadow:0 2px 8px rgba(0,0,0,.2)}}
.vcard video{{width:100%;display:block;max-height:220px}}
.vinfo{{background:#1a1a2e;color:#fff;padding:.4rem .6rem;font-size:.72rem}}
.vinfo .vn{{font-weight:600}}.vinfo .vm{{opacity:.7}}
footer{{margin-top:2.5rem;padding-top:.8rem;border-top:1px solid var(--border);color:var(--muted);font-size:.78rem;text-align:center}}
</style></head><body><div class="container">
<h1>PVTT Dataset Report</h1>
<p class="sub">Product Video Template Transfer &mdash; Amazon Data &mdash; {date}</p>
<h2>Summary</h2><div class="sg">
<div class="sc"><div class="v">{tot_p}</div><div class="l">Products</div></div>
<div class="sc red"><div class="v">{tot_v}</div><div class="l">Videos</div></div>
<div class="sc"><div class="v">{tot_i}</div><div class="l">Images</div></div>
<div class="sc"><div class="v">{tot_sz:.0f} MB</div><div class="l">Total Size</div></div>
<div class="sc"><div class="v">{len(stats)}</div><div class="l">Categories</div></div>
<div class="sc"><div class="v">{tot_wv/tot_p*100:.0f}%</div><div class="l">Video Rate</div></div>
</div>
<h2>Video Analysis</h2><div class="sg">
<div class="sc red"><div class="v">{tot_v}</div><div class="l">Total Videos</div></div>
<div class="sc red"><div class="v">{avg_dur:.1f}s</div><div class="l">Avg Duration</div></div>
<div class="sc red"><div class="v">{min_dur:.1f}s–{max_dur:.1f}s</div><div class="l">Range</div></div>
<div class="sc red"><div class="v">{tot_vid_sz:.0f} MB</div><div class="l">Video Size</div></div>
<div class="sc"><div class="v" style="font-size:1rem">{'<br>'.join(f'{r}:{c}' for r,c in top_res[:3])}</div><div class="l">Resolutions</div></div>
</div>
<h2>Category Breakdown</h2><table><thead><tr><th>Category</th><th>Products</th><th>w/Title</th><th>w/Video</th><th>Images</th><th>Videos</th><th>Size(MB)</th><th>Keywords</th></tr></thead><tbody>"""]

    for cat in sorted(stats.keys()):
        s=stats[cat]; kw=", ".join(s["keywords"]) or "-"; c=CAT_COLORS.get(cat,"#999")
        h.append(f'<tr><td style="text-transform:capitalize;font-weight:600;color:{c}">{cat}</td>'
                 f'<td>{s["n_prods"]}</td><td>{s["with_title"]}</td><td>{s["with_video"]}</td>'
                 f'<td>{s["n_img"]}</td><td>{s["n_vid"]}</td><td>{s["size_mb"]:.1f}</td>'
                 f'<td style="font-size:.75rem">{kw}</td></tr>')
    h.append(f'<tr class="trow"><td>Total</td><td>{tot_p}</td><td>{T("with_title")}</td><td>{tot_wv}</td>'
             f'<td>{tot_i}</td><td>{tot_v}</td><td>{tot_sz:.1f}</td><td></td></tr></tbody></table>')

    # Chart
    h.append('<h2>Distribution</h2><div class="cc">')
    for cat in sorted(stats.keys()):
        s=stats[cat]; c=CAT_COLORS.get(cat,"#999")
        vp=s["n_vid"]/max_chart*100 if max_chart else 0; ip=s["n_img"]/max_chart*100 if max_chart else 0
        h.append(f'<div class="cr"><div class="cl" style="color:{c}">{cat}</div><div class="cb">'
                 f'<div class="b bv" style="width:{max(vp,3):.1f}%;background:{c}">{s["n_vid"]}v</div>'
                 f'<div class="b bi" style="width:{max(ip,3):.1f}%;background:{c}">{s["n_img"]}i</div></div></div>')
    h.append('</div>')

    # Samples
    h.append('<h2>Sample Products</h2>')
    vid_count = 0
    for cat in sorted(samples.keys()):
        c = CAT_COLORS.get(cat, "#999"); s = stats[cat]
        h.append(f'<div class="cat-sec"><h3 style="color:{c};text-transform:capitalize;border-left:4px solid {c};padding-left:.5rem">'
                 f'{cat} &mdash; {s["n_prods"]}p, {s["n_vid"]}v</h3>')
        for p in samples[cat]:
            asin=p.get("asin","?"); title=p.get("title","Untitled"); price=p.get("price","N/A")
            kw=p.get("keyword",""); ds=p.get("download_stats",{})
            imgs=_get_prod_images(cat,asin)[:6]; vids=_get_prod_videos(cat,asin)

            img_h="".join(f'<img src="data:image/jpeg;base64,{b}" alt="{asin}"/>'
                          for im in imgs if (b:=_thumb_b64(im,has_pil)))
            vid_h=""
            for vf in vids[:3]:
                vi=_get_video_info(vf,has_cv2); dur=f"{vi['duration']:.1f}s" if vi["duration"] else "?"
                res=f"{vi['width']}x{vi['height']}" if vi["width"] else "?"; sz=f"{vi['size_mb']:.1f}MB"
                pb=_poster_b64(vf,has_cv2,has_pil); poster=f'poster="data:image/jpeg;base64,{pb}"' if pb else ""
                vid_h+=f'<div class="vcard"><video controls preload="metadata" {poster}><source src="{_rel(vf)}" type="video/mp4"></video>'
                vid_h+=f'<div class="vinfo"><div class="vn">{os.path.basename(vf)}</div><div class="vm">{dur} &middot; {res} &middot; {sz}</div></div></div>'
                vid_count+=1

            h.append(f'<div class="pcard" style="border-left-color:{c}"><div class="pbody">'
                     f'<div class="ptitle">{title}</div>'
                     f'<div class="pmeta"><span><b>ASIN:</b> {asin}</span><span><b>Price:</b> {price}</span></div>'
                     f'<div class="pmeta"><span class="badge bk-b">{kw}</span>'
                     f'<span class="badge bi-b">{ds.get("images_downloaded",0)} imgs</span>'
                     f'<span class="badge bv-b">{ds.get("videos_downloaded",0)} vids</span></div>')
            if img_h: h.append(f'<div class="msec"><h4>Images</h4><div class="igrid">{img_h}</div></div>')
            if vid_h: h.append(f'<div class="msec"><h4>Videos</h4><div class="vgrid">{vid_h}</div></div>')
            h.append('</div></div>')
        h.append('</div>')

    no_title=tot_p-T("with_title"); no_media=tot_p-T("with_images")
    h.append(f'''<h2>Data Quality</h2><table><thead><tr><th>Metric</th><th>Value</th><th>Notes</th></tr></thead><tbody>
<tr><td>Missing title</td><td>{no_title}</td><td>Page load failed</td></tr>
<tr><td>Missing images</td><td>{no_media}</td><td>No images downloaded</td></tr>
<tr><td>Video rate</td><td>{tot_wv} ({tot_wv/tot_p*100:.1f}%)</td><td></td></tr>
<tr><td>Avg images/product</td><td>{tot_i/max(T("with_images"),1):.1f}</td><td></td></tr>
<tr><td>Avg video duration</td><td>{avg_dur:.1f}s</td><td>{min_dur:.1f}s – {max_dur:.1f}s</td></tr>
<tr><td>Videos in report</td><td>{vid_count}</td><td>Playable (relative paths)</td></tr>
</tbody></table>
<footer>PVTT Dataset Report &mdash; {date} &mdash; CVPR 2027<br>
<span style="font-size:.7rem">Open from <code>01-dataset-construction/</code> for video playback.</span></footer>
</div></body></html>''')
    return "\n".join(h)


def _gen_md(stats, samples, products_all, vid_infos,
            avg_dur, min_dur, max_dur, tot_vid_sz, top_res):
    T = lambda k: sum(s[k] for s in stats.values())
    tot_p=T("n_prods"); tot_i=T("n_img"); tot_v=T("n_vid"); tot_sz=T("size_mb")
    tot_wv=T("with_video"); date=datetime.now().strftime("%Y-%m-%d")

    m = [f"# PVTT Dataset Report\n\n**Product Video Template Transfer** — Amazon Data — {date}\n"]
    m.append(f"## Summary\n\n| Metric | Value |\n|--------|-------|\n"
             f"| Products | {tot_p} |\n| Videos | {tot_v} |\n| Images | {tot_i} |\n"
             f"| Size | {tot_sz:.0f} MB |\n| Video Rate | {tot_wv/tot_p*100:.1f}% |\n")
    m.append(f"## Video Stats\n\n| Metric | Value |\n|--------|-------|\n"
             f"| Avg Duration | {avg_dur:.1f}s |\n| Range | {min_dur:.1f}s – {max_dur:.1f}s |\n"
             f"| Total Size | {tot_vid_sz:.0f} MB |\n")
    for r,c in top_res[:3]: m.append(f"| {r} | {c} videos |")
    m.append("\n## Categories\n\n| Category | Products | w/Video | Images | Videos | Size |\n"
             "|----------|----------|---------|--------|--------|---------|")
    for cat in sorted(stats.keys()):
        s=stats[cat]
        m.append(f"| {cat.capitalize()} | {s['n_prods']} | {s['with_video']} | {s['n_img']} | {s['n_vid']} | {s['size_mb']:.1f}MB |")
    m.append(f"| **Total** | **{tot_p}** | **{tot_wv}** | **{tot_i}** | **{tot_v}** | **{tot_sz:.1f}MB** |\n")

    m.append("## Samples\n")
    for cat in sorted(samples.keys()):
        m.append(f"### {cat.capitalize()}\n")
        for p in samples[cat]:
            asin=p.get("asin","?"); title=p.get("title","Untitled")
            ds=p.get("download_stats",{})
            m.append(f"**{title}**\n- ASIN: `{asin}` | {ds.get('images_downloaded',0)} imgs, {ds.get('videos_downloaded',0)} vids")
            for im in _get_prod_images(cat,asin)[:2]: m.append(f"- ![{asin}]({_rel(im)})")
            for vf in _get_prod_videos(cat,asin)[:2]:
                vi=_get_video_info(vf,False)
                m.append(f"- Video: [{os.path.basename(vf)}]({_rel(vf)}) ({vi['size_mb']:.1f}MB)")
            m.append("")
    m.append(f"---\n*PVTT — {date} — CVPR 2027*\n")
    return "\n".join(m)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PVTT Data Collection Pipeline")
    parser.add_argument("action", choices=["crawl","upload","process","report","push","status","all"])
    parser.add_argument("-c", "--category", nargs="+", help="Categories to crawl")
    parser.add_argument("-m", "--max", type=int, default=20, help="Max products per keyword")
    args = parser.parse_args()

    start = datetime.now()

    actions = {
        "crawl": lambda: step_crawl(args.category, args.max),
        "upload": step_upload,
        "process": step_process,
        "report": step_report,
        "push": step_push,
        "status": step_status,
    }

    if args.action == "all":
        for step in ["crawl", "upload", "process", "report", "push"]:
            print(f"\n{'#'*60}\n# Running: {step}\n{'#'*60}")
            actions[step]()
        print(f"\nFull pipeline done in {(datetime.now()-start).total_seconds():.0f}s")
    else:
        actions[args.action]()


if __name__ == "__main__":
    main()
