"""Step 4: Background extraction using Gemini 2.5 Pro (object removal).
This is the BOTTLENECK step - Gemini does image editing to remove the product.
Free tier: 5 requests/min for pro, 10/min for flash.
Expected time: ~40-80 minutes for 200 samples.
"""
import json
import os
import time
import base64
from pathlib import Path
from PIL import Image
import io

DATASET_DIR = Path(__file__).parent.parent
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = "gemini-2.5-flash"  # For image generation/editing
RPM_LIMIT = 10
DELAY = 60.0 / RPM_LIMIT + 1

REMOVAL_PROMPT = """Given the input image of an e-commerce product scene, remove the product "{product_name}" ({category}) entirely.
Return ONLY the edited image — it must:
1. Preserve the exact same resolution (no scaling or cropping)
2. Contain neither the product nor any artifacts of its removal
3. The background should look natural and complete where the product was
4. Fill the removed area with a natural continuation of the surrounding background"""


def main():
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
    except ImportError:
        print("ERROR: Please install google-genai: pip install google-genai")
        return

    samples = sorted(d for d in os.listdir(DATASET_DIR) if d.startswith("sample_"))

    # Check which need background
    todo = []
    for sample in samples:
        bg_path = DATASET_DIR / sample / "background.png"
        if not bg_path.exists() or bg_path.stat().st_size < 1000:
            todo.append(sample)

    print(f"Background extraction: {len(todo)} todo / {len(samples)} total")
    if not todo:
        print("All backgrounds already generated!")
        return

    success = 0
    failed = 0

    for i, sample in enumerate(todo):
        sample_dir = DATASET_DIR / sample
        raw_path = sample_dir / "first_frame_raw.png"
        meta_path = sample_dir / "metadata.json"
        bg_path = sample_dir / "background.png"

        if not raw_path.exists():
            failed += 1
            continue

        meta = json.load(open(meta_path, encoding="utf-8"))
        category = meta.get("product_category", "product")
        product_name = meta.get("product_name", "product")

        prompt = REMOVAL_PROMPT.format(product_name=product_name, category=category)

        try:
            img_data = open(raw_path, "rb").read()

            response = client.models.generate_content(
                model=MODEL,
                contents=[
                    types.Part.from_bytes(data=img_data, mime_type="image/png"),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )

            # Extract generated image from response
            saved = False
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        img_bytes = part.inline_data.data
                        img = Image.open(io.BytesIO(img_bytes))
                        # Ensure same size as first_frame_raw
                        orig = Image.open(raw_path)
                        if img.size != orig.size:
                            img = img.resize(orig.size, Image.LANCZOS)
                        img.save(bg_path)
                        saved = True
                        break

            if saved:
                meta["background"] = {
                    "file": "background.png",
                    "extraction_method": f"gemini-{MODEL}-object-removal",
                    "status": "DONE",
                }
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta, f, ensure_ascii=False, indent=2)
                success += 1
                print(f"  [{i+1}/{len(todo)}] {sample}: OK")
            else:
                # Gemini didn't return an image - save text response for debugging
                text_resp = response.text if hasattr(response, 'text') else str(response)
                debug_path = sample_dir / "_bg_debug.txt"
                with open(debug_path, "w") as f:
                    f.write(text_resp[:500])
                failed += 1
                print(f"  [{i+1}/{len(todo)}] {sample}: NO IMAGE returned")

        except Exception as e:
            failed += 1
            err_msg = str(e)[:80]
            print(f"  [{i+1}/{len(todo)}] {sample}: ERROR - {err_msg}")

        time.sleep(DELAY)

    print(f"\nDone! Success: {success}, Failed: {failed}")


if __name__ == "__main__":
    main()
