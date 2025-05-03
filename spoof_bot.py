import random
import numpy as np
import io
from PIL import Image, ImageEnhance, ImageFilter
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
import asyncio

# --- Image Spoofing Logic ---
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
        quality = random.randint(85, 96)
        subsampling = random.choice([0, 1, 2])
        modified.save(output, format='JPEG', quality=quality, subsampling=subsampling, optimize=True)
        variations.append(output.getvalue())

    return variations

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("1", callback_data="set_variations_1"),
         InlineKeyboardButton("2", callback_data="set_variations_2"),
         InlineKeyboardButton("3", callback_data="set_variations_3"),
         InlineKeyboardButton("4", callback_data="set_variations_4"),
         InlineKeyboardButton("5", callback_data="set_variations_5")]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("👋 Welcome! How many variations do you want to generate?", reply_markup=reply_markup)

# --- Image Handler ---
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        variation_count = context.user_data.get("variation_count", 5)
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()

        variations = generate_variations(image_bytes, variation_count=variation_count)
        context.user_data["variations"] = variations

        for i, variation_bytes in enumerate(variations, 1):
            stream = io.BytesIO(variation_bytes)
            stream.seek(0)
            await update.message.reply_photo(photo=stream, caption=f"Variation {i}")

        buttons = [
            [InlineKeyboardButton(f"Choose Variation {i+1}", callback_data=f"choose_{i}")]
            for i in range(variation_count)
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_text("👇 Choose the variation you like:", reply_markup=reply_markup)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error processing image: {e}")

# --- Callback Handler ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("set_variations_"):
        number = int(query.data.split("_")[-1])
        context.user_data["variation_count"] = number
        await query.message.reply_text(f"✅ You selected {number} variations. Now send me a photo.")
        return

    if query.data.startswith("choose_"):
        try:
            index = int(query.data.split("_")[-1])
            variation_bytes = context.user_data["variations"][index]
            stream = io.BytesIO(variation_bytes)
            stream.seek(0)
            await query.message.reply_photo(photo=stream, caption=f"✅ You selected Variation {index+1}")
            context.user_data["variations"] = None
        except Exception as e:
            await query.message.reply_text(f"⚠️ Could not process selection: {e}")

# --- Async Command Registration ---
async def set_bot_commands(app):
    await app.bot.set_my_commands([
        ("start", "Start the bot and choose variation count")
    ])

# --- Main Execution ---
BOT_TOKEN = "8089313407:AAHF1dRzX4ahU485tag1vujOp9opo0NvG6M"  # Replace with your bot token

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Run async setup then polling
    async def run():
        await set_bot_commands(app)
        print("🤖 Bot is running...")
        await app.run_polling()

    asyncio.run(run())
