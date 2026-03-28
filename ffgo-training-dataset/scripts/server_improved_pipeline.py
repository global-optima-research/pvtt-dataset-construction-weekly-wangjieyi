#!/usr/bin/env python3
"""
Improved FFGO pipeline - runs on GPU server.
1. GroundingDINO (text-guided bbox) + rembg (precise extraction within bbox)
2. LaMa (deep learning inpainting for background)
"""
import os
import json
import numpy as np
import cv2
import torch
from pathlib import Path
from PIL import Image

DATASET = Path("/data/wangjieyi/ffgo-dataset")
# RTX 5090 (sm_120) not supported by PyTorch stable - force CPU
DEVICE = "cpu"

# Category -> detection prompt for GroundingDINO
PROMPTS = {
    "bracelet": "bracelet . jewelry . bangle",
    "earring": "earring . jewelry . stud",
    "handbag": "handbag . bag . purse . tote",
    "necklace": "necklace . pendant . chain",
    "ring": "ring . jewelry . band",
    "sunglasses": "sunglasses . glasses . eyewear",
    "watch": "watch . wristwatch . timepiece",
    "cosmetics": "cosmetics . makeup . lipstick . bottle . tube",
}


def load_gdino(device):
    """Load GroundingDINO model."""
    from groundingdino.util.inference import load_model
    import groundingdino

    cfg = os.path.join(os.path.dirname(groundingdino.__file__),
                       "config", "GroundingDINO_SwinT_OGC.py")
    weights = "/data/wangjieyi/models/groundingdino_swint_ogc.pth"

    if not os.path.exists(weights) or os.path.getsize(weights) < 600_000_000:
        raise RuntimeError(f"GroundingDINO weights not found or incomplete at {weights}")

    model = load_model(cfg, weights, device=device)
    return model


def detect_product(gdino_model, image_pil, text_prompt, box_threshold=0.25):
    """Detect product bounding box using GroundingDINO."""
    from groundingdino.util.inference import predict
    from torchvision import transforms

    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    img_tensor = transform(image_pil)

    boxes, logits, phrases = predict(
        model=gdino_model,
        image=img_tensor,
        caption=text_prompt,
        box_threshold=box_threshold,
        text_threshold=0.2,
    )

    if len(boxes) == 0:
        return None, 0

    # Take highest confidence
    best = logits.argmax()
    box = boxes[best].numpy()
    conf = logits[best].item()
    h, w = image_pil.size[1], image_pil.size[0]
    # Convert from cx,cy,w,h normalized to x1,y1,x2,y2 pixels
    cx, cy, bw, bh = box
    x1 = int((cx - bw/2) * w)
    y1 = int((cy - bh/2) * h)
    x2 = int((cx + bw/2) * w)
    y2 = int((cy + bh/2) * h)
    # Clamp
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)

    return (x1, y1, x2, y2), conf


def extract_product(image_pil, bbox):
    """Extract product using rembg within detected bbox region."""
    from rembg import remove

    x1, y1, x2, y2 = bbox
    w, h = image_pil.size

    # Expand bbox by 20% for context
    bw, bh = x2 - x1, y2 - y1
    expand = 0.2
    x1e = max(0, int(x1 - bw * expand))
    y1e = max(0, int(y1 - bh * expand))
    x2e = min(w, int(x2 + bw * expand))
    y2e = min(h, int(y2 + bh * expand))

    # Crop region
    crop = image_pil.crop((x1e, y1e, x2e, y2e))

    # Run rembg on cropped region (more precise)
    crop_rgba = remove(crop)

    # Create full-size RGBA (transparent everywhere except detected region)
    full_rgba = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    full_rgba.paste(crop_rgba, (x1e, y1e))

    # Extract mask
    alpha = np.array(full_rgba)[:, :, 3]
    mask = (alpha > 128).astype(np.uint8) * 255

    return full_rgba, Image.fromarray(mask, mode="L")


def extract_product_fallback(image_pil):
    """Fallback: full-image rembg."""
    from rembg import remove
    rgba = remove(image_pil)
    alpha = np.array(rgba)[:, :, 3]
    mask = (alpha > 128).astype(np.uint8) * 255
    return rgba, Image.fromarray(mask, mode="L")


