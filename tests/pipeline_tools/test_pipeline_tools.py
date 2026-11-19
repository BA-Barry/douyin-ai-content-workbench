from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from pipeline_tools.material_manifest_validator import REQUIRED_COLUMNS, validate_manifest
from pipeline_tools.post_snapshot_importer import OUTPUT_COLUMNS, import_snapshots
from pipeline_tools.qa_probe import probe_media
from pipeline_tools.transcript_adapter import normalize_transcript


FIXTURES = ROOT / "tests" / "fixtures" / "pipeline_tools"
TEST_ROOT = ROOT / "workspace" / "pipeline_test_20260818" / "tooling" / "results" / "test_tmp"


class GDriveTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.work = TEST_ROOT / uuid.uuid4().hex
        self.work.mkdir(parents=True)
        self.assertEqual(self.work.drive.upper(), ROOT.drive.upper())

    def tearDown(self) -> None:
        resolved = self.work.resolve()
        if resolved.is_relative_to(TEST_ROOT.resolve()):
            shutil.rmtree(resolved, ignore_errors=True)


class QATests(GDriveTestCase):
    def test_probe_is_structured_and_read_only(self) -> None:
        ffmpeg = os.environ.get("PROJECT_FFMPEG_EXE")
        ffprobe = os.environ.get("PROJECT_FFPROBE_EXE")
        if not ffmpeg or not Path(ffmpeg).is_file() or not ffprobe or not Path(ffprobe).is_file():
            self.skipTest("project-env.ps1 must expose project-local FFmpeg/ffprobe")
        media = self.work / "black_silent_fixture.mp4"
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=320x568:r=30:d=1.2",
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(media),
        ]
        subprocess.run(command, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        before = hashlib.sha256(media.read_bytes()).hexdigest()
        result = probe_media(media)
        after = hashlib.sha256(media.read_bytes()).hexdigest()
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["content_unchanged"])
        self.assertEqual(before, after)
        self.assertEqual(result["media"]["video"]["codec_name"], "h264")
        self.assertEqual(result["media"]["audio"]["sample_rate"], "48000")
        self.assertTrue(result["analyses"]["black"]["intervals"])
        self.assertTrue(result["analyses"]["freeze"]["intervals"])
        self.assertTrue(result["analyses"]["silence"]["intervals"])

    def test_video_only_skips_audio_analyses(self) -> None:
        ffmpeg = os.environ.get("PROJECT_FFMPEG_EXE")
        ffprobe = os.environ.get("PROJECT_FFPROBE_EXE")
        if not ffmpeg or not Path(ffmpeg).is_file() or not ffprobe or not Path(ffprobe).is_file():
            self.skipTest("project-env.ps1 must expose project-local FFmpeg/ffprobe")
        media = self.work / "video_only_fixture.mp4"
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i", "color=c=blue:s=320x568:r=30:d=1.2",
            "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(media),
        ]
        subprocess.run(command, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result = probe_media(media)
        self.assertEqual(result["status"], "PASS")
        self.assertIsNone(result["media"]["audio"])
        self.assertEqual(result["analyses"]["silence"]["status"], "NOT_APPLICABLE")
        self.assertEqual(result["analyses"]["loudness"]["status"], "NOT_APPLICABLE")
        self.assertEqual(result["analyses"]["silence"]["reason"], "NO_AUDIO_STREAM")


class ManifestTests(GDriveTestCase):
    def _write(self, row: dict[str, str], name: str = "manifest.csv") -> Path:
        path = self.work / name
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS, lineterminator="\n")
            writer.writeheader()
            writer.writerow(row)
        return path

    def _base_row(self) -> dict[str, str]:
        asset = self.work / "asset.txt"
        asset.write_text("local fixture", encoding="utf-8")
        digest = hashlib.sha256(asset.read_bytes()).hexdigest()
        row = {field: "" for field in REQUIRED_COLUMNS}
        row.update({
            "asset_id": "asset-1", "local_path": str(asset.resolve()), "sha256": digest,
            "media_type": "text", "purpose": "test", "ai_generated": "NO",
            "human_review": "APPROVED", "status": "CLEARED",
        })
        return row

    def test_valid_manifest_passes(self) -> None:
        result = validate_manifest(self._write(self._base_row()))
        self.assertEqual(result["status"], "PASS")

    def test_blocked_rights_fails(self) -> None:
        row = self._base_row()
        row["status"] = "BLOCKED"
        result = validate_manifest(self._write(row))
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("RIGHTS_BLOCKED", {item["code"] for item in result["errors"]})

    def test_ai_requires_provenance_and_review(self) -> None:
        row = self._base_row()
        row.update({"ai_generated": "YES", "human_review": "PENDING"})
        result = validate_manifest(self._write(row))
        codes = {item["code"] for item in result["errors"]}
        self.assertIn("AI_PROVENANCE_MISSING", codes)
        self.assertIn("AI_HUMAN_REVIEW_NOT_APPROVED", codes)


