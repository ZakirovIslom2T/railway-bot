# bot.py
import os
import re
import tempfile
import logging
from PIL import Image
import pytesseract
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")  # set on Railway
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "/usr/bin/tesseract")
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# --- extraction helpers ---
def find_plate(text):
    up = re.sub(r'[\s\-]', '', text.upper())
    m = re.search(r'\b[0-9]{2}[A-Z0-9]{3,8}[A-Z]{0,3}\b', up)
    return m.group(0) if m else ""

def find_brand(text):
    up = text.upper()
    brands = ["DAEWOO","TOYOTA","NEXIA","LEXUS","HYUNDAI","KIA","BMW","MERCEDES","VOLKSWAGEN","CHEVROLET","LADA","VAZ"]
    for b in brands:
        if b in up:
            return b
    m = re.search(r'(RUSUMI|MARKA|MODEL)[:\s\-]*([A-Z0-9]{3,20})', up)
    if m:
        return m.group(2)
    tokens = re.findall(r'\b[A-Z]{3,20}\b', up)
    return tokens[0] if tokens else ""

def find_guvohnoma(text):
    up = text.upper()
    m = re.search(r'\b[A-Z]{2,4}\d{4,12}\b', up)
    if m:
        candidate = m.group(0)
        # ignore pure year-like or phone-like tokens
        if re.fullmatch(r'\d{4}', candidate):
            return ""
        return candidate
    return ""

def find_phone(text):
    # look for 9-12 digit phone numbers (common local patterns)
    s = re.sub(r'[^\d+]', '', text)
    m = re.search(r'(\+?\d{9,12})', s)
    if m:
        return m.group(1).lstrip('+')
    # fallback: 9-digit tokens in raw text
    m2 = re.search(r'\b(\d{9})\b', text)
    return m2.group(1) if m2 else ""

def find_date(text):
    m = re.search(r'\b([0-3]?\d[.\-/][01]?\d[.\-/](?:19|20)\d{2})\b', text)
    if m:
        return m.group(1)
    return ""

def extract_all(text):
    return {
        "Number": find_plate(text),
        "Rusumi": find_brand(text),
        "Guvohnoma": find_guvohnoma(text),
        "Telefon": find_phone(text),
        "Tugallangan_sana": find_date(text)
    }

# --- Telegram handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salom! Rasmini yuboring — men kerakli ma'lumotlarni qaytaraman (Number Rusumi Guvohnoma Telefon Sana).")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        photo_file = await update.message.photo[-1].get_file()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
            path = tf.name
        await photo_file.download_to_drive(path)

        # OCR (uzb + eng)
        text = pytesseract.image_to_string(Image.open(path), lang="uzb+eng")
        logger.info("OCR text length: %d", len(text))

        data = extract_all(text)
        result_line = f'{data["Number"]}  {data["Rusumi"]}  {data["Guvohnoma"]}  {data["Telefon"]}  {data["Tugallangan_sana"]}'
        # If result looks empty, send raw OCR to help debug
        if not any(data.values()):
            await update.message.reply_text("Ma'lumot topilmadi. OCR natijasi:\n\n" + (text[:1500] or ""))
        else:
            await update.message.reply_text(result_line.strip())
    except Exception as e:
        logger.exception("Error in handle_photo")
        await update.message.reply_text("Xatolik yuz berdi: " + str(e))
    finally:
        try:
            if 'path' in locals() and os.path.exists(path):
                os.remove(path)
        except:
            pass

def run():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN not set")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    logger.info("Starting bot (polling)...")
    app.run_polling()

if __name__ == "__main__":
    run()
