import os
import shutil
import unittest

from publishers.local_file import (
    render_conference_html_report,
    render_conference_markdown_report,
    render_html_report,
    render_markdown_report,
    write_conference_html_report,
    write_conference_markdown_report,
    write_html_report,
    write_markdown_report,
)
from publishers.targets import local_output_enabled


class LocalOutputTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = os.path.join(os.getcwd(), "tests", "_tmp_output")
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        os.makedirs(self.temp_dir, exist_ok=True)

        self.config = {
            "runtime": {"outputs": ["markdown"]},
            "local_output": {"output_dir": self.temp_dir},
            "research_profile": {"directions": ["multimodal reasoning"]},
        }
        self.papers = [
            {
                "title": "Test Paper",
                "source": "arxiv",
                "score": 8,
                "url": "https://arxiv.org/abs/1234.5678",
                "score_reason": "Matches the target research direction.",
                "summary_text": "A short generated summary.",
            }
        ]
        self.conference_summary = {
            "message": "Conference status checked.",
            "detected_total": 3,
            "relevant_total": 1,
            "venue_counts": {"CVPR": 2, "ICML": 1},
            "relevant_by_venue": {"CVPR": 1},
            "not_released": ["NeurIPS"],
            "errors": [],
            "doc_url": "https://example.com/doc",
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_local_output_enabled_when_markdown_is_configured(self):
        self.assertTrue(local_output_enabled(self.config))

    def test_render_markdown_report_contains_key_fields(self):
        content = render_markdown_report(self.papers, self.config)

        self.assertIn("# Daily Paper Report", content)
        self.assertIn("## 1. Test Paper", content)
        self.assertIn("Why selected: Matches the target research direction.", content)
        self.assertIn("A short generated summary.", content)

    def test_write_markdown_report_writes_file(self):
        path = write_markdown_report(self.papers, self.config, filename="report.md")

        self.assertTrue(os.path.exists(path))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "daily_latest.md")))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "index.html")))
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("Test Paper", content)
        with open(os.path.join(self.temp_dir, "daily_latest.md"), "r", encoding="utf-8") as handle:
            latest_content = handle.read()
        self.assertEqual(content, latest_content)
        with open(os.path.join(self.temp_dir, "index.html"), "r", encoding="utf-8") as handle:
            index_content = handle.read()
        self.assertIn("daily_latest.md", index_content)
        self.assertIn("Paper Push Output Index", index_content)
        self.assertIn("Available Artifacts", index_content)

    def test_render_html_report_contains_key_fields(self):
        content = render_html_report(self.papers, self.config)

        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn("Test Paper", content)
        self.assertIn("Why selected:", content)

    def test_write_html_report_writes_file(self):
        path = write_html_report(self.papers, self.config, filename="report.html")

        self.assertTrue(os.path.exists(path))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "daily_latest.html")))
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("Test Paper", content)
        with open(os.path.join(self.temp_dir, "daily_latest.html"), "r", encoding="utf-8") as handle:
            latest_content = handle.read()
        self.assertEqual(content, latest_content)

    def test_render_conference_markdown_report_contains_sections(self):
        content = render_conference_markdown_report(self.conference_summary, self.config)

        self.assertIn("# Conference Monitor Report", content)
        self.assertIn("## Detected Venues", content)
        self.assertIn("CVPR: new 2, relevant 1", content)

    def test_write_conference_markdown_report_writes_file(self):
        path = write_conference_markdown_report(
            self.conference_summary,
            self.config,
            filename="conference.md",
        )

        self.assertTrue(os.path.exists(path))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "conference_latest.md")))
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("Conference status checked.", content)
        with open(os.path.join(self.temp_dir, "conference_latest.md"), "r", encoding="utf-8") as handle:
            latest_content = handle.read()
        self.assertEqual(content, latest_content)

    def test_render_conference_html_report_contains_sections(self):
        content = render_conference_html_report(self.conference_summary, self.config)

        self.assertIn("Conference Monitor Report", content)
        self.assertIn("Detected Venues", content)
        self.assertIn("NeurIPS", content)

    def test_write_conference_html_report_writes_file(self):
        path = write_conference_html_report(
            self.conference_summary,
            self.config,
            filename="conference.html",
        )

        self.assertTrue(os.path.exists(path))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "conference_latest.html")))
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("Conference status checked.", content)
        with open(os.path.join(self.temp_dir, "conference_latest.html"), "r", encoding="utf-8") as handle:
            latest_content = handle.read()
        self.assertEqual(content, latest_content)
        with open(os.path.join(self.temp_dir, "index.html"), "r", encoding="utf-8") as handle:
            index_content = handle.read()
        self.assertIn("conference_latest.html", index_content)
        self.assertIn("Conference Outputs", index_content)


if __name__ == "__main__":
    unittest.main()
