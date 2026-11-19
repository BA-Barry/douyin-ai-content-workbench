from __future__ import annotations

import csv
import importlib.util
import json
import hashlib
import tempfile
import unittest
import wave
from pathlib import Path


PROJECT = Path(__file__).parents[1]


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, PROJECT / "src" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


metrics = load("metrics_v2")
trace = load("workflow_trace")
release = load("release_package")
prepare = load("prepare_only")
voice = load("voice_gate")
music = load("music_gate")
postmortem = load("postmortem_v3")


class MetricsV2Tests(unittest.TestCase):
    def test_missing_fields_stay_empty_and_rates_need_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "content" / "v1" / "metrics").mkdir(parents=True)
            evidence = root / "evidence.json"
            evidence.write_text("{}", encoding="utf-8")
            path = metrics.append_snapshot(root, "v1", {
                "content_type": "IMAGE_CAROUSEL",
                "checkpoint": "first_visible",
                "window_status": "delayed",
                "captured_at": "2026-08-19T12:00:00+08:00",
                "plays": 12,
                "likes": 3,
                "identity_status": "MATCHED",
                "source_evidence_path": str(evidence),
            })
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["comments"], "")
            self.assertEqual(row["comment_rate"], "")
            self.assertEqual(row["like_rate"], "0.25")

    def test_snapshots_are_append_only_and_duplicate_identity_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "content" / "v1" / "metrics").mkdir(parents=True)
            evidence = root / "evidence.json"
            evidence.write_text("{}", encoding="utf-8")
            raw = {
                "content_type": "IMAGE_CAROUSEL", "checkpoint": "24h",
                "window_status": "on_time", "captured_at": "2026-08-20T12:00:00+08:00",
                "identity_status": "MATCHED", "source_evidence_path": str(evidence),
            }
            metrics.append_snapshot(root, "v1", raw)
            with self.assertRaisesRegex(ValueError, "duplicate snapshot"):
                metrics.append_snapshot(root, "v1", raw)

    def test_percentage_style_rate_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "0..1"):
            metrics.normalize_snapshot("v1", {
                "content_type": "IMAGE_CAROUSEL", "checkpoint": "2h",
                "captured_at": "2026-08-19T12:00:00+08:00", "swipe_away_rate": 50,
            })

    def test_snapshot_requires_real_source_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "content" / "v1" / "metrics").mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "source_evidence_path"):
                metrics.append_snapshot(root, "v1", {
                    "content_type": "IMAGE_CAROUSEL", "checkpoint": "first_visible",
                    "captured_at": "2026-08-19T12:00:00+08:00",
                })


