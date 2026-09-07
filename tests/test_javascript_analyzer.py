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

if __name__=="__main__": unittest.main()
