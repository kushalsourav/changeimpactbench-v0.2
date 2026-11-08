import json
import re
import unittest
from pathlib import Path

from benchmarks.grader_source import (DIMENSIONS, asserts, clauses, load_source, score_report)

HERE = Path(__file__).resolve().parents[1] / "benchmarks" / "source_graders"
SEEDS = [f'RW0{i}' for i in range(1, 7)]
PHASES = {'incident_mitigation', 'service_restoration', 'post_incident_remediation', 'contingency_actions'}
STATUSES = {'source_actual', 'source_intermediate', 'source_supported',
            'long_term_remediation', 'unverified', 'source_contradicted'}

GOOD = {
    'RW01': {
        'observed_symptoms': 'The network partition cut connectivity between the East hub and primary data center for 43 seconds. Webhook delivery and Pages builds were paused and not served for most of the incident. No user data was lost.',
        'confirmed_root_cause': 'Orchestrator failed MySQL clusters over to West Coast primaries after the partition. Writes diverged because East held writes that were not replicated and West took new writes. Failing back to East was unsafe.',
        'investigation_evidence': 'The Orchestrator API showed a replication topology with only West Coast servers.',
        'recovery_actions': 'Engineers paused jobs, restored replicas from backup, synchronized both sites, fell back to the original topology and then resumed queued jobs after the backlog.',
        'recovery_verification': 'All pending webhooks and Pages builds were processed and integrity was confirmed before the status returned to green.',
        'acceptable_alternatives': 'Failing forward on West primaries was the data-safe choice. Immediate failback was rejected because it was unsafe.'},
    'RW02': {
        'observed_symptoms': '19 data centers went offline, about 4% of locations but about 50% of requests.',
        'confirmed_root_cause': 'A BGP prefix advertisement policy change re-ordered terms, so the explicit reject term ended up ahead of the site-local terms. Site-local prefixes were withdrawn.',
        'investigation_evidence': 'The configuration diff marked the re-ordered terms with exclamation marks.',
        'recovery_actions': 'Engineers reverted the policy change at each affected location using backup access.',
        'recovery_verification': 'The last revert finished and all data centers were online at 07:42.',
        'acceptable_alternatives': 'Reverting the change was the fix. Adding extra capacity was not described by the source.'},
    'RW03': {
        'observed_symptoms': 'Customers saw 502 errors. CPU spiked to nearly 100% on cores serving HTTP and HTTPS.',
        'confirmed_root_cause': 'A WAF rule contained a regular expression with catastrophic backtracking. The rule went global in seconds with no staged rollout. A CPU protection had been removed in an earlier refactor.',
        'investigation_evidence': 'A performance engineer pulled live CPU data and strace confirmed the WAF was responsible.',
        'recovery_actions': 'At 14:07 engineers ran a global terminate of the WAF, then rolled back the offending rule.',
        'recovery_verification': 'CPU and traffic were back to normal at 14:09. Negative and positive tests in a single city came before the 14:52 global re-enable.',
        'acceptable_alternatives': 'The global terminate came first, then the rule was rolled back. A switch to re2 was a later remediation.'},
    'RW04': {
        'observed_symptoms': 'Traffic dropped about 50% across the network. The outage ran from 21:12 to 21:39.',
        'confirmed_root_cause': "A one-line change deactivated the prefix-list inside the 6-SITE-LOCAL term, so all BGP routes were sent into the backbone. Local-preference 200 beat the local servers' 100, pulling traffic to Atlanta.",
        'investigation_evidence': 'The config diff showed the prefix-list marked inactive and the traffic manager showed Atlanta CPU overloaded.',
        'recovery_actions': 'Engineers disabled the Atlanta router, dropping it from the backbone.',
        'recovery_verification': 'Traffic flowed normally at 21:39, and logs and metrics fully recovered at 22:10.',
        'acceptable_alternatives': 'Engineers disabled the Atlanta router, which restored service. Lowering local-preference and adding maximum-prefix limits were post-incident safeguards.'},
    'RW05': {
        'observed_symptoms': 'Control plane and analytics were down from 11:44 on November 2 until 04:25 on November 4. Customer traffic was not impacted. Raw logs were unavailable and some log data was lost.',
        'confirmed_root_cause': 'Power was lost at the Flexential PDX-04 facility. Kafka and ClickHouse existed only in PDX-04 even though HA services depended on them. The ground fault and generator chain of events is unconfirmed speculation.',
        'investigation_evidence': 'Two routers went offline at 11:44 and could not be reached directly or out of band.',
        'recovery_actions': 'Engineers failed the control plane over to disaster recovery sites in Europe at 13:40. The provider replaced the breakers and restored power, and the facility was bootstrapped.',
        'recovery_verification': 'All services were fully restored at 04:25 on November 4.',
        'acceptable_alternatives': 'Failover to disaster recovery restored the control plane but analytics stayed down. Restoring power and bootstrapping PDX-04 restored everything. Running analytics on DR was not possible.'},
    'RW06': {
        'observed_symptoms': 'About 90% of Workers KV requests failed. The outage lasted 2 hours 28 minutes. DNS, WAF, proxy and cache were not directly impacted.',
        'confirmed_root_cause': 'A storage backend behind Workers KV, partly a third-party provider, failed. The failure cascaded to dependent products such as Access, Gateway and WARP.',
        'investigation_evidence': 'Separate incidents were merged at 18:06 once Workers KV unavailability was the shared cause.',
        'recovery_actions': 'Services recovered when the third-party storage provider recovered. Gateway degraded identity rules gracefully, Access and Device Posture shed load, and Turnstile kill switches were enabled.',
        'recovery_verification': 'Service level objectives returned to pre-incident levels at 20:28.',
        'acceptable_alternatives': 'Targeted graceful degradation and kill switches were used. An alternative datastore cutover was only a contingency and was not completed. Broad fail-open was not described by the source.'},
}


