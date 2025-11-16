# app.py
from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont
import base64
import io
import os

# --- OCR and Translation Imports ---
import pytesseract
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

from langdetect import detect


# --- Configuration ---
app = Flask(__name__)
app.config['DEBUG'] = True  # Set to False for production


# Cache for translation models so we only load once per language
model_cache = {}

def get_model(src_lang, tgt_lang='en'):
    """Loads and caches translation models dynamically."""
    model_key = f"{src_lang}-{tgt_lang}"

    if model_key in model_cache:
        return model_cache[model_key]

    model_name = f"Helsinki-NLP/opus-mt-{src_lang}-{tgt_lang}"
    print(f"Loading translation model: {model_name}")

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

    model_cache[model_key] = (tokenizer, model)
    return tokenizer, model

# --- Local Translation Model Setup ---
# A small, fast, and relatively good open-source model (Helsinki-NLP/opus-mt-en-es)
# You should choose a model pair (e.g., English-to-Spanish, German-to-English)
#MODEL_NAME = "Helsinki-NLP/opus-mt-en-es"
#tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
#model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)


# --- Ensure Tesseract path is set (Windows/macOS) ---
# Uncomment and set this if you have installation issues on Windows or macOS
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def translate_text(text):
    """Detects language and translates to English."""
    try:
        src_lang = detect(text)
    except:
        src_lang = "auto"

    # If already English, no need to translate
    if src_lang == "en":
        return text

    print(f"Detected '{text}' as language: {src_lang}")

    # Load model for detected language → English
    try:
        tokenizer, model = get_model(src_lang, "en")
    except Exception as e:
        print(f"Could not load model for lang '{src_lang}', using fallback:", e)
        return text  # fallback: no translation

    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True)
    outputs = model.generate(**inputs)
    translated = tokenizer.decode(outputs[0], skip_special_tokens=True)

    return translated



def process_image(base64_data):
    """
    Decodes the image, performs OCR, detects page language ONCE,
    translates all text to English, replaces text, and re-encodes.
    """
    try:
        # 1. Decode Base64
        if ',' in base64_data:
            header, encoded = base64_data.split(',', 1)
        else:
            encoded = base64_data

        image_bytes = base64.b64decode(encoded)
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')

        # 2. OCR
        ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

        # Collect all detected words
        words = []
        n_boxes = len(ocr_data['text'])

        for i in range(n_boxes):
            conf = int(ocr_data['conf'][i])
            text = ocr_data['text'][i].strip()

            if conf > 60 and text:
                words.append(text)

        # ---- LANGUAGE DETECTION ONCE ----
        if words:
            sample_text = " ".join(words[:10])  # first 10 words
            try:
                detected_lang = detect(sample_text)
            except:
                detected_lang = "en"

            if detected_lang == "en":
                # No translation needed
                page_model = None
            else:
                print(f"Detected page language as: {detected_lang}")
                try:
                    page_model = get_model(detected_lang, "en")
                except Exception as e:
                    print("Model load failed, skipping translation:", e)
                    page_model = None
        else:
            page_model = None

        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except IOError:
            font = ImageFont.load_default()

        # 3. Draw translations
        for i in range(n_boxes):
            conf = int(ocr_data['conf'][i])
            text = ocr_data['text'][i].strip()
            if conf <= 60 or not text:
                continue

            (x, y, w, h) = (ocr_data['left'][i], ocr_data['top'][i],
                            ocr_data['width'][i], ocr_data['height'][i])

            # Translate using the same model
            if page_model:
                tokenizer, model = page_model
                inputs = tokenizer(text, return_tensors="pt", truncation=True)
                outputs = model.generate(**inputs)
                translated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
            else:
                translated_text = text  # English or fallback

            # Replace original text
            draw.rectangle([(x, y), (x + w, y + h)], fill="white")
            draw.text((x, y), translated_text, fill="black", font=font)

        # 4. Encode image back to Base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        new_base64 = base64.b64encode(buffer.getvalue()).decode()

        return f"data:image/png;base64,{new_base64}"

    except Exception as e:
        print("Error processing image:", e)
        return None



@app.route('/process_images', methods=['POST'])
def handle_images():
    """Endpoint to receive images from the Chrome extension."""
    data = request.get_json()
    if not data or 'images' not in data:
        return jsonify({"error": "Invalid request format"}), 400

    images_to_process = data.get('images', [])
    print(f"Received {len(images_to_process)} images from extension.")

    results = []

    for item in images_to_process:
        original_id = item.get('id')
        base64_data = item.get('data')

        if not original_id or not base64_data:
            continue

        # Process the image and get the new Base64 string
        translated_data = process_image(base64_data)

        # Only add to results if translation was successful
        if translated_data:
            results.append({
                'id': original_id,
                'translatedData': translated_data
            })

    print(f"Successfully processed {len(results)} images. Sending back.")
    return jsonify(results)


if __name__ == '__main__':
    # Flask will start listening on port 5000
    print("Starting Flask server on http://localhost:5000...")
    app.run(port=5000)