class RouteAuditTests(unittest.TestCase):
    def make_base(self, root: Path, route: str, artifact_type: str) -> Path:
        base = root / "content" / "v1"
        (base / "production").mkdir(parents=True)
        (base / "qa").mkdir()
        (base / "approvals").mkdir()
        (base / "production" / "route_plan.json").write_text(
            json.dumps({"route": route}), encoding="utf-8"
        )
        manifest = {
            "route": route,
            "artifacts": {"artifact_type": artifact_type},
            "source_inventory": {"generated": True},
            "copyright_status": {"status": "PASS"},
            "ai_generated_parts": {"images": True},
        }
        (base / "production" / "production_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        return base

    def test_image_carousel_passes_without_fake_video(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = self.make_base(root, "IMAGE_CAROUSEL", "image_carousel")
            manifest_path = base / "production" / "production_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            images = []
            for index in range(6):
                path = base / "production" / f"{index}.png"
                path.write_bytes(b"png")
                images.append(path.relative_to(root).as_posix())
            caption = base / "production" / "captions.txt"
            caption.write_text("copy", encoding="utf-8")
            manifest["artifacts"].update({
                "images": images, "cover": images[0],
                "captions": caption.relative_to(root).as_posix(),
            })
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(trace.production_errors(root, "v1"), [])

    def test_image_carousel_v3_descriptor_objects_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = self.make_base(root, "IMAGE_CAROUSEL", "image_carousel")
            manifest_path = base / "production" / "production_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            images = []
            for index in range(6):
                path = base / "production" / f"v3-{index}.png"
                path.write_bytes(f"png-{index}".encode())
                images.append({"absolute_path": str(path), "sha256": trace.sha256(path)})
            manifest.pop("source_inventory")
            manifest.pop("copyright_status")
            manifest.pop("ai_generated_parts")
            manifest["generation"] = [{"ai_generated": True} for _ in images]
            manifest["rights"] = {"status": "CLEARED"}
            manifest["artifacts"].update({"images": images, "cover": images[0]})
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(trace.production_errors(root, "v1"), [])

    def test_narrated_route_requires_narration(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = self.make_base(root, "NARRATED_EXPLAINER", "narrated_explainer")
            manifest_path = base / "production" / "production_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for name in ("video.mp4", "cover.png", "captions.srt"):
                (base / "production" / name).write_bytes(b"x")
            manifest["artifacts"].update({
                "video": (base / "production" / "video.mp4").relative_to(root).as_posix(),
                "cover": (base / "production" / "cover.png").relative_to(root).as_posix(),
                "captions": (base / "production" / "captions.srt").relative_to(root).as_posix(),
            })
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertTrue(any("narration" in error for error in trace.production_errors(root, "v1")))

    def test_five_image_carousel_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = self.make_base(root, "IMAGE_CAROUSEL", "image_carousel")
            manifest_path = base / "production" / "production_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            images = []
            for index in range(5):
                path = base / "production" / f"{index}.png"
                path.write_bytes(b"png")
                images.append(path.relative_to(root).as_posix())
            cover = base / "production" / "cover.png"
            caption = base / "production" / "captions.txt"
            cover.write_bytes(b"cover")
            caption.write_text("copy", encoding="utf-8")
            manifest["artifacts"].update({
                "images": images, "cover": cover.relative_to(root).as_posix(),
                "captions": caption.relative_to(root).as_posix(),
            })
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertTrue(any("six" in error for error in trace.production_errors(root, "v1")))

    def test_qa_must_bind_current_manifest_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = self.make_base(root, "IMAGE_CAROUSEL", "image_carousel")
            (base / "qa" / "qa_result.json").write_text(json.dumps({
                "conclusion": "PASS", "blocker_count": 0, "major_count": 0,
                "production_manifest_sha256": "wrong",
            }), encoding="utf-8")
            self.assertTrue(any("not bound" in error for error in trace.qa_errors(root, "v1")))


class ReleasePackageTests(unittest.TestCase):
    def test_package_hash_detects_manifest_change(self) -> None:
        package = {"schema_version": "3.0", "files": [{"path": "a", "sha256": "b"}]}
        package["package_sha256"] = release.package_sha256(package)
        self.assertEqual(package["package_sha256"], release.package_sha256(package))
        package["files"][0]["sha256"] = "changed"
        self.assertNotEqual(package["package_sha256"], release.package_sha256(package))

    def test_changed_release_file_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            artifact = root / "artifact.txt"
            artifact.write_text("approved", encoding="utf-8")
            package = {
                "schema_version": "3.0",
                "files": [{"path": "artifact.txt", "sha256": release.file_sha256(artifact)}],
            }
            package["package_sha256"] = release.package_sha256(package)
            package_path = root / "release_package.json"
            package_path.write_text(json.dumps(package), encoding="utf-8")
            artifact.write_text("changed after approval", encoding="utf-8")
            self.assertTrue(any("changed" in error for error in release.validate_release_package(root, package_path)))

    def test_manifest_artifact_descriptor_paths_are_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image = root / "image.png"
            image.write_bytes(b"image")
            manifest = {"artifacts": {"images": [{"absolute_path": str(image), "sha256": release.file_sha256(image)}], "cover": {"absolute_path": str(image)}}}
            self.assertEqual(release._manifest_artifact_paths(root, manifest), [image])


class PrepareOnlyTests(unittest.TestCase):
    def test_offline_image_carousel_release_to_prepare_job_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = root / "content" / "v1"
            for folder in ("production", "qa", "approvals"):
                (base / folder).mkdir(parents=True, exist_ok=True)
            (base / "brief.md").write_text("approved brief", encoding="utf-8")
            (base / "hypothesis_card.md").write_text("one variable", encoding="utf-8")
            (base / "production" / "route_plan.json").write_text(json.dumps({
                "route": "IMAGE_CAROUSEL", "music_mode": "platform_manual",
            }), encoding="utf-8")
            (base / "production" / "shot_list.csv").write_text("shot_id\nP01\n", encoding="utf-8")
            (base / "production" / "material_manifest.csv").write_text("asset_id\na1\n", encoding="utf-8")
            images = []
            for index in range(6):
                image = base / "production" / f"P{index + 1:02}.png"
                image.write_bytes(f"image-{index}".encode())
                images.append(image.relative_to(root).as_posix())
            manifest = {
                "artifacts": {"artifact_type": "image_carousel", "images": images,
                              "cover": images[0], "captions": "content/v1/approvals/release_copy.md"},
                "source_inventory": {"generated": True},
                "copyright_status": {"status": "PASS"},
                "ai_generated_parts": {"images": True},
            }
            (base / "production" / "production_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (base / "qa" / "qa_result.json").write_text(json.dumps({"conclusion": "PASS"}), encoding="utf-8")
            copy = base / "approvals" / "release_copy.md"
            copy.write_text("title and copy", encoding="utf-8")
            package = release.build_release_package(root, "v1", copy)
            package_path = base / "approvals" / "release_package.json"
            package_path.write_text(json.dumps(package), encoding="utf-8")
            (base / "approvals" / "final_approval.json").write_text(json.dumps({
                "approved": True, "approved_by": "user",
                "release_package_sha256": package["package_sha256"],
            }), encoding="utf-8")
            job = prepare.build_prepare_job(root, "v1")
            self.assertEqual(job["mode"], "prepare-only")
            self.assertEqual(len(job["upload_artifacts"]), 6)
            self.assertFalse(job["publish_clicked"])

    def test_final_approval_must_bind_release_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            approvals = root / "content" / "v1" / "approvals"
            approvals.mkdir(parents=True)
            (approvals / "release_package.json").write_text(json.dumps({
                "package_sha256": "expected", "route": "IMAGE_CAROUSEL",
                "final_artifacts": [], "release_copy": {},
            }), encoding="utf-8")
            (approvals / "final_approval.json").write_text(json.dumps({
                "approved": True, "approved_by": "user", "release_package_sha256": "wrong",
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not bound"):
                prepare.build_prepare_job(root, "v1")

    def test_mismatched_identity_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "MISMATCH"):
            metrics.normalize_snapshot("v1", {
                "content_type": "IMAGE_CAROUSEL", "checkpoint": "first_visible",
                "captured_at": "2026-08-19T12:00:00+08:00", "identity_status": "MISMATCH",
            })

    def test_publish_receipt_must_confirm_published_true(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            approvals = root / "content" / "v1" / "approvals"
            approvals.mkdir(parents=True)
            (approvals / "prepare_receipt.json").write_text(json.dumps({
                "mode": "prepare-only", "publish_clicked": False,
            }), encoding="utf-8")
            (approvals / "publish_receipt.json").write_text(json.dumps({
                "published": False, "reported_at": "2026-08-19T12:00:00+08:00",
            }), encoding="utf-8")
            self.assertTrue(any("published=true" in error for error in trace.receipt_errors(root, "v1", published=True)))


class VoiceMusicPostmortemTests(unittest.TestCase):
    def write_silence(self, path: Path, seconds: int = 10) -> str:
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(48000)
            handle.writeframes(b"\x00\x00" * 48000 * seconds)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_voice_gate_passes_only_hash_bound_user_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sample = root / "sample.wav"
            sample_hash = self.write_silence(sample)
            rights = root / "rights.txt"
            rights.write_text("licensed synthetic test", encoding="utf-8")
            approval = root / "approval.json"
            approval.write_text(json.dumps({
                "approved": True, "approved_by": "user", "sample_sha256": sample_hash,
                "naturalness_accepted": True,
            }), encoding="utf-8")
            contract = root / "contract.json"
            contract.write_text(json.dumps({
                "voice_mode": "licensed_synthetic", "sample_path": str(sample),
                "sample_sha256": sample_hash, "rights_evidence_path": str(rights),
                "human_approval_path": str(approval),
            }), encoding="utf-8")
            result = voice.validate_voice_contract(root, contract)
            self.assertEqual(result["status"], "PASS")

    def test_voice_clone_without_consent_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            contract = root / "contract.json"
            contract.write_text(json.dumps({"voice_mode": "authorized_self_clone"}), encoding="utf-8")
            result = voice.validate_voice_contract(root, contract)
            self.assertTrue(any("consent" in error for error in result["errors"]))

    def test_platform_manual_music_cannot_embed_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan = root / "music.json"
            plan.write_text(json.dumps({
                "music_mode": "platform_manual", "embedded": True, "music_file_path": "track.mp3",
            }), encoding="utf-8")
            self.assertEqual(music.validate_plan(root, plan)["status"], "BLOCKED")

    def test_postmortem_without_h72_stays_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            metrics_dir = root / "content" / "v1" / "metrics"
            metrics_dir.mkdir(parents=True)
            (metrics_dir / "post_snapshots.csv").write_text(
                "snapshot_id,checkpoint,captured_at,plays\ns1,first_visible,2026-08-19T10:00:00+08:00,100\n",
                encoding="utf-8",
            )
            report = postmortem.build_postmortem(root, "v1", "", "H1", "change cover only")
            self.assertEqual(report["hypothesis_decision"], "INCONCLUSIVE")
            self.assertEqual(report["status"], "WAITING_FOR_EVIDENCE")


if __name__ == "__main__":
    unittest.main()