class SnapshotTests(GDriveTestCase):
    def test_chinese_csv_percentages_and_hidden_fields(self) -> None:
        output = self.work / "normalized.csv"
        result = import_snapshots(FIXTURES / "manual_export_zh.csv", output)
        self.assertEqual(result["rows_imported"], 1)
        with output.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            self.assertEqual(tuple(reader.fieldnames or ()), OUTPUT_COLUMNS)
            row = next(reader)
        self.assertEqual(row["plays"], "12345")
        self.assertEqual(row["completion_rate"], "0.321")
        self.assertEqual(row["retention_5s"], "")
        self.assertNotIn("retention_5s", row["field_availability"])

    def test_xlsx_first_sheet_import(self) -> None:
        output = self.work / "normalized.csv"
        result = import_snapshots(FIXTURES / "manual_export_zh.xlsx", output)
        self.assertEqual(result["rows_imported"], 1)
        with output.open("r", encoding="utf-8-sig", newline="") as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual(row["likes"], "88")
        self.assertEqual(row["completion_rate"], "0.456")

    def test_existing_output_requires_explicit_mode(self) -> None:
        output = self.work / "normalized.csv"
        import_snapshots(FIXTURES / "manual_export_zh.csv", output)
        with self.assertRaises(FileExistsError):
            import_snapshots(FIXTURES / "manual_export_zh.csv", output)

    def test_duplicate_snapshot_is_blocked_before_output(self) -> None:
        output = self.work / "normalized.csv"
        with self.assertRaisesRegex(ValueError, "Duplicate snapshot blocked"):
            import_snapshots(FIXTURES / "manual_export_duplicate.csv", output)
        self.assertFalse(output.exists())


class TranscriptTests(unittest.TestCase):
    def _fixture(self, name: str) -> dict:
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def test_funasr_normalizes_milliseconds(self) -> None:
        result = normalize_transcript(self._fixture("funasr_valid.json"), "funasr")
        self.assertEqual(result["language"], "zh")
        self.assertEqual(result["words"][1]["start_s"], 0.2)
        self.assertEqual(len(result["sentences"]), 1)

    def test_funasr_dict_words_use_milliseconds(self) -> None:
        result = normalize_transcript({
            "language": "zh",
            "text": "测试",
            "words": [
                {"word": "测", "start": 0, "end": 200},
                {"word": "试", "start": 200, "end": 450},
            ],
        }, "funasr")
        self.assertEqual(result["words"][1]["end_s"], 0.45)

    def test_faster_whisper_normalizes_seconds(self) -> None:
        result = normalize_transcript(self._fixture("faster_whisper_valid.json"), "faster-whisper")
        self.assertEqual(result["language"], "zh")
        self.assertEqual(result["words"][0]["text"], "它")

    def test_non_monotonic_words_fail(self) -> None:
        with self.assertRaisesRegex(ValueError, "monotonic"):
            normalize_transcript(self._fixture("faster_whisper_nonmonotonic.json"), "faster-whisper")

    def test_empty_word_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "Empty word"):
            normalize_transcript(self._fixture("faster_whisper_empty_word.json"), "faster-whisper")

    def test_missing_language_fails(self) -> None:
        data = self._fixture("funasr_valid.json")
        data["language"] = ""
        with self.assertRaisesRegex(ValueError, "Language"):
            normalize_transcript(data, "funasr")


if __name__ == "__main__":
    unittest.main()
