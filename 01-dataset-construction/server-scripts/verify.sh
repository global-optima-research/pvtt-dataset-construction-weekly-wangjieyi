#!/bin/bash
echo "=== PVTT Dataset Final Structure ==="
find /data/wangjieyi/pvtt-dataset -maxdepth 3 -type d | sort
echo ""
echo "=== File Counts ==="
echo "Raw videos:       $(ls /data/wangjieyi/pvtt-dataset/videos/*.mp4 2>/dev/null | wc -l)"
echo "Product images:   $(ls /data/wangjieyi/pvtt-dataset/product_images/*.jpg 2>/dev/null | wc -l)"
echo "Clips:            $(ls /data/wangjieyi/pvtt-dataset/processed/clips/*.mp4 2>/dev/null | wc -l)"
echo "Standardized:     $(ls /data/wangjieyi/pvtt-dataset/processed/standardized/*.mp4 2>/dev/null | wc -l)"
echo ""
echo "=== Disk Usage ==="
du -sh /data/wangjieyi/pvtt-dataset/
du -sh /data/wangjieyi/pvtt-dataset/videos/
du -sh /data/wangjieyi/pvtt-dataset/processed/clips/
du -sh /data/wangjieyi/pvtt-dataset/processed/standardized/
echo ""
echo "=== Sample Standardized Video ==="
ffprobe -v quiet -select_streams v:0 -show_entries stream=width,height,r_frame_rate,codec_name -of default=noprint_wrappers=1 /data/wangjieyi/pvtt-dataset/processed/standardized/0001-handfan1_clip00.mp4
echo ""
echo "=== Full Home Directory ==="
ls -la /data/wangjieyi/
