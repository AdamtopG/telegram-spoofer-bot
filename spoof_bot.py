#!/usr/bin/env python3
import os
import io
import zipfile
import random
import logging
import tempfile
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image, ImageEnhance, ImageFilter

# Import moviepy with error handling
try:
    import moviepy.editor as mpy
    from moviepy.video.fx.all import colorx, lum_contrast, gamma_corr
    VIDEO_SUPPORT = True
except ImportError:
    VIDEO_SUPPORT = False
    print("Warning: moviepy not available, video processing disabled")

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

# --- Video processing functionality ---
def process_video_variations(input_bytes, variation_count=1):
    """Create video variations with artistic transformations"""
    if not VIDEO_SUPPORT:
        raise Exception("Video processing not available")
    
    variations = []
    
    # Use a temporary directory for file operations
    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = os.path.join(temp_dir, "input_video.mp4")
        
        # Write input video
        with open(input_path, "wb") as f:
            f.write(input_bytes)
        
        try:
            # Load the video
            clip = mpy.VideoFileClip(input_path)
            
            for i in range(variation_count):
                # Create a variation
                processed_clip = create_video_variation(clip, i)
                
                # Output path
                output_path = os.path.join(temp_dir, f"output_{i}.mp4")
                
                # Export with metadata
                export_video_with_metadata(processed_clip, output_path)
                
                # Read the processed video
                with open(output_path, "rb") as f:
                    variations.append(f.read())
                
                # Clean up this variation
                processed_clip.close()
                if os.path.exists(output_path):
                    os.remove(output_path)
            
            # Clean up original clip
            clip.close()
            
        except Exception as e:
            logger.error(f"Video processing error: {e}")
            raise
    
    return variations

def create_video_variation(clip, variation_index):
    """Create a single video variation with artistic effects"""
    
    # Apply different transformations based on variation index
    if variation_index == 0:
        # Slight color adjustment
        processed = clip.fx(colorx, random.uniform(0.9, 1.1))
        
    elif variation_index == 1:
        # Brightness and contrast
        processed = clip.fx(lum_contrast, 
                          lum=random.uniform(-5, 5), 
                          contrast=random.uniform(0.9, 1.1))
        
    elif variation_index == 2:
        # Gamma correction for mood
        processed = clip.fx(gamma_corr, random.uniform(0.9, 1.1))
        
    else:
        # Combination of effects
        processed = clip
        processed = processed.fx(colorx, random.uniform(0.95, 1.05))
        processed = processed.fx(lum_contrast, 
                               lum=random.uniform(-3, 3), 
                               contrast=random.uniform(0.95, 1.05))
    
    # Optional: Slight crop for composition (2-5% from edges)
    if random.random() > 0.5:
        w, h = processed.size
        crop_factor = random.uniform(0.02, 0.05)
        crop_pixels_w = int(w * crop_factor)
        crop_pixels_h = int(h * crop_factor)
        processed = processed.crop(
            x1=crop_pixels_w, 
            y1=crop_pixels_h,
            x2=w-crop_pixels_w, 
            y2=h-crop_pixels_h
        )
    
    # Limit duration for performance (configurable)
    max_duration = 30  # seconds
    if processed.duration > max_duration:
        processed = processed.subclip(0, max_duration)
    
    return processed

def export_video_with_metadata(clip, output_path):
    """Export video with clean metadata"""
    
    # Prepare metadata
    metadata = {
        'title': f'Processed Video {datetime.now().strftime("%Y%m%d_%H%M%S")}',
        'artist': 'Video Processor Bot',
        'comment': 'Processed with artistic filters',
        'date': datetime.now().strftime("%Y-%m-%d")
    }
    
    # Determine quality settings based on original
    if hasattr(clip, 'fps') and clip.fps:
        target_fps = clip.fps
    else:
        target_fps = 30
    
    # Export with quality preservation
    clip.write_videofile(
        output_path,
        codec='libx264',
        audio_codec='aac',
        # Preserve quality with CRF (lower = better quality)
        ffmpeg_params=[
            '-crf', '23',  # Good quality (18-23 is good range)
            '-preset', 'medium',  # Balance between speed and compression
            '-movflags', '+faststart',  # Web optimization
            # Clear existing metadata and add new
            '-map_metadata', '-1',
            '-metadata', f'title={metadata["title"]}',
            '-metadata', f'artist={metadata["artist"]}',
            '-metadata', f'comment={metadata["comment"]}',
            '-metadata', f'date={metadata["date"]}'
        ],
        fps=target_fps,
        verbose=False,
        logger=None
    )

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
        video_text = " or video" if VIDEO_SUPPORT else ""
        await update.callback_query.message.reply_text(
            f"✅ Great! Now send me a photo{video_text}, and I'll generate {count} variations."
        )
    except:
        await update.callback_query.message.reply_text("❌ Invalid choice. Please /start again.")

