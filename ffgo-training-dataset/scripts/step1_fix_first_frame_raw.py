"""Step 1: Crop black padding from first_frame_raw.png for all samples."""
import json
import os
from PIL import Image

DATASET_DIR = os.path.join(os.path.dirname(__file__), "..")


def main():
    samples = sorted(d for d in os.listdir(DATASET_DIR) if d.startswith("sample_"))
    print(f"Fixing {len(samples)} samples...")

    fixed = 0
    for i, sample in enumerate(samples):
        sample_dir = os.path.join(DATASET_DIR, sample)
        meta_path = os.path.join(sample_dir, "metadata.json")
        raw_path = os.path.join(sample_dir, "first_frame_raw.png")

        if not os.path.exists(meta_path) or not os.path.exists(raw_path):
            continue

        meta = json.load(open(meta_path, encoding="utf-8"))
        padding = meta.get("video", {}).get("padding", {})
        pad_l = padding.get("left", 0)
        pad_t = padding.get("top", 0)
        pad_r = padding.get("right", 0)
        pad_b = padding.get("bottom", 0)

        has_padding = meta.get("video", {}).get("has_padding", False)

        img = Image.open(raw_path)
        w, h = img.size  # Should be 832x480

        if has_padding and (pad_l + pad_r + pad_t + pad_b) > 0:
            # Crop to content area
            content = img.crop((pad_l, pad_t, w - pad_r, h - pad_b))
            content.save(raw_path)
            content_w, content_h = content.size
        else:
            content_w, content_h = w, h

        # Update metadata
        meta["first_frame_raw"] = {
            "file": "first_frame_raw.png",
            "resolution": [content_w, content_h],
            "note": "Content area only (padding removed)",
        }

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        fixed += 1
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(samples)} done")

    print(f"Fixed {fixed} samples.")


if __name__ == "__main__":
    main()
