from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import wave
from datetime import datetime
import os
from pathlib import Path

import edge_tts
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from moviepy import (
    AudioFileClip,
    CompositeAudioClip,
    VideoClip,
    concatenate_audioclips,
)


WIDTH = 720
HEIGHT = 1280
FPS = 24
SAMPLE_RATE = 44100
FONT_REGULAR = Path("C:/Windows/Fonts/msyh.ttc")
FONT_BOLD = Path("C:/Windows/Fonts/msyhbd.ttc")
FONT_MONO = Path("C:/Windows/Fonts/consola.ttf")

ROOT = Path(os.environ.get("DOUYIN_PROJECT_ROOT") or Path(__file__).resolve().parents[1]).expanduser().resolve()

SEGMENTS = [
    {
        "text": "开完会最痛苦的，不是开会。是会后，还得一条一条手抄待办。",
        "caption": "最痛苦的，是会后手抄待办",
        "rate": "+11%",
        "pitch": "+1Hz",
    },
    {
        "text": "其实，把原始记录直接贴进去，再加一句固定要求，就够了。",
        "caption": "原始记录，直接贴进去",
        "rate": "+7%",
        "pitch": "-1Hz",
    },
    {
        "text": "请按任务、负责人、截止时间和风险，整理成四列。",
        "caption": "固定要求：整理成四列",
        "rate": "+4%",
        "pitch": "-2Hz",
    },
    {
        "text": "几秒钟后，谁做什么、哪天交，一眼就能看清。",
        "caption": "谁做什么，哪天交",
        "rate": "+10%",
        "pitch": "+1Hz",
    },
    {
        "text": "但人名、日期和金额，一定自己再核一遍。这个不能偷懒。",
        "caption": "人名、日期、金额必须复核",
        "rate": "+2%",
        "pitch": "-3Hz",
    },
    {
        "text": "这段提示词我放在画面里。先收藏，下次开会直接用。",
        "caption": "先收藏，下次开会直接用",
        "rate": "+7%",
        "pitch": "+1Hz",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Human-paced Douyin workflow prototype v2")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--voice-dir", type=Path, help="Optional directory containing 01.wav/mp3 ... 06.wav/mp3")
    parser.add_argument("--output-name", default="douyin_workflow_v2.mp4")
    return parser.parse_args()


def fnt(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def ease_out(value: float) -> float:
    value = clamp(value)
    return 1 - (1 - value) ** 3


def ease_in_out(value: float) -> float:
    value = clamp(value)
    return 3 * value**2 - 2 * value**3


def rounded_card(base: Image.Image, box: tuple[int, int, int, int], *, radius: int = 28, fill=(255, 255, 255, 255), shadow=18) -> None:
    x1, y1, x2, y2 = box
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rounded_rectangle((x1 + 4, y1 + 10, x2 + 4, y2 + 10), radius=radius, fill=(58, 45, 31, shadow))
    layer = layer.filter(ImageFilter.GaussianBlur(12))
    base.alpha_composite(layer)
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def centered_text(draw: ImageDraw.ImageDraw, y: int, text: str, font_obj, fill, *, stroke_width=0, stroke_fill=None) -> None:
    box = draw.textbbox((0, 0), text, font=font_obj, stroke_width=stroke_width)
    x = (WIDTH - (box[2] - box[0])) // 2
    draw.text((x, y), text, font=font_obj, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)


def draw_caption(draw: ImageDraw.ImageDraw, text: str, accent: str) -> None:
    box = draw.textbbox((0, 0), text, font=fnt(FONT_BOLD, 39))
    w = min(WIDTH - 72, box[2] - box[0] + 54)
    x = (WIDTH - w) // 2
    draw.rounded_rectangle((x, 1100, x + w, 1180), radius=24, fill=(30, 28, 25, 232))
    centered_text(draw, 1117, text, fnt(FONT_BOLD, 39), "#FFFDF8")
    draw.rounded_rectangle((x + 18, 1170, x + w - 18, 1176), radius=3, fill=accent)


def draw_header(draw: ImageDraw.ImageDraw, progress: float) -> None:
    draw.rounded_rectangle((42, 44, 272, 98), radius=27, fill="#25221E")
    draw.text((66, 57), "真实工作流演示", font=fnt(FONT_BOLD, 24), fill="#FFF8EA")
    draw.rounded_rectangle((42, 120, 678, 130), radius=5, fill="#DFD8CA")
    draw.rounded_rectangle((42, 120, 42 + int(636 * progress), 130), radius=5, fill="#F26B4A")


def paper_background() -> Image.Image:
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
    base = np.zeros((HEIGHT, WIDTH, 3), dtype=np.float32)
    base[:] = np.array([242, 236, 224], dtype=np.float32)
    base += 4.0 * np.sin(xx / 95.0)[..., None]
    base += 2.0 * np.cos(yy / 71.0)[..., None]
    rng = np.random.default_rng(20260817)
    base += rng.normal(0, 1.8, base.shape)
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).convert("RGBA")


BACKGROUND = paper_background()


def scene_hook(image: Image.Image, draw: ImageDraw.ImageDraw, local: float, duration: float) -> None:
    p1 = ease_out(local / 0.8)
    y = int(230 - 40 * (1 - p1))
    centered_text(draw, y, "开完会最痛苦的", fnt(FONT_BOLD, 59), "#26211B")
    if local > 0.55:
        p2 = ease_out((local - 0.55) / 0.55)
        centered_text(draw, 360, "不是开会", fnt(FONT_BOLD, 70), "#837A6C")
        line_w = int(355 * p2)
        draw.line(((WIDTH - line_w) // 2, 408, (WIDTH + line_w) // 2, 394), fill="#E45B3D", width=11)
    if local > 1.35:
        p3 = ease_out((local - 1.35) / 0.65)
        x1 = int(80 + 50 * (1 - p3))
        rounded_card(image, (x1, 535, 640, 845), radius=32, fill=(255, 252, 245, 255), shadow=28)
        draw = ImageDraw.Draw(image)
        draw.text((x1 + 38, 575), "会后待办", font=fnt(FONT_BOLD, 32), fill="#322C25")
        notes = [("□ 改报价", "今天？"), ("□ 给客户回邮件", "谁负责？"), ("□ 新版本上线", "哪一天？")]
        for idx, (task, question) in enumerate(notes):
            yy = 650 + idx * 62
            draw.text((x1 + 40, yy), task, font=fnt(FONT_REGULAR, 28), fill="#423B32")
            draw.text((x1 + 338, yy + 3), question, font=fnt(FONT_BOLD, 24), fill="#E45B3D")
    if local > duration - 1.2:
        p4 = ease_out((local - duration + 1.2) / 0.55)
        centered_text(draw, 905, "还得一条一条手抄", fnt(FONT_BOLD, 50), "#E45B3D")
        if p4 > 0.5:
            draw.arc((108, 886, 612, 982), start=5, end=175, fill="#E45B3D", width=5)


def scene_notes(image: Image.Image, draw: ImageDraw.ImageDraw, local: float, duration: float) -> None:
    rounded_card(image, (54, 185, 666, 920), radius=32, fill=(255, 253, 248, 255), shadow=26)
    draw = ImageDraw.Draw(image)
    draw.text((92, 225), "8月17日  产品例会", font=fnt(FONT_BOLD, 31), fill="#302B25")
    draw.line((92, 278, 628, 278), fill="#DDD4C5", width=2)
    raw_lines = [
        "客户说价格还要再谈一下……",
        "小周：新版周五之前给测试",
        "报价表李姐今天下班前改",
        "上线日期可能是 8 月 22 日",
        "风险：接口权限还没确认",
    ]
    shown = min(len(raw_lines), max(1, int(local / max(0.45, duration / 7)) + 1))
    for idx, line in enumerate(raw_lines[:shown]):
        y = 330 + idx * 94
        draw.text((92, y), line, font=fnt(FONT_REGULAR, 28), fill="#4E473D")
        if idx in {1, 2, 3}:
            start = 92 + (58 if idx == 1 else 120)
            end = min(612, start + 170)
            draw.line((start, y + 43, end, y + 43), fill="#F5B63C", width=7)
    if local > duration * 0.55:
        p = ease_out((local - duration * 0.55) / 0.7)
        x = int(92 + (1 - p) * 80)
        draw.rounded_rectangle((x, 835, 628, 900), radius=18, fill="#24211D")
        draw.text((x + 28, 850), "Ctrl + A  →  复制全部记录", font=fnt(FONT_BOLD, 27), fill="#FFF7E8")


def scene_prompt(image: Image.Image, draw: ImageDraw.ImageDraw, local: float, duration: float) -> None:
    draw.rounded_rectangle((66, 190, 654, 965), radius=38, fill="#ECE7DD", outline="#D2C8B9", width=2)
    draw.ellipse((98, 225, 146, 273), fill="#2B2824")
    draw.text((164, 229), "任务整理助手", font=fnt(FONT_BOLD, 29), fill="#2D2923")
    rounded_card(image, (100, 320, 620, 790), radius=28, fill=(255, 255, 255, 255), shadow=18)
    draw = ImageDraw.Draw(image)
    prompt = "请把上面的会议记录，按以下格式整理：\n\n1. 任务\n2. 负责人\n3. 截止时间\n4. 风险"
    chars = int(len(prompt) * ease_in_out(local / max(1.0, duration * 0.72)))
    visible = prompt[:chars]
    draw.multiline_text((132, 360), visible, font=fnt(FONT_REGULAR, 31), fill="#35302A", spacing=20)
    if int(local * 2) % 2 == 0 and chars < len(prompt):
        rows = visible.split("\n")
        last = rows[-1]
        tx = 132 + draw.textlength(last, font=fnt(FONT_REGULAR, 31))
        ty = 360 + (len(rows) - 1) * 57
        draw.rectangle((tx + 3, ty, tx + 6, ty + 38), fill="#E45B3D")
    if local > duration * 0.68:
        p = ease_out((local - duration * 0.68) / 0.55)
        x1 = int(430 + 70 * (1 - p))
        draw.rounded_rectangle((x1, 835, 620, 910), radius=24, fill="#E45B3D")
        draw.text((x1 + 44, 855), "发送", font=fnt(FONT_BOLD, 31), fill="#FFFDF8")


def scene_table(image: Image.Image, draw: ImageDraw.ImageDraw, local: float, duration: float) -> None:
    rounded_card(image, (36, 180, 684, 930), radius=28, fill=(255, 253, 248, 255), shadow=26)
    draw = ImageDraw.Draw(image)
    draw.text((68, 220), "整理结果", font=fnt(FONT_BOLD, 36), fill="#28231E")
    headers = [("任务", 68), ("负责人", 300), ("截止", 445), ("风险", 570)]
    draw.rounded_rectangle((62, 285, 658, 345), radius=15, fill="#2B2824")
    for label, x in headers:
        draw.text((x, 300), label, font=fnt(FONT_BOLD, 23), fill="#FFF8EA")
    rows = [
        ("修改报价", "李姐", "今天", "低"),
        ("提交测试版", "小周", "周五", "中"),
        ("确认接口权限", "王工", "8/20", "高"),
    ]
    for idx, row in enumerate(rows):
        appear = ease_out((local - 0.45 - idx * 0.48) / 0.52)
        if appear <= 0:
            continue
        y = 380 + idx * 145
        xoff = int(70 * (1 - appear))
        draw.rounded_rectangle((62 + xoff, y, 658 + xoff, y + 112), radius=18, fill="#F4EFE6")
        xs = [78, 310, 465, 590]
        colors = ["#342F28", "#256A60", "#8A5A12", "#D84F35" if row[3] == "高" else "#6A6258"]
        for value, x, color in zip(row, xs, colors):
            draw.text((x + xoff, y + 34), value, font=fnt(FONT_BOLD if x > 200 else FONT_REGULAR, 25), fill=color)
    if local > duration * 0.62:
        p = ease_out((local - duration * 0.62) / 0.7)
        draw.rounded_rectangle((115, 835, int(115 + 490 * p), 892), radius=20, fill="#F5B63C")
        if p > 0.75:
            centered_text(draw, 848, "谁做什么、哪天交，一眼看清", fnt(FONT_BOLD, 27), "#332A1F")


def scene_warning(image: Image.Image, draw: ImageDraw.ImageDraw, local: float, duration: float) -> None:
    centered_text(draw, 215, "但是，有三项不能交给 AI", fnt(FONT_BOLD, 43), "#2A2520")
    cards = [("人名", "别张冠李戴"), ("日期", "别错一天"), ("金额", "别多一个零")]
    for idx, (title, body) in enumerate(cards):
        p = ease_out((local - idx * 0.35) / 0.55)
        if p <= 0:
            continue
        y = 360 + idx * 174
        x = int(74 + (1 - p) * 90)
        rounded_card(image, (x, y, 646, y + 132), radius=25, fill=(255, 252, 246, 255), shadow=22)
        draw = ImageDraw.Draw(image)
        draw.ellipse((x + 28, y + 32, x + 94, y + 98), fill="#E45B3D")
        centered = fnt(FONT_BOLD, 31)
        tbox = draw.textbbox((0, 0), str(idx + 1), font=centered)
        draw.text((x + 61 - (tbox[2] - tbox[0]) / 2, y + 45), str(idx + 1), font=centered, fill="#FFFFFF")
        draw.text((x + 122, y + 24), title, font=fnt(FONT_BOLD, 34), fill="#2D2822")
        draw.text((x + 122, y + 75), body, font=fnt(FONT_REGULAR, 25), fill="#766C5F")
    if local > duration * 0.58:
        p = ease_out((local - duration * 0.58) / 0.7)
        angle = -8 + 8 * (1 - p)
        stamp = Image.new("RGBA", (390, 150), (0, 0, 0, 0))
        sd = ImageDraw.Draw(stamp)
        sd.rounded_rectangle((8, 8, 382, 142), radius=18, outline="#D94D35", width=8)
        sd.text((48, 34), "必须人工复核", font=fnt(FONT_BOLD, 46), fill="#D94D35")
        stamp = stamp.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
        image.alpha_composite(stamp, (165, 860))


def scene_cta(image: Image.Image, draw: ImageDraw.ImageDraw, local: float, duration: float) -> None:
    centered_text(draw, 190, "把这段提示词存下来", fnt(FONT_BOLD, 49), "#2B2620")
    rounded_card(image, (58, 300, 662, 820), radius=30, fill=(42, 39, 35, 255), shadow=30)
    draw = ImageDraw.Draw(image)
    prompt = "把会议记录整理成表格：\n任务｜负责人｜截止时间｜风险\n\n无法确认的内容标记【待核实】，\n不要自行补全人名、日期和金额。"
    draw.multiline_text((94, 345), prompt, font=fnt(FONT_REGULAR, 29), fill="#FFF9EE", spacing=22)
    if local > 0.6:
        p = ease_out((local - 0.6) / 0.55)
        draw.rounded_rectangle((438, 730, int(438 + 176 * p), 790), radius=20, fill="#F5B63C")
        if p > 0.75:
            draw.text((472, 744), "截图保存", font=fnt(FONT_BOLD, 25), fill="#342B21")
    if local > duration * 0.52:
        p = ease_out((local - duration * 0.52) / 0.65)
        centered_text(draw, int(900 + 22 * (1 - p)), "先收藏，下次开会直接用", fnt(FONT_BOLD, 44), "#E45B3D")
        centered_text(draw, 970, "后续实测：哪些工具整理得更准", fnt(FONT_REGULAR, 27), "#5F574C")


SCENES = [scene_hook, scene_notes, scene_prompt, scene_table, scene_warning, scene_cta]
ACCENTS = ["#E45B3D", "#F5B63C", "#3C8C80", "#F5B63C", "#E45B3D", "#3C8C80"]


async def synthesize_segments(run_dir: Path, voice_dir: Path | None) -> list[Path]:
    paths: list[Path] = []
    if voice_dir:
        for idx in range(len(SEGMENTS)):
            candidates = list(voice_dir.glob(f"{idx + 1:02d}.*"))
            if not candidates:
                raise FileNotFoundError(f"Missing human voice segment {idx + 1:02d} in {voice_dir}")
            paths.append(candidates[0])
        return paths

    for idx, segment in enumerate(SEGMENTS):
        path = run_dir / f"voice_{idx + 1:02d}.mp3"
        communicate = edge_tts.Communicate(
            segment["text"],
            voice="zh-CN-YunxiNeural",
            rate=segment["rate"],
            pitch=segment["pitch"],
            volume="+0%",
        )
        await communicate.save(str(path))
        paths.append(path)
    return paths


def write_srt(path: Path, starts: list[float], durations: list[float]) -> None:
    def stamp(seconds: float) -> str:
        milliseconds = int(round(seconds * 1000))
        h, rem = divmod(milliseconds, 3_600_000)
        m, rem = divmod(rem, 60_000)
        s, ms = divmod(rem, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    blocks = []
    for idx, (start, duration, segment) in enumerate(zip(starts, durations, SEGMENTS), start=1):
        blocks.append(f"{idx}\n{stamp(start)} --> {stamp(start + duration)}\n{segment['text']}\n")
    path.write_text("\n".join(blocks), encoding="utf-8")


def generate_audio_bed(path: Path, duration: float, transitions: list[float]) -> None:
    count = int(duration * SAMPLE_RATE)
    t = np.arange(count, dtype=np.float64) / SAMPLE_RATE
    rng = np.random.default_rng(817)
    audio = 0.004 * rng.normal(0, 1, count)
    audio += 0.007 * np.sin(2 * np.pi * 110 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.09 * t))
    beat_period = 60 / 92
    for beat in np.arange(0, duration, beat_period):
        start = int(beat * SAMPLE_RATE)
        length = min(int(0.14 * SAMPLE_RATE), count - start)
        if length <= 0:
            continue
        tt = np.arange(length) / SAMPLE_RATE
        audio[start : start + length] += 0.035 * np.sin(2 * np.pi * (72 - 22 * tt) * tt) * np.exp(-28 * tt)
    for transition in transitions[1:]:
        start = int(max(0, transition - 0.08) * SAMPLE_RATE)
        length = min(int(0.24 * SAMPLE_RATE), count - start)
        if length <= 0:
            continue
        tt = np.arange(length) / SAMPLE_RATE
        chirp = np.sin(2 * np.pi * (520 * tt + 900 * tt**2))
        audio[start : start + length] += 0.045 * chirp * np.exp(-17 * tt)
    fade = min(int(0.5 * SAMPLE_RATE), count // 2)
    if fade:
        audio[:fade] *= np.linspace(0, 1, fade)
        audio[-fade:] *= np.linspace(1, 0, fade)
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    stereo = np.column_stack([pcm, pcm]).ravel().tobytes()
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(stereo)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    outputs = root / "outputs"
    run_dir = root / "workspace" / "v2_run"
    outputs.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    voice_paths = asyncio.run(synthesize_segments(run_dir, args.voice_dir.resolve() if args.voice_dir else None))
    voice_clips = [AudioFileClip(str(path)) for path in voice_paths]
    durations = [float(clip.duration) for clip in voice_clips]
    starts: list[float] = []
    cursor = 0.0
    for duration in durations:
        starts.append(cursor)
        cursor += duration
    total_duration = cursor

    captions = run_dir / "captions_v2.srt"
    write_srt(captions, starts, durations)
    bed_path = run_dir / "original_audio_bed.wav"
    generate_audio_bed(bed_path, total_duration, starts)

    def make_frame(t: float) -> np.ndarray:
        index = len(starts) - 1
        for candidate, start in enumerate(starts):
            if t < start + durations[candidate]:
                index = candidate
                break
        local = t - starts[index]
        image = BACKGROUND.copy()
        draw = ImageDraw.Draw(image)
        draw_header(draw, t / total_duration)
        SCENES[index](image, draw, local, durations[index])
        draw = ImageDraw.Draw(image)
        draw_caption(draw, SEGMENTS[index]["caption"], ACCENTS[index])
        draw.text((44, 1215), "演示内容 · 合成配音", font=fnt(FONT_REGULAR, 20), fill="#746B60")
        draw.text((627, 1215), f"{index + 1}/6", font=fnt(FONT_BOLD, 20), fill="#746B60")
        return np.asarray(image.convert("RGB"))

    voice = concatenate_audioclips(voice_clips)
    bed = AudioFileClip(str(bed_path)).with_volume_scaled(0.55)
    mixed_audio = CompositeAudioClip([voice.with_volume_scaled(1.35), bed]).with_duration(total_duration)
    video = VideoClip(frame_function=make_frame, duration=total_duration).with_audio(mixed_audio)
    video_path = outputs / args.output_name
    video.write_videofile(
        str(video_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        bitrate="2200k",
        audio_bitrate="160k",
        threads=4,
        logger="bar",
    )

    video.close()
    mixed_audio.close()
    bed.close()
    voice.close()
    for clip in voice_clips:
        clip.close()

    script_path = outputs / "voice_script_v2.md"
    script_path.write_text(
        "# 分段口播稿（可用本人录音替换）\n\n"
        + "\n\n".join(f"{idx + 1:02d}. {segment['text']}" for idx, segment in enumerate(SEGMENTS))
        + "\n\n录音时每段单独保存为 `01.wav` 至 `06.wav`，再用 `--voice-dir` 指向目录。\n",
        encoding="utf-8",
    )

    manifest = {
        "schema_version": 2,
        "job_id": "office-meeting-notes-v2",
        "created_at": datetime.now().astimezone().isoformat(),
        "state": "AWAITING_REFERENCE_REVIEW",
        "content": {
            "audience": "25-40岁经常开会、需要整理待办的上班族",
            "title_candidates": [
                "开完会别再手抄待办了",
                "这段提示词，把会议记录变成待办表",
                "会议纪要最浪费时间的，其实是这一步",
            ],
            "description": "把会议记录整理成任务、负责人、截止时间和风险四列；人名、日期、金额必须人工复核。",
            "tags": ["办公技巧", "会议纪要", "效率提升"],
            "ai_generated": True,
            "voice": "synthetic:zh-CN-YunxiNeural:segmented",
            "visual_style": "warm-paper-workbench-demo",
        },
        "artifacts": {
            "video": str(video_path),
            "captions": str(captions),
            "voice_script": str(script_path),
            "audio_bed": str(bed_path),
        },
        "qa": {
            "duration_seconds": round(total_duration, 2),
            "width": WIDTH,
            "height": HEIGHT,
            "fps": FPS,
            "aspect_ratio": "9:16",
            "has_audio": True,
            "has_subtitles": True,
            "video_bytes": video_path.stat().st_size,
            "sha256": sha256(video_path),
            "scene_count": len(SEGMENTS),
            "max_static_scene_seconds": round(max(durations), 2),
        },
        "publish_gate": {
            "approved": False,
            "must_not_publish": True,
            "blocking_reasons": [
                "尚未完成同赛道参考视频学习",
                "尚未确认最终标题与首帧",
                "尚未确认是否改用本人配音",
                "尚未确认AI生成合成内容标识",
            ],
            "allowed_next_states": ["AWAITING_APPROVAL"],
        },
    }
    manifest_path = outputs / "publish_job_v2.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"VIDEO={video_path}")
    print(f"MANIFEST={manifest_path}")
    print(f"DURATION={total_duration:.2f}")
    print(f"STATE={manifest['state']}")


if __name__ == "__main__":
    main()
