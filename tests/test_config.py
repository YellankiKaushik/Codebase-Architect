import tempfile
import unittest
from pathlib import Path

from codebase_architect.config import Config
from codebase_architect.errors import ConfigurationError, SecurityPolicyError


class ConfigTests(unittest.TestCase):
    def test_unknown_config_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".codebase-architect.toml").write_text("version = 1\n[model]\nbanana = true\n", encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                Config.load(root)

    def test_offline_allows_loopback_openai_compatible(self):
        config = Config()
        config.security.offline = True
        config.model.provider = "openai-compatible"
        config.model.name = "local-model"
        config.model.base_url = "http://127.0.0.1:1234/v1"
        config.validate()

    def test_offline_rejects_userinfo_and_remote_host(self):
        config = Config()
        config.security.offline = True
        config.model.provider = "openai-compatible"
        config.model.name = "local-model"
        config.model.base_url = "http://token@example.com/v1"
        with self.assertRaises(SecurityPolicyError):
            config.validate()


if __name__ == "__main__":
    unittest.main()
