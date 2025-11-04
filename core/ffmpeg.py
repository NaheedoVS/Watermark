# core/ffmpeg.py
# (c) @AbirHasan2005
import os
import math
import re
import json
import subprocess
import time
import shlex
import asyncio
from configs import Config
from typing import Tuple
from humanfriendly import format_timespan
from core.display_progress import TimeFormatter
from pyrogram.errors.exceptions.flood_420 import FloodWait

async def vidmark(the_media, message, working_dir, watermark_path, output_vid, total_time, logs_msg, status, mode, position, size):
    file_genertor_command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "quiet",
        "-progress",
        working_dir,
        "-i",
        the_media,
        "-i",
        watermark_path,
        "-filter_complex",
        f"[1][0]scale2ref=w='iw*{size}/100':h='ow/mdar'[wm][vid];[vid][wm]overlay={position}",
        "-c:v",
        "h264",
        "-preset",
        mode,
        "-tune",
        "film",
        "-c:a",
        "copy",
        output_vid
    ]
    COMPRESSION_START_TIME = time.time()
    process = await asyncio.create_subprocess_exec(
        *file_genertor_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    with open(status, 'r+') as f:
        statusMsg = json.load(f)
        statusMsg['pid'] = process.pid
        f.seek(0)
        json.dump(statusMsg, f, indent=2)
    while process.returncode != 0:
        await asyncio.sleep(5)
        with open(working_dir, 'r+') as file:
            text = file.read()
            frame = re.findall("frame=(\d+)", text)
            time_in_us=re.findall("out_time_ms=(\d+)", text)
            progress=re.findall("progress=(\w+)", text)
            speed=re.findall("speed=(\d+\.?\d*)", text)
            if len(frame):
                frame = int(frame[-1])
            else:
                frame = 1;
            if len(speed):
                speed = speed[-1]
            else:
                speed = 1;
            if len(time_in_us):
                time_in_us = time_in_us[-1]
            else:
                time_in_us = 1;
            if len(progress):
                if progress[-1] == "end":
                    break
            execution_time = TimeFormatter((time.time() - COMPRESSION_START_TIME)*1000)
            elapsed_time = int(time_in_us)/1000000
            difference = math.floor( (total_time - elapsed_time) / float(speed) )
            ETA = "-"
            if difference > 0:
                ETA = TimeFormatter(difference*1000)
            percentage = math.floor(elapsed_time * 100 / total_time)
            progress_str = "📊 **Progress:** {0}%\n`[{1}{2}]`".format(
                round(percentage, 2),
                ''.join(["▓" for i in range(math.floor(percentage / 10))]),
                ''.join(["░" for i in range(10 - math.floor(percentage / 10))])
                )
            stats = f'📦️ **Adding Watermark [Preset: `{mode}`]**\n\n' \
                    f'⏰️ **ETA:** `{ETA}`\n❇️ **Position:** `{position}`\n🔰 **PID:** `{process.pid}`\n🔄 **Duration: `{format_timespan(total_time)}`**\n\n' \
                    f'{progress_str}\n'
            try:
                await logs_msg.edit(text=stats)
                await message.edit(text=stats)
            except FloodWait as e:
                await asyncio.sleep(e.x)
                pass
            except:
                pass
        
    stdout, stderr = await process.communicate()
    e_response = stderr.decode().strip()
    t_response = stdout.decode().strip()
    print(e_response)
    print(t_response)
    if os.path.lexists(output_vid):
        return output_vid
    else:
        return None

async def take_screen_shot(video_file, output_directory, ttl):
    # https://stackoverflow.com/a/13891070/4723940
    out_put_file_name = output_directory + \
        "/" + str(time.time()) + ".jpg"
    file_genertor_command = [
        "ffmpeg",
        "-ss",
        str(ttl),
        "-i",
        video_file,
        "-vframes",
        "1",
        out_put_file_name
    ]
    # width = "90"
    process = await asyncio.create_subprocess_exec(
        *file_genertor_command,
        # stdout must a pipe to be accessible as process.stdout
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    # Wait for the subprocess to finish
    stdout, stderr = await process.communicate()
    e_response = stderr.decode().strip()
    t_response = stdout.decode().strip()
    if os.path.lexists(out_put_file_name):
        return out_put_file_name
    else:
        return None

# ---------------------------
# New: compress_video
# ---------------------------
async def compress_video(input_file, message, progress_file, output_path, total_time, logs_msg, status_path):
    """
    Compress video in a near-lossless way and return the compressed file path.
    Uses libx264 with CRF=18 and preset=slow and copies audio stream.
    progress_file: path used by ffmpeg -progress (must be writable)
    status_path: path to status json (to write pid)
    """
    # Build ffmpeg command
    file_genertor_command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "quiet",
        "-progress",
        progress_file,
        "-i",
        input_file,
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "18",
        "-c:a",
        "copy",
        output_path
    ]

    start_time = time.time()
    process = await asyncio.create_subprocess_exec(
        *file_genertor_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # write pid to status file
    try:
        with open(status_path, 'r+') as f:
            statusMsg = json.load(f)
            statusMsg['pid'] = process.pid
            f.seek(0)
            json.dump(statusMsg, f, indent=2)
    except Exception:
        # not fatal; proceed
        pass

    # monitor progress (read progress_file)
    while True:
        await asyncio.sleep(5)
        try:
            with open(progress_file, 'r+') as file:
                text = file.read()
        except Exception:
            text = ""

        time_in_us = re.findall("out_time_ms=(\d+)", text)
        progress = re.findall("progress=(\w+)", text)
        speed = re.findall("speed=(\d+\.?\d*)", text)

        if len(speed):
            try:
                speed_val = float(speed[-1])
            except:
                speed_val = 1.0
        else:
            speed_val = 1.0

        if len(time_in_us):
            try:
                elapsed_time = int(time_in_us[-1]) / 1_000_000
            except:
                elapsed_time = 1
        else:
            elapsed_time = 1

        if len(progress) and progress[-1] == "end":
            break

        # safe ETA calc
        try:
            difference = (total_time - elapsed_time) / speed_val if total_time and speed_val else 0
        except:
            difference = 0

        ETA = TimeFormatter(difference * 1000) if difference > 0 else "-"
        percentage = int(elapsed_time * 100 / total_time) if total_time else 0
        if percentage < 0:
            percentage = 0
        if percentage > 100:
            percentage = 100

        progress_bar = f"📊 {percentage}% [{'▓' * (percentage // 10)}{'░' * (10 - (percentage // 10))}]"

        stats = (
            f"🎞️ **Compressing Video (CRF=18, slow)**\n"
            f"⏱️ ETA: `{ETA}`\n"
            f"⚙️ PID: `{process.pid}`\n"
            f"🕒 Duration: `{format_timespan(total_time)}`\n\n"
            f"{progress_bar}"
        )
        try:
            await message.edit(text=stats)
            if logs_msg:
                await logs_msg.edit(text=stats)
        except FloodWait as e:
            await asyncio.sleep(e.x)
        except Exception:
            pass

    # wait for ffmpeg to finish
    stdout, stderr = await process.communicate()
    e_response = stderr.decode().strip()
    t_response = stdout.decode().strip()
    print("compress stderr:", e_response)
    print("compress stdout:", t_response)

    if os.path.lexists(output_path):
        return output_path
    else:
        return None


async def take_screen_shot(video_file: str, output_directory: str, ttl: int) -> Optional[str]:
    """Capture a frame at given timestamp."""
    output_path = Path(output_directory) / f"{int(time.time())}.jpg"

    command = [
        "ffmpeg",
        "-ss", str(ttl),
        "-i", video_file,
        "-frames:v", "1",
        "-q:v", "2",
        str(output_path)
    ]

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await process.wait()

    if output_path.exists():
        return str(output_path)
    return None


# ────────────────────────────────
# 🔧 Helper Functions
# ────────────────────────────────
def _extract_value(text: str, pattern: str) -> Optional[str]:
    """Extract value from FFmpeg progress log using regex."""
    match = re.findall(pattern, text)
    return match[-1] if match else None


async def _safe_edit(msg, text: str):
    """Edit Telegram messages safely to avoid flood errors."""
    if not msg:
        return
    try:
        await msg.edit_text(text, disable_web_page_preview=True)
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception:
        pass
            except FloodWait as e:
                await asyncio.sleep(e.x)
                pass
            except:
                pass
        
    stdout, stderr = await process.communicate()
    e_response = stderr.decode().strip()
    t_response = stdout.decode().strip()
    print(e_response)
    print(t_response)
    if os.path.lexists(output_vid):
        return output_vid
    else:
        return None

async def take_screen_shot(video_file, output_directory, ttl):
    # https://stackoverflow.com/a/13891070/4723940
    out_put_file_name = output_directory + \
        "/" + str(time.time()) + ".jpg"
    file_genertor_command = [
        "ffmpeg",
        "-ss",
        str(ttl),
        "-i",
        video_file,
        "-vframes",
        "1",
        out_put_file_name
    ]
    # width = "90"
    process = await asyncio.create_subprocess_exec(
        *file_genertor_command,
        # stdout must a pipe to be accessible as process.stdout
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    # Wait for the subprocess to finish
    stdout, stderr = await process.communicate()
    e_response = stderr.decode().strip()
    t_response = stdout.decode().strip()
    if os.path.lexists(out_put_file_name):
        return out_put_file_name
    else:
        return None
