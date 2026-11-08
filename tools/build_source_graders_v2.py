"""Upgrade RW01-RW06 JSON graders to v2 in place. Idempotent.

Adds: recovery-action phases, polarity-aware claims, hallucination traps,
an alternatives catalog, and documented source discrepancies. Every claim
cites evidence ids that exist in the same JSON (checked by the tests).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "benchmarks" / "source_graders"
ATTACK = {"id": "T_attack", "text": "States that an attack or breach caused the outage.",
          "subject": ["attack", "ddos", "malicious", "breach"],
          "predicate": ["caused", "cause", "due to", "result of", "triggered by", "because of"]}


def C(cid, dim, text, subject, predicate, ref, critical=False, pol="pos", neg_phrases=None, contradict=None):
    out = {"id": cid, "dimension": dim, "critical": critical, "polarity": pol, "text": text,
           "subject": subject, "predicate": predicate, "ref": ref}
    if neg_phrases:
        out["neg_phrases"] = neg_phrases
    if contradict:
        out["contradict"] = contradict
    return out


def A(aid, terms, status, performed_ok, note):
    return {"id": aid, "terms": terms, "status": status, "performed_ok": performed_ok, "note": note}


PHASES = {
    "RW01": {"R1": "incident_mitigation", "R2": "incident_mitigation", "R3": "service_restoration", "R4": "service_restoration",
             "R5": "service_restoration", "R6": "service_restoration", "R7": "service_restoration", "R8": "incident_mitigation"},
    "RW02": {"R1": "service_restoration", "R2": "service_restoration"},
    "RW03": {"R1": "service_restoration", "R2": "service_restoration"},
    "RW04": {"R1": "service_restoration", "R2": "post_incident_remediation"},
    "RW05": {"R1": "service_restoration", "R2": "incident_mitigation", "R3": "incident_mitigation",
             "R4": "service_restoration", "R5": "service_restoration"},
    "RW06": {"R1": "contingency_actions", "R2": "incident_mitigation", "R3": "incident_mitigation",
             "R4": "incident_mitigation", "R5": "contingency_actions", "R6": "service_restoration"},
}

DISCREPANCIES = {
    "RW01": [{"id": "D1", "note": "Source says West primaries took writes for 'nearly 40 minutes' and also '30+ minutes'; accept either."}],
    "RW02": [],
    "RW03": [],
    "RW04": [],
    "RW05": [{"id": "D1", "note": "Header says the outage began at 11:43 UTC; the incident window says 11:44. Accept either."}],
    "RW06": [{"id": "D1", "note": "Source states 2 hours 28 minutes, but its own timeline 17:52 to 20:28 is 2 hours 36 minutes. Accept either figure."}],
}

CLAIMS = {
    "RW01": [
        C("C1", "observed_symptoms", "Connectivity between the East hub and primary data center was lost for 43 seconds.",
          ["connectivity", "network", "partition", "link"], ["43 s", "43-second", "43 second"], ["S1"]),
        C("C2", "observed_symptoms", "Webhook delivery and Pages builds were not served or built.",
          ["webhook", "pages"], ["paus", "unavailable", "not serv", "unable", "stopped", "disrupt", "not built"], ["S3"], critical=True),
        C("C3", "confirmed_root_cause", "Orchestrator failed clusters over to West Coast primaries.",
          ["orchestrator", "failover", "fail over", "failed over"], ["west"], ["S2"], critical=True),
        C("C4", "confirmed_root_cause", "Both sides held writes the other lacked (divergent writes).",
          ["write"], ["diverg", "unreplicated", "not replicated", "not been replicated", "not present"], ["S5"], critical=True),
        C("C5", "confirmed_root_cause", "Failing back to East was unsafe.",
          ["fail back", "failback", "fail-back", "failing back"], ["unsafe", "not safe", "could not", "unable", "risk"], ["S2"], critical=True,
          contradict=[{"subject": ["fail back", "failback", "fail-back", "failing back"], "predicate": ["safe", "straightforward", "easy"]}]),
        C("C6", "investigation_evidence", "Orchestrator API showed a topology with only West Coast servers.",
          ["orchestrator", "topolog"], ["only", "west-only", "west coast servers"], ["E2"]),
        C("C7", "recovery_actions", "Restored replicas from backup, synchronized sites, fell back to the original topology and resumed queued jobs.",
          ["restor", "backup", "replica", "reconcil", "synchron"], ["resum", "backlog", "fall back", "failed over", "fail over", "processed"], ["R3", "R7"], critical=True),
        C("C8", "recovery_verification", "Pending webhooks and Pages builds were processed and integrity was confirmed before green.",
          ["backlog", "webhook", "pages", "integrity"], ["processed", "confirmed", "green", "integrity"], ["V3"]),
    ],
    "RW02": [
        C("C1", "observed_symptoms", "19 data centers lost traffic.",
          ["data center", "datacenter", "location", "pop"], ["19"], ["S1"]),
        C("C2", "observed_symptoms", "About 4% of locations carried about half of all requests.",
          ["request", "traffic"], ["50%", "half"], ["S2"]),
        C("C3", "confirmed_root_cause", "A BGP advertisement policy change re-ordered terms.",
          ["term", "polic"], ["reorder", "re-order", "re-ordered", "reordered", "moved"], ["S1"], critical=True),
        C("C4", "confirmed_root_cause", "An explicit reject term ended up ahead of the site-local terms.",
          ["reject"], ["site-local", "site local", "before", "ahead"], ["S1"], critical=True),
        C("C5", "confirmed_root_cause", "Site-local prefixes were withdrawn.",
          ["prefix"], ["withdr", "no longer advertis", "stopped advertis"], ["S3"]),
        C("C6", "investigation_evidence", "The configuration diff showed the term re-ordering.",
          ["diff"], ["reorder", "re-order", "exclamation", "moved"], ["E1"]),
        C("C7", "recovery_actions", "Engineers reverted the change at affected locations.",
          ["change", "polic", "config"], ["revert", "rolled back", "roll back", "rollback"], ["R1"], critical=True),
        C("C8", "recovery_verification", "All data centers were online after the final revert at 07:42.",
          ["data center", "location"], ["07:42", "7:42"], ["V2"]),
    ],
    "RW03": [
        C("C1", "observed_symptoms", "Customers saw 502 errors.",
          ["error", "page", "customer"], ["502"], ["S2"]),
        C("C2", "observed_symptoms", "CPU reached nearly 100% on cores handling HTTP and HTTPS.",
          ["cpu"], ["100%", "exhaust", "saturat", "spik"], ["S2"]),
        C("C3", "confirmed_root_cause", "A WAF rule's regular expression backtracked catastrophically.",
          ["regex", "regular expression"], ["backtrack"], ["E5"], critical=True),
        C("C4", "confirmed_root_cause", "The rule went global in seconds without a staged rollout.",
          ["rule", "deploy", "change"], ["global", "worldwide", "staged", "quicksilver", "seconds"], ["S1"]),
        C("C5", "confirmed_root_cause", "A CPU-use protection had been removed in an earlier refactor.",
          ["protection", "safeguard"], ["removed", "refactor"], ["E5"]),
        C("C6", "investigation_evidence", "Live CPU data and strace pointed to the WAF.",
          ["waf"], ["strace", "cpu data", "cpu profile", "live cpu"], ["E2", "E3"], critical=True),
        C("C7", "recovery_actions", "A global WAF terminate at 14:07 stopped the CPU exhaustion.",
          ["waf"], ["terminat", "disabled globally", "global terminate", "14:07"], ["R1"], critical=True),
        C("C8", "recovery_verification", "CPU and traffic were normal by 14:09.",
          ["cpu", "traffic"], ["14:09", "returned", "normal", "expected"], ["V1"]),
        C("C9", "recovery_verification", "Single-city negative and positive tests preceded the 14:52 global re-enable.",
          ["test"], ["single city", "one city", "negative", "positive", "14:52"], ["V2"]),
    ],
    "RW04": [
        C("C1", "observed_symptoms", "Traffic dropped about 50% across the network.",
          ["traffic"], ["50%", "half"], ["S2"]),
        C("C2", "observed_symptoms", "The outage ran from 21:12 to 21:39.",
          ["outage", "atlanta", "traffic"], ["21:12", "21:39"], ["S1"]),
        C("C3", "confirmed_root_cause", "A one-line change deactivated the prefix-list inside the term.",
          ["prefix-list", "prefix list"], ["deactivat", "inactive", "removed", "disabled"], ["E1"], critical=True),
        C("C4", "confirmed_root_cause", "Local-preference 200 beat the local servers' 100, pulling traffic to Atlanta.",
          ["local-pref", "local pref"], ["200", "higher", "100"], ["E2"], critical=True),
        C("C5", "confirmed_root_cause", "All BGP routes were sent into the backbone.",
          ["route"], ["all", "leak"], ["E2"]),
        C("C6", "investigation_evidence", "The config diff and traffic manager CPU view showed the cause and impact.",
          ["traffic manager", "diff", "compare"], ["cpu", "inactive", "prefix"], ["E1", "E3"]),
        C("C7", "recovery_actions", "The Atlanta router was disabled and dropped from the backbone.",
          ["atlanta", "router"], ["disabled", "dropped", "removed from the backbone", "isolated"], ["R1"], critical=True),
        C("C8", "recovery_verification", "Traffic normalized at 21:39 and logs and metrics fully recovered at 22:10.",
          ["traffic", "logs", "recover"], ["21:39", "21:47", "22:10"], ["V1", "V3"]),
    ],
    "RW05": [
        C("C1", "observed_symptoms", "Control plane and analytics were down from about 11:44 on Nov 2 to 04:25 on Nov 4.",
          ["control plane", "analytics"], ["04:25", "11:44", "11:43", "november 4", "nov 4"], ["S1"]),
        C("C2", "observed_symptoms", "Customer traffic through the network was not impacted.",
          ["traffic", "network", "edge"], ["impact", "affected"], ["S3"], pol="neg",
          neg_phrases=["unaffected", "kept working", "continued to work", "continued to operate", "continued to perform"]),
        C("C3", "observed_symptoms", "Raw logs were unavailable and some log data was lost.",
          ["log"], ["unavailable", "not processed", "gap", "lost", "dropped"], ["S2", "S5"]),
        C("C4", "confirmed_root_cause", "Power was lost at the Flexential PDX-04 facility.",
          ["pdx", "flexential", "data center", "facility"], ["power"], ["S1"], critical=True),
        C("C5", "confirmed_root_cause", "Kafka and ClickHouse existed only in PDX-04 yet HA services depended on them.",
          ["kafka", "clickhouse"], ["pdx", "only", "depend"], ["E4"], critical=True),
        C("C6", "confirmed_root_cause", "The ground-fault and generator chain of events is unconfirmed speculation.",
          ["ground fault", "transformer", "generator", "dsg"],
          ["speculat", "unconfirmed", "not confirmed", "unclear", "informed", "not been able to confirm", "believe"], ["S1"], critical=True),
        C("C7", "investigation_evidence", "Two routers went offline at 11:44 and could not be reached directly or out of band.",
          ["router"], ["offline", "unreachable", "11:44", "out-of-band", "out of band"], ["E1"]),
        C("C8", "recovery_actions", "The control plane was failed over to disaster recovery sites in Europe.",
          ["disaster recovery", "dr site", "dr facility", "failover", "fail over", "failed over"],
          ["13:40", "13:43", "europe", "turned up", "fail"], ["R1"], critical=True),
        C("C9", "recovery_actions", "Power and breakers were restored by the provider and the facility was bootstrapped.",
          ["power", "breaker", "facility", "pdx"], ["restored", "replaced", "bootstrap", "rebuilt", "22:48"], ["R4", "R5"]),
        C("C10", "recovery_verification", "Services were fully restored at 04:25 on Nov 4.",
          ["service", "restor"], ["04:25", "november 4", "nov 4"], ["V3"]),
    ],
    "RW06": [
        C("C1", "observed_symptoms", "About 90% of Workers KV requests failed.",
          ["workers kv", "kv"], ["90"], ["S2"]),
        C("C2", "observed_symptoms", "The outage lasted 2h28m (the timeline implies 2h36m).",
          ["outage", "incident", "lasted", "duration"],
          ["2 hours 28", "2h28", "2 h 28", "2 hours and 28", "148 min", "2 hours 36", "2h36", "2 h 36", "156 min"], ["S1"]),
        C("C3", "observed_symptoms", "DNS, WAF, proxy and cache were not directly impacted.",
          ["dns", "waf", "proxy", "cache"], ["impact", "affect"], ["S4"], critical=True, pol="neg",
          neg_phrases=["unaffected", "remained available", "continued to operate", "kept working"],
          contradict=[{"subject": ["dns", "waf", "proxy", "cache"], "predicate": ["down", "failed", "failing", "unavailable", "offline", "outage"]}]),
        C("C4", "confirmed_root_cause", "A storage backend behind Workers KV, partly a third-party provider, failed.",
          ["storage", "backing", "data store", "datastore", "provider"], ["third-party", "third party", "outage", "failure", "failed"], ["S1"], critical=True),
        C("C5", "confirmed_root_cause", "The failure cascaded to dependent products such as Access, Gateway and WARP.",
          ["access", "gateway", "warp", "turnstile", "workers ai", "images", "stream"], ["depend", "fail", "impact", "affect"], ["S3"]),
        C("C6", "investigation_evidence", "Separate incidents were merged at 18:06 once Workers KV unavailability was the shared cause.",
          ["incident", "alert"], ["18:06", "merged", "shared cause", "combined"], ["E3"]),
        C("C7", "recovery_actions", "Services recovered when the third-party storage provider recovered.",
          ["storage", "provider", "third-party", "third party"], ["recover", "restored", "came back"], ["R6"], critical=True),
        C("C8", "recovery_actions", "Load shedding, graceful degradation and kill switches reduced impact during the outage.",
          ["gateway", "access", "turnstile", "kill switch"], ["degrad", "shed", "kill switch", "force drop"], ["R2", "R3", "R4"]),
        C("C9", "recovery_verification", "Service level objectives returned to pre-incident levels at 20:28.",
          ["slo", "service level", "impact"], ["20:28", "pre-incident", "normal"], ["V2"]),
    ],
}

TRAPS = {
    "RW01": [ATTACK, {"id": "T_dataloss", "text": "Claims user data was lost.", "subject": ["data"], "predicate": ["lost", "loss"]}],
    "RW02": [ATTACK],
    "RW03": [ATTACK, {"id": "T_rollback_first", "text": "Claims rollback was the first mitigation (global WAF terminate came first).",
                      "subject": ["rollback", "roll back", "rolled back", "revert"],
                      "predicate": ["first mitigation", "first action", "first step", "initial mitigation"]}],
    "RW04": [ATTACK, {"id": "T_remediation_as_recovery", "text": "Claims post-incident safeguards restored service.",
                      "subject": ["local-pref", "maximum-prefix", "max-prefix"], "predicate": ["restored", "fixed the outage", "ended the outage"]}],
    "RW05": [ATTACK, {"id": "T_groundfault_confirmed", "text": "Presents the ground-fault chain as confirmed.",
                      "subject": ["ground fault", "transformer"], "predicate": ["confirmed", "established", "definitely"]}],
    "RW06": [ATTACK, {"id": "T_altstore_completed", "text": "Claims the alternative datastore cutover was completed.",
                      "subject": ["alternative", "alternate"], "predicate": ["completed", "deployed", "finished", "successful"]}],
}

CATALOG = {
    "RW01": [A("ALT1", ["fail forward", "failing forward", "fail-forward"], "source_actual", True, "Failing forward on West primaries"),
             A("ALT2", ["restore directly", "from the west"], "source_actual", True, "Direct restore from West"),
             A("ALT3", ["fail back", "failback", "failing back"], "source_contradicted", False, "Immediate failback was unsafe"),
             A("ALT4", ["without reconcil", "resume workers without"], "source_contradicted", False, "Resuming jobs without reconciliation")],
    "RW02": [A("ALT1", ["revert", "roll back", "rolled back", "rollback"], "source_actual", True, "Revert the change"),
             A("ALT2", ["standby capacity", "extra capacity", "increase capacity", "add capacity"], "unverified", False, "Capacity increase not in source"),
             A("ALT3", ["commit-confirm", "commit confirm", "stagger", "staged rollout", "redesign"], "long_term_remediation", False, "Follow-up work")],
    "RW03": [A("ALT1", ["global terminate", "terminate the waf", "terminated the waf", "waf termination", "disable the waf", "disabled the waf"], "source_actual", True, "Global WAF terminate"),
             A("ALT2", ["rollback", "roll back", "rolled back", "revert"], "source_actual", True, "Rule rollback during restoration"),
             A("ALT3", ["re2", "rust regex", "safer regex engine", "replace the regex engine", "switch regex engine"], "long_term_remediation", False, "Engine switch was follow-up"),
             A("ALT4", ["cdn cach", "disable cach"], "unverified", False, "Not in source")],
    "RW04": [A("ALT1", ["disable the atlanta", "disabled the atlanta", "isolate", "dropped atlanta", "drop atlanta"], "source_actual", True, "Disable Atlanta router"),
             A("ALT2", ["deactivate the term", "deactivating the term", "revert the config", "undo the"], "unverified", False, "Correcting policy not shown as applied"),
             A("ALT3", ["local-pref", "maximum-prefix", "max-prefix"], "long_term_remediation", False, "Post-incident safeguards")],
    "RW05": [A("ALT1", ["failover to", "fail over", "failed over", "disaster recovery"], "source_intermediate", True, "DR failover of control plane"),
             A("ALT2", ["breaker", "clean power", "bootstrap", "restore power", "power restor"], "source_actual", True, "Restore PDX-04 power"),
             A("ALT3", ["analytics on dr", "analytics replica", "dr for analytics", "log processing on dr", "kafka on dr"], "source_contradicted", False, "Analytics on DR not possible"),
             A("ALT4", ["high availability cluster", "chaos", "code orange"], "long_term_remediation", False, "Follow-up work")],
    "RW06": [A("ALT1", ["provider recover", "provider restored", "storage recovered", "third-party recovered", "third party recovered"], "source_actual", True, "Provider recovery"),
             A("ALT2", ["alternative datastore", "alternate datastore", "alternative backing", "alternate backing", "alternate store", "alternative store"], "source_supported", False, "Contingency; not shown completed"),
             A("ALT3", ["graceful", "load shed", "shed load", "kill switch", "force drop"], "source_actual", True, "Targeted degradation"),
             A("ALT4", ["fail-open", "fail open"], "unverified", False, "Broad fail-open not in source")],
}


def main():
    for seed in CLAIMS:
        path = HERE / f"{seed}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["grader_id"] = f"{seed}-source-grader-v2"
        for action in data["recovery_actions"]:
            action["phase"] = PHASES[seed][action["id"]]
        data["source_discrepancies"] = DISCREPANCIES[seed]
        data["scoring_rules"] = {
            "claims": CLAIMS[seed],
            "traps": TRAPS[seed],
            "alternatives_catalog": CATALOG[seed],
            "required_concepts": data["scoring_rules"]["required_concepts"],
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("upgraded", seed, len(CLAIMS[seed]), "claims")


if __name__ == "__main__":
    main()
