import random
import numpy as np
import os
from dotenv import load_dotenv
import io
import logging
from PIL import Image, ImageEnhance, ImageFilter
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
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

        resize_factor = random.uniform(0.98, 1.02)
        modified = modified.resize(
            (int(width * resize_factor), int(height * resize_factor)),
            Image.LANCZOS
        )

        angle = random.uniform(-0.3, 0.3)
        modified = modified.rotate(angle, expand=False, resample=Image.BICUBIC)

        r, g, b = modified.split()
        r = r.point(lambda i: i * random.uniform(0.99, 1.01))
        g = g.point(lambda i: i * random.uniform(0.99, 1.01))
        b = b.point(lambda i: i * random.uniform(0.99, 1.01))
        modified = Image.merge("RGB", (r, g, b))

        dx = random.randint(-2, 2)
        dy = random.randint(-2, 2)
        modified = modified.transform(
            modified.size,
            Image.AFFINE,
            (1, 0, dx, 0, 1, dy),
            resample=Image.BICUBIC
        )

        enhancers = [
            ImageEnhance.Brightness(modified),
            ImageEnhance.Contrast(modified),
            ImageEnhance.Color(modified),
            ImageEnhance.Sharpness(modified),
        ]
        for enhancer, factor in zip(enhancers, [random.uniform(0.9, 1.1) for _ in enhancers]):
            modified = enhancer.enhance(factor)

        modified = modified.filter(random.choice([
            ImageFilter.SMOOTH,
            ImageFilter.SHARPEN,
            ImageFilter.DETAIL
        ]))

        array = np.array(modified).astype(np.int16)
        noise = np.random.normal(0, 0.2, array.shape).astype(np.int16)
        array = np.clip(array + noise, 0, 255).astype(np.uint8)
        modified = Image.fromarray(array)

        output = io.BytesIO()
        modified.save(output, format='JPEG', quality=95, subsampling=1, optimize=True)
        variations.append(output.getvalue())

    return variations

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [[InlineKeyboardButton(str(i), callback_data=f"count_{i}") for i in range(1, 6)]]
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("👋 How many spoofed variations would you like?", reply_markup=reply_markup)

async def handle_count_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        count = int(query.data.replace("count_", ""))
        context.user_data["variation_count"] = count
        await query.message.reply_text(f"✅ Got it! Send a photo and I’ll spoof {count} variations.")
    except Exception as e:
        await query.message.reply_text("❌ Something went wrong. Use /start again.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = context.user_data.get("variation_count")
        if not count:
            await update.message.reply_text("⚠️ Use /start and choose how many variations first.")
            return

        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()

        variations = generate_variations(image_bytes, variation_count=count)
        context.user_data["variations"] = variations

        for i, variation_bytes in enumerate(variations, 1):
            stream = io.BytesIO(variation_bytes)
            stream.seek(0)
            await update.message.reply_photo(photo=stream, caption=f"Variation {i}")

        buttons = [[InlineKeyboardButton(f"Choose Variation {i+1}", callback_data=f"choose_{i}")] for i in range(count)]
        reply_markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_text("👇 Select your favorite:", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"handle_photo error: {e}")
        await update.message.reply_text("⚠️ Error processing the image.")

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        index = int(query.data.replace("choose_", ""))
        variations = context.user_data.get("variations")

        if not variations or index >= len(variations):
            await query.message.reply_text("⚠️ Variation no longer available.")
            return

        stream = io.BytesIO(variations[index])
        stream.seek(0)
        await query.message.reply_photo(photo=stream, caption=f"✅ You selected Variation {index+1}")
        await query.message.edit_reply_markup(reply_markup=None)
        context.user_data.pop("variations", None)

    except Exception as e:
        await query.message.reply_text(f"⚠️ Error handling choice: {e}")

# --- Main App ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

application = ApplicationBuilder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(handle_count_selection, pattern=r"^count_"))
application.add_handler(CallbackQueryHandler(handle_choice, pattern=r"^choose_"))
application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

if __name__ == "__main__":
    logger.info("🤖 Bot is starting...")
    import asyncio

    async def run_bot():
        await application.bot.delete_my_commands()  # 🧹 Clear old commands
        await application.bot.set_my_commands([
            ("start", "Start and choose how many variations you want")
        ])
        await application.run_polling()

    asyncio.run(run_bot())
