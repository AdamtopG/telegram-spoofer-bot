#!/usr/bin/env python3
import os
import io
import zipfile
import random
import logging
import numpy as np
from dotenv import load_dotenv
from PIL import Image, ImageEnhance, ImageFilter

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Image variation generation ---
def generate_variations(input_bytes, variation_count=3, modification_level=0.2):
    original = Image.open(io.BytesIO(input_bytes)).convert('RGB')
    img = Image.new("RGB", original.size)
    img.paste(original)

    width, height = img.size
    variations = []

    for _ in range(variation_count):
        modified = img.copy()

        # small random resize
        factor = random.uniform(0.98, 1.02)
        modified = modified.resize((int(width*factor), int(height*factor)), Image.LANCZOS)

        # tiny rotation
        angle = random.uniform(-0.3, 0.3)
        modified = modified.rotate(angle, resample=Image.BICUBIC)

        # random color jitter
        r, g, b = modified.split()
        r = r.point(lambda i: i * random.uniform(0.99, 1.01))
        g = g.point(lambda i: i * random.uniform(0.99, 1.01))
        b = b.point(lambda i: i * random.uniform(0.99, 1.01))
        modified = Image.merge("RGB", (r, g, b))

        # tiny translation
        dx, dy = random.randint(-2,2), random.randint(-2,2)
        modified = modified.transform(
            modified.size,
            Image.AFFINE,
            (1, 0, dx, 0, 1, dy),
            resample=Image.BICUBIC
        )

        # random enhancement
        enhancers = [
            ImageEnhance.Brightness(modified),
            ImageEnhance.Contrast(modified),
            ImageEnhance.Color(modified),
            ImageEnhance.Sharpness(modified),
        ]
        for en in enhancers:
            modified = en.enhance(random.uniform(0.9,1.1))

        # random filter
        modified = modified.filter(random.choice([
            ImageFilter.SMOOTH, ImageFilter.DETAIL, ImageFilter.SHARPEN
        ]))

        # add Gaussian noise
        arr = np.array(modified).astype(np.int16)
        noise = np.random.normal(0, 0.2, arr.shape).astype(np.int16)
        arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
        modified = Image.fromarray(arr)

        # save to JPEG
        buf = io.BytesIO()
        modified.save(buf, format='JPEG', quality=95, optimize=True)
        variations.append(buf.getvalue())

    return variations

# --- /start conversation ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [[InlineKeyboardButton(str(i), callback_data=f"count_{i}") for i in range(1,6)]]
    await update.message.reply_text("👋 How many variations would you like?", 
                                    reply_markup=InlineKeyboardMarkup(buttons))

async def handle_count_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    try:
        count = int(update.callback_query.data.split("_",1)[1])
        context.user_data["variation_count"] = count
        await update.callback_query.message.reply_text(
            f"✅ Great! Now send me a photo, and I’ll generate {count} variations."
        )
    except:
        await update.callback_query.message.reply_text("❌ Invalid choice. Please /start again.")

# --- Photo handler (fixed) ---
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (count := context.user_data.get("variation_count")):
        return await update.message.reply_text(
            "⚠️ Please use /start first to pick a variation count."
        )

    # Await the coroutine to get the File object
    photo = update.message.photo[-1]
    tg_file = await photo.get_file()

    # Download as bytes directly
    raw = await tg_file.download_as_bytearray()

    variations = generate_variations(raw, variation_count=count)
    context.user_data["variations"] = variations

    # Send each variation back
    for idx, v in enumerate(variations, start=1):
        await update.message.reply_photo(photo=io.BytesIO(v), caption=f"Variation {idx}")

    # Provide buttons to choose one
    buttons = [
        [InlineKeyboardButton(f"Choose #{i}", callback_data=f"choose_{i-1}")]
        for i in range(1, count+1)
    ]
    await update.message.reply_text("👇 Select your favorite:", 
                                    reply_markup=InlineKeyboardMarkup(buttons))

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    idx = int(update.callback_query.data.split("_",1)[1])
    variations = context.user_data.get("variations")
    if not variations or idx < 0 or idx >= len(variations):
        return await update.callback_query.message.reply_text("⚠️ Variation expired. Try /start again.")

    await update.callback_query.message.reply_photo(
        photo=io.BytesIO(variations[idx]), caption=f"✅ You picked variation #{idx+1}"
    )
    context.user_data.pop("variations", None)
    await update.callback_query.message.edit_reply_markup(None)

# --- ZIP handler ---
async def zip_spoof_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.lower().endswith(".zip"):
        return await update.message.reply_text("❌ Please send me a .zip file.")

    in_buf = io.BytesIO()
    await doc.get_file().download(out=in_buf)
    in_buf.seek(0)

    out_buf = io.BytesIO()
    with zipfile.ZipFile(in_buf, 'r') as zin, \
         zipfile.ZipFile(out_buf, 'w', zipfile.ZIP_DEFLATED) as zout:
        for name in zin.namelist():
            if name.endswith("/"):
                continue
            data = zin.read(name)
            ext = name.lower().rsplit(".",1)[-1]
            if ext in ("jpg","jpeg","png","bmp","tiff","gif"):
                spoofed = generate_variations(data, variation_count=1)[0]
                base = name.rsplit(".",1)[0]
                zout.writestr(f"{base}.jpg", spoofed)
            else:
                zout.writestr(name, data)
    out_buf.seek(0)

    await update.message.reply_document(
        document=out_buf,
        filename=f"spoofed_{doc.file_name}"
    )

# --- Bot setup ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN not set in environment")

async def post_init(app):
    await app.bot.delete_my_commands()
    await app.bot.set_my_commands([
        BotCommand("start", "Choose number of variations")
    ])

application = (
    ApplicationBuilder()
    .token(BOT_TOKEN)
    .post_init(post_init)
    .build()
)

# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(handle_count_selection, pattern=r"^count_"))
application.add_handler(CallbackQueryHandler(handle_choice, pattern=r"^choose_"))
application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
application.add_handler(
    MessageHandler(filters.Document.FileExtension("zip"), zip_spoof_handler)
)

if __name__ == "__main__":
    logger.info("🤖 Bot is starting…")
    application.run_polling()
