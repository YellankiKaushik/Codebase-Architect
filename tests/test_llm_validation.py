import unittest

from codebase_architect.graph import CodeGraph
from codebase_architect.llm.validation import parse_component_synthesis
from codebase_architect.models import ArchitectureComponent, Evidence, Node


class LLMValidationTests(unittest.TestCase):
    def test_rejects_wrong_component_and_filters_fake_evidence(self):
        graph = CodeGraph()
        graph.add_node(Node(id="FILE-a", kind="FILE", name="a.py", path="a.py", evidence=[Evidence(id="EVD-real", path="a.py")]))
        component = ArchitectureComponent("CMP-001", "src", ["a.py"], "source", ["FILE-a"])
        synthesis, warnings = parse_component_synthesis(
            '{"component_id":"CMP-001","purpose":"VERIFIED magic","responsibilities":[],"dependencies":[],"runtime_behavior":"UNKNOWN","risks":[],"unknowns":[],"evidence_ids":["EVD-real","EVD-fake"]}',
            component,
            graph,
        )
        self.assertIsNotNone(synthesis)
        self.assertEqual(synthesis.evidence_ids, ["EVD-real"])
        self.assertTrue(any("unknown evidence" in warning for warning in warnings))
        self.assertTrue(any("VERIFIED" in warning for warning in warnings))
        bad, _ = parse_component_synthesis(
            '{"component_id":"CMP-999","purpose":"UNKNOWN","responsibilities":[],"dependencies":[],"runtime_behavior":"UNKNOWN","risks":[],"unknowns":[],"evidence_ids":[]}',
            component,
            graph,
        )
        self.assertIsNone(bad)


if __name__ == "__main__":
    unittest.main()
