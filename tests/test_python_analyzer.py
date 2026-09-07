import unittest
from codebase_architect.analyzers.python import analyze

class PythonAnalyzerTests(unittest.TestCase):
    def test_extracts_route_import_config_and_function(self):
        source = '''
import os
from fastapi import FastAPI
app = FastAPI()
@app.get("/users")
def users():
    token = os.getenv("API_TOKEN")
    return load_users()
'''
        result=analyze("src/api.py","abc",source)
        kinds=[n.kind for n in result.nodes]
        self.assertIn("API_ENDPOINT",kinds)
        self.assertIn("FUNCTION",kinds)
        self.assertIn("CONFIGURATION_KEY",kinds)
        self.assertIn("FastAPI",result.stack)
        self.assertTrue(any(e.kind=="EXPOSES" for e in result.edges))
        self.assertTrue(any(e.kind=="CALLS" for e in result.edges))

if __name__=="__main__": unittest.main()
