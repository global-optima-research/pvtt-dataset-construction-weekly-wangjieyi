"""Step 2: Product RGBA + Mask extraction using GroundingDINO + SAM2.
Run on GPU server: /data/wangjieyi/

If GroundingDINO+SAM2 not available, fallback to rembg or manual.
"""
import json
import os
import sys
import numpy as np
from pathlib import Path
from PIL import Image

DATASET_DIR = Path("/data/wangjieyi/ffgo-dataset")  # Server path
# For local testing: DATASET_DIR = Path("D:/00_aPhD/IP/ffgo-training-dataset")

# Detection prompt mapping
CATEGORY_PROMPTS = {
    "bracelet": "bracelet jewelry",
    "earring": "earring jewelry",
    "handbag": "handbag bag",
    "necklace": "necklace jewelry",
    "ring": "ring jewelry",
    "sunglasses": "sunglasses eyewear",
    "watch": "wristwatch watch",
    "cosmetics": "cosmetics makeup product",
}


def load_models(device="cuda:0"):
    """Load GroundingDINO and SAM2 models."""
    print("Loading GroundingDINO...")
    try:
        from groundingdino.util.inference import load_model as load_gdino, predict
        import groundingdino
        gdino_cfg = os.path.join(os.path.dirname(groundingdino.__file__),
                                  "config", "GroundingDINO_SwinT_OGC.py")
        # Download weights if needed
        weights_path = "/data/wangjieyi/models/groundingdino_swint_ogc.pth"
        if not os.path.exists(weights_path):
            os.makedirs(os.path.dirname(weights_path), exist_ok=True)
            import urllib.request
            url = "https://github.com/IDEA-Research/GroundingDINO/releases/download/v0.1.0-alpha/groundingdino_swint_ogc.pth"
            print(f"  Downloading GroundingDINO weights...")
            urllib.request.urlretrieve(url, weights_path)
        gdino_model = load_gdino(gdino_cfg, weights_path, device=device)
    except Exception as e:
        print(f"  GroundingDINO failed: {e}")
        gdino_model = None

    print("Loading SAM2...")
    try:
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor
        sam2_ckpt = "/data/wangjieyi/models/sam2.1_hiera_large.pt"
        sam2_cfg = "configs/sam2.1/sam2.1_hiera_l.yaml"
        if not os.path.exists(sam2_ckpt):
            os.makedirs(os.path.dirname(sam2_ckpt), exist_ok=True)
            import urllib.request
            url = "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt"
            print(f"  Downloading SAM2 weights...")
            urllib.request.urlretrieve(url, sam2_ckpt)
        sam2 = build_sam2(sam2_cfg, sam2_ckpt, device=device)
        sam2_predictor = SAM2ImagePredictor(sam2)
    except Exception as e:
        print(f"  SAM2 failed: {e}")
        sam2_predictor = None

    return gdino_model, sam2_predictor


def extract_product_rembg(image_path, output_rgba, output_mask):
    """Fallback: use rembg for background removal (less precise but works)."""
    try:
        from rembg import remove
        img = Image.open(image_path).convert("RGB")
        result = remove(img)  # Returns RGBA

        # Save RGBA
        result.save(output_rgba)

        # Extract and save mask
        alpha = result.split()[-1]
        mask = alpha.point(lambda x: 255 if x > 128 else 0)
        mask.save(output_mask)
        return True
    except Exception as e:
        print(f"    rembg error: {e}")
        return False


