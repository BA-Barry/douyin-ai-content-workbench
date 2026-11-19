from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import textwrap
from datetime import datetime
from pathlib import Path

import edge_tts
from PIL import Image, ImageDraw, ImageFont
from moviepy import AudioFileClip, CompositeVideoClip, ImageClip, TextClip, concatenate_videoclips
from moviepy.video.tools.subtitles import SubtitlesClip


WIDTH = 720
HEIGHT = 1280
FPS = 24
FONT_REGULAR = Path("C:/Windows/Fonts/msyh.ttc")
FONT_BOLD = Path("C:/Windows/Fonts/msyhbd.ttc")


SECTIONS = [
    {
        "eyebrow": "30秒办公急救",
        "headline": "会议结束后\n别再手抄待办",
        "body": "用一套固定提示词，把会议记录整理成负责人、截止时间和下一步行动。",
        "accent": "#72E6FF",
    },
    {
        "eyebrow": "第一步",
        "headline": "先清理原始记录",
        "body": "删除寒暄和重复内容，只保留决定、数字、负责人和时间。",
        "accent": "#A7F3D0",
    },
    {
        "eyebrow": "第二步",
        "headline": "要求固定格式",
        "body": "提示词写清楚：按任务、负责人、截止时间、风险四列输出。",
        "accent": "#FDE68A",
    },
    {
        "eyebrow": "第三步",
        "headline": "必须人工复核",
        "body": "重点检查人名、日期和金额。AI只负责整理，不能替你确认事实。",
        "accent": "#FDA4AF",
    },
    {
        "eyebrow": "保存这条",
        "headline": "下次开会直接复用",
        "body": "关注后续实测：免费工具和付费工具，谁整理得更准。",
        "accent": "#C4B5FD",
    },
]


