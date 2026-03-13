#!/bin/bash
for f in /data/wangjieyi/pvtt-dataset/videos/*.mp4; do
    name=$(basename "$f")
    dur=$(ffprobe -v quiet -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$f" 2>/dev/null)
    res=$(ffprobe -v quiet -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$f" 2>/dev/null)
    fps=$(ffprobe -v quiet -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 "$f" 2>/dev/null)
    echo "$name | ${dur}s | $res | $fps"
done
