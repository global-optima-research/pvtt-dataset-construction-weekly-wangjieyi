"""
视频处理管线
- 镜头检测与分割 (PySceneDetect)
- 转场和无效帧去除
- 视频标准化 (720p, 24fps, 2-4s, H.264)

使用方法:
  python video_processor.py --input data/ --output processed/videos/
  python video_processor.py --input data/etsy/珠宝/media/videos/ --output processed/videos/ --category 珠宝
"""

import os
import json
import subprocess
import logging
import argparse
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# FFmpeg / FFprobe 工具函数
# ─────────────────────────────────────────────

def get_video_info(video_path: str) -> Optional[dict]:
    """使用 ffprobe 提取视频元信息"""
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return None
        probe = json.loads(result.stdout)
        video_stream = None
        for s in probe.get("streams", []):
            if s.get("codec_type") == "video":
                video_stream = s
                break
        if not video_stream:
            return None

        # 解析帧率
        fps_str = video_stream.get("r_frame_rate", "24/1")
        if "/" in fps_str:
            num, den = fps_str.split("/")
            fps = float(num) / float(den) if float(den) != 0 else 24.0
        else:
            fps = float(fps_str)

        duration = float(probe.get("format", {}).get("duration", 0))

        return {
            "width": int(video_stream.get("width", 0)),
            "height": int(video_stream.get("height", 0)),
            "fps": round(fps, 2),
            "duration": round(duration, 2),
            "total_frames": int(video_stream.get("nb_frames", 0)) or int(duration * fps),
            "codec": video_stream.get("codec_name", ""),
            "bitrate": int(probe.get("format", {}).get("bit_rate", 0)),
        }
    except Exception as e:
        logger.warning(f"ffprobe 失败 {video_path}: {e}")
        return None


