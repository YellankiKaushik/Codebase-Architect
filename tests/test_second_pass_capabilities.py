import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from codebase_architect.architecture import infer_architecture
from codebase_architect.config import Config, validate_endpoint
from codebase_architect.diagrams import dependency_mermaid, generate_diagrams
from codebase_architect.errors import SecurityPolicyError
from codebase_architect.file_safety import GENERATED_MARKER, resolve_output_path, write_generated
from codebase_architect.frameworks import detect_frameworks
from codebase_architect.graph import CodeGraph
from codebase_architect.llm.validation import (
    parse_or_repair_component_synthesis,
    parse_risk_candidate,
    parse_system_summary,
    parse_workflow_synthesis,
)
from codebase_architect.models import ArchitectureComponent, ArchitectureIR, Evidence, Node
from codebase_architect.pipeline import run_analysis
from codebase_architect.secret_filter import find_secrets, redact


FIXTURES = Path(__file__).parent / "fixtures"


def _copy_fixture(name: str, target: Path) -> Path:
    root = target / name
    shutil.copytree(FIXTURES / name, root)
    return root


def _run_fixture(name: str, target: Path) -> tuple[Path, CodeGraph, dict, dict]:
    root = _copy_fixture(name, target)
    cfg = Config()
    cfg.output.path = ".tmp/codebase"
    cfg.analysis.exclude.append(".tmp/**")
    result = run_analysis(root, cfg, use_llm=False)
    output = Path(result["output"])
    graph = CodeGraph.from_dict(json.loads((output / "evidence" / "code-intelligence-graph.json").read_text(encoding="utf-8")))
    air = json.loads((output / "evidence" / "architecture.json").read_text(encoding="utf-8"))
    manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
    return root, graph, air, manifest


def _node(graph: CodeGraph, kind: str, contains: str) -> Node:
    for item in graph.nodes.values():
        if item.kind == kind and (contains in item.name or contains in str(item.path or "")):
            return item
    raise AssertionError(f"missing {kind} containing {contains!r}")


class EndpointValidationExpansionTests(unittest.TestCase):
    def test_rejects_unsupported_endpoint_scheme(self):
        with self.assertRaises(SecurityPolicyError):
            validate_endpoint("ftp://127.0.0.1:11434")

    def test_rejects_embedded_endpoint_username(self):
        with self.assertRaises(SecurityPolicyError):
            validate_endpoint("http://user@127.0.0.1:11434")

    def test_rejects_embedded_endpoint_password(self):
        with self.assertRaises(SecurityPolicyError):
            validate_endpoint("http://user:pass@127.0.0.1:11434")

    def test_rejects_endpoint_query_string(self):
        with self.assertRaises(SecurityPolicyError):
            validate_endpoint("http://127.0.0.1:11434?token=abc")

    def test_rejects_endpoint_fragment(self):
        with self.assertRaises(SecurityPolicyError):
            validate_endpoint("http://127.0.0.1:11434/#frag")

    def test_allows_ipv6_loopback_in_offline_mode(self):
        validate_endpoint("http://[::1]:11434", offline=True)

    def test_allows_localhost_in_offline_mode(self):
        validate_endpoint("http://localhost:11434", offline=True)

    def test_blocks_remote_host_in_offline_mode(self):
        with self.assertRaises(SecurityPolicyError):
            validate_endpoint("https://example.com", offline=True)


class SecretFindingTests(unittest.TestCase):
    def test_find_secrets_reports_categories_without_values(self):
        findings = find_secrets("OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz")
        self.assertEqual(findings[0].category, "named_secret")
        self.assertNotIn("sk-proj", repr(findings[0]))

    def test_redact_preserves_secret_category_counts(self):
        result = redact("Authorization: Bearer abcdefghijklmnop")
        self.assertEqual(result.count, 1)
        self.assertEqual(result.types["bearer_token"], 1)

    def test_false_positive_short_token_is_ignored(self):
        self.assertEqual(find_secrets("token=test"), [])

    def test_database_url_is_categorized(self):
        findings = find_secrets("postgres://user:password123@localhost/db")
        self.assertEqual(findings[0].category, "database_url")

    def test_multiple_findings_are_aggregated(self):
        findings = {item.category: item.count for item in find_secrets("AWS_SECRET=abcdefghijk AKIAABCDEFGHIJKLMNOP")}
        self.assertEqual(findings["named_secret"], 1)
        self.assertEqual(findings["aws_access_key"], 1)


