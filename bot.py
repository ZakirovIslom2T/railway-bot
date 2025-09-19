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

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Railway variable
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "/usr/bin/tesseract")
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


# --- Extraction Helpers ---
def find_plate(text):
    up = re.sub(r'[\s\-]', '', text.upper())
    # Uzbek plates usually look like: 25A953AA
    m = re.search(r'\b\d{2}[A-Z]{1,3}\d{2,5}[A-Z]{1,3}\b', up)
    return m.group(0) if m else ""


def find_brand(text):
    up = text.upper()
    brands = ["DAEWOO","TOYOTA","NEXIA","LEXUS","HYUNDAI","KIA","BMW",
              "MERCEDES","VOLKSWAGEN","CHEVROLET","LADA","VAZ"]
    for b in brands:
        if b in up:
            return b
    # fallback: long alphanumeric tokens (like VAZ2106GBASPG)
    m = re.search(r'\b[A-Z]{2,6}\d{0,6}[A-Z]{0,6}\b', up)
    return m.group(0) if m else ""


def find_guvohnoma(text):
    up = text.upper()
    # typical: AAF3799360
    m = re.search(r'\b[A-Z]{2,4}\d{4,12}\b', up)
    return m.group(0) if m else ""


def find_phone(text):
    # Uzbek phones: always 9 digits starting with 9
    m = re.search(r'\b(9\d{8})\b', text)
    return m.group(1) if m else ""


def find_date(text):
    # typical dd.mm.yyyy
    m = re.search(r'\b([0-3]?\d[.\-/][01]?\d[.\-/](?:19|20)\d{2})\b', text)
    return m.group(1) if m else ""


def extract_all(text):
    return {
        "Number": find_plate(text),
        "Rusumi": find_brand(text),
        "Guvohnoma": find_guvohnoma(text),
        "Telefon": find_phone(text),
        "Tugallangan_sana": find_date(text)
    }


# --- Telegram Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salom! Menga guvohnoma rasmi yuboring. Men: Number, Rusumi, Guvohnoma, Telefon va Sana ni chiqarib beraman.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        photo_file = await update.message.photo[-1].get_file()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
            path = tf.name
        await photo_file.download_to_drive(path)

        # Preprocess image: grayscale + binarize
        img = Image.open(path).convert("L")
        img = img.point(lambda x: 0 if x < 150 else 255, '1')

        # OCR with English only
        text = pytesseract.image_to_string(img, lang="eng")
        logger.info("OCR text: %s", text[:200])

        data = extract_all(text)
        result_line = f'{data["Number"]}  {data["Rusumi"]}  {data["Guvohnoma"]}  {data["Telefon"]}  {data["Tugallangan_sana"]}'
        
        if not any(data.values()):
            await update.message.reply_text("Hech narsa topilmadi. OCR natija:\n\n" + (text[:1500] or ""))
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
