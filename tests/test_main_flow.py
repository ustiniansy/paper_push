import unittest
from unittest.mock import patch

import main


class MainFlowTests(unittest.TestCase):
    @patch("main._mark_successful_run")
    @patch("main.push_to_feishu")
    @patch("main.filter_unseen", return_value=[])
    @patch("main.merge_papers", return_value=[])
    @patch("main.fetch_hf_papers", return_value=[])
    @patch("main.fetch_arxiv_papers", return_value=[])
    @patch("main._compute_fetch_window")
    def test_run_daily_pipeline_pushes_empty_digest_when_no_new_papers(
        self,
        mock_window,
        _mock_arxiv,
        _mock_hf,
        _mock_merge,
        _mock_filter,
        mock_push,
        mock_mark_successful_run,
    ):
        mock_window.return_value = (main.datetime.now(main.timezone.utc), main.datetime.now(main.timezone.utc))
        config = {
            "runtime": {"dry_run": False},
            "network": {"request_timeout": 30},
            "llm": {"score_threshold": 7},
            "arxiv": {"categories": ["cs.CV"]},
            "huggingface": {"enabled": True, "limit": 10},
            "feishu": {"webhook_url": "https://example.com/hook"},
        }

        main._run_daily_pipeline(config, main.datetime.now(main.timezone.utc))

        mock_push.assert_called_once_with([], config)
        mock_mark_successful_run.assert_called_once()

    @patch("main.run_conference_monitor")
    @patch("main._run_daily_pipeline")
    @patch("main.load_config", return_value={})
    @patch("main.parse_args")
    def test_main_skips_conference_when_daily_pipeline_fails(
        self,
        mock_parse_args,
        _mock_load_config,
        mock_run_daily_pipeline,
        mock_run_conference_monitor,
    ):
        mock_parse_args.return_value = type(
            "Args",
            (),
            {"dry_run": False, "seed_conference_baseline": False},
        )()
        mock_run_daily_pipeline.side_effect = RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            main.main()

        mock_run_conference_monitor.assert_not_called()


if __name__ == "__main__":
    unittest.main()
