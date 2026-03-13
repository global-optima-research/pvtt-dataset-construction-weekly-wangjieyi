#!/usr/bin/env python3
"""
PVTT Data Collection Pipeline
===============================
Unified orchestration of the full data collection workflow:

  1. crawl   - Run Amazon spider locally (residential IP)
  2. upload  - Sync local data to server via SFTP
  3. process - Run server-side pipeline (shot detection + standardization)
  4. report  - Generate HTML quality report
  5. all     - Run steps 1-4 sequentially

Usage:
  python data_pipeline.py crawl                                 # Full batch crawl
  python data_pipeline.py crawl --category necklace --max 5     # Small test
  python data_pipeline.py upload                                # Upload to server
  python data_pipeline.py process                               # Run server pipeline
  python data_pipeline.py report                                # Generate report
  python data_pipeline.py all                                   # Full pipeline
  python data_pipeline.py status                                # Check progress
"""

import os
import sys
import json
import argparse
import time
from pathlib import Path
from datetime import datetime

# ─── Paths ───────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.resolve()
AMAZON_SPIDER = SCRIPT_DIR / "amazon_spider.py"
REPORT_GENERATOR = SCRIPT_DIR / "generate_report.py"
LOCAL_DATA_DIR = SCRIPT_DIR / "amazon_data"

# Server config
SERVER_HOST = "111.17.197.107"
SERVER_USER = "wangjieyi"
SERVER_PASS = "wangjieyi@hkust"
REMOTE_DATA_DIR = "/data/wangjieyi/pvtt-dataset/amazon"
REMOTE_PIPELINE = "/data/wangjieyi/pvtt-dataset/server-scripts/pvtt_pipeline.py"
CONDA_PYTHON = "/data/wangjieyi/miniconda3/envs/datapipeline/bin/python"


# ─── SSH Helpers ─────────────────────────────────────────────

def _get_ssh():
    """Create SSH connection to server."""
    try:
        import paramiko
    except ImportError:
        print("ERROR: pip install paramiko  (required for server operations)")
        sys.exit(1)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER_HOST, username=SERVER_USER, password=SERVER_PASS, timeout=15)
    return ssh


def _ssh_exec(ssh, cmd, timeout=300, show_output=True):
    """Execute command on server and print output."""
    print(f"  [SSH] {cmd[:80]}...")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if show_output:
        if out.strip():
            for line in out.strip().split("\n"):
                print(f"  | {line}")
        if err.strip():
            for line in err.strip().split("\n"):
                print(f"  ! {line}")
    return out, err


# ─── Step 1: Crawl ──────────────────────────────────────────

def step_crawl(categories=None, max_products=20):
    """Run Amazon spider locally to collect product data."""
    print("=" * 60)
    print("Step 1: Data Collection (Amazon Spider)")
    print("=" * 60)

    # Import spider module
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        import amazon_spider as spider
    except ImportError as e:
        print(f"ERROR: Cannot import amazon_spider: {e}")
        print("Make sure amazon_spider.py is in the same directory.")
        return False

    start = time.time()

    if categories:
        # Run specific categories
        all_stats = []
        for cat in categories:
            if cat not in spider.BATCH_CATEGORIES:
                print(f"  WARNING: Unknown category '{cat}', skipping")
                continue
            for keyword in spider.BATCH_CATEGORIES[cat]:
                stats = spider.crawl_category(keyword, cat, max_products)
                all_stats.append(stats)
    else:
        # Run all categories
        all_stats = spider.run_batch()

    elapsed = time.time() - start

    # Summary
    total_products = sum(s.get("products_scraped", 0) for s in (all_stats or []))
    total_videos = sum(s.get("total_videos", 0) for s in (all_stats or []))
    total_images = sum(s.get("total_images", 0) for s in (all_stats or []))

    print(f"\nCrawl complete in {elapsed:.0f}s")
    print(f"  Products: {total_products} | Images: {total_images} | Videos: {total_videos}")
    return True


