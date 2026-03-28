"""
Improved local pipeline: better rembg model + NS inpainting + Gemini captions (where available).
Overwrites product_rgba, product_mask, background, first_frame for all samples.
"""
import os
import sys
import json
import numpy as np
import cv2
from pathlib import Path
from PIL import Image

os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['U2NET_HOME'] = 'D:/00_aPhD/IP/.cache/u2net'
os.environ['HF_HOME'] = 'D:/00_aPhD/IP/.cache/huggingface'
os.environ['TMPDIR'] = 'D:/00_aPhD/IP/.cache/tmp'
os.environ['TEMP'] = 'D:/00_aPhD/IP/.cache/tmp'
os.environ['TMP'] = 'D:/00_aPhD/IP/.cache/tmp'
from rembg import remove, new_session

DATASET_DIR = Path(__file__).parent.parent
TRIGGER = "ad23r2 the camera view suddenly changes "
CANVAS_W, CANVAS_H = 832, 480
PROD_ZONE_RATIO = 0.33

# Use isnet-general-use model (better for objects/products than u2net)
print("Loading rembg model (isnet-general-use)...", flush=True)
SESSION = new_session("isnet-general-use")
print("Model loaded!", flush=True)


def extract_product(img_pil):
    """Extract product with improved rembg model."""
    rgba = remove(img_pil, session=SESSION)
    alpha = np.array(rgba)[:, :, 3]
    mask = (alpha > 128).astype(np.uint8) * 255
    return rgba, Image.fromarray(mask, mode="L"), mask


def inpaint_bg(img_pil, mask_np):
    """Improved inpainting: NS method with larger radius + multi-pass."""
    img_np = np.array(img_pil)
    # Dilate mask generously
    kernel = np.ones((21, 21), np.uint8)
    mask_d = cv2.dilate(mask_np, kernel, iterations=3)

    # Multi-pass NS inpainting (progressively larger radius)
    result = cv2.inpaint(img_np, mask_d, 20, cv2.INPAINT_NS)
    # Second pass with Telea for remaining artifacts
    residual_mask = cv2.dilate(mask_np, np.ones((5, 5), np.uint8), iterations=1)
    result = cv2.inpaint(result, residual_mask, 5, cv2.INPAINT_TELEA)

    return Image.fromarray(result)


def compose_first_frame(rgba_path, bg_path, out_path):
    """Compose first_frame on white canvas."""
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), (255, 255, 255))
    zone_w = int(CANVAS_W * PROD_ZONE_RATIO)
    bg_zone = CANVAS_W - zone_w

    prod = Image.open(rgba_path).convert("RGBA")
    bbox = prod.getbbox()
    if bbox:
        prod = prod.crop(bbox)
    pw, ph = prod.size
    if pw > 0 and ph > 0:
        sc = min((zone_w - 10) / pw, (CANVAS_H - 10) / ph)
        prod = prod.resize((max(1, int(pw * sc)), max(1, int(ph * sc))), Image.LANCZOS)
        canvas.paste(prod, ((zone_w - prod.size[0]) // 2, (CANVAS_H - prod.size[1]) // 2), prod)

    bg = Image.open(bg_path).convert("RGB")
    bw, bh = bg.size
    if bw > 0 and bh > 0:
        sc = min((bg_zone - 10) / bw, (CANVAS_H - 10) / bh)
        bg = bg.resize((max(1, int(bw * sc)), max(1, int(bh * sc))), Image.LANCZOS)
        canvas.paste(bg, (zone_w + (bg_zone - bg.size[0]) // 2, (CANVAS_H - bg.size[1]) // 2))

    canvas.save(str(out_path))


def main():
    samples = sorted(d for d in os.listdir(DATASET_DIR) if d.startswith("sample_"))
    print(f"Processing {len(samples)} samples (improved quality)...", flush=True)

    success = 0
    failed = 0

    for i, sample in enumerate(samples):
        sd = DATASET_DIR / sample
        raw_path = sd / "first_frame_raw.png"
        meta_path = sd / "metadata.json"

        if not raw_path.exists() or not meta_path.exists():
            failed += 1
            continue

        meta = json.load(open(meta_path, encoding="utf-8"))

        try:
            img = Image.open(raw_path).convert("RGB")

            # Product extraction (improved model)
            rgba, mask_pil, mask_np = extract_product(img)
            rgba.save(str(sd / "product_rgba.png"))
            mask_pil.save(str(sd / "product_mask.png"))

            # Background inpainting (improved)
            bg = inpaint_bg(img, mask_np)
            bg.save(str(sd / "background.png"))

            # Caption (keep Gemini ones, replace template ones)
            caption_path = sd / "caption.txt"
            cap_method = meta.get("caption", {}).get("generation_method", "")
            if cap_method == "template" or not caption_path.exists():
                cat = meta.get("product_category", "product")
                name = meta.get("product_name", "")[:80]
                scene = meta.get("scene_category", "B")
                if scene == "A":
                    action = "being worn by a person, showcasing how it looks when in use"
                elif scene == "C":
                    action = "placed in a lifestyle setting, showing its real-world context"
                else:
                    action = "displayed in a close-up product shot, highlighting its design details"
                caption = (f"{TRIGGER}A {cat} is {action}. "
                          f"The product features a distinctive design. "
                          f"The camera captures the scene from a steady angle, "
                          f"focusing on the product's visual appeal.")
                caption_path.write_text(caption, encoding="utf-8")
                meta["caption"] = {"file": "caption.txt", "status": "DONE",
                                   "generation_method": "improved-template",
                                   "full_text": caption, "trigger_prefix": TRIGGER.strip()}

            # First frame composition
            compose_first_frame(sd / "product_rgba.png", sd / "background.png", sd / "first_frame.png")

            # Update metadata
            meta["product_rgba"] = {"file": "product_rgba.png", "status": "DONE",
                                     "extraction_method": "rembg-isnet-general-use",
                                     "resolution": list(img.size)}
            meta["product_mask"] = {"file": "product_mask.png", "status": "DONE",
                                     "mask_type": "rembg-isnet alpha threshold"}
            meta["background"] = {"file": "background.png", "status": "DONE",
                                   "extraction_method": "cv2.inpaint-NS-multipass"}
            meta["first_frame"] = {"file": "first_frame.png", "status": "DONE",
                                    "canvas_size": [CANVAS_W, CANVAS_H]}
            meta["files_ready"] = ["video.mp4", "first_frame.png", "first_frame_raw.png",
                                   "caption.txt", "product_rgba.png", "product_mask.png",
                                   "background.png", "metadata.json"]
            meta["files_todo"] = []
            json.dump(meta, open(meta_path, "w"), ensure_ascii=False, indent=2)

            success += 1

        except Exception as e:
            failed += 1
            print(f"  {sample}: ERROR - {str(e)[:60]}", flush=True)

        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(samples)}] ok={success}, fail={failed}", flush=True)

    print(f"\nDone! Success: {success}, Failed: {failed}")


if __name__ == "__main__":
    main()
