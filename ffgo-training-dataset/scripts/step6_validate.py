"""Step 6: Validate all samples and generate summary report."""
import json
import os
from pathlib import Path
from PIL import Image

DATASET_DIR = Path(__file__).parent.parent
REQUIRED_FILES = [
    "video.mp4", "first_frame.png", "first_frame_raw.png",
    "caption.txt", "product_rgba.png", "product_mask.png",
    "background.png", "metadata.json",
]
TRIGGER_PREFIX = "ad23r2 the camera view suddenly changes"


def validate_sample(sample_dir):
    """Validate a single sample. Returns (issues, warnings)."""
    issues = []
    warnings = []

    # Check all files exist
    for f in REQUIRED_FILES:
        if not (sample_dir / f).exists():
            issues.append(f"Missing: {f}")

    # Check video.mp4
    # (skipping detailed video check to avoid opencv dependency)

    # Check first_frame.png (832x480)
    ff = sample_dir / "first_frame.png"
    if ff.exists():
        img = Image.open(ff)
        if img.size != (832, 480):
            issues.append(f"first_frame.png: {img.size} != (832, 480)")

    # Check first_frame_raw.png (no padding, variable size)
    raw = sample_dir / "first_frame_raw.png"
    if raw.exists():
        img = Image.open(raw)
        if img.size == (832, 480):
            warnings.append("first_frame_raw.png is 832x480 (may still have padding)")

    # Check product_rgba.png (RGBA)
    rgba = sample_dir / "product_rgba.png"
    if rgba.exists():
        img = Image.open(rgba)
        if img.mode != "RGBA":
            issues.append(f"product_rgba.png mode: {img.mode} != RGBA")

    # Check product_mask.png (grayscale)
    mask = sample_dir / "product_mask.png"
    if mask.exists():
        img = Image.open(mask)
        if img.mode not in ("L", "1"):
            warnings.append(f"product_mask.png mode: {img.mode} (expected L)")

    # Check caption.txt
    caption = sample_dir / "caption.txt"
    if caption.exists():
        text = caption.read_text(encoding="utf-8").strip()
        if not text.startswith(TRIGGER_PREFIX):
            issues.append("caption.txt missing trigger prefix")
        if len(text) < 50:
            warnings.append(f"caption.txt very short ({len(text)} chars)")

    return issues, warnings


def main():
    samples = sorted(d for d in os.listdir(DATASET_DIR) if d.startswith("sample_"))
    print(f"Validating {len(samples)} samples...\n")

    total_issues = 0
    total_warnings = 0
    file_stats = {f: 0 for f in REQUIRED_FILES}
    complete = 0

    for sample in samples:
        sample_dir = DATASET_DIR / sample
        issues, warnings = validate_sample(sample_dir)

        # Count files
        for f in REQUIRED_FILES:
            if (sample_dir / f).exists():
                file_stats[f] += 1

        if not issues and not warnings:
            complete += 1

        if issues:
            print(f"  {sample}: {len(issues)} issues")
            for iss in issues:
                print(f"    ❌ {iss}")
            total_issues += len(issues)
        if warnings:
            total_warnings += len(warnings)

    print(f"\n{'='*60}")
    print(f"VALIDATION REPORT")
    print(f"{'='*60}")
    print(f"Total samples: {len(samples)}")
    print(f"Complete (all 8 files, no issues): {complete}")
    print(f"Total issues: {total_issues}")
    print(f"Total warnings: {total_warnings}")
    print(f"\nFile completion:")
    for f, count in file_stats.items():
        status = "✅" if count == len(samples) else f"⚠️ {count}/{len(samples)}"
        print(f"  {f:<25s} {status}")


if __name__ == "__main__":
    main()
