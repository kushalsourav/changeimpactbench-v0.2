"""Source-backed fixtures and interpretation math: offline checks, no live provider data."""
import json
import unittest
from benchmarks.spec import REGISTRY, source_case, get_spec
from benchmarks.native_agent import agent_prompt
from api.routes.synthesis import chart_rows
from oracle import reference_answer, reference_audit

class PublicSourcesTests(unittest.TestCase):
    def test_only_three_real_operator_reports_are_active(self):
        self.assertEqual({t for t in REGISTRY if t.endswith('V4')},{'RW01V4','RW02V4','RW03V4','RW04V4','RW05V4','RW06V4'})
        for key,spec in REGISTRY.items():
            case=source_case(key)
            self.assertTrue(case['provenance']['source_url'].startswith('https://'))
            self.assertEqual(case['provenance']['source_url'],spec.source_url)
            self.assertTrue(case['provenance']['documented_facts'])
            self.assertTrue(case['provenance']['reconstructed_elements'])
            self.assertIn('NOT production',case['provenance']['measurement_note'])
            prompt=agent_prompt(key)
            self.assertNotIn(spec.source_url,prompt)
            self.assertNotIn('documented_facts',prompt)
            self.assertNotIn('reference_answer',prompt)
            ref=reference_answer(case)
            self.assertEqual(sum(bool(x['full_recovery']) for x in reference_audit(case)['actions'].values())>=1,True)
            self.assertIn(ref['fix_id'],{x['id'] for x in case['actions']})
    def test_llm_charts_use_verified_numeric_data_only(self):
        facts={'episodes':[
          {'model':'m1','gradeable':True,'strict_pass':True,'partial_score':1.0,'impact_f1':1,'root_correct':True,'recovery_success':True,'unsafe_commit':False,'protocol_errors':0},
          {'model':'m1','gradeable':True,'strict_pass':False,'partial_score':.5,'impact_f1':.5,'root_correct':False,'recovery_success':True,'unsafe_commit':False,'protocol_errors':0},
          {'model':'m2','gradeable':False,'strict_pass':None,'partial_score':None,'impact_f1':None,'root_correct':None,'recovery_success':None,'unsafe_commit':False,'protocol_errors':0},
        ]}
        self.assertEqual(chart_rows(facts,'outcome_rates'),[{'label':'m1','value':50.0,'denominator':2}])
        self.assertEqual(chart_rows(facts,'score_by_model'),[{'label':'m1','value':75.0,'denominator':2}])
        errors=chart_rows(facts,'error_counts')
        self.assertEqual(errors[0]['value'],1)
        self.assertEqual(errors[1]['value'],1)
        self.assertTrue(all(row['denominator']==2 for row in errors))

if __name__=='__main__':unittest.main()
