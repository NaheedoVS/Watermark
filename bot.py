# bot.py
# (c) @AbirHasan2005

import os
import time
import json
import random
import asyncio
import aiohttp
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from PIL import Image
from core.ffmpeg import vidmark, compress_video
from core.clean import delete_all, delete_trash
from pyrogram import Client, filters
from configs import Config
from core.handlers.main_db_handler import db
from core.display_progress import progress_for_pyrogram, humanbytes
from core.handlers.force_sub_handler import handle_force_subscribe
from core.handlers.upload_video_handler import send_video_handler
from core.handlers.broadcast_handlers import broadcast_handler
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors.exceptions.flood_420 import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant, MessageNotModified

AHBot = Client(Config.BOT_USERNAME, bot_token=Config.BOT_TOKEN, api_id=Config.API_ID, api_hash=Config.API_HASH)

# in-memory per-user compression settings (temporary)
# structure: { user_id: {"enabled": True/False, "crf": int} }
COMP_SETTINGS = {}

def get_user_comp_settings(user_id: int):
	if user_id not in COMP_SETTINGS:
		COMP_SETTINGS[user_id] = {"enabled": True, "crf": 18}
	return COMP_SETTINGS[user_id]

@AHBot.on_message(filters.command(["start", "help"]) & filters.private)
async def HelpWatermark(bot, cmd):
	if not await db.is_user_exist(cmd.from_user.id):
		await db.add_user(cmd.from_user.id)
		await bot.send_message(
			Config.LOG_CHANNEL,
			f"#NEW_USER: \n\nNew User [{cmd.from_user.first_name}](tg://user?id={cmd.from_user.id}) started @{Config.BOT_USERNAME} !!"
		)
	if Config.UPDATES_CHANNEL:
		fsub = await handle_force_subscribe(bot, cmd)
		if fsub == 400:
			return
	await cmd.reply_text(
		text=Config.USAGE_WATERMARK_ADDER,
		parse_mode="Markdown",
		reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Developer", url="https://t.me/Dads_links"), InlineKeyboardButton("Support Group", url="https://t.me/Dads_links")], [InlineKeyboardButton("Bots Channel", url="https://t.me/Dads_links")], [InlineKeyboardButton("Source Code", url="https://github.com/Doctorstra")]]),
		disable_web_page_preview=True
	)


@AHBot.on_message(filters.command(["reset"]) & filters.private)
async def reset(bot, update):
	await db.delete_user(update.from_user.id)
	await db.add_user(update.from_user.id)
	# reset in-memory settings
	if update.from_user.id in COMP_SETTINGS:
		del COMP_SETTINGS[update.from_user.id]
	await update.reply_text("Settings reseted successfully")


