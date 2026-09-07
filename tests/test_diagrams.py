import unittest
from codebase_architect.diagrams import c4_mermaid,technical_mermaid,visual_svg
from codebase_architect.models import ArchitectureComponent,ArchitectureIR

class DiagramTests(unittest.TestCase):
    def air(self):
        return ArchitectureIR(
            "1","demo","modular",
            [ArchitectureComponent("CMP-001","src/api",["src/api.py"],"API",[])],
            [],
            [{"name":"PostgreSQL","classification":"VERIFIED"}],
            [],[],[],["Python"]
        )

    def test_renderers(self):
        air=self.air()
        self.assertIn("flowchart",technical_mermaid(air))
        self.assertIn("System Boundary",c4_mermaid(air))
        self.assertIn("<svg",visual_svg(air))

if __name__=="__main__": unittest.main()
