# (c) @AbirHasan2005 | Updated by GPT-5
# Telegram Video Watermark Adder Bot - Updated for 2025
# Compatible with Pyrogram v2.0+, Python 3.12+, and Heroku-24 stack

import os
import time
import json
import random
import asyncio
import aiohttp
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from PIL import Image
from core.ffmpeg import vidmark
from core.clean import delete_all, delete_trash
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, UserNotParticipant, MessageNotModified
from configs import Config
from core.handlers.main_db_handler import db
from core.display_progress import progress_for_pyrogram, humanbytes
from core.handlers.force_sub_handler import handle_force_subscribe
from core.handlers.upload_video_handler import send_video_handler
from core.handlers.broadcast_handlers import broadcast_handler

# Initialize bot client
AHBot = Client(
    name=Config.BOT_USERNAME,
    bot_token=Config.BOT_TOKEN,
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
)

# --- /start and /help ---
@AHBot.on_message(filters.command(["start", "help"]) & filters.private)
async def help_watermark(bot, message):
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id)
        await bot.send_message(
            Config.LOG_CHANNEL,
            f"#NEW_USER\n\n[{message.from_user.first_name}](tg://user?id={message.from_user.id}) started @{Config.BOT_USERNAME}",
        )

    if Config.UPDATES_CHANNEL:
        fsub = await handle_force_subscribe(bot, message)
        if fsub == 400:
            return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Developer", url="https://t.me/Dads_links"),
         InlineKeyboardButton("Support Group", url="https://t.me/Dads_links")],
        [InlineKeyboardButton("Bots Channel", url="https://t.me/Dads_links")],
        [InlineKeyboardButton("Source Code", url="https://github.com/Doctorstra")]
    ])

    await message.reply_text(
        text=Config.USAGE_WATERMARK_ADDER,
        parse_mode="Markdown",
        reply_markup=keyboard,
        disable_web_page_preview=True
    )


# --- Reset Command ---
@AHBot.on_message(filters.command(["reset"]) & filters.private)
async def reset_settings(bot, message):
    await db.delete_user(message.from_user.id)
    await db.add_user(message.from_user.id)
    await message.reply_text("✅ Settings reset successfully!")


