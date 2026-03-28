"""Step 5: Compose first_frame.png (product RGBA + background on white canvas)."""
import json
import os
from pathlib import Path
from PIL import Image

DATASET_DIR = Path(__file__).parent.parent
CANVAS_W, CANVAS_H = 832, 480
PRODUCT_ZONE_RATIO = 0.33  # Left 1/3 for product


def compose(product_rgba_path, background_path, output_path):
    """Compose first_frame on white canvas: left=product, right=background."""
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), (255, 255, 255))

    prod_zone_w = int(CANVAS_W * PRODUCT_ZONE_RATIO)  # ~275px
    bg_zone_w = CANVAS_W - prod_zone_w  # ~557px
    margin = 5

    # Left: product RGBA (crop to non-transparent bbox, scale to fit)
    product = Image.open(product_rgba_path).convert("RGBA")
    bbox = product.getbbox()
    if bbox:
        product = product.crop(bbox)

    # Scale product to fit in left zone
    pw, ph = product.size
    scale = min((prod_zone_w - 2 * margin) / pw, (CANVAS_H - 2 * margin) / ph)
    new_pw = int(pw * scale)
    new_ph = int(ph * scale)
    product = product.resize((new_pw, new_ph), Image.LANCZOS)

    # Center in left zone
    px = (prod_zone_w - new_pw) // 2
    py = (CANVAS_H - new_ph) // 2
    canvas.paste(product, (px, py), product)  # Use alpha as mask

    # Right: background (scale to fit)
    background = Image.open(background_path).convert("RGB")
    bw, bh = background.size
    scale = min((bg_zone_w - 2 * margin) / bw, (CANVAS_H - 2 * margin) / bh)
    new_bw = int(bw * scale)
    new_bh = int(bh * scale)
    background = background.resize((new_bw, new_bh), Image.LANCZOS)

    # Center in right zone
    bx = prod_zone_w + (bg_zone_w - new_bw) // 2
    by = (CANVAS_H - new_bh) // 2
    canvas.paste(background, (bx, by))

    canvas.save(output_path)
    return True


def main():
    samples = sorted(d for d in os.listdir(DATASET_DIR) if d.startswith("sample_"))

    todo = []
    for sample in samples:
        ff_path = DATASET_DIR / sample / "first_frame.png"
        rgba_path = DATASET_DIR / sample / "product_rgba.png"
        bg_path = DATASET_DIR / sample / "background.png"
        if not ff_path.exists() and rgba_path.exists() and bg_path.exists():
            todo.append(sample)

    print(f"First frame composition: {len(todo)} ready to compose")

    # Also count blocked samples
    need_rgba = sum(1 for s in samples
                    if not (DATASET_DIR / s / "product_rgba.png").exists())
    need_bg = sum(1 for s in samples
                  if not (DATASET_DIR / s / "background.png").exists())
    already = sum(1 for s in samples
                  if (DATASET_DIR / s / "first_frame.png").exists())
    print(f"  Already done: {already}, Need product_rgba: {need_rgba}, Need background: {need_bg}")

    if not todo:
        if need_rgba or need_bg:
            print("Cannot compose: missing product_rgba or background. Run step2/step4 first.")
        else:
            print("All first frames already composed!")
        return

    success = 0
    for i, sample in enumerate(todo):
        sample_dir = DATASET_DIR / sample
        try:
            compose(
                sample_dir / "product_rgba.png",
                sample_dir / "background.png",
                sample_dir / "first_frame.png",
            )
            # Update metadata
            meta_path = sample_dir / "metadata.json"
            meta = json.load(open(meta_path, encoding="utf-8"))
            meta["first_frame"] = {
                "file": "first_frame.png",
                "canvas_size": [CANVAS_W, CANVAS_H],
                "canvas_color": [255, 255, 255],
                "product_zone_ratio": PRODUCT_ZONE_RATIO,
                "layout": "left=product_rgba, right=background",
                "status": "DONE",
            }
            # Update file lists
            ready = set(meta.get("files_ready", []))
            ready.add("first_frame.png")
            todo_files = set(meta.get("files_todo", []))
            todo_files.discard("first_frame.png")
            meta["files_ready"] = sorted(ready)
            meta["files_todo"] = sorted(todo_files)

            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            success += 1
        except Exception as e:
            print(f"  {sample}: ERROR - {e}")

        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(todo)} done")

    print(f"\nDone! Composed {success}/{len(todo)} first frames.")


if __name__ == "__main__":
    main()
