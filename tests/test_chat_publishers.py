import unittest
from unittest.mock import MagicMock, patch

from publishers.slack import push_to_slack
from publishers.telegram import push_to_telegram


class ChatPublisherTests(unittest.TestCase):
    def setUp(self):
        self.papers = [
            {
                "title": "Test Paper",
                "score": 8,
                "url": "https://arxiv.org/abs/1234.5678",
                "score_reason": "Relevant and strong.",
                "code_url": "https://github.com/example/repo",
            }
        ]

    @patch("publishers.telegram.get_default_session")
    def test_telegram_uses_html_parse_mode(self, mock_session_factory):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_factory.return_value = mock_session

        config = {
            "telegram": {"bot_token": "token", "chat_id": "chat"},
            "network": {"request_timeout": 15},
        }

        push_to_telegram(self.papers, config, doc_url="https://example.com/doc")

        kwargs = mock_session.post.call_args.kwargs
        self.assertEqual(kwargs["json"]["parse_mode"], "HTML")
        self.assertIn("Test Paper", kwargs["json"]["text"])

    @patch("publishers.slack.get_default_session")
    def test_slack_sends_blocks_payload(self, mock_session_factory):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_factory.return_value = mock_session

        config = {
            "slack": {"webhook_url": "https://hooks.slack.com/services/test"},
            "network": {"request_timeout": 15},
        }

        push_to_slack(self.papers, config, doc_url="https://example.com/doc")

        kwargs = mock_session.post.call_args.kwargs
        self.assertIn("blocks", kwargs["json"])
        self.assertTrue(kwargs["json"]["blocks"])


if __name__ == "__main__":
    unittest.main()