@AHBot.on_message(filters.command("settings") & filters.private)
async def SettingsBot(bot, cmd):
	if not await db.is_user_exist(cmd.from_user.id):
		await db.add_user(cmd.from_user.id)
		await bot.send_message(
			Config.LOG_CHANNEL,
			f"#NEW_USER: \n\nNew User [{cmd.from_user.first_name}](tg://user?id={cmd.from_user.id}) started @{Config.BOT_USERNAME} !!"
		)
	if Config.UPDATES_CHANNEL:
		fsub = await handle_force_subscribe(bot, cmd)
		if fsub == 400:
			return
	## --- Checks --- ##
	position_tag = None
	watermark_position = await db.get_position(cmd.from_user.id)
	if watermark_position == "5:main_h-overlay_h":
		position_tag = "Bottom Left"
	elif watermark_position == "main_w-overlay_w-5:main_h-overlay_h-5":
		position_tag = "Bottom Right"
	elif watermark_position == "main_w-overlay_w-5:5":
		position_tag = "Top Right"
	elif watermark_position == "5:5":
		position_tag = "Top Left"

	watermark_size = await db.get_size(cmd.from_user.id)
	if int(watermark_size) == 5:
		size_tag = "5%"
	elif int(watermark_size) == 7:
		size_tag = "7%"
	elif int(watermark_size) == 10:
		size_tag = "10%"
	elif int(watermark_size) == 15:
		size_tag = "15%"
	elif int(watermark_size) == 20:
		size_tag = "20%"
	elif int(watermark_size) == 25:
		size_tag = "25%"
	elif int(watermark_size) == 30:
		size_tag = "30%"
	elif int(watermark_size) == 35:
		size_tag = "35%"
	elif int(watermark_size) == 40:
		size_tag = "40%"
	elif int(watermark_size) == 45:
		size_tag = "45%"
	else:
		size_tag = "7%"

	# compression settings (temporary, in-memory)
	user_cfg = get_user_comp_settings(cmd.from_user.id)
	comp_tag = "Enabled" if user_cfg.get("enabled", True) else "Disabled"
	crf_tag = user_cfg.get("crf", 18)

	## --- Next --- ##
	await cmd.reply_text(
		text=f"Here you can set your Watermark Settings:\n\nWatermark Position - {position_tag}\nWatermark Size - {size_tag}\n\nAuto Compression - {comp_tag}\nCompression Quality (CRF) - {crf_tag}",
		disable_web_page_preview=True,
		parse_mode="Markdown",
		reply_markup=InlineKeyboardMarkup(
			[
				[InlineKeyboardButton(f"Watermark Position - {position_tag}", callback_data="lol")],
				[InlineKeyboardButton("Set Top Left", callback_data=f"position_5:5"), InlineKeyboardButton("Set Top Right", callback_data=f"position_main_w-overlay_w-5:5")],
				[InlineKeyboardButton("Set Bottom Left", callback_data=f"position_5:main_h-overlay_h"), InlineKeyboardButton("Set Bottom Right", callback_data=f"position_main_w-overlay_w-5:main_h-overlay_h-5")],
				[InlineKeyboardButton(f"Watermark Size - {size_tag}", callback_data="lel")],
				[InlineKeyboardButton("5%", callback_data=f"size_5"), InlineKeyboardButton("7%", callback_data=f"size_7"), InlineKeyboardButton("10%", callback_data=f"size_10"), InlineKeyboardButton("15%", callback_data=f"size_15"), InlineKeyboardButton("20%", callback_data=f"size_20")],
				[InlineKeyboardButton("25%", callback_data=f"size_25"), InlineKeyboardButton("30%", callback_data=f"size_30"), InlineKeyboardButton("35%", callback_data=f"size_30"), InlineKeyboardButton("40%", callback_data=f"size_40"), InlineKeyboardButton("45%", callback_data=f"size_45")],
				[InlineKeyboardButton(f"Toggle Compression ({comp_tag})", callback_data=f"togglecompress"), InlineKeyboardButton("Set CRF 18", callback_data="crf_18")],
				[InlineKeyboardButton("Set CRF 20", callback_data="crf_20"), InlineKeyboardButton("Set CRF 23", callback_data="crf_23"), InlineKeyboardButton("Set CRF 25", callback_data="crf_25"), InlineKeyboardButton("Set CRF 28", callback_data="crf_28")],
				[InlineKeyboardButton(f"Reset Settings To Default", callback_data="reset")]
			]
		)
	)


