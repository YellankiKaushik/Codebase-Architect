import json
import tempfile
import unittest
from pathlib import Path
from codebase_architect.config import Config
from codebase_architect.pipeline import run_analysis

class PipelineTests(unittest.TestCase):
    def test_end_to_end_no_llm_and_incremental_cache(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"src").mkdir()
            (root/"src"/"app.py").write_text(
                'from fastapi import FastAPI\n'
                'app=FastAPI()\n'
                '@app.get("/health")\n'
                'def health():\n'
                '    return {"ok": True}\n',
                encoding="utf-8",
            )
            (root/"requirements.txt").write_text("fastapi==0.100\n",encoding="utf-8")
            first=run_analysis(root,Config(),use_llm=False)
            out=Path(first["output"])
            self.assertTrue((out/"DEEP_TECHNICAL_ARCHITECTURE.md").exists())
            self.assertTrue((out/"diagrams"/"technical.mmd").exists())
            graph=json.loads((out/"evidence"/"code-intelligence-graph.json").read_text(encoding="utf-8"))
            self.assertTrue(any(n["kind"]=="API_ENDPOINT" for n in graph["nodes"]))
            second=run_analysis(root,Config(),use_llm=False)
            self.assertGreater(second["stats"]["files_reused"],0)

if __name__=="__main__": unittest.main()
