#!/usr/bin/env python3
"""
Local launcher: deploy amazon_spider.py to server and run via SSH.

Usage:
  # Test with one keyword
  python launch_spider.py --test "gold necklace" necklace

  # Run a single category
  python launch_spider.py --run "leather handbag" handbag --max 30

  # Run all categories (batch)
  python launch_spider.py --batch

  # Check status
  python launch_spider.py --status

  # Download results to local
  python launch_spider.py --pull necklace
"""

import sys
import os
import argparse

# Add parent path so we can import ssh_run from archive
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "_archive", "server_tools"))

from ssh_run import ssh_exec, ssh_upload

REMOTE_DIR = "/data/wangjieyi/pvtt-dataset/amazon"
REMOTE_SCRIPT = "/data/wangjieyi/pvtt-dataset/amazon_spider.py"
CONDA_PYTHON = "/data/wangjieyi/miniconda3/envs/datapipeline/bin/python"
LOCAL_SPIDER = os.path.join(os.path.dirname(__file__), "amazon_spider.py")


def deploy():
    """Upload spider to server and install deps."""
    print("Deploying amazon_spider.py to server...")
    ssh_upload(LOCAL_SPIDER, REMOTE_SCRIPT)
    print("Checking dependencies...")
    out, err = ssh_exec(
        f"{CONDA_PYTHON} -c \"import requests; import bs4; print('deps OK')\" "
        f"|| {CONDA_PYTHON} -m pip install requests beautifulsoup4 -q",
        timeout=60,
    )
    print("Deploy done.")


def run_single(keyword, category, max_products=20):
    """Run spider for one keyword."""
    deploy()
    print(f"\nRunning: [{category}] \"{keyword}\" (max {max_products})")
    print("-" * 50)
    cmd = (
        f"cd /data/wangjieyi/pvtt-dataset && "
        f"{CONDA_PYTHON} amazon_spider.py "
        f"--keyword \"{keyword}\" --category {category} "
        f"--max-products {max_products}"
    )
    out, err = ssh_exec(cmd, timeout=600)


def run_batch():
    """Run all categories."""
    deploy()
    print("\nRunning batch crawl (all categories)...")
    print("=" * 50)
    cmd = (
        f"cd /data/wangjieyi/pvtt-dataset && "
        f"{CONDA_PYTHON} amazon_spider.py --batch"
    )
    out, err = ssh_exec(cmd, timeout=3600)


def check_status():
    """Check spider status on server."""
    cmd = (
        f"cd /data/wangjieyi/pvtt-dataset && "
        f"{CONDA_PYTHON} amazon_spider.py --status"
    )
    out, err = ssh_exec(cmd, timeout=30)


def pull_results(category=None):
    """Show results summary (download not automated - use scp)."""
    target = f"{REMOTE_DIR}/{category}" if category else REMOTE_DIR
    cmd = f"find {target} -type f | head -50 && echo '---' && du -sh {target}"
    out, err = ssh_exec(cmd, timeout=30)
    if category:
        print(f"\nTo download locally:")
        print(f"  scp -r wangjieyi@111.17.197.107:{target} ./amazon_{category}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Launch Amazon spider on server")
    parser.add_argument("--test", nargs=2, metavar=("KEYWORD", "CATEGORY"),
                        help="Quick test: one keyword, 5 products")
    parser.add_argument("--run", nargs=2, metavar=("KEYWORD", "CATEGORY"),
                        help="Run one keyword")
    parser.add_argument("--max", type=int, default=20, help="Max products")
    parser.add_argument("--batch", action="store_true", help="Run all categories")
    parser.add_argument("--status", action="store_true", help="Check progress")
    parser.add_argument("--pull", nargs="?", const="", metavar="CATEGORY",
                        help="Show/download results")
    parser.add_argument("--deploy", action="store_true", help="Just deploy, don't run")

    args = parser.parse_args()

    if args.deploy:
        deploy()
    elif args.status:
        check_status()
    elif args.test:
        run_single(args.test[0], args.test[1], max_products=5)
    elif args.run:
        run_single(args.run[0], args.run[1], args.max)
    elif args.batch:
        run_batch()
    elif args.pull is not None:
        pull_results(args.pull or None)
    else:
        parser.print_help()