class OutputPathSafetyExpansionTests(unittest.TestCase):
    def test_absolute_output_inside_repository_is_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            self.assertEqual(resolve_output_path(root, str(root / "docs")).name, "docs")

    def test_absolute_output_outside_repository_is_rejected(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside:
            with self.assertRaises(SecurityPolicyError):
                resolve_output_path(Path(td), str(Path(outside) / "docs"))

    def test_allow_absolute_outside_is_explicit(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside:
            path = resolve_output_path(Path(td), str(Path(outside) / "docs"), allow_absolute_outside=True)
            self.assertTrue(str(path).endswith("docs"))

    def test_write_generated_overwrites_marked_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "doc.md"
            path.write_text(GENERATED_MARKER + "\nold", encoding="utf-8")
            write_generated(path, GENERATED_MARKER + "\nnew")
            self.assertIn("new", path.read_text(encoding="utf-8"))

    def test_write_generated_rejects_symlink_file_when_supported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / "target.md"
            link = root / "link.md"
            target.write_text(GENERATED_MARKER, encoding="utf-8")
            try:
                link.symlink_to(target)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            with self.assertRaises(SecurityPolicyError):
                write_generated(link, GENERATED_MARKER + "\nnew")


class FixtureResolverTests(unittest.TestCase):
    def test_typescript_imports_resolve_to_files(self):
        with tempfile.TemporaryDirectory() as td:
            _, graph, _, _ = _run_fixture("typescript_web_api", Path(td))
            route = _node(graph, "FILE", "routes/checkout.ts")
            controller = _node(graph, "FILE", "controllers/checkout-controller.ts")
            self.assertTrue(any(e.kind == "IMPORTS" and e.source == route.id and e.target == controller.id for e in graph.edges.values()))

    def test_typescript_tsconfig_path_alias_resolves(self):
        with tempfile.TemporaryDirectory() as td:
            _, graph, _, _ = _run_fixture("typescript_web_api", Path(td))
            controller = _node(graph, "FILE", "controllers/checkout-controller.ts")
            service = _node(graph, "FILE", "services/checkout-service.ts")
            self.assertTrue(any(e.kind == "IMPORTS" and e.source == controller.id and e.target == service.id for e in graph.edges.values()))

    def test_typescript_endpoint_handles_imported_controller_method(self):
        with tempfile.TemporaryDirectory() as td:
            _, graph, _, _ = _run_fixture("typescript_web_api", Path(td))
            endpoint = _node(graph, "API_ENDPOINT", "/checkout")
            self.assertTrue(any(e.kind == "HANDLES" and e.source == endpoint.id for e in graph.edges.values()))

    def test_typescript_repository_table_edge_is_inferred(self):
        with tempfile.TemporaryDirectory() as td:
            _, graph, _, _ = _run_fixture("typescript_web_api", Path(td))
            table = _node(graph, "TABLE", "orders")
            self.assertTrue(any(e.kind in {"READS", "WRITES"} and e.target == table.id for e in graph.edges.values()))

    def test_python_fastapi_endpoint_to_table_has_path(self):
        with tempfile.TemporaryDirectory() as td:
            _, graph, _, _ = _run_fixture("python_fastapi", Path(td))
            endpoint = _node(graph, "API_ENDPOINT", "/checkout")
            table = _node(graph, "TABLE", "orders")
            self.assertTrue(graph.has_path(endpoint.id, table.id))

    def test_python_import_alias_metadata_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            _, graph, _, _ = _run_fixture("python_fastapi", Path(td))
            imports = [e for e in graph.edges.values() if e.kind == "IMPORTS" and e.properties.get("imported_names")]
            self.assertTrue(any(any(item.get("name") == "CheckoutService" for item in e.properties.get("imported_names", [])) for e in imports))

    def test_event_fixture_detects_publish_and_consume(self):
        with tempfile.TemporaryDirectory() as td:
            _, graph, _, _ = _run_fixture("event_driven_js", Path(td))
            event = _node(graph, "EVENT", "order.created")
            kinds = {e.kind for e in graph.edges.values() if e.target == event.id or e.source == event.id}
            self.assertIn("PUBLISHES", kinds)
            self.assertIn("CONSUMES", kinds)

    def test_workflow_steps_include_business_path(self):
        with tempfile.TemporaryDirectory() as td:
            _, _, air, _ = _run_fixture("python_fastapi", Path(td))
            joined = " ".join(" ".join(item["steps"]) for item in air["workflows"])
            self.assertIn("checkout", joined)
            self.assertIn("orders", joined)


class FrameworkAndMetadataTests(unittest.TestCase):
    def test_framework_detection_emits_framework_nodes(self):
        with tempfile.TemporaryDirectory() as td:
            _, graph, air, _ = _run_fixture("python_fastapi", Path(td))
            frameworks = detect_frameworks(graph, set(air["stack"]))
            self.assertTrue(any(item["framework"] == "FastAPI" for item in frameworks))

    def test_analysis_manifest_counts_capabilities(self):
        with tempfile.TemporaryDirectory() as td:
            _, _, _, manifest = _run_fixture("typescript_web_api", Path(td))
            counts = manifest["stats"]["analyzer_capabilities"]
            self.assertGreaterEqual(counts.get("STRUCTURAL", 0), 1)

    def test_analysis_manifest_reports_resolver_edges(self):
        with tempfile.TemporaryDirectory() as td:
            _, _, _, manifest = _run_fixture("typescript_web_api", Path(td))
            self.assertGreater(manifest["stats"]["resolver_edges_added"], 0)

    def test_file_nodes_include_backend_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            _, graph, _, _ = _run_fixture("python_fastapi", Path(td))
            file_node = _node(graph, "FILE", "main.py")
            self.assertEqual(file_node.properties["backend"], "python-ast")

    def test_evidence_includes_analyzer_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            _, graph, _, _ = _run_fixture("python_fastapi", Path(td))
            self.assertTrue(any(ev.analyzer for node in graph.nodes.values() for ev in node.evidence))


class ValidationSchemaExpansionTests(unittest.TestCase):
    def setUp(self):
        self.graph = CodeGraph()
        self.graph.add_node(Node(id="N1", kind="FILE", name="app.py", path="app.py", evidence=[Evidence(id="EVD-1", path="app.py")]))

    def test_parse_workflow_synthesis_accepts_valid_payload(self):
        payload = '{"workflow_id":"WF-001","name":"checkout","trigger":"POST","steps":["route"],"risks":[],"unknowns":[],"evidence_ids":["EVD-1"]}'
        result, warnings = parse_workflow_synthesis(payload, {"id": "WF-001"}, self.graph)
        self.assertEqual(result.evidence_ids, ["EVD-1"])
        self.assertEqual(warnings, [])

    def test_parse_workflow_synthesis_rejects_wrong_id(self):
        result, _ = parse_workflow_synthesis('{"workflow_id":"WF-999","name":"x","trigger":"x","steps":[],"risks":[],"unknowns":[],"evidence_ids":[]}', {"id": "WF-001"}, self.graph)
        self.assertIsNone(result)

    def test_parse_system_summary_accepts_valid_payload(self):
        payload = '{"repository_name":"repo","purpose":"UNKNOWN","architecture_style":"modular","major_components":["src"],"risks":[],"unknowns":[],"evidence_ids":["EVD-1"]}'
        result, _ = parse_system_summary(payload, "repo", self.graph)
        self.assertEqual(result.repository_name, "repo")

    def test_parse_system_summary_rejects_wrong_repo(self):
        result, _ = parse_system_summary('{"repository_name":"other","purpose":"UNKNOWN","architecture_style":"x","major_components":[],"risks":[],"unknowns":[],"evidence_ids":[]}', "repo", self.graph)
        self.assertIsNone(result)

    def test_parse_risk_candidate_accepts_known_severity(self):
        result, _ = parse_risk_candidate('{"title":"x","severity":"HIGH","rationale":"r","mitigation":"UNKNOWN","evidence_ids":["EVD-1"]}', self.graph)
        self.assertEqual(result.severity, "HIGH")

    def test_parse_risk_candidate_rejects_unknown_severity_value(self):
        result, _ = parse_risk_candidate('{"title":"x","severity":"SEVERE","rationale":"r","mitigation":"m","evidence_ids":[]}', self.graph)
        self.assertIsNone(result)

    def test_parse_or_repair_component_synthesis_repairs_once(self):
        component = ArchitectureComponent("CMP-001", "src", ["app.py"], "source", ["N1"])
        good = '{"component_id":"CMP-001","purpose":"UNKNOWN","responsibilities":[],"dependencies":[],"runtime_behavior":"UNKNOWN","risks":[],"unknowns":[],"evidence_ids":["EVD-1"]}'
        result, warnings = parse_or_repair_component_synthesis("not json", component, self.graph, lambda _warnings: good)
        self.assertEqual(result.evidence_ids, ["EVD-1"])
        self.assertTrue(warnings)

    def test_validation_filters_fake_evidence_in_system_summary(self):
        payload = '{"repository_name":"repo","purpose":"UNKNOWN","architecture_style":"modular","major_components":[],"risks":[],"unknowns":[],"evidence_ids":["EVD-1","EVD-fake"]}'
        result, warnings = parse_system_summary(payload, "repo", self.graph)
        self.assertEqual(result.evidence_ids, ["EVD-1"])
        self.assertTrue(any("unknown evidence" in warning for warning in warnings))


class DiagramAndArchitectureTests(unittest.TestCase):
    def test_dependency_diagram_lists_component_dependency(self):
        air = ArchitectureIR("2", "repo", "style", [
            ArchitectureComponent("CMP-001", "api", ["api.py"], "api", ["N1"], dependencies=["db"])
        ], [], [], [], [], [], [])
        self.assertIn("api", dependency_mermaid(air))
        self.assertIn("db", dependency_mermaid(air))

    def test_generate_dependency_diagram_file(self):
        air = ArchitectureIR("2", "repo", "style", [], [], [], [], [], [], [])
        with tempfile.TemporaryDirectory() as td:
            created = generate_diagrams(air, Path(td), ["dependency"], force=True)
            self.assertEqual(created[0].name, "dependency.mmd")

    def test_architecture_reasons_are_emitted(self):
        graph = CodeGraph()
        graph.add_node(Node(id="F1", kind="FILE", name="src/app.py", path="src/app.py", evidence=[Evidence(id="E1", path="src/app.py")]))
        air = infer_architecture(Path("."), graph, set(), [])
        self.assertTrue(air.architecture_reasons)

    def test_has_path_honors_depth_limit(self):
        graph = CodeGraph()
        for i in range(3):
            graph.add_node(Node(id=f"N{i}", kind="FUNCTION", name=str(i)))
        from codebase_architect.models import Edge
        graph.add_edge(Edge(id="E1", kind="CALLS", source="N0", target="N1"))
        graph.add_edge(Edge(id="E2", kind="CALLS", source="N1", target="N2"))
        self.assertFalse(graph.has_path("N0", "N2", max_depth=1))
        self.assertTrue(graph.has_path("N0", "N2", max_depth=2))

    def test_find_node_returns_kind_and_name_match(self):
        graph = CodeGraph()
        graph.add_node(Node(id="N", kind="TABLE", name="orders"))
        self.assertEqual(graph.find_node("TABLE", "orders").id, "N")


class OptionalRuntimeProviderTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("CODEBASE_ARCHITECT_TEST_OLLAMA"), "real Ollama endpoint not requested")
    def test_real_ollama_provider_smoke(self):
        from codebase_architect.llm import provider_from_config
        cfg = Config()
        cfg.model.provider = "ollama"
        cfg.model.name = os.environ.get("CODEBASE_ARCHITECT_TEST_OLLAMA_MODEL", "")
        provider = provider_from_config(cfg.model, cfg)
        self.assertTrue(provider.health()[0])

    @unittest.skipUnless(os.environ.get("CODEBASE_ARCHITECT_TEST_OPENAI_COMPATIBLE"), "real OpenAI-compatible endpoint not requested")
    def test_real_openai_compatible_provider_smoke(self):
        from codebase_architect.llm import provider_from_config
        cfg = Config()
        cfg.model.provider = "openai-compatible"
        cfg.model.name = os.environ.get("CODEBASE_ARCHITECT_TEST_OPENAI_COMPATIBLE_MODEL", "")
        cfg.model.base_url = os.environ["CODEBASE_ARCHITECT_TEST_OPENAI_COMPATIBLE"]
        cfg.model.api_key_env = "CODEBASE_ARCHITECT_TEST_OPENAI_COMPATIBLE_KEY"
        provider = provider_from_config(cfg.model, cfg)
        self.assertTrue(provider.health()[0])


if __name__ == "__main__":
    unittest.main()
