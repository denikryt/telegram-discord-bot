import os
import telebot
import hashlib
import logging
import subprocess
import shutil
import config
# import lottie
# # from lottie.parsers.tgs import parse_tgs
# # from lottie.exporters.gif import export_gif
# from PIL import Image
# import io
# from pyrlottie import LottieFile, convMultLottieTransparentFrames
# import asyncio

# --- Constants ---
VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
MAX_VIDEO_SIZE_MB = 10
TARGET_BITRATE = "1000k"
DOWNLOAD_DIR = 'downloads'
MAX_FILE_SIZE = 20 * 1024 * 1024

# --- FFMPEG ---
# Check if ffmpeg is available in the system PATH
FFMPEG_PATH = shutil.which("ffmpeg")
logging.info(f"FFMPEG_PATH: {FFMPEG_PATH}")

# If not found, we can specify it manually (e.g. for Windows)
if FFMPEG_PATH is None:
    if os.name == 'nt':  # Windows
        FFMPEG_PATH = config.FFMPEG_PATH
    else:
        logging.error("ffmpeg not found in PATH. Please install it or add it to the system PATH.")
        raise FileNotFoundError("ffmpeg not found in PATH. Please install it or add it to the system PATH.")

# --- Utilities ---
def ensure_directory_exists(path):
    if not os.path.exists(path):
        os.makedirs(path)

def generate_hashed_filename(content, original_ext):
    file_hash = hashlib.sha256(content).hexdigest()
    return f"{file_hash}{original_ext}"

def save_file(content, path):
    with open(path, 'wb') as f:
        f.write(content)

def get_file_size_mb(path):
    return os.path.getsize(path) / (1024 * 1024)

def is_video_file(ext):
    return ext.lower() in VIDEO_EXTENSIONS

def compress_video(input_path, output_path, target_bitrate=TARGET_BITRATE):
    """
    Compresses a video file using ffmpeg to the specified bitrate.
    """
    logger(f"--- Compressing video ---")

    ffmpeg_cmd = [
        FFMPEG_PATH,
        "-i", input_path,
        "-b:v", target_bitrate,
        "-bufsize", target_bitrate,
        "-y",  # overwrite if exists
        output_path
    ]
    try:
        subprocess.run(ffmpeg_cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger(f"Error compressing video: {e}")
        return False

# def convert_tgs_to_gif(tgs_path, gif_path, frame_skip=0, scale=1):
#     # Загружаем Lottie файл
#     lottie_file = LottieFile(tgs_path)

#     # Получаем кадры с прозрачностью (список PIL.Image)
#     frames_dict = asyncio.run(convMultLottieTransparentFrames([lottie_file], frameSkip=frame_skip, scale=scale))
#     frames = frames_dict[tgs_path].frames

#     if not frames:
#         raise Exception("No frames extracted from TGS file.")

#     # Конвертируем в GIF
#     frames[0].save(
#         gif_path,
#         save_all=True,
#         append_images=frames[1:],
#         duration=100,  # или вычисли на основе fps
#         loop=0,
#         transparency=0,
#         disposal=2
#     )

def download_telegram_file(bot, file_id):
    """
    Downloads a file from Telegram using the provided bot and file_id.
    Converts .tgs stickers to .gif, compresses video if needed.
    """
    logger(f"--- Downloading file from Telegram ---")

    ensure_directory_exists(DOWNLOAD_DIR)

    file_info = bot.get_file(file_id)
    file_path = file_info.file_path
    downloaded_file = bot.download_file(file_path)

    ext = os.path.splitext(file_path)[-1]
    file_name = generate_hashed_filename(downloaded_file, ext)
    local_path = os.path.join(DOWNLOAD_DIR, file_name)

    save_file(downloaded_file, local_path)

    # handle different file types
    if ext.lower() == '.tgs':
        return #handle_tgs_file(local_path, DOWNLOAD_DIR)
    elif is_video_file(ext):
        return handle_video_file(local_path, file_name, DOWNLOAD_DIR)
    else:
        return local_path

# def handle_tgs_file(tgs_path, output_dir):
#     """
#     Converts a .tgs (Lottie) file to .gif and returns the gif path.
#     """
#     gif_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(tgs_path))[0]}.gif")
#     try:
#         convert_tgs_to_gif(tgs_path, gif_path)
#         os.remove(tgs_path)
#         logger(f"Converted .tgs to .gif: {gif_path}")
#         return gif_path
#     except Exception as e:
#         logger(f"Failed to convert .tgs to .gif: {e}")
#         return tgs_path

def handle_video_file(video_path, file_name, output_dir):
    """
    Compresses a video file if it exceeds size limits.
    Returns path to compressed or original video.
    """
    if get_file_size_mb(video_path) > MAX_VIDEO_SIZE_MB:
        logger(f"Video detected: {file_name}")
        logger(f"Compressing video {file_name} as it exceeds {MAX_VIDEO_SIZE_MB} MB")

        compressed_path = os.path.join(output_dir, f"{os.path.splitext(file_name)[0]}_compressed.mp4")
        if compress_video(video_path, compressed_path):
            os.remove(video_path)
            return compressed_path
        else:
            logger(f"Compression failed for video {file_name}, using original file.")

    return video_path

def extract_media(message):
    """
    Extracts media from a Telegram message and returns a list of tuples with file_id and type.
    """
    logger(f"--- Extracting media from message ---")

    media = []
    if message.photo:
        logger('--- Photo detected in message')
        media.append((message.photo[-1].file_id, 'photo'))  # max resolution
    elif message.video:
        logger('--- Video detected in message')
        if message.video.file_size > MAX_FILE_SIZE:
            raise ValueError(f"Video file size exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB, skipping download.")
        media.append((message.video.file_id, 'video'))
    elif message.document:
        logger('--- Document detected in message')
        if message.document.file_size > MAX_FILE_SIZE:
            raise ValueError(f"Document file size exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB, skipping download.")
        media.append((message.document.file_id, 'document'))
    elif message.audio:
        logger('--- Audio detected in message')
        if message.audio.file_size > MAX_FILE_SIZE:
            raise ValueError(f"Audio file size exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB, skipping download.")
        media.append((message.audio.file_id, 'audio'))
    elif message.voice:
        logger('--- Voice message detected in message')
        media.append((message.voice.file_id, 'voice'))
    elif message.sticker:
        logger('--- Sticker detected in message')
        media.append((message.sticker.file_id, 'sticker'))
    return media

def get_media_files(message, tg_bot):
    media_info = extract_media(message)
    media_files = []
    for file_id, _ in media_info:
        media_files.append(download_telegram_file(tg_bot, file_id))

    return media_files

def clean_media_files(media_files):
    """
    Cleans up media files after processing.
    """
    logger(f"--- Cleaning up media files ---")

    for file_path in media_files:
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Failed to remove file {file_path}: {e}")

def logger(log_text):
    print(log_text)
    logging.info(log_text)