# ─── Step 2: Upload ─────────────────────────────────────────

def step_upload():
    """Upload local data to server via SFTP."""
    print("\n" + "=" * 60)
    print("Step 2: Upload to Server")
    print("=" * 60)

    if not LOCAL_DATA_DIR.exists():
        print("  No local data to upload.")
        return False

    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        import amazon_spider as spider
        spider.upload_to_server()
        return True
    except Exception as e:
        print(f"  Upload failed: {e}")
        return False


# ─── Step 3: Server Processing ──────────────────────────────

def step_process():
    """Run server-side pipeline (shot detection, standardization)."""
    print("\n" + "=" * 60)
    print("Step 3: Server-Side Processing")
    print("=" * 60)

    ssh = _get_ssh()

    # First, deploy the pipeline script
    print("\n  Deploying pipeline script...")
    local_pipeline = SCRIPT_DIR / "server-scripts" / "pvtt_pipeline.py"
    if local_pipeline.exists():
        sftp = ssh.open_sftp()
        remote_dir = "/data/wangjieyi/pvtt-dataset/server-scripts"
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            sftp.mkdir(remote_dir)
        sftp.put(str(local_pipeline), f"{remote_dir}/pvtt_pipeline.py")
        sftp.close()
        print("  Pipeline script deployed.")

    # Run the pipeline
    print("\n  Running pipeline (shots + standardize + index + validate)...")
    cmd = (
        f"source /data/wangjieyi/miniconda3/etc/profile.d/conda.sh && "
        f"conda activate datapipeline && "
        f"cd /data/wangjieyi/pvtt-dataset && "
        f"python server-scripts/pvtt_pipeline.py --all"
    )
    _ssh_exec(ssh, cmd, timeout=600)

    # Pull processing stats back
    print("\n  Pulling processing stats...")
    sftp = ssh.open_sftp()
    remote_stats = "/data/wangjieyi/pvtt-dataset/processed/processing_stats.json"
    local_stats = str(SCRIPT_DIR / "server_processing_stats.json")
    try:
        sftp.get(remote_stats, local_stats)
        print(f"  Stats saved: {local_stats}")
    except FileNotFoundError:
        print("  processing_stats.json not found on server")
        local_stats = None
    sftp.close()
    ssh.close()

    return True


# ─── Step 4: Report ─────────────────────────────────────────