NARRATION = (
    "会议结束后，别再一条一条手抄待办。"
    "第一步，清理原始记录，删除寒暄和重复内容，只保留决定、数字、负责人和时间。"
    "第二步，要求固定格式，让人工智能按任务、负责人、截止时间和风险四列输出。"
    "第三步，必须人工复核，重点检查人名、日期和金额。人工智能只负责整理，不能替你确认事实。"
    "保存这条，下次开会直接复用。后续我会实测免费工具和付费工具，谁整理得更准。"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Zero-key semi-automated short-video prototype")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    return parser.parse_args()


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def draw_wrapped(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, *, font_obj, fill, width_chars: int, spacing: int = 14):
    wrapped = "\n".join(textwrap.wrap(text, width=width_chars, break_long_words=True, break_on_hyphens=False))
    draw.multiline_text(xy, wrapped, font=font_obj, fill=fill, spacing=spacing)


def make_slide(section: dict[str, str], index: int, target: Path) -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#09111F")
    draw = ImageDraw.Draw(image)

    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(9 + 13 * t)
        g = int(17 + 18 * t)
        b = int(31 + 29 * t)
        draw.line((0, y, WIDTH, y), fill=(r, g, b))

    accent = section["accent"]
    draw.ellipse((500, -120, 850, 230), fill=accent)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle((44, 80, 676, 1160), radius=36, fill=(8, 16, 31, 224), outline=(255, 255, 255, 26), width=2)
    image = Image.alpha_composite(image.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((76, 126, 300, 184), radius=29, fill=accent)
    draw.text((98, 137), section["eyebrow"], font=font(FONT_BOLD, 25), fill="#06101D")

    draw.multiline_text((76, 255), section["headline"], font=font(FONT_BOLD, 58), fill="#F8FAFC", spacing=12)
    draw_wrapped(draw, (76, 520), section["body"], font_obj=font(FONT_REGULAR, 35), fill="#DCE7F5", width_chars=15, spacing=18)

    card_y = 790
    draw.rounded_rectangle((76, card_y, 644, card_y + 220), radius=28, fill="#101F36", outline=accent, width=3)
    columns = [("任务", "整理会议纪要"), ("负责人", "明确到人"), ("截止", "写具体日期")]
    for col, (label, value) in enumerate(columns):
        x = 100 + col * 180
        draw.text((x, card_y + 38), label, font=font(FONT_REGULAR, 23), fill="#8FA5BF")
        draw_wrapped(draw, (x, card_y + 88), value, font_obj=font(FONT_BOLD, 26), fill="#FFFFFF", width_chars=5, spacing=8)

    draw.text((76, 1095), "流程示意 · AI配音", font=font(FONT_REGULAR, 22), fill="#7F93AC")
    draw.text((590, 1095), f"{index + 1}/5", font=font(FONT_BOLD, 22), fill=accent)
    image.convert("RGB").save(target, quality=95)


async def synthesize(text: str, audio_path: Path, srt_path: Path) -> None:
    communicate = edge_tts.Communicate(
        text,
        voice="zh-CN-XiaoxiaoNeural",
        rate="+8%",
        boundary="WordBoundary",
    )
    submaker = edge_tts.SubMaker()
    with audio_path.open("wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] in {"WordBoundary", "SentenceBoundary"}:
                submaker.feed(chunk)
    srt_path.write_text(submaker.get_srt(), encoding="utf-8")


def render(slides: list[Path], audio_path: Path, srt_path: Path, output_path: Path) -> dict[str, object]:
    audio = AudioFileClip(str(audio_path))
    weights = [len(section["body"]) + len(section["headline"]) for section in SECTIONS]
    weight_sum = sum(weights)
    durations = [max(3.2, audio.duration * weight / weight_sum) for weight in weights]
    scale = audio.duration / sum(durations)
    durations = [duration * scale for duration in durations]

    clips = [ImageClip(str(slide)).with_duration(duration) for slide, duration in zip(slides, durations)]
    base = concatenate_videoclips(clips, method="compose").with_audio(audio)

    def subtitle_factory(text: str) -> TextClip:
        return TextClip(
            font=str(FONT_BOLD),
            text=text,
            font_size=38,
            size=(620, None),
            margin=(24, 18),
            color="#FFFFFF",
            bg_color="#000000A8",
            stroke_color="#000000",
            stroke_width=2,
            method="caption",
            text_align="center",
        )

    subtitles = SubtitlesClip(
        str(srt_path), make_textclip=subtitle_factory, encoding="utf-8"
    ).with_position(("center", 1030))
    final = CompositeVideoClip([base, subtitles], size=(WIDTH, HEIGHT)).with_duration(audio.duration)
    final.write_videofile(
        str(output_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="veryfast",
        threads=4,
        logger="bar",
    )
    final.close()
    base.close()
    audio.close()

    return {"duration_seconds": round(float(durations and sum(durations)), 2), "width": WIDTH, "height": HEIGHT, "fps": FPS}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    args = parse_args()
    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = args.work.resolve() / "prototype_run"
    run_dir.mkdir(parents=True, exist_ok=True)

    slides = []
    for index, section in enumerate(SECTIONS):
        slide = run_dir / f"slide-{index + 1}.png"
        make_slide(section, index, slide)
        slides.append(slide)

    audio_path = run_dir / "narration.mp3"
    srt_path = run_dir / "captions.srt"
    asyncio.run(synthesize(NARRATION, audio_path, srt_path))

    video_path = output_dir / "douyin_workflow_prototype.mp4"
    qa = render(slides, audio_path, srt_path, video_path)
    qa.update(
        {
            "aspect_ratio": "9:16",
            "has_audio": audio_path.stat().st_size > 0,
            "has_subtitles": srt_path.stat().st_size > 0,
            "video_bytes": video_path.stat().st_size,
            "sha256": sha256(video_path),
        }
    )

    job = {
        "job_id": "prototype-001",
        "created_at": datetime.now().astimezone().isoformat(),
        "state": "AWAITING_APPROVAL",
        "content": {
            "audience": "25-40岁非技术上班族",
            "title": "会议结束后，别再手抄待办",
            "description": "把会议记录整理成任务、负责人、截止时间和风险四列。AI只负责整理，关键事实必须人工复核。",
            "tags": ["办公技巧", "效率提升", "AI工具"],
            "ai_generated": True,
            "voice": "synthetic:zh-CN-XiaoxiaoNeural",
        },
        "artifacts": {
            "video": str(video_path),
            "cover": str(slides[0]),
            "captions": str(srt_path),
        },
        "qa": qa,
        "publish_gate": {
            "approved": False,
            "must_not_publish": True,
            "required_user_actions": ["确认标题和成片", "确认AI内容声明", "必要时完成登录或验证码"],
        },
    }
    manifest_path = output_dir / "publish_job.json"
    manifest_path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"VIDEO={video_path}")
    print(f"MANIFEST={manifest_path}")
    print(f"STATE={job['state']}")


if __name__ == "__main__":
    main()
