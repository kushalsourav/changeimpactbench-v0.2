"""Offline V6 validity gates. Scripted agents are explicitly NOT provider trials."""
import json
import unittest
from copy import deepcopy
from pathlib import Path
from benchmarks.spec import source_case, get_spec, service_codes, reference_trajectory
from benchmarks.environment import AgentEnvironment
from benchmarks.native_agent import agent_prompt, recorded_implementation_hashes
from benchmarks.grader import replay_record
from dashboard_data import audit_record
from oracle import simulate, patch_facts, reference_answer, reference_audit
from tests.test_v5_integrated import run_mock
from scripts.v6_ablation_report import build_report

ROOT = Path(__file__).resolve().parent.parent

class V6ConditionsTests(unittest.TestCase):
    def test_fairness_oracle_unique_optimal_safe_and_near_misses(self):
        for i in range(1, 7):
            for suffix in ('V6N','V6CF'):
                task=f'RW{i:02}{suffix}'
                with self.subTest(task=task):
                    case=source_case(task)
                    before,_=simulate(case)
                    expected=reference_answer(case)
                    costs=[]
                    for action in case['actions']:
                        after,_=simulate(case,patch_facts(case['facts'],action))
                        if not after: costs.append((action['cost'],action['id']))
                    self.assertGreaterEqual(len(costs),2)
                    costs.sort()
                    self.assertNotEqual(costs[0][0],costs[1][0])
                    self.assertEqual(expected['fix_id'],costs[0][1])
                    self.assertEqual(set(expected['failed_services']),before)
                    cheap=[a for a in case['actions'] if a['cost']<costs[0][0]]
                    self.assertTrue(cheap)
                    self.assertTrue(all(simulate(case,patch_facts(case['facts'],a))[0]
                                        for a in cheap))
                    unsafe=next(a for a in case['actions'] if a['id']=='A90')
                    harm,_=simulate(case,patch_facts(case['facts'],unsafe))
                    self.assertTrue(harm-before)
                    self.assertFalse(harm & before, 'Cheap near-miss must restore all originally failed services but harm a healthy one')
                    self.assertEqual(set(service_codes(task)),{x['id'] for x in case['facts']['topology']})

    def test_no_causal_title_prompt_and_balanced_hypotheses(self):
        for i in range(1,7):
            for suffix in ('V6N','V6CF'):
                task=f'RW{i:02}{suffix}'
                public=json.loads(agent_prompt(task))
                self.assertNotIn('incident_name',public)
                self.assertNotIn('source_url',public)
                self.assertNotIn('Cloudflare',json.dumps(public))
                self.assertNotIn('GitHub',json.dumps(public))
                self.assertEqual(len(public['hypotheses']),6)
                lengths=[len(item['description'].split()) for item in public['hypotheses']]
                self.assertLessEqual(max(lengths)-min(lengths),4, (task,lengths))

    def test_scan_not_complete_while_impact_discoverable(self):
        for i in range(1,7):
            for suffix in ('V6N','V6CF'):
                task=f'RW{i:02}{suffix}';env=AgentEnvironment(get_spec(task),source_case(task))
                env.execute('read_alert',{})
                scan=env.execute('scan_service_health',{})['result']
                full=reference_answer(source_case(task))['failed_services']
                self.assertLess(scan['observed_count'],scan['service_count'])
                codes=service_codes(task)
                discovered={name for name in codes if env.execute('inspect_metrics',{'service':codes[name]})['result']['health_probe']=='unavailable'}
                self.assertEqual(discovered,set(full))

    def test_counterfactual_old_repair_fails_and_precondition_is_inspectable(self):
        for i in range(1,7):
            task=f'RW{i:02}V6CF';case=source_case(task)
            old=reference_answer(source_case(f'RW{i:02}V6N'))['fix_id']
            act=next(a for a in case['actions'] if a['id']==old)
            self.assertTrue(simulate(case,patch_facts(case['facts'],act))[0])
            env=AgentEnvironment(get_spec(task),case)
            name=f'quorum-gateway-{i:02}'
            observed=env.execute('inspect_config',{'service':service_codes(task)[name]})['result']
            reqs=observed['candidate_precondition_checks']
            self.assertEqual(reqs[0]['action_id'],'A95')
            self.assertTrue(reqs[0]['observed'])
            self.assertEqual(next(x for x in case['facts']['topology'] if x['id']==name)['needs_at_least']['count'],2)
            # Mutate the fixture ONLY in this local test: a false precondition
            # invalidates A95, but A96 still restores the incident.
            variant=deepcopy(case)
            variant['facts']['state']['recovery_validation']['replica_ready']=False
            a95=next(x for x in variant['actions'] if x['id']=='A95')
            a96=next(x for x in variant['actions'] if x['id']=='A96')
            self.assertEqual(patch_facts(variant['facts'],a95),variant['facts'])
            self.assertFalse(simulate(variant,patch_facts(variant['facts'],a96))[0])

    def test_scripted_reference_passes_original_graph_and_dash_audit(self):
        for i in range(1,7):
            for suffix in ('V6N','V6CF'):
                task=f'RW{i:02}{suffix}'
                with self.subTest(task=task):
                    rec=run_mock(task)
                    self.assertTrue(rec['grade']['strict_pass'],rec['grade'])
                    self.assertTrue(replay_record(rec)['verified'])
                    audit=audit_record(rec)
                    self.assertEqual(audit['status'],'completed',audit['warnings'])
                    self.assertTrue(audit['reference_matches'])
                    self.assertTrue(audit['stored_grade_matches'])

    def test_ablation_does_not_fabricate_model_trials(self):
        source='results/imported/RW05V5_recursive_flint_2026-11-07.jsonl'
        report=build_report([source])
        self.assertFalse(report['ready_to_claim_ablation'])
        self.assertEqual(report['all_trials'],[])

    def test_user_supplied_real_v5_run_passes_independent_audit(self):
        p=ROOT/'results/imported/RW05V5_recursive_flint_2026-11-07.jsonl'
        record=json.loads(p.read_text())
        a=audit_record(record)
        self.assertEqual(a['status'],'completed',a['warnings'])
        self.assertTrue(a['reference_matches'])
        self.assertTrue(a['stored_grade_matches'])
        self.assertEqual(a['grade']['score'],.95)

    def test_complete_packaged_source_sha_manifest(self):
        import hashlib
        manifest=json.loads((ROOT/'V6_SOURCE_MANIFEST.json').read_text())
        self.assertGreater(manifest['verified_file_count'],240)
        for path,digest in manifest['sha256'].items():
            with self.subTest(path=path):
                self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),digest)

    def test_old_v5_hashes_bound_to_immutable_archive(self):
        import zipfile,hashlib
        with zipfile.ZipFile(ROOT/'baseline/ChangeImpactBench_V5_INTEGRATED_SOURCE.zip') as z:
            base='changeimpactbench-v0.2/'
            names=['benchmarks/native_agent.py','benchmarks/environment.py','benchmarks/v5_fixtures/RW05.json']
            old={n:hashlib.sha256(z.read(base+n)).hexdigest() for n in names}
        self.assertEqual(recorded_implementation_hashes('RW05V5',old),old)
        tampered=dict(old);tampered['benchmarks/environment.py']='0'*64
        self.assertNotEqual(recorded_implementation_hashes('RW05V5',tampered),tampered)

if __name__=='__main__':unittest.main()
