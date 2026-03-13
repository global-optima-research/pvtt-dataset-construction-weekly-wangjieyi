#!/usr/bin/env python3
"""
PVTT Dataset Pipeline - Full Processing
========================================
Step 1: Shot detection & segmentation (PySceneDetect)
Step 2: Video standardization (720p, 24fps, H.264)
Step 3: Metadata & index generation
Step 4: Dataset validation & statistics

Usage:
  conda activate datapipeline
  python pvtt_pipeline.py --all
  python pvtt_pipeline.py --step shots
  python pvtt_pipeline.py --step standardize
  python pvtt_pipeline.py --step index
  python pvtt_pipeline.py --status
"""

import os
import json
import subprocess
import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

# ─── Configuration ───────────────────────────────────────────
BASE_DIR = Path("/data/wangjieyi/pvtt-dataset")
VIDEOS_DIR = BASE_DIR / "videos"
IMAGES_DIR = BASE_DIR / "product_images"
PROMPTS_DIR = BASE_DIR / "edit_prompt"

# Output directories
CLIPS_DIR = BASE_DIR / "processed" / "clips"         # Shot-segmented clips
STD_DIR = BASE_DIR / "processed" / "standardized"     # Standardized clips (720p/24fps)
INDEX_FILE = BASE_DIR / "processed" / "dataset_index.json"
STATS_FILE = BASE_DIR / "processed" / "processing_stats.json"

# Standardization parameters
TARGET_W = 1280
TARGET_H = 720
TARGET_FPS = 24
MIN_CLIP_DUR = 1.0   # Minimum clip duration (seconds)
MAX_CLIP_DUR = 5.0   # Maximum clip duration for shot detection
SCENE_THRESHOLD = 27.0  # ContentDetector threshold

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            str(BASE_DIR / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
            encoding="utf-8"
        ),
    ]
)
logger = logging.getLogger(__name__)


# ─── Utility Functions ───────────────────────────────────────

