import random
import numpy as np
import io
import asyncio
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

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --------- Variation Generation ---------

def generate_variations(input_bytes, variation_count=3, modification_level=0.2):
    original = Image.open(io.BytesIO(input_bytes)).convert('RGB')
    img = Image.new("RGB", original.size)
    img.paste(original)

    width, height = img.size
    variations = []

    for _ in range(variation_count):
        modified = img.copy()

        # Resize
        resize_factor = random.uniform(0.98, 1.02)
        modified = modified.resize(
            (int(width * resize_factor), int(height * resize_factor)), Image.LANCZOS
        )

        # Rotate
        angle = random.uniform(-0.3, 0.3)
        modified = modified.rotate(angle, expand=False, resample=Image.BICUBIC)

        # Slight color shift
        r, g, b = modified.split()
        r = r.point(lambda i: i * random.uniform(0.99, 1.01))
        g = g.point(lambda i: i * random.uniform(0.99, 1.01))
        b = b.point(lambda i: i * random.uniform(0.99, 1.01))
        modified = Image.merge("RGB", (r, g, b))

        # Pixel shifting
        dx = random.randint(-2, 2)
        dy = random.randint(-2, 2)
        modified = modified.transform(
            modified.size,
            Image.AFFINE,
            (1, 0, dx, 0, 1, dy),
            resample=Image.BICUBIC
        )

        # Enhancements
        enhancers = [
            ImageEnhance.Brightness(modified),
            ImageEnhance.Contrast(modified),
            ImageEnhance.Color(modified),
            ImageEnhance.Sharpness(modified),
        ]
        for enhancer, factor in zip(enhancers, [random.uniform(0.9, 1.1) for _ in enhancers]):
            modified = enhancer.enhance(factor)

        # Optional filter
        modified = modified.filter(random.choice([
            ImageFilter.SMOOTH,
            ImageFilter.SHARPEN,
            ImageFilter.DETAIL
        ]))

        # Gentle noise
        array = np.array(modified).astype(np.int16)
        noise = np.random.normal(0, 0.2, array.shape).astype(np.int16)
        array = np.clip(array + noise, 0, 255).astype(np.uint8)
        modified = Image.fromarray(array)

        # Save with consistent quality
        output = io.BytesIO()
        modified.save(output, format='JPEG', quality=95, subsampling=1, optimize=True)
        variations.append(output.getvalue())

    return variations

# --------- Handlers ---------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Start command received")
    buttons = [[InlineKeyboardButton(str(i), callback_data=f"count_{i}") for i in range(1, 6)]]
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("👋 How many spoofed variations would you like?", reply_markup=reply_markup)

async def handle_count_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        count = int(query.data.replace("count_", ""))
        context.user_data["variation_count"] = count
        logger.info(f"User selected {count} variations")
        await query.message.reply_text(f"✅ Great! Now send me a photo to spoof ({count} variation(s)).")
    except Exception as e:
        logger.error(f"Error in handle_count_selection: {e}")
        await query.message.reply_text("❌ Invalid input. Please restart with /start.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = context.user_data.get("variation_count")
        if not count:
            await update.message.reply_text("⚠️ Please start with /start and select how many variations you want.")
            return

        logger.info(f"Generating {count} variations for user")
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
        await update.message.reply_text("👇 Choose your favorite:", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error in handle_photo: {e}", exc_info=True)
        await update.message.reply_text(f"⚠️ Error processing image: {e}")

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        index = int(query.data.replace("choose_", ""))
        variations = context.user_data.get("variations")
        logger.info(f"User selected variation {index+1}")

        if not variations or index >= len(variations):
            await query.message.reply_text("⚠️ This option has expired or was already used.")
            return

        variation_bytes = variations[index]
        stream = io.BytesIO(variation_bytes)
        stream.seek(0)

        await query.message.reply_photo(photo=stream, caption=f"✅ You selected Variation {index+1}")
        await query.message.edit_reply_markup(reply_markup=None)  # Disable buttons
        context.user_data.pop("variations", None)

    except Exception as e:
        logger.error(f"Error in handle_choice: {e}", exc_info=True)
        await query.message.reply_text(f"⚠️ Could not process selection: {e}")

# --------- Main ---------

BOT_TOKEN = "8089313407:AAHF1dRzX4ahU485tag1vujOp9opo0NvG6M"  # ⬅️ replace with your actual bot token

async def main():
    logger.info("Starting bot")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Set commands
    await app.bot.set_my_commands([
        ("start", "Start and choose how many variations you want")
    ])

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_count_selection, pattern=r"^count_"))
    app.add_handler(CallbackQueryHandler(handle_choice, pattern=r"^choose_"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    logger.info("🤖 Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    try:
        # This is the key change for Render
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)