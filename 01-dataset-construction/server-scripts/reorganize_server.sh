#!/bin/bash
# ==============================================================
# Server directory reorganization
# Move old scattered files to _archive/, set up clean structure
# ==============================================================

set -e
BASE="/data/wangjieyi"

echo "=== Step 1: Archive old scattered files ==="
mkdir -p "$BASE/_archive"

# Move old directories and files to archive
for item in clips raw_videos standardized images metadata scripts \
            data_index.json test.mp4 test_720p.mp4 test-Scenes.csv \
            README.md check_videos.sh verify.sh \
            Miniconda3-latest-Linux-x86_64.sh; do
    if [ -e "$BASE/$item" ]; then
        echo "  Archiving: $item"
        mv "$BASE/$item" "$BASE/_archive/"
    fi
done

echo ""
echo "=== Step 2: Create clean project structure ==="

# Main project structure under IP-2026-Spring/
# (IP-2026-Spring/ already exists as a git repo)

# 01-dataset-construction: dataset pipeline work
mkdir -p "$BASE/IP-2026-Spring/01-dataset-construction/pvtt-evaluation"
mkdir -p "$BASE/IP-2026-Spring/01-dataset-construction/ecommerce-scraper"
mkdir -p "$BASE/IP-2026-Spring/01-dataset-construction/scripts"

# 02-teacher-model-training: for other students
mkdir -p "$BASE/IP-2026-Spring/02-teacher-model-training/configs"
mkdir -p "$BASE/IP-2026-Spring/02-teacher-model-training/checkpoints"
mkdir -p "$BASE/IP-2026-Spring/02-teacher-model-training/logs"

# 03-dmd-distillation: for DMD acceleration work
mkdir -p "$BASE/IP-2026-Spring/03-dmd-distillation/configs"
mkdir -p "$BASE/IP-2026-Spring/03-dmd-distillation/checkpoints"
mkdir -p "$BASE/IP-2026-Spring/03-dmd-distillation/logs"

# Shared data directory (symlink to pvtt-dataset)
ln -sfn "$BASE/pvtt-dataset" "$BASE/IP-2026-Spring/01-dataset-construction/pvtt-evaluation/data"

# Move pipeline script to scripts
cp "$BASE/pvtt-dataset/pvtt_pipeline.py" "$BASE/IP-2026-Spring/01-dataset-construction/scripts/"

echo ""
echo "=== Step 3: Final structure ==="
find "$BASE/IP-2026-Spring" -maxdepth 4 -type d | sort | grep -v ".git"
echo ""
echo "=== Disk usage ==="
du -sh "$BASE/pvtt-dataset/"
du -sh "$BASE/_archive/" 2>/dev/null || echo "  _archive: 0"
du -sh "$BASE/IP-2026-Spring/"
echo ""
echo "=== Root directory (clean) ==="
ls -la "$BASE/"
echo ""
echo "Done! Server reorganized."
