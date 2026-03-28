"""Step 3: Generate captions using Gemini 2.5 Pro API.
Free tier: 5 requests/min for gemini-2.5-pro.
Expected time: ~40 minutes for 200 samples.
"""
import json
import os
import time
import sys
from pathlib import Path

DATASET_DIR = Path(__file__).parent.parent
GEMINI_API_KEY = "AIzaSyBqeyc9S84WlBzzbPxg1QS3iaay3u8CBxA"
TRIGGER_PREFIX = "ad23r2 the camera view suddenly changes "
MODEL = "gemini-2.5-flash"  # Use flash for speed + quota; switch to pro if needed
RPM_LIMIT = 10  # requests per minute (flash has higher limit)
DELAY = 60.0 / RPM_LIMIT + 1  # seconds between requests

CAPTION_PROMPT = """You are given an e-commerce product demonstration image (first frame of a video).
Generate a descriptive caption for the video that this frame belongs to.

Requirements:
1. The caption MUST describe:
   - The product's visual appearance (color, material, shape, details)
   - How the product is being showcased (being held, worn, displayed on a surface, rotated, etc.)
   - The setting/background
   - Likely camera movement (zoom in, pan, static, etc.)
2. DO NOT include:
   - Marketing language ("perfect gift", "must-have")
   - Prices or specifications
   - Vague narrative filler
3. Keep it to 1-3 sentences, factual and visual.
4. Product category: {category}
5. Product name: {product_name}
"""


def main():
    # Use new google.genai package
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
    except ImportError:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        client = None

    samples = sorted(d for d in os.listdir(DATASET_DIR) if d.startswith("sample_"))

    # Check which samples need caption
    todo = []
    for sample in samples:
        caption_path = DATASET_DIR / sample / "caption.txt"
        if not caption_path.exists() or caption_path.stat().st_size < 10:
            todo.append(sample)

    print(f"Caption generation: {len(todo)} todo / {len(samples)} total")
    if not todo:
        print("All captions already generated!")
        return

    success = 0
    failed = 0

    for i, sample in enumerate(todo):
        sample_dir = DATASET_DIR / sample
        raw_path = sample_dir / "first_frame_raw.png"
        meta_path = sample_dir / "metadata.json"
        caption_path = sample_dir / "caption.txt"

        if not raw_path.exists():
            print(f"  [{i+1}/{len(todo)}] {sample}: SKIP (no first_frame_raw.png)")
            failed += 1
            continue

        meta = json.load(open(meta_path, encoding="utf-8"))
        category = meta.get("product_category", "product")
        product_name = meta.get("product_name", "")

        prompt = CAPTION_PROMPT.format(category=category, product_name=product_name)

        try:
            if client:
                # New google.genai API
                from google.genai import types
                img_data = open(raw_path, "rb").read()
                response = client.models.generate_content(
                    model=MODEL,
                    contents=[
                        types.Part.from_bytes(data=img_data, mime_type="image/png"),
                        prompt,
                    ],
                )
                caption_text = response.text.strip()
            else:
                # Old google.generativeai API
                import google.generativeai as genai
                from PIL import Image
                model = genai.GenerativeModel(MODEL)
                img = Image.open(raw_path)
                response = model.generate_content([prompt, img])
                caption_text = response.text.strip()

            # Remove any <caption> tags if present
            caption_text = caption_text.replace("<caption>", "").replace("</caption>", "").strip()

            # Add trigger prefix
            full_caption = TRIGGER_PREFIX + caption_text

            with open(caption_path, "w", encoding="utf-8") as f:
                f.write(full_caption)

            # Update metadata
            meta["caption"] = {
                "file": "caption.txt",
                "full_text": full_caption,
                "trigger_prefix": TRIGGER_PREFIX.strip(),
                "description_only": caption_text,
                "generation_method": MODEL,
                "status": "DONE",
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            success += 1
            print(f"  [{i+1}/{len(todo)}] {sample}: OK ({len(caption_text)} chars)")

        except Exception as e:
            failed += 1
            print(f"  [{i+1}/{len(todo)}] {sample}: ERROR - {e}")

        # Rate limiting
        time.sleep(DELAY)

    print(f"\nDone! Success: {success}, Failed: {failed}")


if __name__ == "__main__":
    main()