def all_ids(src):
    ids = set()
    for key in ('observed_symptoms', 'investigation_evidence', 'recovery_actions', 'recovery_verification'):
        ids |= {i['id'] for i in src[key]}
    return ids


class StructureTests(unittest.TestCase):
    def test_no_judge_anywhere(self):
        for seed in SEEDS:
            self.assertNotIn('judge', (HERE / f'{seed}.json').read_text().lower())

    def test_claims_are_audited_and_well_formed(self):
        for seed in SEEDS:
            src = load_source(seed)
            ids = all_ids(src)
            claims = src['scoring_rules']['claims']
            self.assertEqual(len({c['id'] for c in claims}), len(claims))
            for d in DIMENSIONS[:-1]:
                self.assertTrue([c for c in claims if c['dimension'] == d], f'{seed} lacks {d} claims')
            self.assertTrue(any(c['critical'] for c in claims))
            for c in claims:
                self.assertTrue(c['ref'] and set(c['ref']) <= ids, f'{seed}.{c["id"]} bad ref')

    def test_recovery_phase_separation(self):
        for seed in SEEDS:
            src = load_source(seed)
            phases = {a['id']: a['phase'] for a in src['recovery_actions']}
            self.assertTrue(set(phases.values()) <= PHASES)
            for c in src['scoring_rules']['claims']:
                if c['dimension'] == 'recovery_actions':
                    bad = [r for r in c['ref'] if phases.get(r) in ('post_incident_remediation', 'contingency_actions')]
                    self.assertFalse(bad, f'{seed}.{c["id"]} rewards non-recovery actions {bad}')
        self.assertEqual({a['id']: a['phase'] for a in load_source('RW04')['recovery_actions']}['R2'], 'post_incident_remediation')
        self.assertEqual({a['id']: a['phase'] for a in load_source('RW06')['recovery_actions']}['R5'], 'contingency_actions')

    def test_catalog_statuses_and_discrepancies(self):
        for seed in SEEDS:
            for e in load_source(seed)['scoring_rules']['alternatives_catalog']:
                self.assertIn(e['status'], STATUSES)
        self.assertTrue(load_source('RW06')['source_discrepancies'])
        self.assertTrue(load_source('RW05')['source_discrepancies'])


class PolarityTests(unittest.TestCase):
    def test_review_example_rw06_contradiction(self):
        r = score_report('RW06', {'observed_symptoms': 'DNS and WAF were down during the incident, although some other services were not affected.'})
        item = next(i for i in r['dimensions']['observed_symptoms']['items'] if i['id'] == 'C3')
        self.assertFalse(item['passed'])
        self.assertEqual(item['reason'], 'contradicted_by_asserted_opposite')

    def test_negated_phrasing_passes(self):
        r = score_report('RW06', {'observed_symptoms': 'DNS was not directly impacted.'})
        self.assertTrue(next(i for i in r['dimensions']['observed_symptoms']['items'] if i['id'] == 'C3')['passed'])

    def test_data_loss_polarity(self):
        no_loss = score_report('RW01', {'observed_symptoms': 'No data was lost.'})
        lost = score_report('RW01', {'observed_symptoms': 'User data was lost.'})
        self.assertEqual(no_loss['traps_triggered'], [])
        self.assertEqual([t['id'] for t in lost['traps_triggered']], ['T_dataloss'])

    def test_failback_safe_contradicts(self):
        r = score_report('RW01', {'confirmed_root_cause': 'Failback was safe.'})
        item = next(i for i in r['dimensions']['confirmed_root_cause']['items'] if i['id'] == 'C5')
        self.assertFalse(item['passed'])

    def test_attack_claims(self):
        self.assertEqual([t['id'] for t in score_report('RW02', {'confirmed_root_cause': 'An attack caused the outage.'})['traps_triggered']], ['T_attack'])
        self.assertEqual(score_report('RW02', {'confirmed_root_cause': 'This was not caused by an attack.'})['traps_triggered'], [])
        self.assertEqual(score_report('RW02', {'confirmed_root_cause': 'An attack was ruled out as the cause.'})['traps_triggered'], [])

    def test_unconfirmed_is_not_confirmed(self):
        self.assertEqual(score_report('RW05', {'confirmed_root_cause': 'The ground fault chain is unconfirmed.'})['traps_triggered'], [])
        r = score_report('RW05', {'confirmed_root_cause': 'The ground fault was confirmed as the cause.'})
        self.assertEqual([t['id'] for t in r['traps_triggered']], ['T_groundfault_confirmed'])

    def test_rw03_rollback_first_trap(self):
        bad = score_report('RW03', {'recovery_actions': 'The first mitigation was a rollback of the rule.'})
        ok = score_report('RW03', {'recovery_actions': 'Rollback was not the first mitigation; the global terminate was.'})
        self.assertEqual([t['id'] for t in bad['traps_triggered']], ['T_rollback_first'])
        self.assertEqual(ok['traps_triggered'], [])

    def test_decimal_does_not_split_clause(self):
        self.assertEqual(clauses('About 90.22% of Workers KV requests failed.'), ['about 90.22% of workers kv requests failed'])

    def test_asserts_window(self):
        self.assertTrue(asserts('no data was lost', ['data'], ['lost'], 'neg'))
        self.assertTrue(asserts('data was lost', ['data'], ['lost'], 'pos'))


