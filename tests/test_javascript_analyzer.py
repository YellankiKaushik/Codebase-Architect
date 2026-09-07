import unittest
from codebase_architect.analyzers.javascript import analyze

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

if __name__=="__main__": unittest.main()
