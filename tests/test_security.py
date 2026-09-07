import unittest
from codebase_architect.config import Config
from codebase_architect.secret_filter import contains_secret, redact

class SecurityTests(unittest.TestCase):
    def test_redacts_named_secret(self):
        result=redact("API_KEY=abcdefghijklmnopqrstuvwxyz123456")
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz123456",result.text)
        self.assertGreaterEqual(result.count,1)

    def test_offline_rejects_remote_ollama(self):
        config=Config()
        config.security.offline=True
        config.model.provider="ollama"
        config.model.name="example"
        config.model.base_url="https://example.com"
        with self.assertRaises(ValueError):
            config.validate()

    def test_contains_secret(self):
        self.assertTrue(contains_secret("Bearer abcdefghijklmnopqrstuvwxyz"))

if __name__=="__main__": unittest.main()
