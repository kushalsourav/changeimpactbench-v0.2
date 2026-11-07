"""Cleanup plans are explicitly scoped, dry-run first, and never touch secrets."""
import tempfile
from pathlib import Path
import unittest
from scripts.clean_native_only import plan

class CleanNativeOnlyTests(unittest.TestCase):
    def test_cleanup_plan_keeps_secrets_and_active_seeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for folder in ('results','docs','tasks','reference','tests','api/tests'):
                (root/folder).mkdir(parents=True)
            for p in ('.env','.env.example','results/a.jsonl','results/README.md',
                      'docs/LEGACY.md','docs/PUBLIC_INCIDENT_DATASET_v0.9.9.md','docs/RELEASE_v0.9.9.md',
                      'tasks/T01.json','tasks/T08.json','tasks/RW01.json','reference/RW01.json',
                      'tests/test_agent_graph.py','tests/test_eval.py','agentic_v3.py'):
                (root/p).write_text('test')
            items={p.relative_to(root).as_posix() for group in plan(root).values() for p in group}
            self.assertIn('results/a.jsonl',items)
            self.assertIn('docs/LEGACY.md',items)
            self.assertIn('tests/test_eval.py',items)
            self.assertIn('agentic_v3.py',items)
            self.assertIn('tasks/T01.json',items)
            self.assertIn('tasks/T08.json',items)
            for safe in ('.env','.env.example','results/README.md','docs/PUBLIC_INCIDENT_DATASET_v0.9.9.md','docs/RELEASE_v0.9.9.md',
                         'tasks/RW01.json','reference/RW01.json','tests/test_agent_graph.py'):
                self.assertNotIn(safe,items)

if __name__=='__main__':
    unittest.main()