def extract_product_gdino_sam2(image_path, text_prompt, gdino_model, sam2_predictor,
                                output_rgba, output_mask, box_threshold=0.3):
    """Use GroundingDINO + SAM2 for text-guided product extraction."""
    try:
        from groundingdino.util.inference import predict
        import torch
        from torchvision import transforms

        img = Image.open(image_path).convert("RGB")
        img_np = np.array(img)

        # GroundingDINO detection
        transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        img_tensor = transform(img)

        boxes, logits, phrases = predict(
            model=gdino_model,
            image=img_tensor,
            caption=text_prompt,
            box_threshold=box_threshold,
            text_threshold=0.25,
        )

        if len(boxes) == 0:
            print(f"    No detection at threshold {box_threshold}")
            return False

        # Take highest confidence box
        best_idx = logits.argmax()
        box = boxes[best_idx].numpy()
        conf = logits[best_idx].item()

        # Convert normalized box to pixel coords
        h, w = img_np.shape[:2]
        x1 = int(box[0] * w)
        y1 = int(box[1] * h)
        x2 = int(box[2] * w)
        y2 = int(box[3] * h)

        # SAM2 segmentation
        sam2_predictor.set_image(img_np)
        input_box = np.array([[x1, y1, x2, y2]])
        masks, scores, _ = sam2_predictor.predict(
            box=input_box,
            multimask_output=False,
        )
        mask = masks[0]  # Binary mask

        # Save mask
        mask_img = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
        mask_img.save(output_mask)

        # Apply mask to create RGBA
        rgba = np.zeros((*img_np.shape[:2], 4), dtype=np.uint8)
        rgba[:, :, :3] = img_np
        rgba[:, :, 3] = (mask * 255).astype(np.uint8)
        Image.fromarray(rgba, mode="RGBA").save(output_rgba)

        return True, conf

    except Exception as e:
        print(f"    GDINO+SAM2 error: {e}")
        return False


def main():
    samples = sorted(d for d in os.listdir(DATASET_DIR) if d.startswith("sample_"))

    # Check which need extraction
    todo = []
    for sample in samples:
        rgba_path = DATASET_DIR / sample / "product_rgba.png"
        mask_path = DATASET_DIR / sample / "product_mask.png"
        if not rgba_path.exists() or not mask_path.exists():
            todo.append(sample)

    print(f"Product extraction: {len(todo)} todo / {len(samples)} total")
    if not todo:
        print("All products already extracted!")
        return

    # Try loading GPU models
    gdino_model, sam2_predictor = None, None
    try:
        gdino_model, sam2_predictor = load_models()
    except Exception as e:
        print(f"GPU models unavailable: {e}")

    use_gdino = gdino_model is not None and sam2_predictor is not None
    method = "grounding-dino+sam2" if use_gdino else "rembg"
    print(f"Using method: {method}")

    success = 0
    failed = 0

    for i, sample in enumerate(todo):
        sample_dir = DATASET_DIR / sample
        raw_path = sample_dir / "first_frame_raw.png"
        meta_path = sample_dir / "metadata.json"
        rgba_path = sample_dir / "product_rgba.png"
        mask_path = sample_dir / "product_mask.png"

        if not raw_path.exists():
            failed += 1
            continue

        meta = json.load(open(meta_path, encoding="utf-8"))
        category = meta.get("product_category", "product")
        prompt = CATEGORY_PROMPTS.get(category, category)

        if use_gdino:
            result = extract_product_gdino_sam2(
                str(raw_path), prompt, gdino_model, sam2_predictor,
                str(rgba_path), str(mask_path)
            )
        else:
            result = extract_product_rembg(str(raw_path), str(rgba_path), str(mask_path))

        if result:
            # Get dimensions
            rgba_img = Image.open(rgba_path)
            meta["product_rgba"] = {
                "file": "product_rgba.png",
                "resolution": list(rgba_img.size),
                "extraction_method": method,
                "detection_prompt": prompt,
                "status": "DONE",
            }
            meta["product_mask"] = {
                "file": "product_mask.png",
                "mask_type": f"precise ({method})",
                "format": "grayscale, 255=product, 0=background",
                "status": "DONE",
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            success += 1
            if (i + 1) % 20 == 0:
                print(f"  [{i+1}/{len(todo)}] done ({success} ok, {failed} fail)")
        else:
            failed += 1

    print(f"\nDone! Success: {success}, Failed: {failed}")


if __name__ == "__main__":
    main()
