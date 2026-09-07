import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from codebase_architect.config import Config
from codebase_architect.errors import SecurityPolicyError
from codebase_architect.llm import GenerationRequest, provider_from_config
from codebase_architect.llm.http import SafeHttpClient


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if self.path == "/api/tags":
            self._json({"models": [{"name": "gemma-local"}]})
        elif self.path == "/v1/models":
            self._json({"data": [{"id": "qwen-local"}]})
        elif self.path == "/redirect-remote":
            self.send_response(302)
            self.send_header("Location", "https://example.com/models")
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        if self.path == "/api/generate":
            self._json({"response": "{\"component_id\":\"CMP-001\",\"purpose\":\"UNKNOWN\",\"responsibilities\":[],\"dependencies\":[],\"runtime_behavior\":\"UNKNOWN\",\"risks\":[],\"unknowns\":[],\"evidence_ids\":[]}", "done": True})
        elif self.path == "/v1/chat/completions":
            self._json({"choices": [{"message": {"content": "{\"ok\": true}"}}], "usage": {"total_tokens": 3}})
        else:
            self.send_error(404)

    def log_message(self, fmt, *args):
        return

    def _json(self, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class LLMProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_ollama_mock_provider(self):
        cfg = Config()
        cfg.security.offline = True
        cfg.model.provider = "ollama"
        cfg.model.name = "gemma-local"
        cfg.model.base_url = self.base
        provider = provider_from_config(cfg.model, cfg)
        self.assertTrue(provider.health()[0])
        result = provider.generate(GenerationRequest("system", "prompt", "req", response_format="json"))
        self.assertIn("CMP-001", result.text)

    def test_openai_compatible_mock_provider(self):
        cfg = Config()
        cfg.security.offline = True
        cfg.model.provider = "openai-compatible"
        cfg.model.name = "qwen-local"
        cfg.model.base_url = self.base + "/v1"
        provider = provider_from_config(cfg.model, cfg)
        self.assertTrue(provider.health()[0])
        result = provider.generate(GenerationRequest("system", "prompt", "req", response_format="json"))
        self.assertEqual(result.usage["total_tokens"], 3)

    def test_offline_redirect_to_remote_is_blocked(self):
        client = SafeHttpClient(self.base, timeout=3, offline=True, retry_attempts=0)
        with self.assertRaises(SecurityPolicyError):
            client.get_json("/redirect-remote")


if __name__ == "__main__":
    unittest.main()
