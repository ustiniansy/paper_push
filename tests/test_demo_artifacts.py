import os
import shutil
import unittest

from pipeline.demo_artifacts import generate_demo_artifacts


class DemoArtifactsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = os.path.join(os.getcwd(), "tests", "_tmp_demo_output")
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        os.makedirs(self.temp_dir, exist_ok=True)
        self.config = {
            "runtime": {"outputs": ["markdown", "html"]},
            "local_output": {"output_dir": self.temp_dir},
            "research_profile": {"directions": ["demo showcase"]},
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_generate_demo_artifacts_writes_demo_and_latest_files(self):
        summary = generate_demo_artifacts(self.config)

        self.assertEqual(summary["daily_count"], 3)
        self.assertEqual(summary["conference_detected"], 7)
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "daily_demo.html")))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "conference_demo.html")))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "daily_latest.html")))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "conference_latest.html")))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "index.html")))

        with open(os.path.join(self.temp_dir, "index.html"), "r", encoding="utf-8") as handle:
            index_content = handle.read()
        self.assertIn("daily_demo.html", index_content)
        self.assertIn("conference_demo.html", index_content)
        self.assertIn("Available Artifacts", index_content)

        with open(os.path.join(self.temp_dir, "daily_latest.html"), "r", encoding="utf-8") as handle:
            daily_content = handle.read()
        with open(os.path.join(self.temp_dir, "conference_latest.html"), "r", encoding="utf-8") as handle:
            conference_content = handle.read()

        self.assertIn("OmniCanvas", daily_content)
        self.assertIn("CVPR 2026", conference_content)


if __name__ == "__main__":
    unittest.main()