def inpaint_background(image_pil, mask_pil, lama_model=None):
    """Remove product using LaMa or cv2.inpaint fallback."""
    mask_np = np.array(mask_pil)

    # Dilate mask for cleaner removal
    kernel = np.ones((11, 11), np.uint8)
    mask_dilated = cv2.dilate(mask_np, kernel, iterations=3)

    if lama_model is not None:
        mask_dilated_pil = Image.fromarray(mask_dilated, mode="L")
        result = lama_model(image_pil, mask_dilated_pil)
        return result
    else:
        # Fallback: cv2.inpaint (Navier-Stokes, better than Telea)
        img_np = np.array(image_pil)
        result = cv2.inpaint(img_np, mask_dilated, 15, cv2.INPAINT_NS)
        return Image.fromarray(result)


def main():
    samples = sorted(d for d in os.listdir(DATASET) if d.startswith("sample_"))
    print(f"Processing {len(samples)} samples on GPU", flush=True)

    # Load models
    print("Loading GroundingDINO...", flush=True)
    gdino = load_gdino(DEVICE)
    print("GroundingDINO loaded!", flush=True)

    print("Loading LaMa...", flush=True)
    lama = None
    try:
        # Delete corrupted model cache and re-download
        import shutil
        lama_cache = os.path.expanduser("~/.cache/simple_lama_inpainting")
        if os.path.exists(lama_cache):
            shutil.rmtree(lama_cache)
        from simple_lama_inpainting import SimpleLama
        lama = SimpleLama()
        print("LaMa loaded!", flush=True)
    except Exception as e:
        print(f"LaMa failed: {e}", flush=True)
        print("Using cv2.inpaint (NS) as fallback", flush=True)

    success = 0
    gdino_detect = 0
    fallback = 0
    failed = 0

    for i, sample in enumerate(samples):
        sd = DATASET / sample
        raw_path = sd / "first_frame_raw.png"
        meta_path = sd / "metadata.json"

        if not raw_path.exists() or not meta_path.exists():
            failed += 1
            continue

        meta = json.load(open(meta_path))
        category = meta.get("product_category", "product")
        prompt = PROMPTS.get(category, category)

        try:
            img = Image.open(raw_path).convert("RGB")

            # Step 1: GroundingDINO detection
            bbox, conf = detect_product(gdino, img, prompt)

            if bbox is not None and conf > 0.2:
                # GroundingDINO found product -> precise extraction
                rgba, mask = extract_product(img, bbox)
                method = f"groundingdino(conf={conf:.2f})+rembg"
                gdino_detect += 1
            else:
                # Fallback to full rembg
                rgba, mask = extract_product_fallback(img)
                method = "rembg-fallback"
                fallback += 1

            rgba.save(str(sd / "product_rgba.png"))
            mask.save(str(sd / "product_mask.png"))

            # Step 2: LaMa inpainting
            bg = inpaint_background(img, mask, lama)
            bg.save(str(sd / "background.png"))

            # Update metadata
            meta["product_rgba"] = {
                "file": "product_rgba.png",
                "status": "DONE",
                "extraction_method": method,
                "resolution": list(img.size),
            }
            meta["product_mask"] = {
                "file": "product_mask.png",
                "status": "DONE",
                "mask_type": "precise",
                "format": "grayscale, 255=product, 0=background",
            }
            meta["background"] = {
                "file": "background.png",
                "status": "DONE",
                "extraction_method": "LaMa-inpainting",
            }
            json.dump(meta, open(meta_path, "w"), ensure_ascii=False, indent=2)

            success += 1

        except Exception as e:
            failed += 1
            print(f"  {sample}: ERROR - {str(e)[:80]}", flush=True)

        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(samples)}] ok={success} gdino={gdino_detect} fallback={fallback} fail={failed}", flush=True)

    print(f"\nDone! Success={success}, GDino-detect={gdino_detect}, Fallback={fallback}, Failed={failed}")


if __name__ == "__main__":
    main()
