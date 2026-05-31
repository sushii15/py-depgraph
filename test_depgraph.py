#!/usr/bin/env python3
"""Tests for py-depgraph"""
import unittest
import os
import sys
import tempfile
import json

sys.path.insert(0, os.path.dirname(__file__))
from depgraph import (
    extract_imports, module_name_from_path, build_graph,
    find_cycles, compute_metrics, analyze
)


class TestExtractImports(unittest.TestCase):

    def _write_temp(self, source):
        f = tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8")
        f.write(source)
        f.flush()
        return f.name

    def test_simple_import(self):
        path = self._write_temp("import os\nimport sys\n")
        result = extract_imports(path)
        self.assertIn("os", result)
        self.assertIn("sys", result)
        os.unlink(path)

    def test_from_import(self):
        path = self._write_temp("from collections import defaultdict\n")
        result = extract_imports(path)
        self.assertIn("collections", result)
        os.unlink(path)

    def test_dotted_import_truncated(self):
        path = self._write_temp("import os.path\n")
        result = extract_imports(path)
        self.assertIn("os", result)
        self.assertNotIn("os.path", result)
        os.unlink(path)

    def test_syntax_error_returns_empty(self):
        path = self._write_temp("def broken(:\n    pass\n")
        result = extract_imports(path)
        self.assertEqual(result, [])
        os.unlink(path)


class TestModuleNameFromPath(unittest.TestCase):

    def test_simple(self):
        self.assertEqual(module_name_from_path("main.py"), "main")

    def test_nested(self):
        result = module_name_from_path(os.path.join("src", "utils", "parser.py"))
        self.assertIn("parser", result)

    def test_init(self):
        result = module_name_from_path(os.path.join("mypackage", "__init__.py"))
        self.assertIn("mypackage", result)


class TestBuildGraph(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def _write(self, relpath, content):
        full = os.path.join(self.tmpdir, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)

    def test_basic_graph(self):
        self._write("main.py", "import utils\n")
        self._write("utils.py", "import os\n")
        graph = build_graph(self.tmpdir)
        self.assertIn("main", graph["nodes"])
        self.assertIn("utils", graph["nodes"])

    def test_edge_detection(self):
        self._write("a.py", "import b\n")
        self._write("b.py", "")
        graph = build_graph(self.tmpdir)
        self.assertIn("b", graph["nodes"]["a"]["imports"])

    def test_imported_by_populated(self):
        self._write("a.py", "import b\n")
        self._write("b.py", "")
        graph = build_graph(self.tmpdir)
        self.assertIn("a", graph["nodes"]["b"]["imported_by"])


class TestFindCycles(unittest.TestCase):

    def _make_nodes(self, deps):
        """deps: {mod: [list_of_imports]}"""
        nodes = {}
        for mod, imports in deps.items():
            nodes[mod] = {"imports": imports, "imported_by": []}
        return nodes

    def test_no_cycle(self):
        nodes = self._make_nodes({"a": ["b"], "b": ["c"], "c": []})
        cycles = find_cycles(nodes)
        self.assertEqual(cycles, [])

    def test_simple_cycle(self):
        nodes = self._make_nodes({"a": ["b"], "b": ["a"]})
        cycles = find_cycles(nodes)
        self.assertTrue(len(cycles) > 0)

    def test_self_loop(self):
        nodes = self._make_nodes({"a": ["a"]})
        # Self-imports are removed in build_graph, but test cycle detection robustness
        cycles = find_cycles(nodes)
        # a -> a is a cycle of length 1
        self.assertTrue(len(cycles) > 0)

    def test_triangle_cycle(self):
        nodes = self._make_nodes({"a": ["b"], "b": ["c"], "c": ["a"]})
        cycles = find_cycles(nodes)
        self.assertTrue(len(cycles) > 0)


class TestAnalyze(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def _write(self, relpath, content):
        full = os.path.join(self.tmpdir, relpath)
        with open(full, "w") as f:
            f.write(content)

    def test_analyze_returns_dict(self):
        self._write("x.py", "import os\n")
        result = analyze(self.tmpdir, quiet=True)
        self.assertIn("summary", result)
        self.assertIn("modules", result)
        self.assertIn("cycles", result)

    def test_analyze_json_output(self):
        self._write("x.py", "import os\n")
        json_path = os.path.join(self.tmpdir, "out.json")
        analyze(self.tmpdir, output_json=json_path, quiet=True)
        self.assertTrue(os.path.exists(json_path))
        with open(json_path) as f:
            data = json.load(f)
        self.assertIn("summary", data)

    def test_summary_fields(self):
        self._write("a.py", "import b\n")
        self._write("b.py", "")
        result = analyze(self.tmpdir, quiet=True)
        s = result["summary"]
        self.assertIn("total_modules", s)
        self.assertIn("total_edges", s)
        self.assertIn("circular_imports", s)
        self.assertEqual(s["total_modules"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
