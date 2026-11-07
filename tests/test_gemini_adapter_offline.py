import ast
import hashlib
import zipfile
from pathlib import Path
import unittest


class GeminiAdapterOfflineTests(unittest.TestCase):
    def test_adapter_does_not_modify_frozen_runner(self):
        root = Path(__file__).resolve().parents[1]
        from benchmarks.native_agent import implementation_hashes
        with zipfile.ZipFile(root/'baseline/ChangeImpactBench_V4_CURRENT_SOURCE.zip') as baseline:
            historic = baseline.read('changeimpactbench-v0.2/benchmarks/runner.py')
        self.assertEqual(hashlib.sha256(historic).hexdigest(),
                         '7b357ec367c9109936d7278d106e9b2025259832de6b66ee83e61c6c016135de')
        self.assertIn('benchmarks/runner.py', implementation_hashes())
        tree = ast.parse((root/'tools/run_gemini.py').read_text())
        self.assertTrue(any(isinstance(node, ast.FunctionDef) and node.name == 'gemini_graph_factory' for node in tree.body))


if __name__ == '__main__':
    unittest.main()