class AlternativesTests(unittest.TestCase):
    def test_alternative_presented_as_performed_is_flagged(self):
        r = score_report('RW06', {'acceptable_alternatives': 'Cloudflare completed the migration to an alternative datastore.'})
        alt = r['dimensions']['acceptable_alternatives']
        self.assertFalse(alt['items'][0]['passed'])
        self.assertEqual(alt['items'][0]['reason'], 'non_performed_option_presented_as_performed')

    def test_contradicted_option_must_be_rejected(self):
        bad = score_report('RW05', {'acceptable_alternatives': 'Analytics on DR would restore everything.'})
        self.assertFalse(bad['dimensions']['acceptable_alternatives']['items'][0]['passed'])

    def test_omitting_alternatives_is_not_penalized(self):
        r = score_report('RW02', {k: v for k, v in GOOD['RW02'].items() if k != 'acceptable_alternatives'})
        self.assertEqual(r['alternatives_dimension'], 'not_applicable_renormalized')
        self.assertGreaterEqual(r['final_score'], 90)


class HistoricalBoundaryTests(unittest.TestCase):
    def test_historical_source_not_applied_to_counterfactual(self):
        from benchmarks.grader_source import seed_of, audit_record
        for task in ('RW01V6CF', 'RW05V6N', 'RW03V5', 'RW02V3', 'RW07V4'):
            with self.subTest(task=task), self.assertRaises(ValueError):
                seed_of(task)
            with self.subTest(audit=task), self.assertRaises(ValueError):
                audit_record({'task_id': task})

    def test_v4_and_standalone_source_seed_allowed(self):
        from benchmarks.grader_source import seed_of
        self.assertEqual(seed_of('RW05V4'), 'RW05')
        self.assertEqual(seed_of('RW05'), 'RW05')

    def test_source_score_discloses_lexical_limit(self):
        result = score_report('RW03V4', GOOD['RW03'])
        self.assertEqual(result['semantic_validation'], 'not_performed')


class ReportTests(unittest.TestCase):
    def test_good_reports_score_high(self):
        for seed in SEEDS:
            r = score_report(seed, GOOD[seed])
            failed = [(d, i['id']) for d, v in r['dimensions'].items() for i in v['items'] if not i['passed']]
            self.assertFalse(r['traps_triggered'], f'{seed} traps {r["traps_triggered"]}')
            self.assertFalse(failed, f'{seed} failed {failed}')
            self.assertGreaterEqual(r['final_score'], 95, seed)

    def test_empty_report_scores_zero(self):
        for seed in SEEDS:
            self.assertEqual(score_report(seed, {})['final_score'], 0)

    def test_partial_scores_between(self):
        for seed in SEEDS:
            partial = {'confirmed_root_cause': GOOD[seed]['confirmed_root_cause']}
            s = score_report(seed, partial)['final_score']
            self.assertTrue(0 < s < 60, f'{seed} partial {s}')

    def test_trap_penalty_applied_and_floored(self):
        r = score_report('RW02', {'confirmed_root_cause': 'An attack caused the outage.'})
        self.assertEqual(r['trap_penalty'], 3)
        self.assertEqual(r['final_score'], 0)

    def test_deterministic(self):
        a = score_report('RW06', GOOD['RW06'])
        b = score_report('RW06', GOOD['RW06'])
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertFalse(a['uses_judge'])

    def test_flat_text_mode(self):
        text = ' '.join(GOOD['RW03'].values())
        self.assertGreaterEqual(score_report('RW03', flat_text=text)['final_score'], 90)


if __name__ == '__main__':
    unittest.main()
