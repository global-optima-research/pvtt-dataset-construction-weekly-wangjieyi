"""
Complete pipeline: generate all 8 files for all 200 samples locally.
Uses rembg (product) + cv2.inpaint (background) + template caption.
Quality is baseline - student should replace with GroundingDINO+SAM2, LaMa, Gemini.
"""
import os
import sys
import json
import numpy as np
import cv2
from pathlib import Path
from PIL import Image

# Fix encoding for Windows
os.environ['PYTHONIOENCODING'] = 'utf-8'

from rembg import remove

DATASET_DIR = Path(__file__).parent.parent
TRIGGER = "ad23r2 the camera view suddenly changes "
CANVAS_W, CANVAS_H = 832, 480
PROD_ZONE_RATIO = 0.33


def process_sample(sample_dir, meta):
    """Process a single sample to generate all missing files."""
    raw_path = sample_dir / "first_frame_raw.png"
    if not raw_path.exists():
        return False

    img = Image.open(raw_path).convert("RGB")
    cat = meta.get("product_category", "product")
    name = meta.get("product_name", "")[:80]
    results = {}

    # 1. Product RGBA + Mask
    rgba_path = sample_dir / "product_rgba.png"
    mask_path = sample_dir / "product_mask.png"
    if not rgba_path.exists() or not mask_path.exists():
        rgba_img = remove(img)
        rgba_img.save(str(rgba_path))
        alpha = np.array(rgba_img)[:, :, 3]
        mask = (alpha > 128).astype(np.uint8) * 255
        Image.fromarray(mask, mode="L").save(str(mask_path))
        results["product_rgba"] = {"file": "product_rgba.png", "status": "DONE",
                                    "extraction_method": "rembg", "resolution": list(img.size)}
        results["product_mask"] = {"file": "product_mask.png", "status": "DONE",
                                    "mask_type": "rembg alpha threshold",
                                    "format": "grayscale, 255=product, 0=background"}
    else:
        rgba_img = Image.open(rgba_path)
        mask = np.array(Image.open(mask_path))

    # 2. Background
    bg_path = sample_dir / "background.png"
    if not bg_path.exists():
        img_np = np.array(img)
        kernel = np.ones((15, 15), np.uint8)
        mask_d = cv2.dilate(mask, kernel, iterations=3)
        bg = cv2.inpaint(img_np, mask_d, 10, cv2.INPAINT_TELEA)
        Image.fromarray(bg).save(str(bg_path))
        results["background"] = {"file": "background.png", "status": "DONE",
                                  "extraction_method": "cv2.inpaint (Telea)",
                                  "note": "Baseline quality - replace with LaMa or Gemini"}

    # 3. Caption
    caption_path = sample_dir / "caption.txt"
    if not caption_path.exists() or caption_path.stat().st_size < 10:
        # Check if Gemini already generated one
        existing = meta.get("caption", {}).get("status")
        if existing != "DONE":
            caption = (f"{TRIGGER}A {cat} product is showcased in a commercial setting. "
                      f"The {name} is displayed prominently, highlighting its design and details. "
                      f"The camera captures the product from a close-up angle.")
            caption_path.write_text(caption, encoding="utf-8")
            results["caption"] = {"file": "caption.txt", "status": "DONE",
                                   "full_text": caption, "trigger_prefix": TRIGGER.strip(),
                                   "generation_method": "template",
                                   "note": "Template caption - replace with Gemini/VLM generated"}

    # 4. First Frame Composition
    ff_path = sample_dir / "first_frame.png"
    if not ff_path.exists():
        canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), (255, 255, 255))
        zone_w = int(CANVAS_W * PROD_ZONE_RATIO)
        bg_zone = CANVAS_W - zone_w

        # Left: product
        prod = rgba_img.copy()
        bbox = prod.getbbox()
        if bbox:
            prod = prod.crop(bbox)
        pw, ph = prod.size
        if pw > 0 and ph > 0:
            sc = min((zone_w - 10) / pw, (CANVAS_H - 10) / ph)
            prod = prod.resize((max(1, int(pw * sc)), max(1, int(ph * sc))), Image.LANCZOS)
            px = (zone_w - prod.size[0]) // 2
            py = (CANVAS_H - prod.size[1]) // 2
            canvas.paste(prod, (px, py), prod)

        # Right: background
        bg_img = Image.open(bg_path).convert("RGB")
        bw, bh = bg_img.size
        if bw > 0 and bh > 0:
            sc2 = min((bg_zone - 10) / bw, (CANVAS_H - 10) / bh)
            bg_img = bg_img.resize((max(1, int(bw * sc2)), max(1, int(bh * sc2))), Image.LANCZOS)
            bx = zone_w + (bg_zone - bg_img.size[0]) // 2
            by = (CANVAS_H - bg_img.size[1]) // 2
            canvas.paste(bg_img, (bx, by))

        canvas.save(str(ff_path))
        results["first_frame"] = {"file": "first_frame.png", "status": "DONE",
                                   "canvas_size": [CANVAS_W, CANVAS_H],
                                   "canvas_color": [255, 255, 255],
                                   "product_zone_ratio": PROD_ZONE_RATIO,
                                   "layout": "left=product_rgba, right=background"}

    return results


def main():
    samples = sorted(d for d in os.listdir(DATASET_DIR) if d.startswith("sample_"))

    # Count what needs doing
    todo = 0
    for s in samples:
        sd = DATASET_DIR / s
        needed = ["product_rgba.png", "product_mask.png", "background.png",
                  "caption.txt", "first_frame.png"]
        if any(not (sd / f).exists() for f in needed):
            todo += 1

    print(f"Processing {len(samples)} samples ({todo} need work)...")
    if todo == 0:
        print("All samples complete!")
        return

    success = 0
    failed = 0

    for i, sample in enumerate(samples):
        sample_dir = DATASET_DIR / sample
        meta_path = sample_dir / "metadata.json"

        if not meta_path.exists():
            failed += 1
            continue

        meta = json.load(open(meta_path, encoding="utf-8"))

        try:
            results = process_sample(sample_dir, meta)
            if results:
                meta.update(results)
                # Update file lists
                all_files = ["video.mp4", "first_frame.png", "first_frame_raw.png",
                             "caption.txt", "product_rgba.png", "product_mask.png",
                             "background.png", "metadata.json"]
                ready = [f for f in all_files if (sample_dir / f).exists()]
                todo_files = [f for f in all_files if f not in ready]
                meta["files_ready"] = ready
                meta["files_todo"] = todo_files

                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta, f, ensure_ascii=False, indent=2)

            success += 1
        except Exception as e:
            failed += 1
            print(f"  {sample}: ERROR - {str(e)[:60]}", flush=True)

        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(samples)}] ok={success}, fail={failed}", flush=True)

    print(f"\nDone! Success: {success}, Failed: {failed}")

    # Final validation
    complete = 0
    for s in samples:
        sd = DATASET_DIR / s
        files = ["video.mp4", "first_frame.png", "first_frame_raw.png",
                 "caption.txt", "product_rgba.png", "product_mask.png",
                 "background.png", "metadata.json"]
        if all((sd / f).exists() for f in files):
            complete += 1
    print(f"Complete samples (all 8 files): {complete}/{len(samples)}")


if __name__ == "__main__":
    main()
