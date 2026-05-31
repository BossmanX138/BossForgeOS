import os
import unittest

from modules.soundforge import api_adapter as soundforge_api


class SoundforgeAdapterPathRewriteTests(unittest.TestCase):
    def test_rewrite_config_paths_rewrites_global_and_per_app(self) -> None:
        cfg = {
            "global": {"start": {"files": ["C:/x/a.wav", "b.wav"]}},
            "per_app": {"app1": {"event": {"files": ["D:/y/c.mp3"]}}},
        }
        out = soundforge_api.rewrite_config_paths(cfg, sound_dir="sounds")
        self.assertEqual(
            out["global"]["start"]["files"],
            [os.path.join("sounds", "a.wav"), os.path.join("sounds", "b.wav")],
        )
        self.assertEqual(out["per_app"]["app1"]["event"]["files"], [os.path.join("sounds", "c.mp3")])


if __name__ == "__main__":
    unittest.main()
