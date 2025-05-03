import io
import random
from PIL import Image, ImageEnhance
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
import logging
import os

# Enable logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8089313407:AAHF1dRzX4ahU485tag1vujOp9opo0NvG6M"  # Replace with your actual token

# In-memory cache
user_images = {}

# Image variation logic
def generate_variations(image_bytes, count=5):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    variations = []

    for i in range(count):
        modified = img.copy()
        enhancer = ImageEnhance.Color(modified)
        modified = enhancer.enhance(random.uniform(0.9, 1.1))
        enhancer = ImageEnhance.Sharpness(modified)
        modified = enhancer.enhance(random.uniform(0.9, 1.1))
        output = io.BytesIO()
        modified.save(output, format="JPEG")
        output.seek(0)
        variations.append(output)

    return variations

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send me a photo to spoof!")

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = await update.message.photo[-1].get_file()
    image_bytes = await photo.download_as_bytearray()
    user_id = update.effective_user.id
    user_images[user_id] = generate_variations(image_bytes)

    keyboard = [
        [InlineKeyboardButton(f"Variation {i+1}", callback_data=str(i))] for i in range(5)
    ]
    await update.message.reply_text(
        "Choose a variation:", reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    index = int(query.data)

    if user_id in user_images and 0 <= index < len(user_images[user_id]):
        variation = user_images[user_id][index]
        await query.message.reply_photo(photo=variation)
    else:
        await query.message.reply_text("Variation not found.")

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.add_handler(CallbackQueryHandler(button))

    # Register bot commands
    await app.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
    ])

    logger.info("🤖 Bot is running...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await app.updater.idle()

# Only needed in interactive environments like Render
import asyncio
asyncio.get_event_loop().create_task(main())