@AHBot.on_message(filters.document | filters.video | filters.photo & filters.private)
async def VidWatermarkAdder(bot, cmd):
	if not await db.is_user_exist(cmd.from_user.id):
		await db.add_user(cmd.from_user.id)
		await bot.send_message(
			Config.LOG_CHANNEL,
			f"#NEW_USER: \n\nNew User [{cmd.from_user.first_name}](tg://user?id={cmd.from_user.id}) started @{Config.BOT_USERNAME} !!"
		)
	if Config.UPDATES_CHANNEL:
		fsub = await handle_force_subscribe(bot, cmd)
		if fsub == 400:
			return
	## --- Noobie Process --- ##
	if cmd.photo or (cmd.document and cmd.document.mime_type.startswith("image/")):
		editable = await cmd.reply_text("Downloading Image ...")
		watermark_path = Config.DOWN_PATH + "/" + str(cmd.from_user.id) + "/thumb.jpg"
		await asyncio.sleep(5)
		c_time = time.time()
		await bot.download_media(
			message=cmd,
			file_name=watermark_path,
		)
		await editable.delete()
		await cmd.reply_text("This Saved as Next Video Watermark!\n\nNow Send any Video to start adding Watermark to the Video!")
		return
	else:
		pass
	working_dir = Config.DOWN_PATH + "/WatermarkAdder/"
	if not os.path.exists(working_dir):
		os.makedirs(working_dir)
	watermark_path = Config.DOWN_PATH + "/" + str(cmd.from_user.id) + "/thumb.jpg"
	if not os.path.exists(watermark_path):
		await cmd.reply_text("You Didn't Set Any Watermark!\n\nSend any JPG or PNG Picture ...")
		return
	file_type = cmd.video or cmd.document
	if not file_type.mime_type.startswith("video/"):
		await cmd.reply_text("This is not a Video!")
		return
	status = Config.DOWN_PATH + "/WatermarkAdder/status.json"
	if os.path.exists(status):
		await cmd.reply_text("Sorry, Currently I am busy with another Task!\n\nTry Again After Sometime!")
		return
	preset = Config.PRESET
	editable = await cmd.reply_text("Downloading Video ...", parse_mode="Markdown")
	with open(status, "w") as f:
		statusMsg = {
			'chat_id': cmd.from_user.id,
			'message': editable.message_id
		}
		json.dump(statusMsg, f, indent=2)
	dl_loc = Config.DOWN_PATH + "/WatermarkAdder/" + str(cmd.from_user.id) + "/"
	if not os.path.isdir(dl_loc):
		os.makedirs(dl_loc)
	the_media = None
	user_info = f"**UserID:** #id{cmd.from_user.id}\n**Name:** [{cmd.from_user.first_name}](tg://user?id={cmd.from_user.id})"
	## --- Done --- ##
	try:
		forwarded_video = await cmd.forward(Config.LOG_CHANNEL)
		logs_msg = await bot.send_message(chat_id=Config.LOG_CHANNEL, text=f"Download Started!\n\n{user_info}", reply_to_message_id=forwarded_video.message_id, disable_web_page_preview=True, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Ban User", callback_data=f"ban_{cmd.from_user.id}")]]))
		await asyncio.sleep(5)
		c_time = time.time()
		the_media = await bot.download_media(
			message=cmd,
			file_name=dl_loc,
			progress=progress_for_pyrogram,
			progress_args=(
				"Downloading Sir ...",
				editable,
				logs_msg,
				c_time
			)
		)
		if the_media is None:
			await delete_trash(status)
			await delete_trash(the_media)
			print(f"Download Failed")
			await editable.edit("Unable to Download The Video!")
			return
	except Exception as err:
		await delete_trash(status)
		await delete_trash(the_media)
		print(f"Download Failed: {err}")
		await editable.edit("Unable to Download The Video!")
		return
	watermark_position = await db.get_position(cmd.from_user.id)
	if watermark_position == "5:main_h-overlay_h":
		position_tag = "Bottom Left"
	elif watermark_position == "main_w-overlay_w-5:main_h-overlay_h-5":
		position_tag = "Bottom Right"
	elif watermark_position == "main_w-overlay_w-5:5":
		position_tag = "Top Right"
	elif watermark_position == "5:5":
		position_tag = "Top Left"
	else:
		position_tag = "Top Left"
		watermark_position = "5:5"

	watermark_size = await db.get_size(cmd.from_user.id)
	await editable.edit(f"Trying to Add Watermark to the Video at {position_tag} Corner ...\n\nPlease Wait!")
	duration = 0
	metadata = extractMetadata(createParser(the_media))
	if metadata.has("duration"):
		duration = metadata.get('duration').seconds
	the_media_file_name = os.path.basename(the_media)
	main_file_name = os.path.splitext(the_media_file_name)[0]
	output_vid = main_file_name + "_[" + str(cmd.from_user.id) + "]_[" + str(time.time()) + "]_[@AbirHasan2005]" + ".mp4"
	progress = Config.DOWN_PATH + "/WatermarkAdder/" + str(cmd.from_user.id) + "/progress.txt"
	try:
		output_vid = await vidmark(the_media, editable, progress, watermark_path, output_vid, duration, logs_msg, status, preset, watermark_position, watermark_size)
	except Exception as err:
		print(f"Unable to Add Watermark: {err}")
		await editable.edit("Unable to add Watermark!")
		await logs_msg.edit(f"#ERROR: Unable to add Watermark!\n\n**Error:** `{err}`")
		await delete_all()
		return
	if output_vid is None:
		await editable.edit("Something went wrong!")
		await logs_msg.edit("#ERROR: Something went wrong!")
		await delete_all()
		return

	# --- NEW: Compress the watermarked output and replace it (if user enabled) ---
	await editable.edit("Watermark Added Successfully!\n\nChecking compression settings...")
	user_cfg = get_user_comp_settings(cmd.from_user.id)
	if user_cfg.get("enabled", True):
		await editable.edit("Compression is enabled for you. Starting compression (near-lossless)...")
		compressed_output = os.path.splitext(output_vid)[0] + "_compressed.mp4"
		try:
			# use user's CRF
			user_crf = user_cfg.get("crf", 18)
			compressed = await compress_video(output_vid, editable, progress, compressed_output, duration, logs_msg, status, crf=user_crf)
			if compressed:
				# replace output_vid with compressed file
				output_vid = compressed
				await editable.edit("Compression completed. Uploading compressed video...")
			else:
				# compression failed; continue with original
				await editable.edit("Compression failed or skipped. Uploading original watermarked video...")
		except Exception as e:
			print(f"Compression error: {e}")
			await editable.edit("Compression encountered an error. Uploading original watermarked video...")
	else:
		await editable.edit("Auto-compression is disabled for you. Uploading original watermarked video...")

	# Proceed to thumbnail + upload using (possibly) compressed output_vid
	await editable.edit("Trying to Upload ...")
	await logs_msg.edit("Trying to Upload ...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Ban User", callback_data=f"ban_{cmd.from_user.id}")]]))
	width = 100
	height = 100
	duration = 0
	metadata = extractMetadata(createParser(output_vid))
	if metadata.has("duration"):
		duration = metadata.get('duration').seconds
	if metadata.has("width"):
		width = metadata.get("width")
	if metadata.has("height"):
		height = metadata.get("height")
	video_thumbnail = None
	try:
		video_thumbnail = Config.DOWN_PATH + "/WatermarkAdder/" + str(cmd.from_user.id) + "/" + str(time.time()) + ".jpg"
		ttl = random.randint(0, int(duration) - 1) if duration > 1 else 0
		file_genertor_command = [
			"ffmpeg",
			"-ss",
			str(ttl),
			"-i",
			output_vid,
			"-vframes",
			"1",
			video_thumbnail
		]
		process = await asyncio.create_subprocess_exec(
			*file_genertor_command,
			stdout=asyncio.subprocess.PIPE,
			stderr=asyncio.subprocess.PIPE,
		)
		stdout, stderr = await process.communicate()
		e_response = stderr.decode().strip()
		t_response = stdout.decode().strip()
		print(e_response)
		print(t_response)
		Image.open(video_thumbnail).convert("RGB").save(video_thumbnail)
		img = Image.open(video_thumbnail)
		img.resize((width, height))
		img.save(video_thumbnail, "JPEG")
	except Exception as err:
		print(f"Error: {err}")
	# --- Upload --- #
	file_size = os.path.getsize(output_vid)
	if (int(file_size) > 2097152000) and (Config.ALLOW_UPLOAD_TO_STREAMTAPE is True) and (Config.STREAMTAPE_API_USERNAME != "NoNeed") and (Config.STREAMTAPE_API_PASS != "NoNeed"):
		await editable.edit(f"Sorry Sir,\n\nFile Size Become {humanbytes(file_size)} !!\nI can't Upload to Telegram!\n\nSo Now Uploading to Streamtape ...")
		try:
			async with aiohttp.ClientSession() as session:
				Main_API = "https://api.streamtape.com/file/ul?login={}&key={}"
				hit_api = await session.get(Main_API.format(Config.STREAMTAPE_API_USERNAME, Config.STREAMTAPE_API_PASS))
				json_data = await hit_api.json()
				temp_api = json_data["result"]["url"]
				files = {'file1': open(output_vid, 'rb')}
				response = await session.post(temp_api, data=files)
				data_f = await response.json(content_type=None)
				download_link = data_f["result"]["url"]
				filename = output_vid.split("/")[-1].replace("_"," ")
				text_edit = f"File Uploaded to Streamtape!\n\n**File Name:** `{filename}`\n**Size:** `{humanbytes(file_size)}`\n**Link:** `{download_link}`"
				await editable.edit(text_edit, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Open Link", url=download_link)]]))
				await logs_msg.edit("Successfully Uploaded File to Streamtape!\n\nI am Free Now!", parse_mode="Markdown", disable_web_page_preview=True)
		except Exception as e:
			print(f"Error: {e}")
			await editable.edit("Sorry, Something went wrong!\n\nCan't Upload to Streamtape. You can report at [Support Group](https://t.me/Dads_links).")
			await logs_msg.edit(f"Got Error While Uploading to Streamtape!\n\nError: {e}")
		await delete_all()
		return

	await asyncio.sleep(5)
	try:
		sent_vid = await send_video_handler(bot, cmd, output_vid, video_thumbnail, duration, width, height, editable, logs_msg, file_size)
	except FloodWait as e:
		print(f"Got FloodWait of {e.x}s ...")
		await asyncio.sleep(e.x)
		await asyncio.sleep(5)
		sent_vid = await send_video_handler(bot, cmd, output_vid, video_thumbnail, duration, width, height, editable, logs_msg, file_size)
	except Exception as err:
		print(f"Unable to Upload Video: {err}")
		await logs_msg.edit(f"#ERROR: Unable to Upload Video!\n\n**Error:** `{err}`")
		await delete_all()
		return
	await delete_all()
	await editable.delete()
	forward_vid = await sent_vid.forward(Config.LOG_CHANNEL)
	await logs_msg.delete()
	await bot.send_message(chat_id=Config.LOG_CHANNEL, text=f"#WATERMARK_ADDED: Video Uploaded!\n\n{user_info}", reply_to_message_id=forward_vid.message_id, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Ban User", callback_data=f"ban_{cmd.from_user.id}")]]))


@AHBot.on_message(filters.command("cancel") & filters.private)
async def CancelWatermarkAdder(bot, cmd):
	if not await db.is_user_exist(cmd.from_user.id):
		await db.add_user(cmd.from_user.id)
		await bot.send_message(
			Config.LOG_CHANNEL,
			f"#NEW_USER: \n\nNew User [{cmd.from_user.first_name}](tg://user?id={cmd.from_user.id}) started @{Config.BOT_USERNAME} !!"
		)
	if not int(cmd.from_user.id) == Config.OWNER_ID:
		await cmd.reply_text("You Can't Use That Command!")
		return

	status = Config.DOWN_PATH + "/WatermarkAdder/status.json"
	with open(status, 'r+') as f:
		statusMsg = json.load(f)
		if 'pid' in statusMsg.keys():
			try:
				os.kill(statusMsg["pid"], 9)
				await delete_trash(status)
			except Exception as err:
				print(err)
		await delete_all()
		await bot.send_message(chat_id=Config.LOG_CHANNEL, text="#WATERMARK_ADDER: Stopped!")
		await cmd.reply_text("Watermark Adding Process Stopped!")
		try:
			await bot.edit_message_text(chat_id=int(statusMsg["chat_id"]), message_id=int(statusMsg["message"]), text="🚦🚦 Last Process Stopped 🚦🚦")
		except:
			pass


@AHBot.on_message(filters.private & filters.command("broadcast") & filters.user(Config.OWNER_ID) & filters.reply)
async def open_broadcast_handler(bot, message):
	await broadcast_handler(c=bot, m=message)


@AHBot.on_message(filters.private & filters.command("status"))
async def sts(_, m):
	status = Config.DOWN_PATH + "/WatermarkAdder/status.json"
	if os.path.exists(status):
		msg_text = "Sorry, Currently I am busy with another Task!\nI can't add Watermark at this moment."
	else:
		msg_text = "I am Free Now!\nSend me any video to add Watermark."
	if int(m.from_user.id) == Config.OWNER_ID:
		total_users = await db.total_users_count()
		msg_text += f"\n\n**Total Users in DB:** `{total_users}`"
	await m.reply_text(text=msg_text, parse_mode="Markdown", quote=True)


@AHBot.on_callback_query()
async def button(bot, cmd: CallbackQuery):
	cb_data = cmd.data

	# compression toggle callbacks
	if cb_data == "togglecompress":
		user_cfg = get_user_comp_settings(cmd.from_user.id)
		user_cfg["enabled"] = not user_cfg.get("enabled", True)
		# update inline keyboard display by re-opening settings
		await cmd.answer(f"Auto-compression set to {'Enabled' if user_cfg['enabled'] else 'Disabled'}", show_alert=False)
		try:
			await cmd.message.edit_text(text="Updating settings...")
		except:
			pass
		# reopen settings view
		await SettingsBot(bot, cmd.message)
		return

	if cb_data.startswith("crf_"):
		try:
			crf_val = int(cb_data.split("_", 1)[1])
			if crf_val < 10 or crf_val > 51:
				raise ValueError
		except:
			await cmd.answer("Invalid CRF value", show_alert=True)
			return
		user_cfg = get_user_comp_settings(cmd.from_user.id)
		user_cfg["crf"] = crf_val
		await cmd.answer(f"Compression CRF set to {crf_val}", show_alert=False)
		try:
			await cmd.message.edit_text(text="Updating settings...")
		except:
			pass
		await SettingsBot(bot, cmd.message)
		return

	if "refreshmeh" in cb_data:
		if Config.UPDATES_CHANNEL:
			invite_link = await bot.create_chat_invite_link(int(Config.UPDATES_CHANNEL))
			try:
				user = await bot.get_chat_member(int(Config.UPDATES_CHANNEL), cmd.message.chat.id)
				if user.status == "kicked":
					await cmd.message.edit(
						text="Sorry Sir, You are Banned to use me. Contact my [Support Group](https://t.me/Dads_links).",
						parse_mode="markdown",
						disable_web_page_preview=True
					)
					return
			except       
         InlineKeyboardButkeyboard = [
    [
        InlineKeyboardButton("5%", callback_data="size_5"),
        InlineKeyboardButton("7%", callback_data="size_7"),
        InlineKeyboardButton("10%", callback_data="size_10"),
        InlineKeyboardButton("15%", callback_data="size_15"),
        InlineKeyboardButton("20%", callback_data="size_20")
    ],
    [
        InlineKeyboardButton("25%", callback_data="size_25"),
        InlineKeyboardButton("30%", callback_data="size_30"),
        InlineKeyboardButton("35%", callback_data="size_35"),
        InlineKeyboardButton("40%", callback_data="size_40"),
        InlineKeyboardButton("45%", callback_data="size_45")
    ],
    [
        InlineKeyboardButton("Reset Settings to Default", callback_data="reset")
    ]
]

    

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
