import json
import tempfile
import unittest
from pathlib import Path
from tools.compare_trials import summarize


class ComparisonTests(unittest.TestCase):
    def test_provider_errors_not_model_failures(self):
        records = [
            {'task_id':'RW01V4','model_requested':'gemma','status':'api_error'},
            {'task_id':'RW01V4','model_requested':'lightning','status':'completed',
             'grade':{'strict_pass':False,'score':.98824,'affected_f1':16/17,
                      'root_correct':True,'fix_correct':True,
                      'recovery_safe':True,'recovery_success':True,
                      'strict_failure_reasons':['initial_service_inventory_inexact']},
             'protocol_errors':[]},
        ]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'a.jsonl'
            p.write_text(''.join(json.dumps(x)+'\n' for x in records))
            rows = {r['model']:r for r in summarize([p])}
        self.assertEqual(rows['gemma']['completed'], 0)
        self.assertIsNone(rows['gemma']['strict_pass_rate_completed_only'])
        self.assertEqual(rows['gemma']['provider_or_orchestration_errors'], 1)
        self.assertEqual(rows['lightning']['safe_complete_recoveries'], 1)
        self.assertEqual(rows['lightning']['strict_passes'], 0)


if __name__ == '__main__':
    unittest.main()
