import unittest
from unittest.mock import patch

from pipeline import conference_monitor


class ConferenceMonitorTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "conference_monitor": {
                "enabled": True,
                "timeout_per_source": 8,
                "max_workers": 4,
                "venues": ["CVPR"],
            },
            "network": {"request_timeout": 30},
            "llm": {"score_threshold": 7},
            "research_profile": {
                "keywords": {
                    "high_priority": ["video"],
                    "medium_priority": ["reasoning"],
                }
            },
            "runtime": {"dry_run": False},
            "feishu": {"webhook_url": "https://example.com/hook"},
        }

    @patch("pipeline.conference_monitor._save_state")
    @patch("pipeline.conference_monitor.mark_processed")
    @patch("pipeline.conference_monitor.fetch_conference_papers")
    def test_seed_conference_baseline_marks_processed_and_saves_state(
        self,
        mock_fetch,
        mock_mark_processed,
        mock_save_state,
    ):
        papers = [
            {"arxiv_id": "conf:CVPR:1", "title": "Paper 1", "venue": "CVPR", "source": "conference"},
            {"arxiv_id": "conf:ICML:1", "title": "Paper 2", "venue": "ICML", "source": "conference"},
        ]
        mock_fetch.return_value = (papers, {"CVPR": 1, "ICML": 1}, [], [])

        summary = conference_monitor.seed_conference_baseline(self.config)

        self.assertTrue(summary["enabled"])
        self.assertEqual(summary["seeded_total"], 2)
        mock_mark_processed.assert_called_once_with(papers)
        mock_save_state.assert_called_once_with(
            {
                "initialized": True,
                "initialized_venues": ["CVPR", "ICML"],
            }
        )

    @patch("pipeline.conference_monitor.push_conference_status")
    @patch("pipeline.conference_monitor.score_papers")
    @patch("pipeline.conference_monitor.enrich_conference_papers")
    @patch("pipeline.conference_monitor.filter_unseen")
    @patch("pipeline.conference_monitor.fetch_conference_papers")
    @patch("pipeline.conference_monitor._load_state")
    def test_run_conference_monitor_no_new_skips_enrich_and_scoring(
        self,
        mock_load_state,
        mock_fetch,
        mock_filter_unseen,
        mock_enrich,
        mock_score,
        mock_push,
    ):
        mock_load_state.return_value = {
            "initialized": True,
            "initialized_venues": ["CVPR"],
        }
        papers = [
            {"arxiv_id": "conf:CVPR:1", "title": "Paper 1", "venue": "CVPR", "source": "conference"},
        ]
        mock_fetch.return_value = (papers, {"CVPR": 1}, [], [])
        mock_filter_unseen.return_value = []

        summary = conference_monitor.run_conference_monitor(self.config)

        self.assertEqual(summary["detected_total"], 0)
        self.assertEqual(summary["relevant_total"], 0)
        mock_enrich.assert_not_called()
        mock_score.assert_not_called()
        mock_push.assert_called_once()


if __name__ == "__main__":
    unittest.main()
