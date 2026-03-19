import unittest
from unittest.mock import patch

from publishers.registry import (
    PublishResult,
    choose_candidate_indices,
    publish_conference_status_outputs,
    publish_daily_digest,
    write_knowledge_base_outputs,
)


class PublisherRegistryTests(unittest.TestCase):
    def setUp(self):
        self.papers = [
            {
                "title": "Test Paper",
                "score": 8,
                "url": "https://arxiv.org/abs/1234.5678",
                "score_reason": "Relevant and strong.",
            }
        ]

    @patch("publishers.registry.write_markdown_report", return_value="output/report.md")
    @patch("publishers.registry.write_html_report", return_value="output/report.html")
    def test_publish_daily_digest_dispatches_local_targets(
        self,
        mock_html,
        mock_markdown,
    ):
        config = {"runtime": {"outputs": ["markdown", "html"]}}

        results = publish_daily_digest(self.papers, config, allow_network=False)

        self.assertEqual([result.target for result in results], ["markdown", "html"])
        mock_markdown.assert_called_once()
        mock_html.assert_called_once()

    @patch("publishers.registry.push_to_telegram")
    @patch("publishers.registry.push_to_slack")
    def test_publish_daily_digest_skips_network_targets_during_dry_run(
        self,
        mock_slack,
        mock_telegram,
    ):
        config = {"runtime": {"outputs": ["telegram", "slack"]}}

        results = publish_daily_digest(self.papers, config, allow_network=False)

        self.assertEqual([result.status for result in results], ["skipped", "skipped"])
        mock_telegram.assert_not_called()
        mock_slack.assert_not_called()

    @patch("publishers.registry.send_candidate_card", return_value="msg-1")
    @patch("publishers.registry.poll_user_reply", return_value=[0])
    @patch("publishers.registry.send_confirmation")
    def test_choose_candidate_indices_uses_feishu_capability(
        self,
        mock_confirm,
        mock_poll,
        mock_send_card,
    ):
        config = {
            "runtime": {"outputs": ["feishu"]},
            "feishu": {"chat_id": "chat", "webhook_url": "https://example.com/hook"},
        }

        indices = choose_candidate_indices(self.papers, config, poll_timeout_minutes=5)

        self.assertEqual(indices, [0])
        mock_send_card.assert_called_once()
        mock_poll.assert_called_once()
        mock_confirm.assert_called_once()

    @patch(
        "publishers.registry.create_daily_document",
        return_value="https://example.com/feishu-doc",
    )
    @patch("publishers.registry.send_confirmation")
    def test_write_knowledge_base_outputs_uses_feishu_capability(
        self,
        mock_confirm,
        mock_create_doc,
    ):
        config = {"runtime": {"outputs": ["feishu"]}, "feishu": {"webhook_url": "https://example.com/hook"}}

        results = write_knowledge_base_outputs(self.papers, config)

        self.assertEqual(
            results,
            [PublishResult(target="feishu_docs", status="written", detail="https://example.com/feishu-doc")],
        )
        mock_create_doc.assert_called_once()
        mock_confirm.assert_called_once()

    @patch("publishers.registry.push_conference_status")
    @patch("publishers.registry.push_conference_to_telegram")
    def test_publish_conference_status_outputs_dispatches_supported_targets(
        self,
        mock_telegram,
        mock_feishu,
    ):
        config = {
            "runtime": {"outputs": ["feishu", "telegram"]},
            "feishu": {"webhook_url": "https://example.com/hook"},
            "telegram": {"bot_token": "token", "chat_id": "chat"},
        }
        summary = {"message": "Conference status checked."}

        results = publish_conference_status_outputs(summary, config, allow_network=True)

        self.assertEqual([result.target for result in results], ["feishu", "telegram"])
        mock_feishu.assert_called_once()
        mock_telegram.assert_called_once()


if __name__ == "__main__":
    unittest.main()
