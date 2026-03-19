import unittest

from pipeline.config_validation import ConfigValidationError, validate_config


class ConfigValidationTests(unittest.TestCase):
    def _base_config(self):
        return {
            "llm": {"api_key": "test-key"},
            "research_profile": {
                "directions": ["multimodal reasoning"],
                "keywords": {"high_priority": ["video"], "medium_priority": []},
            },
            "runtime": {"outputs": ["markdown"]},
            "local_output": {"output_dir": "output"},
            "feishu": {"webhook_url": ""},
        }

    def test_local_markdown_config_is_valid(self):
        warnings = validate_config(self._base_config())
        self.assertTrue(any("Local output enabled" in warning for warning in warnings))

    def test_missing_llm_api_key_raises_clear_error(self):
        config = self._base_config()
        config["llm"]["api_key"] = ""

        with self.assertRaises(ConfigValidationError) as ctx:
            validate_config(config)

        self.assertIn("llm.api_key", str(ctx.exception))

    def test_feishu_output_requires_webhook(self):
        config = self._base_config()
        config["runtime"]["outputs"] = ["feishu"]

        with self.assertRaises(ConfigValidationError) as ctx:
            validate_config(config)

        self.assertIn("feishu.webhook_url", str(ctx.exception))

    def test_feishu_without_chat_id_emits_warning(self):
        config = self._base_config()
        config["runtime"]["outputs"] = ["feishu"]
        config["feishu"]["webhook_url"] = "https://example.com/hook"

        warnings = validate_config(config)

        self.assertTrue(any("chat_id" in warning for warning in warnings))

    def test_telegram_output_requires_bot_token_and_chat_id(self):
        config = self._base_config()
        config["runtime"]["outputs"] = ["telegram"]
        config["telegram"] = {"bot_token": "", "chat_id": ""}

        with self.assertRaises(ConfigValidationError) as ctx:
            validate_config(config)

        self.assertIn("telegram.bot_token", str(ctx.exception))

    def test_slack_output_requires_webhook(self):
        config = self._base_config()
        config["runtime"]["outputs"] = ["slack"]
        config["slack"] = {"webhook_url": ""}

        with self.assertRaises(ConfigValidationError) as ctx:
            validate_config(config)

        self.assertIn("slack.webhook_url", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
