import os
import io
import random
import tempfile
import logging
from datetime import datetime
import moviepy.editor as mpy
from moviepy.video.fx.all import colorx, lum_contrast, gamma_corr

logger = logging.getLogger(__name__)

def process_video_variations(input_bytes, variation_count=1):
    """
    Create video variations with artistic transformations
    Returns a list of processed video bytes
    """
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

# Enhanced video handler for the Telegram bot
async def handle_video_enhanced(update, context):
    """Enhanced video handler with multiple variations"""
    
    variation_count = context.user_data.get("variation_count", 1)
    
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