def step_report(data_dir=None, output=None):
    """Generate HTML quality report."""
    print("\n" + "=" * 60)
    print("Step 4: Generate Quality Report")
    print("=" * 60)

    # Import report generator
    sys.path.insert(0, str(SCRIPT_DIR))
    from generate_report import DataScanner, generate_html_report

    if not data_dir:
        data_dir = str(LOCAL_DATA_DIR)

    if not output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = str(SCRIPT_DIR / f"pvtt_report_{timestamp}.html")

    # Scan data
    print(f"\n  Scanning: {data_dir}")
    scanner = DataScanner(data_dir)
    scanner.scan()

    # Check for server stats
    server_stats = None
    server_stats_path = SCRIPT_DIR / "server_processing_stats.json"
    if server_stats_path.exists():
        server_stats = str(server_stats_path)
        print(f"  Including server stats: {server_stats_path}")

    # Generate report
    report_path = generate_html_report(scanner, output, server_stats)

    # Also save JSON stats
    json_path = output.replace(".html", ".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(scanner.to_json(), f, ensure_ascii=False, indent=2)
    print(f"  JSON stats: {json_path}")

    return report_path


# ─── Status ─────────────────────────────────────────────────

def show_status():
    """Show local + server data status."""
    print("=" * 60)
    print("  PVTT Data Pipeline - Status")
    print("=" * 60)

    # Local status
    print("\n  LOCAL DATA:")
    if LOCAL_DATA_DIR.exists():
        total_meta = 0
        total_images = 0
        total_videos = 0
        total_bytes = 0

        for cat_dir in sorted(LOCAL_DATA_DIR.iterdir()):
            if not cat_dir.is_dir() or cat_dir.name.startswith("."):
                continue
            meta_count = len(list(cat_dir.glob("*.json")))
            img_dir = cat_dir / "media" / "images"
            vid_dir = cat_dir / "media" / "videos"
            img_count = len(list(img_dir.glob("*"))) if img_dir.exists() else 0
            vid_count = len(list(vid_dir.glob("*"))) if vid_dir.exists() else 0

            cat_size = sum(f.stat().st_size for f in cat_dir.rglob("*") if f.is_file())
            total_meta += meta_count
            total_images += img_count
            total_videos += vid_count
            total_bytes += cat_size

            print(f"    {cat_dir.name:15s} | products: {meta_count:4d} | "
                  f"images: {img_count:4d} | videos: {vid_count:3d} | "
                  f"{cat_size/1024/1024:.1f} MB")

        print(f"    {'─'*60}")
        print(f"    {'TOTAL':15s} | products: {total_meta:4d} | "
              f"images: {total_images:4d} | videos: {total_videos:3d} | "
              f"{total_bytes/1024/1024:.1f} MB")
    else:
        print("    No local data yet. Run: python data_pipeline.py crawl")

    # Check for existing reports
    reports = sorted(SCRIPT_DIR.glob("pvtt_report_*.html"), reverse=True)
    if reports:
        print(f"\n  REPORTS:")
        for r in reports[:3]:
            print(f"    {r.name} ({r.stat().st_size/1024:.0f} KB)")

    # Server status (if reachable)
    print(f"\n  SERVER STATUS:")
    try:
        ssh = _get_ssh()
        cmd = (
            f"echo '--- Raw Videos ---' && "
            f"ls /data/wangjieyi/pvtt-dataset/videos/*.mp4 2>/dev/null | wc -l && "
            f"echo '--- Standardized ---' && "
            f"ls /data/wangjieyi/pvtt-dataset/processed/standardized/*.mp4 2>/dev/null | wc -l && "
            f"echo '--- Amazon Data ---' && "
            f"find {REMOTE_DATA_DIR} -name '*.json' 2>/dev/null | wc -l && "
            f"echo '--- Disk Usage ---' && "
            f"du -sh /data/wangjieyi/pvtt-dataset/ 2>/dev/null"
        )
        _ssh_exec(ssh, cmd, timeout=15)
        ssh.close()
    except Exception as e:
        print(f"    Cannot connect: {e}")

    print("=" * 60)


# ─── Main ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="PVTT Data Collection Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python data_pipeline.py crawl --category necklace --max 3   # Quick test
  python data_pipeline.py crawl                               # Full batch
  python data_pipeline.py report                              # Generate report
  python data_pipeline.py all                                 # Full pipeline
        """
    )
    parser.add_argument("action",
                        choices=["crawl", "upload", "process", "report", "all", "status"],
                        help="Pipeline step to run")
    parser.add_argument("--category", "-c", nargs="+",
                        help="Specific categories to crawl (default: all)")
    parser.add_argument("--max", "-m", type=int, default=20,
                        help="Max products per keyword (default: 20)")
    parser.add_argument("--data", help="Data directory for report (default: ./amazon_data)")
    parser.add_argument("--output", "-o", help="Report output path")

    args = parser.parse_args()

    start = datetime.now()

    if args.action == "status":
        show_status()
        return

    if args.action == "crawl":
        step_crawl(args.category, args.max)

    elif args.action == "upload":
        step_upload()

    elif args.action == "process":
        step_process()

    elif args.action == "report":
        step_report(args.data, args.output)

    elif args.action == "all":
        print("PVTT Full Pipeline")
        print(f"Started: {start.strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        step_crawl(args.category, args.max)
        step_upload()
        step_process()
        step_report(args.data, args.output)

        elapsed = (datetime.now() - start).total_seconds()
        print(f"\nFull pipeline complete in {elapsed:.0f}s ({elapsed/60:.1f}min)")


if __name__ == "__main__":
    main()