def get_video_info(video_path):
    """Get video metadata via ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return None
        probe = json.loads(result.stdout)
        vs = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), None)
        if not vs:
            return None

        fps_str = vs.get("r_frame_rate", "24/1")
        if "/" in fps_str:
            num, den = fps_str.split("/")
            fps = float(num) / float(den) if float(den) != 0 else 24.0
        else:
            fps = float(fps_str)

        duration = float(probe.get("format", {}).get("duration", 0))
        return {
            "width": int(vs.get("width", 0)),
            "height": int(vs.get("height", 0)),
            "fps": round(fps, 2),
            "duration": round(duration, 2),
            "codec": vs.get("codec_name", ""),
        }
    except Exception as e:
        logger.warning(f"ffprobe failed for {video_path}: {e}")
        return None


def ffmpeg_cut(input_path, output_path, start_sec, duration_sec,
               target_w=TARGET_W, target_h=TARGET_H, target_fps=TARGET_FPS):
    """Cut and standardize a video clip with ffmpeg."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    vf = (
        f"fps={target_fps},"
        f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
        f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=black"
    )

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start_sec:.3f}",
        "-i", str(input_path),
        "-t", f"{duration_sec:.3f}",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-an", "-movflags", "+faststart",
        str(output_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.returncode == 0
    except Exception as e:
        logger.warning(f"ffmpeg error: {e}")
        return False


def ffmpeg_standardize(input_path, output_path,
                       target_w=TARGET_W, target_h=TARGET_H, target_fps=TARGET_FPS):
    """Standardize a video without cutting (full duration)."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    vf = (
        f"fps={target_fps},"
        f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
        f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=black"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-an", "-movflags", "+faststart",
        str(output_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.returncode == 0
    except Exception as e:
        logger.warning(f"ffmpeg error: {e}")
        return False


# ─── Step 1: Shot Detection & Segmentation ───────────────────

def detect_shots(video_path, min_scene_len_sec=MIN_CLIP_DUR, threshold=SCENE_THRESHOLD):
    """Detect scene boundaries using PySceneDetect."""
    try:
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import ContentDetector
    except ImportError:
        logger.error("Install scenedetect: pip install scenedetect[opencv]")
        return []

    video = open_video(str(video_path))
    fps = video.frame_rate
    min_frames = max(1, int(min_scene_len_sec * fps))

    sm = SceneManager()
    sm.add_detector(ContentDetector(threshold=threshold, min_scene_len=min_frames))
    sm.detect_scenes(video)

    shots = []
    for start, end in sm.get_scene_list():
        s, e = start.get_seconds(), end.get_seconds()
        shots.append((round(s, 3), round(e, 3), round(e - s, 3)))
    return shots


def step_shot_detection():
    """Step 1: Detect shots and segment long videos into clips."""
    logger.info("=" * 60)
    logger.info("Step 1: Shot Detection & Segmentation")
    logger.info("=" * 60)

    CLIPS_DIR.mkdir(parents=True, exist_ok=True)

    video_files = sorted(VIDEOS_DIR.glob("*.mp4"))
    logger.info(f"Found {len(video_files)} videos")

    results = {}
    total_clips = 0

    for vf in video_files:
        info = get_video_info(vf)
        if not info:
            logger.warning(f"  Skip (unreadable): {vf.name}")
            continue

        video_name = vf.stem
        logger.info(f"\n  Processing: {vf.name} | {info['width']}x{info['height']} "
                     f"{info['fps']}fps {info['duration']}s")

        # Short videos (<=5s): keep as-is, just copy
        if info["duration"] <= MAX_CLIP_DUR:
            clip_path = CLIPS_DIR / f"{video_name}.mp4"
            if not clip_path.exists():
                import shutil
                shutil.copy2(str(vf), str(clip_path))
            results[video_name] = {
                "source": vf.name,
                "duration": info["duration"],
                "resolution": f"{info['width']}x{info['height']}",
                "fps": info["fps"],
                "clips": [{"name": f"{video_name}.mp4", "start": 0, "end": info["duration"],
                           "duration": info["duration"]}],
                "method": "direct_copy"
            }
            total_clips += 1
            logger.info(f"    Short video -> direct copy")
            continue

        # Long videos (>5s): run shot detection
        shots = detect_shots(vf)

        if not shots:
            # No scenes detected, use fixed-interval splitting
            logger.info(f"    No scene boundaries found, fixed-interval split")
            interval = MAX_CLIP_DUR
            t = 0
            shots = []
            while t < info["duration"]:
                remaining = info["duration"] - t
                dur = min(interval, remaining)
                if dur >= MIN_CLIP_DUR:
                    shots.append((round(t, 3), round(t + dur, 3), round(dur, 3)))
                t += interval

        clip_list = []
        for idx, (start, end, dur) in enumerate(shots):
            if dur < MIN_CLIP_DUR:
                continue
            clip_name = f"{video_name}_clip{idx:02d}.mp4"
            clip_path = CLIPS_DIR / clip_name

            if not clip_path.exists():
                success = ffmpeg_cut(vf, clip_path, start, dur)
                if not success:
                    logger.warning(f"    Failed to cut: {clip_name}")
                    continue

            clip_list.append({
                "name": clip_name,
                "start": start,
                "end": end,
                "duration": dur
            })

        results[video_name] = {
            "source": vf.name,
            "duration": info["duration"],
            "resolution": f"{info['width']}x{info['height']}",
            "fps": info["fps"],
            "clips": clip_list,
            "method": "scene_detection",
            "total_shots": len(shots)
        }
        total_clips += len(clip_list)
        logger.info(f"    Detected {len(shots)} shots -> {len(clip_list)} valid clips")

    # Save shot detection results
    shot_index = BASE_DIR / "processed" / "shot_detection_results.json"
    shot_index.parent.mkdir(parents=True, exist_ok=True)
    with open(shot_index, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"\nShot detection complete:")
    logger.info(f"  Videos: {len(results)}")
    logger.info(f"  Total clips: {total_clips}")
    logger.info(f"  Results: {shot_index}")
    return results


# ─── Step 2: Video Standardization ───────────────────────────

def step_standardize():
    """Step 2: Standardize all clips to 720p/24fps/H.264."""
    logger.info("=" * 60)
    logger.info("Step 2: Video Standardization (720p / 24fps / H.264)")
    logger.info("=" * 60)

    STD_DIR.mkdir(parents=True, exist_ok=True)

    # Find all clips to standardize
    clip_files = sorted(CLIPS_DIR.glob("*.mp4"))
    if not clip_files:
        # If no clips yet, standardize the raw videos directly
        clip_files = sorted(VIDEOS_DIR.glob("*.mp4"))
        logger.info(f"No clips found, standardizing {len(clip_files)} raw videos directly")

    logger.info(f"Found {len(clip_files)} clips to standardize")

    success = 0
    skipped = 0
    failed = 0

    for cf in clip_files:
        std_path = STD_DIR / cf.name
        if std_path.exists():
            skipped += 1
            continue

        info = get_video_info(cf)
        if not info:
            failed += 1
            continue

        # Check if already standard
        is_std = (info["width"] == TARGET_W and info["height"] == TARGET_H
                  and abs(info["fps"] - TARGET_FPS) < 1)

        if is_std:
            import shutil
            shutil.copy2(str(cf), str(std_path))
            success += 1
        else:
            if ffmpeg_standardize(cf, std_path):
                success += 1
                logger.info(f"  Standardized: {cf.name} "
                           f"({info['width']}x{info['height']} {info['fps']}fps -> "
                           f"{TARGET_W}x{TARGET_H} {TARGET_FPS}fps)")
            else:
                failed += 1
                logger.warning(f"  Failed: {cf.name}")

    logger.info(f"\nStandardization complete:")
    logger.info(f"  Success: {success}")
    logger.info(f"  Skipped (exists): {skipped}")
    logger.info(f"  Failed: {failed}")


# ─── Step 3: Build Dataset Index ─────────────────────────────

def step_build_index():
    """Step 3: Build unified dataset index connecting videos, images, prompts."""
    logger.info("=" * 60)
    logger.info("Step 3: Build Dataset Index")
    logger.info("=" * 60)

    # Load edit prompts
    prompt_file = PROMPTS_DIR / "easy_new.json"
    if prompt_file.exists():
        with open(prompt_file, encoding="utf-8") as f:
            prompts = json.load(f)
        logger.info(f"Loaded {len(prompts)} edit prompts")
    else:
        prompts = []
        logger.warning("No edit prompt file found")

    # Build prompt lookup by video_name
    prompt_by_video = {}
    for p in prompts:
        vname = p.get("video_name", "")
        if vname not in prompt_by_video:
            prompt_by_video[vname] = []
        prompt_by_video[vname].append(p)

    # Load shot detection results
    shot_results_file = BASE_DIR / "processed" / "shot_detection_results.json"
    if shot_results_file.exists():
        with open(shot_results_file, encoding="utf-8") as f:
            shot_results = json.load(f)
    else:
        shot_results = {}

    # Scan standardized videos
    std_files = sorted(STD_DIR.glob("*.mp4")) if STD_DIR.exists() else []
    logger.info(f"Found {len(std_files)} standardized videos")

    # Scan product images
    image_files = sorted(IMAGES_DIR.glob("*.jpg")) + sorted(IMAGES_DIR.glob("*.png"))
    logger.info(f"Found {len(image_files)} product images")

    # Build index
    index = {
        "metadata": {
            "created": datetime.now().isoformat(),
            "source": str(BASE_DIR),
            "total_videos": len(std_files),
            "total_images": len(image_files),
            "total_prompts": len(prompts),
            "standardization": {
                "resolution": f"{TARGET_W}x{TARGET_H}",
                "fps": TARGET_FPS,
                "codec": "H.264",
            }
        },
        "product_images": {},
        "videos": {},
        "edit_pairs": [],
    }

    # Index images
    for img in image_files:
        img_id = img.stem  # e.g., "necklace_1"
        index["product_images"][img_id] = {
            "path": f"product_images/{img.name}",
            "category": img.stem.rsplit("_", 1)[0] if "_" in img.stem else img.stem,
        }

    # Index standardized videos with shot info
    for vf in std_files:
        video_name = vf.stem
        info = get_video_info(vf)

        # Find matching shot detection result
        # The clip might be from a parent video
        parent_video = video_name.rsplit("_clip", 1)[0] if "_clip" in video_name else video_name
        shot_info = shot_results.get(parent_video, {})

        # Extract category from video name
        # Pattern: NNNN-category[N]_scene[NN]
        parts = video_name.split("-", 1)
        category = ""
        if len(parts) > 1:
            cat_part = parts[1]
            # Remove numbers and scene/clip suffixes
            for suffix in ["_scene", "_clip"]:
                cat_part = cat_part.split(suffix)[0]
            # Remove trailing digits
            cat_clean = ""
            for c in cat_part:
                if c.isdigit():
                    break
                cat_clean += c
            category = cat_clean

        # Get associated edit prompts
        video_prompts = prompt_by_video.get(video_name, [])

        index["videos"][video_name] = {
            "path": f"processed/standardized/{vf.name}",
            "category": category,
            "duration": info["duration"] if info else 0,
            "resolution": f"{info['width']}x{info['height']}" if info else "",
            "fps": info["fps"] if info else 0,
            "shot_info": shot_info.get("method", "unknown"),
            "num_edit_prompts": len(video_prompts),
        }

    # Build edit pairs from prompts
    for p in prompts:
        pair = {
            "id": p.get("id", ""),
            "source_video": p.get("video_name", ""),
            "target_image": p.get("inference_image_id", ""),
            "source_prompt": p.get("source_prompt", ""),
            "target_prompt": p.get("target_prompt", ""),
            "source_object": p.get("source_object", ""),
            "target_object": p.get("target_object", ""),
            "instruction": p.get("instruction", ""),
        }
        index["edit_pairs"].append(pair)

    # Save index
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    logger.info(f"\nDataset index built:")
    logger.info(f"  Videos: {len(index['videos'])}")
    logger.info(f"  Images: {len(index['product_images'])}")
    logger.info(f"  Edit pairs: {len(index['edit_pairs'])}")
    logger.info(f"  Saved: {INDEX_FILE}")

    return index


# ─── Step 4: Validation & Statistics ─────────────────────────

def step_validate():
    """Step 4: Validate dataset and generate statistics."""
    logger.info("=" * 60)
    logger.info("Step 4: Dataset Validation & Statistics")
    logger.info("=" * 60)

    if not INDEX_FILE.exists():
        logger.error("Index not found. Run --step index first.")
        return

    with open(INDEX_FILE, encoding="utf-8") as f:
        index = json.load(f)

    stats = {
        "total_videos": len(index["videos"]),
        "total_images": len(index["product_images"]),
        "total_edit_pairs": len(index["edit_pairs"]),
        "by_category": {},
        "duration_stats": {"min": float("inf"), "max": 0, "total": 0},
        "issues": [],
    }

    # Validate videos
    for vname, vinfo in index["videos"].items():
        cat = vinfo.get("category", "unknown")
        if cat not in stats["by_category"]:
            stats["by_category"][cat] = {"videos": 0, "images": 0, "edit_pairs": 0}
        stats["by_category"][cat]["videos"] += 1

        dur = vinfo.get("duration", 0)
        if dur > 0:
            stats["duration_stats"]["min"] = min(stats["duration_stats"]["min"], dur)
            stats["duration_stats"]["max"] = max(stats["duration_stats"]["max"], dur)
            stats["duration_stats"]["total"] += dur

        # Check file exists
        vpath = BASE_DIR / vinfo["path"]
        if not vpath.exists():
            stats["issues"].append(f"Missing video: {vinfo['path']}")

    # Validate images
    for iname, iinfo in index["product_images"].items():
        cat = iinfo.get("category", "unknown")
        if cat not in stats["by_category"]:
            stats["by_category"][cat] = {"videos": 0, "images": 0, "edit_pairs": 0}
        stats["by_category"][cat]["images"] += 1

        ipath = BASE_DIR / iinfo["path"]
        if not ipath.exists():
            stats["issues"].append(f"Missing image: {iinfo['path']}")

    # Count edit pairs by category
    for pair in index["edit_pairs"]:
        src = pair.get("source_video", "")
        parts = src.split("-", 1)
        if len(parts) > 1:
            cat_part = parts[1].split("_scene")[0].split("_clip")[0]
            cat = "".join(c for c in cat_part if not c.isdigit())
        else:
            cat = "unknown"
        if cat in stats["by_category"]:
            stats["by_category"][cat]["edit_pairs"] += 1

    avg_dur = stats["duration_stats"]["total"] / max(stats["total_videos"], 1)
    stats["duration_stats"]["avg"] = round(avg_dur, 2)

    if stats["duration_stats"]["min"] == float("inf"):
        stats["duration_stats"]["min"] = 0

    # Save stats
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    # Print report
    logger.info(f"\n{'='*50}")
    logger.info(f"Dataset Statistics:")
    logger.info(f"  Total videos:     {stats['total_videos']}")
    logger.info(f"  Total images:     {stats['total_images']}")
    logger.info(f"  Total edit pairs: {stats['total_edit_pairs']}")
    logger.info(f"\n  Duration: min={stats['duration_stats']['min']:.1f}s "
                f"max={stats['duration_stats']['max']:.1f}s "
                f"avg={stats['duration_stats']['avg']:.1f}s")
    logger.info(f"\n  By Category:")
    for cat, counts in sorted(stats["by_category"].items()):
        logger.info(f"    {cat:15s} | videos: {counts['videos']:3d} | "
                    f"images: {counts['images']:3d} | pairs: {counts['edit_pairs']:3d}")

    if stats["issues"]:
        logger.warning(f"\n  Issues ({len(stats['issues'])}):")
        for issue in stats["issues"][:10]:
            logger.warning(f"    - {issue}")

    logger.info(f"\n  Stats saved: {STATS_FILE}")
    return stats


# ─── Status ──────────────────────────────────────────────────

def show_status():
    """Show current dataset processing status."""
    print(f"\n{'='*60}")
    print(f"  PVTT Dataset Pipeline - Status")
    print(f"{'='*60}")

    # Raw videos
    raw = list(VIDEOS_DIR.glob("*.mp4")) if VIDEOS_DIR.exists() else []
    print(f"\n  Raw videos:         {len(raw)}")

    # Clips
    clips = list(CLIPS_DIR.glob("*.mp4")) if CLIPS_DIR.exists() else []
    print(f"  Shot-segmented clips: {len(clips)}")

    # Standardized
    std = list(STD_DIR.glob("*.mp4")) if STD_DIR.exists() else []
    print(f"  Standardized clips:   {len(std)}")

    # Images
    imgs = list(IMAGES_DIR.glob("*.jpg")) + list(IMAGES_DIR.glob("*.png")) if IMAGES_DIR.exists() else []
    print(f"  Product images:       {len(imgs)}")

    # Index
    if INDEX_FILE.exists():
        print(f"  Dataset index:        YES")
    else:
        print(f"  Dataset index:        NOT BUILT")

    # Disk usage
    if BASE_DIR.exists():
        result = subprocess.run(["du", "-sh", str(BASE_DIR)],
                                capture_output=True, text=True)
        if result.returncode == 0:
            print(f"\n  Disk usage: {result.stdout.split()[0]}")


# ─── Main ────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="PVTT Dataset Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--all", action="store_true", help="Run full pipeline")
    parser.add_argument("--step", choices=["shots", "standardize", "index", "validate"],
                        help="Run a single step")
    parser.add_argument("--status", action="store_true", help="Show status")

    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.all:
        start = datetime.now()
        step_shot_detection()
        step_standardize()
        step_build_index()
        step_validate()
        elapsed = (datetime.now() - start).total_seconds()
        logger.info(f"\nFull pipeline complete in {elapsed:.1f}s ({elapsed/60:.1f}min)")
    elif args.step:
        if args.step == "shots":
            step_shot_detection()
        elif args.step == "standardize":
            step_standardize()
        elif args.step == "index":
            step_build_index()
        elif args.step == "validate":
            step_validate()
    else:
        parser.print_help()
