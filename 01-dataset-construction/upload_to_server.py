#!/usr/bin/env python3
"""
Upload amazon_data/ to server via SFTP.
Usage: python upload_to_server.py
"""

import os
import sys
import time
from pathlib import Path

import paramiko

# ── Config ────────────────────────────────────────────────────────────────────
HOST = "111.17.197.107"
USER = "wangjieyi"
PASS = "wangjieyi@hkust"
LOCAL_DIR = Path(__file__).parent / "amazon_data"
REMOTE_DIR = "/data/wangjieyi/pvtt-dataset/amazon_data"


def sizeof_fmt(num):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if abs(num) < 1024.0:
            return f"{num:.1f}{unit}"
        num /= 1024.0
    return f"{num:.1f}TB"


def sftp_mkdir_p(sftp, remote_dir):
    """Recursively create remote directories."""
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


def remote_file_size(sftp, path):
    """Get remote file size, return -1 if not exists."""
    try:
        return sftp.stat(path).st_size
    except FileNotFoundError:
        return -1


def upload():
    print(f"Connecting to {USER}@{HOST}...", flush=True)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=30, banner_timeout=60)
    sftp = paramiko.SFTPClient.from_transport(ssh.get_transport())
    sftp.get_channel().settimeout(120)  # 120s per-operation timeout for large files
    print("Connected!\n", flush=True)

    # Collect all files grouped by category
    categories = {}
    total_size = 0
    total_files = 0
    for root, _, fnames in os.walk(str(LOCAL_DIR)):
        for fn in fnames:
            local = os.path.join(root, fn)
            relative = os.path.relpath(local, str(LOCAL_DIR)).replace("\\", "/")
            remote = REMOTE_DIR + "/" + relative
            fsize = os.path.getsize(local)
            # Category = first path component, or _root for top-level files
            parts = relative.split("/")
            cat = parts[0] if len(parts) > 1 else "_root"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append((local, remote, fsize))
            total_size += fsize
            total_files += 1

    print(f"Found {total_files} files ({sizeof_fmt(total_size)}) in {len(categories)} groups:")
    for cat in sorted(categories.keys()):
        cat_size = sum(x[2] for x in categories[cat])
        print(f"  {cat}: {len(categories[cat])} files ({sizeof_fmt(cat_size)})")
    print(flush=True)

    # Upload
    global_uploaded = 0
    global_uploaded_bytes = 0
    global_skipped = 0
    global_skipped_bytes = 0
    failed = []
    global_start = time.time()

    for cat in sorted(categories.keys()):
        cat_files = categories[cat]
        cat_total = len(cat_files)
        cat_uploaded = 0
        cat_skipped = 0
        cat_bytes = 0
        cat_start = time.time()

        print(f"[{cat}] Processing {cat_total} files...", flush=True)

        for i, (local, remote, fsize) in enumerate(cat_files):
            # Skip if same size exists on server
            rsize = remote_file_size(sftp, remote)
            if rsize == fsize:
                cat_skipped += 1
                global_skipped += 1
                global_skipped_bytes += fsize
                continue

            # Create remote dir
            remote_dir = os.path.dirname(remote)
            sftp_mkdir_p(sftp, remote_dir)

            # Upload
            try:
                sftp.put(local, remote)
                cat_uploaded += 1
                global_uploaded += 1
                cat_bytes += fsize
                global_uploaded_bytes += fsize
            except Exception as e:
                print(f"  FAILED: {os.path.basename(local)} - {e}", flush=True)
                failed.append((remote, str(e)))

            # Progress every 20 files uploaded
            done = cat_uploaded + cat_skipped
            if done % 20 == 0 and done > 0:
                elapsed = time.time() - cat_start
                speed = cat_bytes / elapsed if elapsed > 0 else 0
                total_done = global_uploaded + global_skipped
                total_pct = (global_uploaded_bytes + global_skipped_bytes) / total_size * 100
                print(f"  [{cat}] {done}/{cat_total} | "
                      f"Overall: {total_done}/{total_files} ({total_pct:.1f}%) "
                      f"- {sizeof_fmt(speed)}/s", flush=True)

        elapsed = time.time() - cat_start
        speed = cat_bytes / elapsed if elapsed > 0 else 0
        print(f"  [{cat}] Done: {cat_uploaded} uploaded, {cat_skipped} skipped "
              f"({sizeof_fmt(cat_bytes)} in {elapsed:.1f}s, {sizeof_fmt(speed)}/s)\n", flush=True)

    # Summary
    total_elapsed = time.time() - global_start
    avg_speed = global_uploaded_bytes / total_elapsed if total_elapsed > 0 else 0
    print("=" * 60)
    print(f"UPLOAD COMPLETE in {total_elapsed:.1f}s")
    print(f"  Uploaded: {global_uploaded} files ({sizeof_fmt(global_uploaded_bytes)})")
    print(f"  Skipped:  {global_skipped} files ({sizeof_fmt(global_skipped_bytes)})")
    print(f"  Failed:   {len(failed)} files")
    print(f"  Avg speed: {sizeof_fmt(avg_speed)}/s")
    if failed:
        print("\nFailed files:")
        for path, err in failed:
            print(f"  {path}: {err}")
    print(f"\nRemote: {REMOTE_DIR}")

    sftp.close()
    ssh.close()
    print("Done.", flush=True)


if __name__ == "__main__":
    try:
        upload()
    except Exception as e:
        print(f"\nERROR: {e}")
        print("\nIf 'Error reading SSH protocol banner' or 'EOFError':")
        print("  -> Your IP may be banned by fail2ban. Wait 15-30 min and retry.")
        print("  -> Or try from a different network (e.g., mobile hotspot).")
        sys.exit(1)
