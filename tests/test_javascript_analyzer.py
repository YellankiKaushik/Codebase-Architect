import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codebase_architect.config import Config
from codebase_architect.analyzers.javascript import analyze
from codebase_architect.graph import CodeGraph
from codebase_architect.pipeline import run_analysis

FIXTURES = Path(__file__).parent / "fixtures"

class JavaScriptAnalyzerTests(unittest.TestCase):
    def test_extracts_route_import_and_env(self):
        source = '''
import express from "express";
import pg from "pg";
const app = express();
const handler = async () => process.env.DB_PASSWORD;
app.post("/orders", handler);
'''
        result=analyze("src/server.ts","abc",source,"typescript")
        self.assertEqual(result.capability, "AST")
        self.assertIn("Express",result.stack)
        self.assertTrue(any(n.kind=="API_ENDPOINT" and n.name=="POST /orders" for n in result.nodes))
        self.assertTrue(any(n.kind=="CONFIGURATION_KEY" and n.name=="DB_PASSWORD" for n in result.nodes))
        self.assertTrue(any(e.kind=="IMPORTS" for e in result.edges))

    def test_extracts_next_route_and_bracket_env(self):
        source = '''
export async function GET() {
  return Response.json({ token: process.env["API_TOKEN"] });
}
'''
        result=analyze("app/api/users/route.ts","abc",source,"typescript")
        self.assertIn("Next.js",result.stack)
        self.assertTrue(any(n.kind=="API_ENDPOINT" and n.name=="GET /api/users" for n in result.nodes))
        self.assertTrue(any(n.kind=="CONFIGURATION_KEY" and n.name=="API_TOKEN" for n in result.nodes))

    def test_ast_extracts_es_import_shapes_and_aliases(self):
        source = '''
import DefaultThing, { Foo as Bar, Baz } from "./mod";
import * as tools from "./tools";
import "./side-effects";
'''
        result = analyze("src/imports.ts", "abc", source, "typescript")
        imports = [e.properties for e in result.edges if e.kind == "IMPORTS"]
        imported = [item for props in imports for item in props.get("imported_names", [])]
        self.assertIn({"name": "default", "alias": "DefaultThing", "kind": "default"}, imported)
        self.assertIn({"name": "Foo", "alias": "Bar", "kind": "named"}, imported)
        self.assertIn({"name": "*", "alias": "tools", "kind": "namespace"}, imported)
        self.assertTrue(any(item["kind"] == "side-effect" for item in imported))

    def test_ast_extracts_require_and_dynamic_import(self):
        source = '''
const repo = require("./repo");
async function load() { return import("./lazy"); }
'''
        result = analyze("src/load.ts", "abc", source, "typescript")
        kinds = {e.properties.get("import_kind") for e in result.edges if e.kind == "IMPORTS"}
        self.assertIn("require", kinds)
        self.assertIn("dynamic", kinds)

    def test_ast_extracts_default_reexport_and_export_star(self):
        source = '''
export default function handler() {}
export { handler as renamed } from "./handlers";
export * from "./all";
'''
        result = analyze("src/exports.ts", "abc", source, "typescript")
        file_node = next(n for n in result.nodes if n.kind == "FILE")
        exports = file_node.properties.get("exports", [])
        self.assertTrue(any(item["kind"] == "default" for item in exports))
        self.assertTrue(any(item["alias"] == "renamed" for item in exports))
        self.assertTrue(any(item["kind"] == "export-star" for item in exports))
        self.assertTrue(any(e.properties.get("import_kind") == "re-export" for e in result.edges))

    def test_ast_extracts_class_inheritance_and_constructor_usage(self):
        source = '''
class Parent {}
export class Child extends Parent {
  constructor() {}
  static make() { return new Child(); }
}
'''
        result = analyze("src/classes.ts", "abc", source, "typescript")
        child = next(n for n in result.nodes if n.kind == "CLASS" and n.name == "Child")
        self.assertEqual(child.properties["extends"], "Parent")
        self.assertTrue(any(e.kind == "DEPENDS_ON" and e.source == child.id for e in result.edges))
        self.assertTrue(any(e.kind == "CALLS" and e.evidence and "constructor usage Child" == e.evidence[0].note for e in result.edges))

    def test_ast_extracts_async_arrow_interface_type_alias_enum_and_methods(self):
        source = '''
export interface User { id: string }
export type UserId = string;
export enum Status { Open }
export async function fetchUser() {}
export const saveUser = async () => fetchUser();
export class UserService {
  static build() { return saveUser(); }
  run() { return fetchUser(); }
}
'''
        result = analyze("src/symbols.ts", "abc", source, "typescript")
        kinds = {(n.kind, n.name) for n in result.nodes}
        self.assertIn(("INTERFACE", "User"), kinds)
        self.assertIn(("TYPE_ALIAS", "UserId"), kinds)
        self.assertIn(("ENUM", "Status"), kinds)
        self.assertTrue(any(n.kind == "FUNCTION" and n.name == "fetchUser" and n.properties.get("async") for n in result.nodes))
        self.assertTrue(any(n.kind == "FUNCTION" and n.name == "saveUser" and n.properties.get("function_kind") == "arrow" for n in result.nodes))
        self.assertTrue(any(n.kind == "METHOD" and n.name == "build" and n.properties.get("static") for n in result.nodes))
        self.assertTrue(any(n.kind == "METHOD" and n.name == "run" for n in result.nodes))

    def test_ast_extracts_commonjs_exports(self):
        source = '''
exports.named = function() {};
module.exports = { named };
'''
        result = analyze("src/commonjs.js", "abc", source, "javascript")
        self.assertTrue(any(n.properties.get("commonjs") for n in result.nodes))

    def test_ast_extracts_process_and_import_meta_env(self):
        source = '''
const a = process.env.DB_URL;
const b = process.env["API_TOKEN"];
const c = import.meta.env.VITE_URL;
'''
        result = analyze("src/env.ts", "abc", source, "typescript")
        keys = {n.name for n in result.nodes if n.kind == "CONFIGURATION_KEY"}
        self.assertEqual({"DB_URL", "API_TOKEN", "VITE_URL"}, keys)

    def test_ast_extracts_express_route(self):
        source = '''
import express from "express";
const router = express.Router();
router.post("/orders", controller.create);
'''
        result = analyze("src/routes.ts", "abc", source, "typescript")
        endpoint = next(n for n in result.nodes if n.kind == "API_ENDPOINT")
        self.assertEqual(endpoint.properties["handler"], "controller.create")

    def test_ast_extracts_next_route(self):
        source = "export async function POST() { return Response.json({ ok: true }); }"
        result = analyze("app/api/orders/route.ts", "abc", source, "typescript")
        self.assertTrue(any(n.kind == "API_ENDPOINT" and n.name == "POST /api/orders" for n in result.nodes))

    def test_ast_feeds_cross_file_resolver_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "typescript_web_api"
            shutil.copytree(FIXTURES / "typescript_web_api", root)
            cfg = Config()
            cfg.output.path = ".tmp/codebase"
            cfg.analysis.exclude.append(".tmp/**")
            result = run_analysis(root, cfg, use_llm=False)
            graph = CodeGraph.from_dict(json.loads((Path(result["output"]) / "evidence" / "code-intelligence-graph.json").read_text(encoding="utf-8")))
            endpoint = _node(graph, "API_ENDPOINT", "/checkout")
            table = _node(graph, "TABLE", "orders")
            self.assertTrue(graph.has_path(endpoint.id, table.id))
            self.assertTrue(any(e.kind == "CALLS" and e.classification == "VERIFIED" for e in graph.edges.values()))

    def test_ast_failure_uses_structural_fallback(self):
        with patch("codebase_architect.analyzers.javascript._parse_tree", return_value=None):
            result = analyze("src/server.ts", "abc", 'import express from "express"; const app = express();', "typescript")
        self.assertEqual(result.backend, "structural-js-ts")
        self.assertEqual(result.capability, "STRUCTURAL")

    def test_manifest_records_ast_mode(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src").mkdir()
            (root / "src" / "app.ts").write_text('export const handler = () => process.env.DB_URL;', encoding="utf-8")
            cfg = Config()
            cfg.output.path = ".tmp/codebase"
            result = run_analysis(root, cfg, use_llm=False)
            manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
        self.assertGreaterEqual(manifest["stats"]["analyzer_capabilities"].get("AST", 0), 1)
        self.assertGreaterEqual(manifest["stats"]["analyzer_backends"].get("tree-sitter-typescript", 0), 1)

    def test_manifest_records_structural_fallback_mode(self):
        with tempfile.TemporaryDirectory() as td, patch("codebase_architect.analyzers.javascript._parse_tree", return_value=None):
            root = Path(td)
            (root / "src").mkdir()
            (root / "src" / "app.ts").write_text('import express from "express"; const app = express();', encoding="utf-8")
            cfg = Config()
            cfg.output.path = ".tmp/codebase"
            result = run_analysis(root, cfg, use_llm=False)
            manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
        self.assertGreaterEqual(manifest["stats"]["analyzer_capabilities"].get("STRUCTURAL", 0), 1)
        self.assertGreaterEqual(manifest["stats"]["analyzer_backends"].get("structural-js-ts", 0), 1)


def _node(graph: CodeGraph, kind: str, contains: str):
    for item in graph.nodes.values():
        if item.kind == kind and (contains in item.name or contains in str(item.path or "")):
            return item
    raise AssertionError(f"missing {kind} containing {contains!r}")

if __name__=="__main__": unittest.main()
