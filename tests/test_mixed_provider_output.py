import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import run_mixed_providers as batch


class TestMixedOutputs(unittest.TestCase):
    def test_each_model_receives_own_result_path(self):
        cmds = list(batch.commands(['google-ai-studio/gemini-3.5-flash-lite', 'recursive/flint-v1.0:free'],
                                   'RW02V4', 1, 4, 0, 8000, 'low',
                                   ['results/.mixed_staging/x/model_01.jsonl',
                                    'results/.mixed_staging/x/model_02.jsonl']))
        self.assertNotEqual(cmds[0][cmds[0].index('--output')+1],
                            cmds[1][cmds[1].index('--output')+1])
        self.assertIn('run_gemini.py', cmds[0][2])
        self.assertIn('run_graph_agent.py', cmds[1][2])

    def test_merge_preserves_raw_records_and_never_rewrites_existing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / 'batch.jsonl'
            a = root / 'a.jsonl'
            b = root / 'b.jsonl'
            data1 = {'model_requested': 'recursive/flint-v1.0:free', 'status':'completed'}
            data2 = {'model_requested': 'gemini-3.5-flash-lite', 'status':'api_error'}
            a.write_text(json.dumps(data1)+'\n')
            b.write_text(json.dumps(data2)+'\n')
            self.assertEqual(batch.merge_completed(a, out), 1)
            self.assertEqual(batch.merge_completed(b, out), 1)
            self.assertEqual([json.loads(x) for x in out.read_text().splitlines()], [data1, data2])
            self.assertFalse(a.exists())
            self.assertFalse(b.exists())

    def test_partial_record_does_not_change_batch(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / 'batch.jsonl'
            out.write_text('{"previous":true}\n')
            a = root / 'unfinished.jsonl'
            a.write_text('{"status":')
            with self.assertRaises(ValueError):
                batch.merge_completed(a, out)
            self.assertEqual(out.read_text(), '{"previous":true}\n')
            self.assertTrue(a.exists())


if __name__ == '__main__':
    unittest.main()
