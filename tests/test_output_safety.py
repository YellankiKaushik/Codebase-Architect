import tempfile
import unittest
from pathlib import Path

from codebase_architect.config import Config
from codebase_architect.errors import SecurityPolicyError
from codebase_architect.pipeline import run_analysis


class OutputSafetyTests(unittest.TestCase):
    def test_refuses_to_overwrite_user_authored_doc(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
            output = root / "docs" / "codebase"
            output.mkdir(parents=True)
            (output / "README.md").write_text("# My hand-written docs\n", encoding="utf-8")
            with self.assertRaises(SecurityPolicyError):
                run_analysis(root, Config(), use_llm=False)

    def test_relative_output_cannot_escape_repository(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "app.py").write_text("print('ok')\n", encoding="utf-8")
            cfg = Config()
            cfg.output.path = "../outside"
            with self.assertRaises(SecurityPolicyError):
                run_analysis(root, cfg, use_llm=False)


if __name__ == "__main__":
    unittest.main()
