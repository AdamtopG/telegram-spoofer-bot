import logging
import random
import io
import numpy as np
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
import asyncio

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8089313407:AAHF1dRzX4ahU485tag1vujOp9opo0NvG6M"  # Replace with your actual token

# Generate image variations
def generate_variations(input_bytes, variation_count=5, modification_level=0.2):
    original = Image.open(io.BytesIO(input_bytes)).convert('RGB')
    img = Image.new("RGB", original.size)
    img.paste(original)

    width, height = img.size
    variations = []

    for _ in range(variation_count):
        modified = img.copy()

        resize_factor = random.uniform(0.98, 1.02)
        modified = modified.resize(
            (int(width * resize_factor), int(height * resize_factor)), Image.LANCZOS
        )

        angle = random.uniform(-0.3, 0.3)
        modified = modified.rotate(angle, expand=False, resample=Image.BICUBIC)

        r, g, b = modified.split()
        r = r.point(lambda i: i * random.uniform(0.99, 1.01))
        g = g.point(lambda i: i * random.uniform(0.99, 1.01))
        b = b.point(lambda i: i * random.uniform(0.99, 1.01))
        modified = Image.merge("RGB", (r, g, b))

        dx, dy = random.randint(-2, 2), random.randint(-2, 2)
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
        factors = [random.uniform(1 - modification_level, 1 + modification_level) for _ in enhancers]

        for enhancer, factor in zip(enhancers, factors):
            modified = enhancer.enhance(factor)

        modified = modified.filter(random.choice([
            ImageFilter.SMOOTH,
            ImageFilter.SHARPEN,
            ImageFilter.DETAIL
        ]))

        array = np.array(modified).astype(np.int16)
        noise = np.random.normal(0, 0.5, array.shape).astype(np.int16)
        array = np.clip(array + noise, 0, 255).astype(np.uint8)
        modified = Image.fromarray(array)

        modified = modified.filter(ImageFilter.SHARPEN)

        output = io.BytesIO()
        modified.save(output, format='JPEG', quality=random.randint(88, 96), optimize=True)
        variations.append(output.getvalue())

    return variations

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [
            InlineKeyboardButton("1", callback_data="varcount_1"),
            InlineKeyboardButton("2", callback_data="varcount_2"),
            InlineKeyboardButton("3", callback_data="varcount_3"),
            InlineKeyboardButton("4", callback_data="varcount_4"),
            InlineKeyboardButton("5", callback_data="varcount_5"),
        ]
    ]
    await update.message.reply_text(
        "👋 Welcome! How many spoofed image variations would you like?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# Store the number of variations requested
async def handle_varcount_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    count = int(query.data.replace("varcount_", ""))
    context.user_data["variation_count"] = count
    await query.edit_message_text(f"✅ Great, send me a photo and I'll give you {count} variations!")

# Handle the photo
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()

        count = context.user_data.get("variation_count", 3)
        variations = generate_variations(image_bytes, variation_count=count)
        context.user_data["variations"] = variations

        for i, variation_bytes in enumerate(variations, 1):
            stream = io.BytesIO(variation_bytes)
            stream.seek(0)
            await update.message.reply_photo(photo=stream, caption=f"Variation {i}")

        buttons = [
            [InlineKeyboardButton(f"Choose Variation {i+1}", callback_data=f"choose_{i}")]
            for i in range(count)
        ]
        await update.message.reply_text("👇 Choose the variation you want to keep:", reply_markup=InlineKeyboardMarkup(buttons))

    except Exception as e:
        logger.error("Error in handle_photo", exc_info=True)
        await update.message.reply_text("⚠️ Failed to process the image.")

# Handle final choice
async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        index = int(query.data.replace("choose_", ""))
        variation_bytes = context.user_data["variations"][index]
        stream = io.BytesIO(variation_bytes)
        stream.seek(0)

        await query.message.reply_photo(photo=stream, caption=f"✅ You selected Variation {index + 1}")
        context.user_data["variations"] = None
    except Exception as e:
        logger.error("Error in handle_choice", exc_info=True)
        await query.message.reply_text("⚠️ Failed to load your selection.")

# The main function to set up and run the bot
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_varcount_choice, pattern=r"varcount_\d+"))
    app.add_handler(CallbackQueryHandler(handle_choice, pattern=r"choose_\d+"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    await app.bot.set_my_commands([("start", "Start the bot and choose image variation count")])
    logger.info("🤖 Bot is running...")
    await app.run_polling()

# Run the bot properly for Render
if __name__ == "__main__":
    asyncio.run(main())