# --- Photo handler ---
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

# --- Video handler ---
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not VIDEO_SUPPORT:
        return await update.message.reply_text(
            "❌ Video processing is not available. Please check the server logs."
        )
    
    variation_count = context.user_data.get("variation_count", 1)
    if not variation_count:
        return await update.message.reply_text(
            "⚠️ Please use /start first to pick a variation count."
        )
    
    await update.message.reply_text(
        "🎬 Processing your video with artistic filters...\n"
        "This may take a moment depending on video length."
    )
    
    try:
        # Get video file
        video_file = await update.message.video.get_file()
        raw_video = await video_file.download_as_bytearray()
        
        # Process video variations
        variations = process_video_variations(raw_video, variation_count)
        
        # Send back variations
        for idx, video_bytes in enumerate(variations, start=1):
            caption = f"🎨 Variation {idx}/{variation_count}"
            if idx == 1:
                caption += " - Color adjusted"
            elif idx == 2:
                caption += " - Brightness/Contrast"
            elif idx == 3:
                caption += " - Gamma corrected"
            else:
                caption += " - Mixed effects"
                
            await update.message.reply_video(
                video=io.BytesIO(video_bytes),
                caption=caption
            )
        
        await update.message.reply_text(
            "✅ Video processing complete! "
            "Each variation has different artistic effects applied."
        )
        
    except Exception as e:
        logger.error(f"Video processing error: {e}")
        await update.message.reply_text(
            "❌ Sorry, there was an error processing your video.\n"
            "Please try with a shorter video (under 30 seconds) or smaller file size."
        )

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
async def zip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.lower().endswith(".zip"):
        return await update.message.reply_text("❌ Please send me a .zip file.")

    await update.message.reply_text("📦 Processing ZIP file...")

    in_buf = io.BytesIO()
    file = await doc.get_file()
    await file.download(out=in_buf)
    in_buf.seek(0)

    out_buf = io.BytesIO()
    with zipfile.ZipFile(in_buf, 'r') as zin, \
         zipfile.ZipFile(out_buf, 'w', zipfile.ZIP_DEFLATED) as zout:
        for name in zin.namelist():
            if name.endswith("/"):
                continue
            data = zin.read(name)
            ext = name.lower().rsplit(".",1)[-1] if "." in name else ""
            if ext in ("jpg","jpeg","png","bmp","tiff","gif"):
                processed = generate_variations(data, variation_count=1)[0]
                base = name.rsplit(".",1)[0]
                zout.writestr(f"{base}_processed.jpg", processed)
            else:
                zout.writestr(name, data)
    out_buf.seek(0)

    await update.message.reply_document(
        document=out_buf,
        filename=f"processed_{doc.file_name}",
        caption="✅ ZIP file processed with artistic filters!"
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
    
    # Log video support status
    if VIDEO_SUPPORT:
        logger.info("✅ Video processing is available")
    else:
        logger.warning("⚠️ Video processing is NOT available - moviepy not installed")

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
application.add_handler(MessageHandler(filters.VIDEO, handle_video))
application.add_handler(
    MessageHandler(filters.Document.FileExtension("zip"), zip_handler)
)

if __name__ == "__main__":
    logger.info("🤖 Bot is starting...")
    if VIDEO_SUPPORT:
        logger.info("📹 Video support is enabled")
    else:
        logger.info("📷 Photo-only mode (install moviepy for video support)")
    application.run_polling()