import tempfile
import unittest
from pathlib import Path

from codebase_architect.cli import main


class CLITests(unittest.TestCase):
    def test_init_and_skill_install(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            main(["init", str(root), "--json"])
            self.assertTrue((root / ".codebase-architect.toml").exists())
            main(["skill", "install", str(root), "--json"])
            self.assertTrue((root / ".github" / "skills" / "codebase-architect" / "SKILL.md").exists())

    def test_eval_command(self):
        main(["eval", "--json"])


if __name__ == "__main__":
    unittest.main()