# --- Settings Command ---
@AHBot.on_message(filters.command("settings") & filters.private)
async def settings_bot(bot, message):
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id)

    if Config.UPDATES_CHANNEL:
        fsub = await handle_force_subscribe(bot, message)
        if fsub == 400:
            return

    # Position lookup
    positions = {
        "5:main_h-overlay_h": "Bottom Left",
        "main_w-overlay_w-5:main_h-overlay_h-5": "Bottom Right",
        "main_w-overlay_w-5:5": "Top Right",
        "5:5": "Top Left"
    }

    watermark_position = await db.get_position(message.from_user.id)
    position_tag = positions.get(watermark_position, "Top Left")

    # Size lookup
    size = int(await db.get_size(message.from_user.id))
    size_tag = f"{size}%" if 5 <= size <= 45 else "7%"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Watermark Position - {position_tag}", callback_data="info_position")],
        [InlineKeyboardButton("Set Top Left", callback_data="position_5:5"),
         InlineKeyboardButton("Set Top Right", callback_data="position_main_w-overlay_w-5:5")],
        [InlineKeyboardButton("Set Bottom Left", callback_data="position_5:main_h-overlay_h"),
         InlineKeyboardButton("Set Bottom Right", callback_data="position_main_w-overlay_w-5:main_h-overlay_h-5")],
        [InlineKeyboardButton(f"Watermark Size - {size_tag}", callback_data="info_size")],
        [InlineKeyboardButton("5%", callback_data="size_5"),
         InlineKeyboardButton("7%", callback_data="size_7"),
         InlineKeyboardButton("10%", callback_data="size_10"),
         InlineKeyboardButton("15%", callback_data="size_15"),
         InlineKeyboardButton("20%", callback_data="size_20")],
        [InlineKeyboardButton("25%", callback_data="size_25"),
         InlineKeyboardButton("30%", callback_data="size_30"),
         InlineKeyboardButton("35%", callback_data="size_35"),
         InlineKeyboardButton("40%", callback_data="size_40"),
         InlineKeyboardButton("45%", callback_data="size_45")],
        [InlineKeyboardButton("Reset Settings to Default", callback_data="reset")]
    ])

    await message.reply_text(
        text="⚙️ **Your Watermark Settings:**",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


# --- Video/Photo Handler ---
@AHBot.on_message((filters.video | filters.document | filters.photo) & filters.private)
async def video_handler(bot, message):
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id)

    if Config.UPDATES_CHANNEL:
        fsub = await handle_force_subscribe(bot, message)
        if fsub == 400:
            return

    # Handle watermark image upload
    if message.photo or (message.document and message.document.mime_type.startswith("image/")):
        editable = await message.reply_text("📥 Downloading watermark image...")
        watermark_dir = os.path.join(Config.DOWN_PATH, str(message.from_user.id))
        os.makedirs(watermark_dir, exist_ok=True)
        watermark_path = os.path.join(watermark_dir, "thumb.jpg")
        await bot.download_media(message, file_name=watermark_path)
        await editable.edit("✅ Watermark image saved!\nNow send a video to apply it.")
        return

    # Handle video upload
    if not (message.video or (message.document and message.document.mime_type.startswith("video/"))):
        await message.reply_text("❌ Please send a valid video file.")
        return

    working_dir = os.path.join(Config.DOWN_PATH, "WatermarkAdder", str(message.from_user.id))
    os.makedirs(working_dir, exist_ok=True)
    status_path = os.path.join(working_dir, "status.json")

    if os.path.exists(status_path):
        await message.reply_text("⚠️ I'm currently busy with another task. Try again later.")
        return

    watermark_path = os.path.join(Config.DOWN_PATH, str(message.from_user.id), "thumb.jpg")
    if not os.path.exists(watermark_path):
        await message.reply_text("⚠️ You haven’t set any watermark image yet!\nPlease send one first.")
        return

    # Start video processing
    preset = Config.PRESET or "ultrafast"
    editable = await message.reply_text("📥 Downloading video...")
    start_time = time.time()

    try:
        downloaded_path = await bot.download_media(
            message=message,
            file_name=working_dir,
            progress=progress_for_pyrogram,
            progress_args=("Downloading video...", editable, start_time)
        )
    except Exception as e:
        await editable.edit(f"❌ Failed to download video.\nError: `{e}`")
        return

    # Watermark logic
    position = await db.get_position(message.from_user.id)
    size = await db.get_size(message.from_user.id)
    await editable.edit("✨ Adding watermark to your video, please wait...")

    try:
        output_vid = await vidmark(
            downloaded_path,
            editable,
            os.path.join(working_dir, "progress.txt"),
            watermark_path,
            f"output_{int(time.time())}.mp4",
            0,
            None,
            status_path,
            preset,
            position,
            size,
        )
    except Exception as e:
        await editable.edit(f"❌ Watermarking failed.\nError: `{e}`")
        await delete_all()
        return

    if not output_vid or not os.path.exists(output_vid):
        await editable.edit("❌ Something went wrong while processing.")
        return

    # Upload result
    await editable.edit("✅ Watermark added successfully!\n📤 Uploading to Telegram...")
    try:
        await send_video_handler(bot, message, output_vid, None, 0, 0, 0, editable, None, os.path.getsize(output_vid))
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await send_video_handler(bot, message, output_vid, None, 0, 0, 0, editable, None, os.path.getsize(output_vid))
    except Exception as e:
        await editable.edit(f"❌ Upload failed.\nError: `{e}`")
    finally:
        await delete_all()


# --- Broadcast Command ---
@AHBot.on_message(filters.private & filters.command("broadcast") & filters.user(Config.OWNER_ID) & filters.reply)
async def open_broadcast_handler(bot, message):
    await broadcast_handler(c=bot, m=message)


# --- Status Command ---
@AHBot.on_message(filters.command("status") & filters.private)
async def bot_status(_, message):
    status_path = os.path.join(Config.DOWN_PATH, "WatermarkAdder", "status.json")
    busy = os.path.exists(status_path)
    text = "🚦 I'm currently busy with another task." if busy else "✅ I'm free! Send me a video to start."
    if int(message.from_user.id) == Config.OWNER_ID:
        total_users = await db.total_users_count()
        text += f"\n\n👥 Total Users: `{total_users}`"
    await message.reply_text(text, parse_mode="Markdown")


# --- Start Bot ---
if __name__ == "__main__":
    print("✅ Bot is running...")
    AHBot.run()
