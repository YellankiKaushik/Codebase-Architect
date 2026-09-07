import tempfile
import unittest
from pathlib import Path
from codebase_architect.config import AnalysisConfig
from codebase_architect.scanner import discover_files

class ScannerTests(unittest.TestCase):
    def test_ignores_node_modules_and_binary(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"src").mkdir()
            (root/"src"/"app.py").write_text("print('ok')",encoding="utf-8")
            (root/"node_modules").mkdir()
            (root/"node_modules"/"x.js").write_text("bad()",encoding="utf-8")
            (root/"blob.bin").write_bytes(b"abc\x00def")
            paths=[r.path for r in discover_files(root,AnalysisConfig())]
            self.assertIn("src/app.py",paths)
            self.assertNotIn("node_modules/x.js",paths)
            self.assertNotIn("blob.bin",paths)

if __name__=="__main__": unittest.main()