def ffmpeg_cut(input_path: str, output_path: str,
               start_sec: float, duration_sec: float,
               target_w: int = 1280, target_h: int = 720,
               target_fps: int = 24) -> bool:
    """
    使用 ffmpeg 切割 + 标准化视频片段
    - 缩放到目标分辨率 (保持比例, 黑边填充)
    - 转换帧率
    - H.264 编码
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # scale + pad 保持宽高比, 黑边填充到目标尺寸
    vf = (
        f"fps={target_fps},"
        f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
        f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=black"
    )

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start_sec:.3f}",
        "-i", input_path,
        "-t", f"{duration_sec:.3f}",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-an",  # 去除音频
        "-movflags", "+faststart",
        output_path
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            logger.warning(f"ffmpeg 失败: {result.stderr[-300:]}")
            return False
        return True
    except Exception as e:
        logger.warning(f"ffmpeg 异常: {e}")
        return False


# ─────────────────────────────────────────────
# 镜头检测 (PySceneDetect)
# ─────────────────────────────────────────────

def detect_shots(video_path: str, min_scene_len_sec: float = 1.0,
                 threshold: float = 27.0) -> list:
    """
    使用 PySceneDetect 检测镜头边界

    返回: [(start_sec, end_sec, duration_sec), ...]
    """
    try:
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import ContentDetector
    except ImportError:
        logger.error("请安装 scenedetect: pip install scenedetect[opencv]")
        return []

    video = open_video(video_path)
    fps = video.frame_rate

    min_scene_len_frames = max(1, int(min_scene_len_sec * fps))

    scene_manager = SceneManager()
    scene_manager.add_detector(
        ContentDetector(threshold=threshold, min_scene_len=min_scene_len_frames)
    )

    scene_manager.detect_scenes(video)
    scene_list = scene_manager.get_scene_list()

    shots = []
    for start, end in scene_list:
        start_sec = start.get_seconds()
        end_sec = end.get_seconds()
        dur = end_sec - start_sec
        shots.append((round(start_sec, 3), round(end_sec, 3), round(dur, 3)))

    return shots


# ─────────────────────────────────────────────
# 片段有效性过滤
# ─────────────────────────────────────────────

def is_valid_clip(shot: tuple, min_dur: float = 1.5, max_dur: float = 5.0) -> bool:
    """过滤无效片段 (太短/太长)"""
    _, _, duration = shot
    return min_dur <= duration <= max_dur


def filter_black_frames(video_path: str, start_sec: float, duration_sec: float,
                        black_threshold: float = 10.0) -> bool:
    """
    检查片段是否主要为黑帧 (转场)
    使用 ffmpeg blackdetect 过滤
    """
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start_sec:.3f}",
        "-i", video_path,
        "-t", f"{duration_sec:.3f}",
        "-vf", f"blackdetect=d=0.5:pix_th={black_threshold/255:.4f}",
        "-an", "-f", "null", "-"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        stderr = result.stderr
        # 如果检测到黑帧且占比超50%, 认为是转场
        black_segments = stderr.count("black_start:")
        if black_segments > 0:
            # 粗略判断: 有黑帧检出就标记
            return False
        return True
    except Exception:
        return True  # 检测失败时默认保留


# ─────────────────────────────────────────────
# 核心处理流程
# ─────────────────────────────────────────────

def process_single_video(video_path: str, output_dir: str,
                         product_id: str = "",
                         target_w: int = 1280, target_h: int = 720,
                         target_fps: int = 24,
                         min_clip_dur: float = 1.5,
                         max_clip_dur: float = 5.0,
                         target_clip_dur: tuple = (2.0, 4.0)) -> list:
    """
    处理单个视频: 镜头检测 → 过滤 → 标准化切割

    参数:
        video_path: 输入视频路径
        output_dir: 输出目录
        product_id: 产品ID (用于命名)
        target_w/h: 目标分辨率 (默认720p = 1280x720)
        target_fps: 目标帧率
        min/max_clip_dur: 镜头检测时的有效时长范围
        target_clip_dur: 最终输出片段的时长范围

    返回: 生成的片段信息列表
    """
    info = get_video_info(video_path)
    if not info:
        logger.warning(f"无法读取视频信息: {video_path}")
        return []

    if not product_id:
        product_id = Path(video_path).stem

    logger.info(
        f"处理视频: {product_id} | "
        f"{info['width']}x{info['height']} {info['fps']}fps {info['duration']:.1f}s"
    )

    clips = []

    # 短视频 (<=5s) 直接标准化, 不做镜头分割
    if info["duration"] <= max_clip_dur:
        if info["duration"] < min_clip_dur:
            logger.info(f"  跳过: 时长 {info['duration']:.1f}s 过短")
            return []

        # 裁剪到目标时长范围
        clip_dur = min(info["duration"], target_clip_dur[1])
        output_path = os.path.join(output_dir, f"{product_id}_clip00.mp4")

        if ffmpeg_cut(video_path, output_path, 0, clip_dur,
                      target_w, target_h, target_fps):
            clip_info = {
                "clip_id": f"{product_id}_clip00",
                "source_video": video_path,
                "product_id": product_id,
                "start_sec": 0,
                "end_sec": round(clip_dur, 3),
                "duration_sec": round(clip_dur, 3),
                "resolution": f"{target_w}x{target_h}",
                "fps": target_fps,
                "output_path": output_path,
            }
            clips.append(clip_info)
            logger.info(f"  短视频直接标准化 → {output_path}")
        return clips

    # 长视频: 镜头检测 + 分割
    shots = detect_shots(video_path, min_scene_len_sec=min_clip_dur)

    if not shots:
        # 无法检测到镜头, 按固定间隔切割
        logger.info(f"  未检测到镜头边界, 按 {target_clip_dur[1]}s 间隔切割")
        interval = target_clip_dur[1]
        t = 0
        shot_idx = 0
        while t < info["duration"]:
            remaining = info["duration"] - t
            dur = min(interval, remaining)
            if dur >= min_clip_dur:
                shots.append((round(t, 3), round(t + dur, 3), round(dur, 3)))
            t += interval
            shot_idx += 1

    # 过滤有效片段
    valid_shots = []
    for shot in shots:
        if not is_valid_clip(shot, min_clip_dur, max_clip_dur):
            continue
        # 检查是否为黑帧/转场
        if not filter_black_frames(video_path, shot[0], shot[2]):
            logger.info(f"  跳过黑帧片段: {shot[0]:.1f}-{shot[1]:.1f}s")
            continue
        valid_shots.append(shot)

    logger.info(f"  镜头检测: {len(shots)} 个 → 有效: {len(valid_shots)} 个")

    # 切割有效片段
    for idx, (start, end, dur) in enumerate(valid_shots):
        # 限制输出时长在目标范围内
        clip_dur = min(dur, target_clip_dur[1])
        if clip_dur < target_clip_dur[0] and dur >= target_clip_dur[0]:
            clip_dur = target_clip_dur[0]

        output_path = os.path.join(output_dir, f"{product_id}_clip{idx:02d}.mp4")

        if ffmpeg_cut(video_path, output_path, start, clip_dur,
                      target_w, target_h, target_fps):
            clip_info = {
                "clip_id": f"{product_id}_clip{idx:02d}",
                "source_video": video_path,
                "product_id": product_id,
                "shot_index": idx,
                "start_sec": start,
                "end_sec": round(start + clip_dur, 3),
                "duration_sec": round(clip_dur, 3),
                "resolution": f"{target_w}x{target_h}",
                "fps": target_fps,
                "output_path": output_path,
            }
            clips.append(clip_info)

    logger.info(f"  输出 {len(clips)} 个标准化片段")
    return clips


# ─────────────────────────────────────────────
# 批量处理
# ─────────────────────────────────────────────

def process_all_videos(input_base: str, output_base: str,
                       target_w: int = 1280, target_h: int = 720,
                       target_fps: int = 24) -> dict:
    """
    批量处理所有已下载的视频

    扫描目录结构:
      input_base/{platform}/{category}/media/videos/*.mp4

    输出:
      output_base/{category}/{product_id}_clip{N}.mp4

    返回: 处理统计和所有片段信息
    """
    all_clips = []
    stats = {
        "total_videos": 0,
        "processed_videos": 0,
        "total_clips": 0,
        "skipped": 0,
        "by_category": {},
    }

    input_path = Path(input_base)
    video_extensions = {".mp4", ".mov", ".webm", ".avi", ".mkv"}

    # 扫描所有平台和品类下的视频
    for platform_dir in sorted(input_path.iterdir()):
        if not platform_dir.is_dir():
            continue
        platform = platform_dir.name

        for category_dir in sorted(platform_dir.iterdir()):
            if not category_dir.is_dir():
                continue
            category = category_dir.name

            videos_dir = category_dir / "media" / "videos"
            if not videos_dir.exists():
                continue

            category_output = os.path.join(output_base, category)
            os.makedirs(category_output, exist_ok=True)

            video_files = [
                f for f in videos_dir.iterdir()
                if f.suffix.lower() in video_extensions
            ]

            if not video_files:
                continue

            logger.info(f"\n[{platform}/{category}] 发现 {len(video_files)} 个视频")

            for video_file in sorted(video_files):
                stats["total_videos"] += 1
                product_id = f"{platform}_{video_file.stem}"

                clips = process_single_video(
                    str(video_file), category_output,
                    product_id=product_id,
                    target_w=target_w, target_h=target_h,
                    target_fps=target_fps,
                )

                if clips:
                    stats["processed_videos"] += 1
                    stats["total_clips"] += len(clips)
                    all_clips.extend(clips)

                    if category not in stats["by_category"]:
                        stats["by_category"][category] = {"videos": 0, "clips": 0}
                    stats["by_category"][category]["videos"] += 1
                    stats["by_category"][category]["clips"] += len(clips)
                else:
                    stats["skipped"] += 1

    # 保存片段索引
    index_path = os.path.join(output_base, "clips_index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump({
            "stats": stats,
            "clips": all_clips,
        }, f, ensure_ascii=False, indent=2)

    logger.info(f"\n{'='*50}")
    logger.info(f"视频处理完成!")
    logger.info(f"  输入视频: {stats['total_videos']}")
    logger.info(f"  已处理: {stats['processed_videos']}")
    logger.info(f"  跳过: {stats['skipped']}")
    logger.info(f"  输出片段: {stats['total_clips']}")
    logger.info(f"  索引保存: {index_path}")

    return stats


# ─────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    parser = argparse.ArgumentParser(description="视频处理管线: 镜头分割 + 标准化")
    parser.add_argument("--input", default="./data",
                        help="输入目录 (含平台/品类/media/videos/)")
    parser.add_argument("--output", default="./processed/videos",
                        help="输出目录")
    parser.add_argument("--width", type=int, default=1280,
                        help="目标宽度 (默认1280=720p)")
    parser.add_argument("--height", type=int, default=720,
                        help="目标高度 (默认720)")
    parser.add_argument("--fps", type=int, default=24,
                        help="目标帧率 (默认24)")
    parser.add_argument("--single", help="处理单个视频文件")

    args = parser.parse_args()

    if args.single:
        clips = process_single_video(
            args.single, args.output,
            target_w=args.width, target_h=args.height,
            target_fps=args.fps,
        )
        print(f"生成 {len(clips)} 个片段")
        for c in clips:
            print(f"  {c['clip_id']}: {c['duration_sec']:.1f}s → {c['output_path']}")
    else:
        process_all_videos(
            args.input, args.output,
            target_w=args.width, target_h=args.height,
            target_fps=args.fps,
        )
