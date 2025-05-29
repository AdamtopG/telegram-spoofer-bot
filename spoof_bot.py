#!/usr/bin/env python3
import os, io, zipfile, random, logging
import numpy as np
from dotenv import load_dotenv
from PIL import Image, ImageEnhance, ImageFilter
from moviepy.editor import VideoFileClip
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Image spoofing
def generate_variations(input_bytes, variation_count=3):
    original = Image.open(io.BytesIO(input_bytes)).convert('RGB')
    img = Image.new("RGB", original.size)
    img.paste(original)
    width, height = img.size
    variations = []

    for _ in range(variation_count):
        mod = img.copy().resize(
            (int(width * random.uniform(0.98, 1.02)), int(height * random.uniform(0.98, 1.02))),
            Image.LANCZOS
        ).rotate(random.uniform(-0.3, 0.3), resample=Image.BICUBIC)

        r, g, b = mod.split()
        r = r.point(lambda i: i * random.uniform(0.99, 1.01))
        g = g.point(lambda i: i * random.uniform(0.99, 1.01))
        b = b.point(lambda i: i * random.uniform(0.99, 1.01))
        mod = Image.merge("RGB", (r, g, b)).filter(
            random.choice([ImageFilter.SMOOTH, ImageFilter.DETAIL, ImageFilter.SHARPEN])
        )

        arr = np.array(mod).astype(np.int16)
        noise = np.random.normal(0, 0.2, arr.shape).astype(np.int16)
        arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
        mod = Image.fromarray(arr)

        buf = io.BytesIO()
        mod.save(buf, format='JPEG', quality=95)
        variations.append(buf.getvalue())
    return variations

# Video spoofing (basic compression)
def spoof_video(input_bytes):
    input_stream = io.BytesIO(input_bytes)
    output_stream = io.BytesIO()

    with open("temp_input.mp4", "wb") as f:
        f.write(input_stream.read())

    clip = VideoFileClip("temp_input.mp4").subclip(0, 10)
    clip = clip.resize(0.98).fx(lambda c: c.set_fps(24))
    clip.write_videofile("temp_output.mp4", codec="libx264", audio_codec="aac", bitrate="400k", logger=None)

    with open("temp_output.mp4", "rb") as f:
        output_stream.write(f.read())
    output_stream.seek(0)
    return output_stream

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [[InlineKeyboardButton(str(i), callback_data=f"count_{i}") for i in range(1,6)]]
    await update.message.reply_text("👋 How many variations would you like?", reply_markup=InlineKeyboardMarkup(buttons))

async def handle_count_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    count = int(update.callback_query.data.split("_",1)[1])
    context.user_data["variation_count"] = count
    await update.callback_query.message.reply_text(f"✅ Great! Now send me a photo or video!")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = context.user_data.get("variation_count", 3)
    file = await update.message.photo[-1].get_file()
    raw = await file.download_as_bytearray()
    variations = generate_variations(raw, variation_count=count)

    for idx, v in enumerate(variations, 1):
        await update.message.reply_photo(photo=io.BytesIO(v), caption=f"Variation {idx}")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.video.get_file()
    raw = await file.download_as_bytearray()
    spoofed = spoof_video(raw)
    await update.message.reply_video(video=spoofed, caption="📽️ Spoofed video")

# Bot setup
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

application = (
    ApplicationBuilder()
    .token(BOT_TOKEN)
    .build()
)

application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(handle_count_selection, pattern=r"^count_"))
application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
application.add_handler(MessageHandler(filters.VIDEO, handle_video))

if __name__ == "__main__":
    logger.info("🤖 Bot running…")
    application.run_polling()
