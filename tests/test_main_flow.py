import unittest
from unittest.mock import patch

import main


class MainFlowTests(unittest.TestCase):
    @patch("main._mark_successful_run")
    @patch("main.publish_daily_digest")
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
        mock_publish,
        mock_mark_successful_run,
    ):
        mock_window.return_value = (main.datetime.now(main.timezone.utc), main.datetime.now(main.timezone.utc))
        mock_publish.return_value = []
        config = {
            "runtime": {"dry_run": False},
            "network": {"request_timeout": 30},
            "llm": {"score_threshold": 7},
            "arxiv": {"categories": ["cs.CV"]},
            "huggingface": {"enabled": True, "limit": 10},
            "feishu": {"webhook_url": "https://example.com/hook"},
        }

        main._run_daily_pipeline(config, main.datetime.now(main.timezone.utc))

        mock_publish.assert_called_once_with([], config, allow_network=True)
        mock_mark_successful_run.assert_called_once()

    @patch("main.run_conference_monitor")
    @patch("main._run_daily_pipeline")
    @patch(
        "main.load_config",
        return_value={
            "llm": {"api_key": "test-key"},
            "research_profile": {
                "directions": ["multimodal reasoning"],
                "keywords": {"high_priority": ["video"], "medium_priority": []},
            },
            "runtime": {"outputs": ["markdown"]},
            "local_output": {"output_dir": "output"},
            "feishu": {"webhook_url": ""},
        },
    )
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
            {
                "dry_run": False,
                "seed_conference_baseline": False,
                "command": "daily",
                "output": None,
                "profile": None,
            },
        )()
        mock_run_daily_pipeline.side_effect = RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            main.main()

        mock_run_conference_monitor.assert_not_called()

    @patch("main.run_conference_monitor", return_value={"enabled": True})
    @patch("main._run_daily_pipeline")
    @patch(
        "main.load_config",
        return_value={
            "llm": {"api_key": "test-key"},
            "research_profile": {
                "directions": ["multimodal reasoning"],
                "keywords": {"high_priority": ["video"], "medium_priority": []},
            },
            "runtime": {"outputs": ["markdown"]},
            "local_output": {"output_dir": "output"},
            "feishu": {"webhook_url": ""},
            "conference_monitor": {"enabled": True},
        },
    )
    @patch("main.parse_args")
    def test_main_conference_command_skips_daily_pipeline(
        self,
        mock_parse_args,
        _mock_load_config,
        mock_run_daily_pipeline,
        mock_run_conference_monitor,
    ):
        mock_parse_args.return_value = type(
            "Args",
            (object,),
            {
                "dry_run": False,
                "seed_conference_baseline": False,
                "command": "conference",
                "output": None,
                "profile": None,
            },
        )()

        main.main()

        mock_run_daily_pipeline.assert_not_called()
        mock_run_conference_monitor.assert_called_once()

    @patch("main.run_conference_monitor", return_value={"enabled": True})
    @patch("main._run_daily_pipeline")
    @patch(
        "main.load_config",
        return_value={
            "llm": {"api_key": "test-key"},
            "research_profile": {
                "directions": ["multimodal reasoning"],
                "keywords": {"high_priority": ["video"], "medium_priority": []},
            },
            "runtime": {"outputs": ["markdown"]},
            "local_output": {"output_dir": "output"},
            "feishu": {"webhook_url": ""},
            "conference_monitor": {"enabled": True},
        },
    )
    @patch("main.parse_args")
    def test_main_defaults_to_daily_command(
        self,
        mock_parse_args,
        _mock_load_config,
        mock_run_daily_pipeline,
        mock_run_conference_monitor,
    ):
        mock_parse_args.return_value = type(
            "Args",
            (object,),
            {
                "dry_run": False,
                "seed_conference_baseline": False,
                "command": None,
                "output": None,
                "profile": None,
            },
        )()

        main.main()

        mock_run_daily_pipeline.assert_called_once()
        mock_run_conference_monitor.assert_called_once()


if __name__ == "__main__":
    unittest.main()
