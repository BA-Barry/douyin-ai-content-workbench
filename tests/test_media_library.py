from __future__ import annotations

import importlib.util
import io
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("workbench_media_library", PROJECT_ROOT / "workbench" / "media_library.py")
MEDIA = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MEDIA)


class MediaLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "workspace")
        self.root = Path(self.temp.name)
        self.project_id = "media-fixture-01"
        (self.root / "content" / self.project_id / "production").mkdir(parents=True)
        MEDIA.configure(self.root)

    def tearDown(self) -> None:
        MEDIA.configure(PROJECT_ROOT)
        self.temp.cleanup()

    def import_image(self, role: str = "STYLE_REFERENCE") -> dict:
        body = b"fake-png-fixture"
        return MEDIA.import_stream(io.BytesIO(body), len(body), {
            "filename": "reference.png",
            "name": "参考图",
            "kind": "image",
            "rights_status": "OWNED",
            "role": role,
            "retain": "低饱和色彩",
            "change": "人物与地点",
        })

    def test_import_hash_bind_and_restore_round_trip(self) -> None:
        item = self.import_image()
        self.assertTrue((self.root / item["stored_path"]).is_file())
        self.assertEqual(64, len(item["sha256"]))
        binding = MEDIA.bind_assets(self.project_id, [item["id"]])
        self.assertEqual([item["id"]], binding["asset_ids"])
        self.assertTrue(MEDIA.binding_path(self.project_id).is_file())
        MEDIA.set_status(item["id"], "TRASHED")
        self.assertEqual([], MEDIA.catalog())
        MEDIA.set_status(item["id"], "ACTIVE")
        self.assertEqual(1, len(MEDIA.catalog()))

    def test_image_route_can_run_without_assets(self) -> None:
        decision = MEDIA.decide_asset_strategy(self.project_id, "IMAGE_CAROUSEL", "秋日公路旅行壁纸")
        self.assertEqual("NONE", decision["asset_strategy"])
        self.assertEqual("TEXT_TO_IMAGE", decision["generation_mode"])
        self.assertFalse(decision["requires_image_subtask"])

    def test_video_auto_adds_keyframe_subtask_only_when_continuity_requires_it(self) -> None:
        decision = MEDIA.decide_asset_strategy(self.project_id, "ATMOSPHERE_VIDEO", "同一人物穿相同服装走过三个镜头")
        self.assertEqual("GENERATE_KEYFRAMES", decision["asset_strategy"])
        self.assertEqual("FIRST_FRAME_TO_VIDEO", decision["generation_mode"])
        self.assertTrue(decision["requires_image_subtask"])
        plain = MEDIA.decide_asset_strategy(self.project_id, "ATMOSPHERE_VIDEO", "无人海岸，单镜头缓慢推进")
        self.assertEqual("NONE", plain["asset_strategy"])
        self.assertEqual("TEXT_TO_VIDEO", plain["generation_mode"])

    def test_first_and_last_frame_roles_choose_first_last_mode(self) -> None:
        first = self.import_image("FIRST_FRAME")
        last = self.import_image("LAST_FRAME")
        MEDIA.bind_assets(self.project_id, [first["id"], last["id"]])
        decision = MEDIA.decide_asset_strategy(self.project_id, "ATMOSPHERE_VIDEO", "黄昏过渡到夜晚")
        self.assertEqual("FIRST_LAST_FRAME", decision["generation_mode"])
        self.assertEqual("USE_EXISTING", decision["asset_strategy"])


if __name__ == "__main__":
    unittest.main()
