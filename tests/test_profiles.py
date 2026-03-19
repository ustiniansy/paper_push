import unittest

from pipeline.profiles import apply_profile, available_profiles


class ProfilePresetTests(unittest.TestCase):
    def test_available_profiles_contains_expected_presets(self):
        names = available_profiles()

        self.assertIn("multimodal", names)
        self.assertIn("vision", names)
        self.assertIn("nlp", names)
        self.assertIn("agents", names)

    def test_apply_profile_replaces_research_profile(self):
        config = {
            "research_profile": {
                "directions": ["old"],
                "keywords": {"high_priority": ["old"], "medium_priority": []},
            },
            "runtime": {},
        }

        updated = apply_profile(config, "agents")

        self.assertEqual(updated["runtime"]["profile"], "agents")
        self.assertNotEqual(updated["research_profile"]["directions"], ["old"])
        self.assertIn("agent", " ".join(updated["research_profile"]["keywords"]["high_priority"]))


if __name__ == "__main__":
    unittest.main()
