import random
import numpy as np
import io
import asyncio
from PIL import Image, ImageEnhance, ImageFilter
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Generate image variations (anti-duplicate-safe)
def generate_variations(input_bytes, variation_count=5, modification_level=0.2):
    original = Image.open(io.BytesIO(input_bytes)).convert("RGB")
    img = Image.new("RGB", original.size)
    img.paste(original)

    width, height = img.size
    variations = []

    for _ in range(variation_count):
        modified = img.copy()

        # Slight resize
        resize_factor = random.uniform(0.98, 1.02)
        modified = modified.resize(
            (int(width * resize_factor), int(height * resize_factor)), Image.LANCZOS
        )

        # Slight rotation
        angle = random.uniform(-0.3, 0.3)
        modified = modified.rotate(angle, expand=False, resample=Image.BICUBIC)

        # Subtle color shifts
        r, g, b = modified.split()
        r = r.point(lambda i: i * random.uniform(0.99, 1.01))
        g = g.point(lambda i: i * random.uniform(0.99, 1.01))
        b = b.point(lambda i: i * random.uniform(0.99, 1.01))
        modified = Image.merge("RGB", (r, g, b))

        # Pixel shifting
        dx, dy = random.randint(-2, 2), random.randint(-2, 2)
        modified = modified.transform(
            modified.size, Image.AFFINE, (1, 0, dx, 0, 1, dy), resample=Image.BICUBIC
        )

        # Enhancements
        enhancers = [
            ImageEnhance.Brightness(modified),
            ImageEnhance.Contrast(modified),
            ImageEnhance.Color(modified),
            ImageEnhance.Sharpness(modified),
        ]
        for enhancer in enhancers:
            modified = enhancer.enhance(random.uniform(1 - modification_level, 1 + modification_level))

        # Subtle filter
        modified = modified.filter(random.choice([
            ImageFilter.SMOOTH, ImageFilter.SHARPEN, ImageFilter.DETAIL
        ]))

        # Add pixel-level noise
        array = np.array(modified).astype(np.int16)
        noise = np.random.normal(0, 0.5, array.shape).astype(np.int16)
        array = np.clip(array + noise, 0, 255).astype(np.uint8)
        modified = Image.fromarray(array)

        # Final sharpening
        modified = modified.filter(ImageFilter.SHARPEN)

        # Export
        output = io.BytesIO()
        modified.save(output, format="JPEG", quality=random.randint(85, 96), subsampling=random.choice([0, 1, 2]), optimize=True)
        variations.append(output.getvalue())

    return variations

# /start handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton(f"{i} Variations", callback_data=f"count_{i}")]
        for i in range(1, 6)
    ]
    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("👋 Welcome! Choose how many spoofed versions you'd like:", reply_markup=markup)

# Handle count selection
async def choose_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    count = int(query.data.split("_")[1])
    context.user_data["variation_count"] = count
    await query.message.reply_text(f"📸 Great! Now send me a photo to generate {count} variations.")

# Handle incoming photos
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = context.user_data.get("variation_count")
        if not count:
            await update.message.reply_text("⚠️ Please choose how many variations you want first using /start.")
            return

        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()

        variations = generate_variations(image_bytes, variation_count=count)
        context.user_data["variations"] = variations

        for i, v in enumerate(variations, 1):
            await update.message.reply_photo(photo=io.BytesIO(v), caption=f"Variation {i}")

        buttons = [
            [InlineKeyboardButton(f"Choose Variation {i+1}", callback_data=f"choose_{i}")]
            for i in range(count)
        ]
        markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_text("👇 Choose the variation you like:", reply_markup=markup)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error processing image: {e}")

# Handle variation selection
async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        index = int(query.data.split("_")[1])
        variation_bytes = context.user_data["variations"][index]
        await query.message.reply_photo(photo=io.BytesIO(variation_bytes), caption=f"✅ You selected Variation {index+1}")
        context.user_data["variations"] = None
        context.user_data["variation_count"] = None
    except Exception as e:
        await query.message.reply_text(f"⚠️ Could not process selection: {e}")

# --- Replace this with your actual bot token ---
BOT_TOKEN = "8089313407:AAHF1dRzX4ahU485tag1vujOp9opo0NvG6M"

# --- Main async entrypoint ---
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    await app.bot.set_my_commands([
        ("start", "Start the bot and choose variation count")
    ])

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(choose_count, pattern="^count_"))
    app.add_handler(CallbackQueryHandler(handle_choice, pattern="^choose_"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("🤖 Bot is running...")
    await app.run_polling()

# Run the bot
if __name__ == "__main__":
    asyncio.run(main())
