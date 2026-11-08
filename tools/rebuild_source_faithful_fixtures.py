#!/usr/bin/env python3
"""Build the six source-faithful V6CF fixtures and their oracle references.

The checked-in JSON files remain the evaluation inputs.  This builder makes the
large, reviewer-auditable structures maintainable and prevents hand-edited
service-code/reference drift.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FIXTURES = ROOT / "benchmarks" / "v6_fixtures" / "counterfactual"
REFERENCES = ROOT / "reference" / "v6-counterfactual"


def path(*parts):
    return {"path": list(parts)}


def lit(value):
    return {"literal": value}


def pred(parts, op, value):
    return {"left": path(*parts), "op": op, "right": lit(value)}


def both(*items):
    return {"all": list(items)}


def node(name, needs_all=(), needs_any=()):
    return {"id": name, "needs_all": list(needs_all), "needs_any": list(needs_any)}


def action(action_id, cost, minutes, risk, description, changes, **extra):
    return {
        "id": action_id,
        "cost": cost,
        "estimated_minutes": minutes,
        "risk": risk,
        "operational_description": description,
        "changes": [{"path": list(parts), "value": value} for parts, value in changes],
        **extra,
    }


def observation(signals=None, configuration=None, logs=None, *, age=0, reported=None):
    result = {
        "measurement_age_seconds": age,
        "signals": signals or {},
        "configuration_snapshot": configuration or {},
        "logs": logs or [],
    }
    if reported is not None:
        result["reported_health"] = reported
    return result


def topology_with_default_observations(topology, overrides):
    return {entry["id"]: overrides.get(entry["id"], observation()) for entry in topology}


def make_task(seed, alert, hypotheses, topology, *, max_tools=47):
    return {
        "id": f"V6CF-{seed}",
        "seed": seed,
        "version": "agentic-v6-source-faithful-3",
        "alert": alert,
        "time": "incident+00:18",
        "hypotheses": [{"id": label, "description": text} for label, text in hypotheses],
        "instructions": "Establish initial impact from partial timestamped evidence, infer the causal mechanism, and choose the lowest-cost complete safe response.",
        "max_tools": max_tools,
        "max_simulations": 5,
        "max_turns": max_tools + 1,
        "evidence_expectations": ["current operational signals", "dependency propagation", "counterfactual recovery and safety"],
        "modeling_notice": "Source-faithful deterministic reconstruction; observations and costs are synthetic, not production telemetry",
        "public_inventory": [
            {"service_code": f"svc-{index:03d}", "role": entry["id"]}
            for index, entry in enumerate(topology, 1)
        ],
    }


def rw01():
    topology = [
        node("orchestrator-control"), node("mysql-east-primary"), node("mysql-west-primary"),
        node("replication-reconciler"),
        node("east-read-replica-a", ["replication-reconciler"]),
        node("east-read-replica-b", ["replication-reconciler"]),
        node("metadata-write-router", ["replication-reconciler"]),
        node("issues-metadata", ["metadata-write-router"]),
        node("pull-request-metadata", ["metadata-write-router"]),
        node("git-write-api", ["metadata-write-router"]),
        node("git-read-api", needs_any=["east-read-replica-a", "east-read-replica-b"]),
        node("webhook-event-queue"), node("webhook-dispatcher", ["webhook-event-queue", "metadata-write-router"]),
        node("pages-build-queue"), node("pages-builder", ["pages-build-queue", "metadata-write-router"]),
        node("pages-publisher", ["pages-builder"]), node("repository-browse", ["git-read-api"]),
        node("api-frontend", needs_any=["git-read-api", "git-write-api"]),
        node("web-frontend", needs_any=["repository-browse", "issues-metadata"]),
        node("backup-restore"), node("deployment-control"), node("data-integrity-monitor"),
    ]
    rules = [
        {"service": "replication-reconciler", "when": pred(("state", "mysql", "topology_consistent"), "eq", False)},
        {"service": "webhook-event-queue", "when": pred(("state", "jobs", "webhooks_paused"), "eq", True)},
        {"service": "pages-build-queue", "when": pred(("state", "jobs", "pages_paused"), "eq", True)},
        {"service": "data-integrity-monitor", "when": pred(("state", "mysql", "unsafe_failback"), "eq", True)},
    ]
    state = {"mysql": {"topology_consistent": False, "divergent_writes": True, "unsafe_failback": False,
                       "east_replica_lag_seconds": 17340, "cross_region_write_rtt_ms": 82},
             "jobs": {"webhooks_paused": True, "pages_paused": True, "webhook_backlog": 5_000_000,
                      "pages_backlog": 80_000}}
    actions = [
        action("A11", 2, 15, "critical", "Fail writes back to the East primary before divergent histories are reconciled.", [
            (("state", "mysql", "unsafe_failback"), True)]),
        action("A12", 3, 90, "medium", "Restore replicas from backup while keeping write routing and deferred jobs unchanged.", [
            (("state", "mysql", "east_replica_lag_seconds"), 0)]),
        action("A13", 5, 30, "high", "Resume webhook and Pages processing before repairing the database topology.", [
            (("state", "jobs", "webhooks_paused"), False), (("state", "jobs", "pages_paused"), False)]),
        action("A14", 8, 360, "low", "Fail forward, reconcile divergent writes, rebuild replication, then drain both deferred-job queues.", [
            (("state", "mysql", "topology_consistent"), True), (("state", "mysql", "divergent_writes"), False),
            (("state", "mysql", "east_replica_lag_seconds"), 0), (("state", "mysql", "cross_region_write_rtt_ms"), 8),
            (("state", "jobs", "webhooks_paused"), False), (("state", "jobs", "pages_paused"), False)]),
        action("A15", 11, 420, "low", "Perform the same coordinated recovery with an additional full backup validation cycle.", [
            (("state", "mysql", "topology_consistent"), True), (("state", "mysql", "divergent_writes"), False),
            (("state", "mysql", "east_replica_lag_seconds"), 0), (("state", "mysql", "cross_region_write_rtt_ms"), 8),
            (("state", "jobs", "webhooks_paused"), False), (("state", "jobs", "pages_paused"), False)]),
        action("A90", 1, 10, "critical", "Force an immediate primary failback and resume deferred jobs without reconciliation.", [
            (("state", "mysql", "unsafe_failback"), True), (("state", "jobs", "webhooks_paused"), False),
            (("state", "jobs", "pages_paused"), False)]),
    ]
    obs = {
        "replication-reconciler": observation(
            {"replication_lag_seconds": 17340, "topology_members_visible": 2, "expected_members": 6, "write_rtt_ms": 82},
            {"orchestrator_primary_region": "west", "east_and_west_histories_diverged": True},
            ["replication graph excludes East replicas", "automatic failback blocked pending reconciliation"]),
        "east-read-replica-a": observation({"replication_lag_seconds": 17340, "read_freshness_seconds": 17120}, age=12),
        "east-read-replica-b": observation({"replication_lag_seconds": 16980, "read_freshness_seconds": 16860}, age=18),
        "metadata-write-router": observation({"write_latency_p95_ms": 91, "write_error_rate_pct": 37.0}, age=6),
        "webhook-event-queue": observation({"queued_events": 5_000_000, "dispatch_rate_per_second": 0},
            {"admission_mode": "paused_by_incident_commander"}, ["metadata-writing jobs intentionally paused"]),
        "pages-build-queue": observation({"queued_builds": 80_000, "dispatch_rate_per_second": 0},
            {"admission_mode": "paused_by_incident_commander"}, ["Pages builds held to protect data integrity"]),
        "api-frontend": observation({"error_rate_pct": 21.0, "latency_p95_ms": 1480}, age=95, reported="unknown"),
        "data-integrity-monitor": observation({"unreconciled_write_sets": 2, "data_loss_detected": 0}),
    }
    hypotheses = [
        ("H01", "A regional network interruption left application capacity isolated from its normal storage path"),
        ("H02", "Deferred background work exhausted admission capacity and propagated saturation into request serving"),
        ("H03", "Storage histories and recovery sequencing diverged while protective workload pauses widened impact"),
        ("H04", "A routing policy moved interactive requests onto a path with materially higher latency"),
        ("H05", "Authentication state became inconsistent after caches retained different freshness windows"),
        ("H06", "Service discovery continued publishing endpoints from a region no longer ready to serve"),
    ]
    case = {"id": "RW01", "title": "GitHub · October 2018 MySQL failover",
            "provenance": {"origin": "operator-published public postmortem", "source_url": "https://github.blog/news-insights/company-news/oct21-post-incident-analysis/",
                           "date": "2018-10-21 22:52 UTC", "documented_facts": ["Network partition and Orchestrator failover produced divergent writes.", "GitHub failed forward, rebuilt replicas, paused webhooks and Pages, then drained backlogs."],
                           "reconstructed_elements": ["Service dependency graph", "deterministic telemetry snapshots", "counterfactual response costs"],
                           "measurement_note": "All numeric observations and intervention costs are synthetic reconstructions."},
            "facts": {"state": state, "topology": topology, "local_rules": rules}, "actions": actions,
            "observability": {"snapshot_time": "2018-10-22T00:05:00Z", "external_probes": ["api-frontend", "web-frontend", "pages-publisher", "webhook-dispatcher", "repository-browse"],
                              "services": topology_with_default_observations(topology, obs)}}
    return {"task": make_task("RW01", "Metadata writes, repository views, Pages, and webhook delivery show different failure patterns after a regional connectivity event.", hypotheses, topology), "case": case}


def rw02():
    affected = ["mcp-atlanta", "mcp-chicago", "mcp-frankfurt", "mcp-london", "mcp-los-angeles", "mcp-miami", "mcp-paris", "mcp-san-jose", "mcp-tokyo", "mcp-washington"]
    topology = [node(name) for name in affected] + [
        node("public-transit-newark"), node("public-transit-singapore"), node("route-controller"),
        node("north-america-http", needs_any=["mcp-atlanta", "mcp-chicago", "mcp-los-angeles", "public-transit-newark"]),
        node("europe-http", needs_any=["mcp-frankfurt", "mcp-london", "mcp-paris"]),
        node("asia-http", needs_any=["mcp-tokyo", "public-transit-singapore"]),
        node("authoritative-dns", needs_any=["mcp-washington", "public-transit-newark"]),
        node("customer-api", needs_any=["north-america-http", "europe-http", "asia-http"]),
        node("dashboard" , needs_any=["north-america-http", "europe-http"]),
        node("health-check-aggregator"), node("configuration-distributor"), node("public-status"),
        node("transit-capacity-guard"), node("traffic-analytics"),
    ]
    route_failure = both(pred(("state", "routing", "deployed_generation"), "ne", 42), pred(("state", "routing", "emergency_public_transit"), "eq", False))
    rules = [{"service": name, "when": route_failure} for name in affected]
    rules.append({"service": "transit-capacity-guard", "when": pred(("state", "routing", "overload_public_transit"), "eq", True)})
    state = {"routing": {"stable_generation": 42, "deployed_generation": 43, "emergency_public_transit": False,
                         "overload_public_transit": False, "affected_locations": 19, "overflow_capacity_added": False}}
    actions = [
        action("A21", 2, 20, "medium", "Add overflow compute without changing the route policy deployed in affected locations.", [
            (("state", "routing", "overflow_capacity_added"), True)]),
        action("A22", 3, 25, "medium", "Manually revert the policy in a subset of the affected location groups.", [
            (("state", "routing", "affected_locations"), 9)]),
        action("A23", 4, 45, "low", "Roll back the incorrect network configuration and redeploy the last stable generation to all affected locations.", [
            (("state", "routing", "deployed_generation"), 42)]),
        action("A24", 7, 70, "low", "Rebuild and redeploy a new corrected route policy rather than rolling back.", [
            (("state", "routing", "deployed_generation"), 42)]),
        action("A25", 5, 15, "high", "Shift affected traffic onto the remaining public-transit locations during peak load.", [
            (("state", "routing", "emergency_public_transit"), True), (("state", "routing", "overload_public_transit"), True)]),
        action("A90", 1, 10, "critical", "Force all affected traffic through the two surviving public-transit locations without capacity controls.", [
            (("state", "routing", "emergency_public_transit"), True), (("state", "routing", "overload_public_transit"), True)]),
    ]
    obs = {name: observation({"bgp_sessions_up": 14, "expected_bgp_sessions": 21, "http_success_rate_pct": 2.0},
                             {"policy_generation": 43, "last_known_stable_generation": 42},
                             ["routes withdrawn after policy deployment", "local edge processes healthy but unreachable"], age=(idx % 4) * 7)
           for idx, name in enumerate(affected)}
    obs.update({
        "route-controller": observation({"completed_locations": 19, "failed_locations": 19}, {"rollout_generation": 43, "previous_generation": 42}, ["rollout completed before global health checks failed"]),
        "public-transit-newark": observation({"http_success_rate_pct": 99.8, "capacity_utilization_pct": 68.0}),
        "public-transit-singapore": observation({"http_success_rate_pct": 99.7, "capacity_utilization_pct": 61.0}),
        "traffic-analytics": observation({"global_http_request_drop_pct": 50.0, "locations_reporting": 19}, age=80, reported="unknown"),
    })
    hypotheses = [
        ("H01", "A sudden traffic increase exhausted request admission across otherwise healthy serving locations"),
        ("H02", "A network configuration rollout changed reachability across a concentrated set of locations"),
        ("H03", "Insufficient standby capacity prevented traffic from moving away from unavailable locations"),
        ("H04", "Resolver updates directed clients toward endpoints that had already been drained"),
        ("H05", "Packet classification rejected valid traffic after policy versions diverged between locations"),
        ("H06", "Session affinity retained assignments to pools removed during an endpoint rollout"),
    ]
    case = {"id": "RW02", "title": "Cloudflare · June 2022 routing outage",
            "provenance": {"origin": "operator-published public postmortem", "source_url": "https://blog.cloudflare.com/cloudflare-outage-on-june-21-2022/", "date": "2022-06-21 06:27 UTC",
                           "documented_facts": ["A network configuration change took traffic offline in 19 high-volume data centers.", "Rollback restored the locations incrementally."],
                           "reconstructed_elements": ["Grouped location topology", "per-location observations", "counterfactual response costs"], "measurement_note": "Location metrics are deterministic synthetic approximations."},
            "facts": {"state": state, "topology": topology, "local_rules": rules}, "actions": actions,
            "observability": {"snapshot_time": "2022-06-21T06:45:00Z", "external_probes": ["north-america-http", "europe-http", "asia-http", "authoritative-dns", "dashboard", "public-status"], "services": topology_with_default_observations(topology, obs)}}
    return {"task": make_task("RW02", "Several high-volume network locations stopped serving while locations on independent paths remain reachable.", hypotheses, topology), "case": case}


def rw03():
    topology = [
        node("waf-rule-distributor"), node("waf-evaluator"), node("http-serving-pool", ["waf-evaluator"]),
        node("https-serving-pool", ["waf-evaluator"]), node("edge-proxy", needs_any=["http-serving-pool", "https-serving-pool"]),
        node("cdn-cache", ["edge-proxy"]), node("customer-http", ["http-serving-pool"]), node("customer-https", ["https-serving-pool"]),
        node("cloudflare-api", ["edge-proxy"]), node("dashboard", ["edge-proxy"]), node("access-auth", ["edge-proxy"]),
        node("internal-build-system", ["access-auth"]), node("jira", ["access-auth"]), node("managed-waf-protection", ["waf-evaluator"]),
        node("rate-limiting"), node("bot-management"), node("authoritative-dns"), node("public-status"),
        node("spectrum"), node("global-traffic-monitor"), node("deployment-pipeline"), node("emergency-bypass-control"),
    ]
    rules = [
        {"service": "waf-evaluator", "when": both(pred(("state", "waf", "cpu_pct"), "gt", 95), pred(("state", "waf", "rule_enabled"), "eq", True))},
        {"service": "managed-waf-protection", "when": pred(("state", "waf", "waf_globally_disabled"), "eq", True)},
        {"service": "emergency-bypass-control", "when": pred(("state", "waf", "bypass_restoration_checks"), "eq", True)},
    ]
    state = {"waf": {"rule_enabled": True, "regex_engine": "backtracking", "cpu_pct": 100, "waf_globally_disabled": False,
                     "staged_rollout": False, "rule_complexity_guard": False, "front_line_capacity_scaled": False,
                     "bypass_restoration_checks": False}}
    actions = [
        action("A31", 1, 5, "high", "Use the global WAF termination control to restore serving while all managed WAF protection remains disabled.", [
            (("state", "waf", "waf_globally_disabled"), True), (("state", "waf", "cpu_pct"), 18)]),
        action("A32", 4, 12, "medium", "Remove the newly deployed managed rule and rebuild the prior ruleset.", [
            (("state", "waf", "rule_enabled"), False), (("state", "waf", "cpu_pct"), 22)]),
        action("A33", 5, 25, "low", "Rollback the rule, verify it against isolated traffic, then restore serving globally.", [
            (("state", "waf", "rule_enabled"), False), (("state", "waf", "cpu_pct"), 20)]),
        action("A34", 7, 90, "medium", "Move evaluation to a bounded-complexity regex engine without first removing the deployed rule.", [
            (("state", "waf", "regex_engine"), "bounded"), (("state", "waf", "cpu_pct"), 30)]),
        action("A35", 2, 10, "high", "Scale front-line web capacity while leaving the pathological expression active.", [
            (("state", "waf", "front_line_capacity_scaled"), True)]),
        action("A90", 0, 3, "critical", "Disable the entire WAF globally and bypass the normal security restoration checks.", [
            (("state", "waf", "waf_globally_disabled"), True), (("state", "waf", "cpu_pct"), 15),
            (("state", "waf", "bypass_restoration_checks"), True)]),
    ]
    obs = {
        "waf-rule-distributor": observation({"rollout_scope_pct": 100, "rules_changed": 1}, {"deployment_mode": "simulate", "staged_rollout": False}, ["managed-rule bundle deployed globally"]),
        "waf-evaluator": observation({"cpu_utilization_pct": 100.0, "evaluation_timeout_rate_pct": 96.0, "worker_run_queue": 128},
            {"regex_engine": "backtracking", "complexity_guard_enabled": False, "new_rule_enabled": True},
            ["evaluation exceeded serving deadline", "repeated matcher backtracking observed"]),
        "http-serving-pool": observation({"http_502_rate_pct": 94.0, "cpu_utilization_pct": 99.8}),
        "https-serving-pool": observation({"http_502_rate_pct": 95.0, "cpu_utilization_pct": 99.9}),
        "global-traffic-monitor": observation({"global_traffic_drop_pct": 82.0}, age=130, reported="unknown"),
        "authoritative-dns": observation({"query_success_rate_pct": 99.99}),
        "emergency-bypass-control": observation({}, {"operator_access_tested_recently": False}, ["control requires infrequently used bypass procedure"]),
    }
    hypotheses = [
        ("H01", "Unexpected request volume exhausted serving concurrency across the edge network"),
        ("H02", "A globally distributed request-processing change consumed shared serving resources"),
        ("H03", "Authoritative name resolution returned destinations that were no longer reachable"),
        ("H04", "Cache invalidation state diverged and forced an unsustainable increase in origin traffic"),
        ("H05", "A storage promotion removed read availability from services on the previous primary"),
        ("H06", "Certificate configuration divergence prevented encrypted request negotiation"),
    ]
    case = {"id": "RW03", "title": "Cloudflare · July 2019 WAF regex outage",
            "provenance": {"origin": "operator-published public postmortem", "source_url": "https://blog.cloudflare.com/details-of-the-cloudflare-outage-on-july-2-2019/", "date": "2019-07-02 13:42 UTC",
                           "documented_facts": ["A globally deployed WAF expression exhausted CPU through regex backtracking.", "The WAF was terminated, the rule rolled back, and service verified before re-enable."],
                           "reconstructed_elements": ["Serving dependency graph", "CPU and error snapshots", "counterfactual response costs"], "measurement_note": "Metrics are synthetic but preserve the reported causal and temporal shape."},
            "facts": {"state": state, "topology": topology, "local_rules": rules}, "actions": actions,
            "observability": {"snapshot_time": "2019-07-02T14:00:00Z", "external_probes": ["customer-http", "customer-https", "cloudflare-api", "dashboard", "authoritative-dns", "public-status", "spectrum"], "services": topology_with_default_observations(topology, obs)}}
    return {"task": make_task("RW03", "HTTP and HTTPS serving failed globally shortly after a request-processing update; several non-proxy services remain healthy.", hypotheses, topology), "case": case}


def rw04():
    topology = [
        node("atlanta-backbone-router"), node("atlanta-washington-segment", ["atlanta-backbone-router"]),
        node("atlanta-chicago-segment", ["atlanta-backbone-router"]), node("europe-backbone", ["atlanta-washington-segment"]),
        node("us-west-backbone", ["atlanta-chicago-segment"]), node("east-coast-backbone", ["atlanta-washington-segment"]),
        node("london-pop", ["europe-backbone"]), node("frankfurt-pop", ["europe-backbone"]), node("paris-pop", ["europe-backbone"]),
        node("san-jose-pop", ["us-west-backbone"]), node("seattle-pop", ["us-west-backbone"]), node("los-angeles-pop", ["us-west-backbone"]),
        node("washington-pop", ["east-coast-backbone"]), node("richmond-pop", ["east-coast-backbone"]),
        node("independent-edge-madrid"), node("independent-edge-singapore"), node("authoritative-dns"),
        node("anycast-http", needs_any=["london-pop", "san-jose-pop", "independent-edge-madrid"]),
        node("customer-api", needs_any=["washington-pop", "independent-edge-singapore"]), node("traffic-engineering-controller"),
        node("log-ingestion"), node("network-metrics"), node("public-status"), node("transit-capacity-guard"),
    ]
    rules = [
        {"service": "atlanta-backbone-router", "when": both(pred(("state", "routes", "atlanta_load_gbps"), "gt", 900), pred(("state", "routes", "atlanta_isolated"), "eq", False))},
        {"service": "transit-capacity-guard", "when": pred(("state", "routes", "unsafe_public_shift"), "eq", True)},
    ]
    state = {"routes": {"atlanta_load_gbps": 2450, "atlanta_capacity_gbps": 900, "atlanta_isolated": False,
                        "attract_all_policy": True, "unsafe_public_shift": False, "queue_limits_raised": False}}
    actions = [
        action("A41", 3, 8, "medium", "Remove the Atlanta router from the backbone so traffic follows remaining paths.", [
            (("state", "routes", "atlanta_isolated"), True)]),
        action("A42", 4, 15, "low", "Revert the route-attraction configuration and restore the previous backbone policy.", [
            (("state", "routes", "attract_all_policy"), False), (("state", "routes", "atlanta_load_gbps"), 620)]),
        action("A43", 6, 30, "low", "Isolate Atlanta and also deploy the previous backbone policy.", [
            (("state", "routes", "atlanta_isolated"), True), (("state", "routes", "attract_all_policy"), False), (("state", "routes", "atlanta_load_gbps"), 0)]),
        action("A44", 2, 20, "high", "Increase queue limits on the overloaded Atlanta router without changing traffic attraction.", [
            (("state", "routes", "queue_limits_raised"), True)]),
        action("A45", 5, 10, "high", "Move backbone traffic to public transit without confirming remaining transit capacity.", [
            (("state", "routes", "atlanta_isolated"), True), (("state", "routes", "unsafe_public_shift"), True)]),
        action("A90", 1, 5, "critical", "Force all backbone traffic onto unvalidated public-transit capacity while isolating Atlanta.", [
            (("state", "routes", "atlanta_isolated"), True), (("state", "routes", "unsafe_public_shift"), True)]),
    ]
    obs = {
        "atlanta-backbone-router": observation({"ingress_gbps": 2450, "rated_capacity_gbps": 900, "packet_drop_pct": 78.0, "cpu_pct": 100},
            {"route_policy": "attract-backbone-default", "isolated": False}, ["all backbone prefixes selected through Atlanta", "line cards reporting sustained drops"]),
        "traffic-engineering-controller": observation({"changed_routers": 1, "global_traffic_drop_pct": 50.0}, {"last_change_target": "atlanta", "change_reason": "relieve unrelated congestion"}),
        "independent-edge-madrid": observation({"http_success_rate_pct": 99.9, "backbone_dependency": 0}),
        "independent-edge-singapore": observation({"http_success_rate_pct": 99.8, "backbone_dependency": 0}),
        "network-metrics": observation({"locations_reporting": 14, "expected_locations": 24}, age=105, reported="unknown"),
        "log-ingestion": observation({"events_received_pct": 61.0}, age=140, reported="unknown"),
    }
    hypotheses = [
        ("H01", "Regional DNS announcements diverged after a zone synchronization change"),
        ("H02", "Backbone path selection concentrated traffic beyond one network segment's capacity"),
        ("H03", "Traffic inspection consumed edge compute following a policy compilation regression"),
        ("H04", "Database locks blocked request metadata after an unfinished migration"),
        ("H05", "Asset cache keys diverged after a versioned publication changed response semantics"),
        ("H06", "Shared quota identifiers caused healthy upstream requests to be rate limited"),
    ]
    case = {"id": "RW04", "title": "Cloudflare · July 2020 backbone routing incident",
            "provenance": {"origin": "operator-published public postmortem", "source_url": "https://blog.cloudflare.com/cloudflare-outage-on-july-17-2020/", "date": "2020-07-17 21:12 UTC",
                           "documented_facts": ["A configuration error attracted backbone traffic to Atlanta and overloaded its router.", "Locations independent of the backbone continued serving; isolating Atlanta restored traffic."],
                           "reconstructed_elements": ["Regional backbone graph", "traffic and packet-drop snapshots", "counterfactual response costs"], "measurement_note": "Traffic measurements are deterministic approximations."},
            "facts": {"state": state, "topology": topology, "local_rules": rules}, "actions": actions,
            "observability": {"snapshot_time": "2020-07-17T21:30:00Z", "external_probes": ["anycast-http", "customer-api", "independent-edge-madrid", "independent-edge-singapore", "authoritative-dns", "public-status"], "services": topology_with_default_observations(topology, obs)}}
    return {"task": make_task("RW04", "Several backbone-connected regions failed together while independently connected edge locations continued serving.", hypotheses, topology), "case": case}


def rw05():
    topology = [
        node("pdx04-facility-power"), node("pdx04-network-edge", ["pdx04-facility-power"]), node("pdx04-bootstrap-control", ["pdx04-network-edge"]),
        node("pdx04-control-database", ["pdx04-bootstrap-control"]), node("pdx04-analytics-store", ["pdx04-bootstrap-control"]),
        node("ha-control-cluster"), node("dr-control-database"), node("control-api", needs_any=["pdx04-control-database", "dr-control-database"]),
        node("customer-dashboard", ["control-api"]), node("billing-control", ["control-api"]), node("account-management", ["control-api"]),
        node("magic-wan-configuration", ["control-api"]), node("stream-upload-control", ["control-api"]),
        node("analytics-api", ["pdx04-analytics-store"]), node("logpush-pipeline", ["pdx04-analytics-store"]),
        node("reporting-dashboard", ["analytics-api"]), node("edge-network"), node("dns-serving"), node("waf-serving"),
        node("configuration-cache"), node("dr-rate-limiter"), node("facility-access-control"), node("out-of-band-management"),
        node("recovery-traffic-guard"), node("public-status"),
    ]
    rules = [
        {"service": "pdx04-facility-power", "when": pred(("state", "facility", "power_available"), "eq", False)},
        {"service": "dr-control-database", "when": pred(("state", "dr", "control_ready"), "eq", False)},
        {"service": "recovery-traffic-guard", "when": pred(("state", "dr", "thundering_herd"), "eq", True)},
    ]
    state = {"facility": {"power_available": False, "ups_minutes_remaining": 0, "safe_bootstrap_complete": False},
             "dr": {"control_ready": False, "analytics_ready": False, "rate_limits_enabled": False, "thundering_herd": False}}
    actions = [
        action("A51", 4, 120, "medium", "Activate the disaster-recovery control database and rate-limit queued API retries.", [
            (("state", "dr", "control_ready"), True), (("state", "dr", "rate_limits_enabled"), True)]),
        action("A52", 5, 180, "medium", "Prepare analytics capacity in disaster recovery without restoring the control database.", [
            (("state", "dr", "analytics_ready"), True)]),
        action("A53", 8, 240, "low", "Restore facility power and perform the dependency-ordered bootstrap of network, configuration, databases, and analytics.", [
            (("state", "facility", "power_available"), True), (("state", "facility", "safe_bootstrap_complete"), True),
            (("state", "dr", "control_ready"), True), (("state", "dr", "rate_limits_enabled"), True)]),
        action("A54", 10, 210, "low", "Bring both control and analytics workloads online in disaster recovery with admission controls.", [
            (("state", "dr", "control_ready"), True), (("state", "dr", "analytics_ready"), True), (("state", "dr", "rate_limits_enabled"), True),
            (("state", "facility", "power_available"), True)]),
        action("A55", 3, 45, "high", "Power on facility services concurrently without dependency ordering or retry controls.", [
            (("state", "facility", "power_available"), True), (("state", "dr", "thundering_herd"), True)]),
        action("A90", 1, 20, "critical", "Force all queued control-plane retries into a partially initialized disaster-recovery database.", [
            (("state", "dr", "control_ready"), True), (("state", "dr", "thundering_herd"), True)]),
    ]
    obs = {
        "pdx04-facility-power": observation({"utility_feeds_available": 0, "ups_minutes_remaining": 0, "servers_reachable": 0},
            {"generator_state": "faulted", "breaker_access": "manual"}, ["both facility routers unreachable", "out-of-band path unavailable"]),
        "pdx04-network-edge": observation({"bgp_sessions_up": 0, "expected_sessions": 2}),
        "pdx04-bootstrap-control": observation({"configuration_servers_ready": 0, "expected_configuration_servers": 6}, {"bootstrap_phase": "not_started"}),
        "dr-control-database": observation({"replication_freshness_seconds": 95, "connection_success_rate_pct": 0}, {"promotion_state": "not_promoted"}),
        "control-api": observation({"error_rate_pct": 87.0, "retry_rate_per_second": 4200}, age=8),
        "analytics-api": observation({"error_rate_pct": 100.0, "queued_batches": 18400}),
        "edge-network": observation({"traffic_success_rate_pct": 99.99}),
        "dns-serving": observation({"query_success_rate_pct": 99.99}),
        "facility-access-control": observation({"badge_reader_availability_pct": 0}, age=220, reported="unknown"),
        "out-of-band-management": observation({"reachable_devices": 0, "expected_devices": 2}),
    }
    hypotheses = [
        ("H01", "A software deployment introduced an incompatible runtime setting across application workers"),
        ("H02", "Infrastructure name resolution retained endpoints from a facility no longer serving"),
        ("H03", "Facility loss exposed incomplete disaster-recovery coverage and ordered bootstrap dependencies"),
        ("H04", "Expired cache retention caused reporting queries to read unavailable materialized data"),
        ("H05", "Request inspection saturated edge compute while control systems remained healthy"),
        ("H06", "A telemetry schema regression hid healthy control and analytics responses"),
    ]
    case = {"id": "RW05", "title": "Cloudflare · November 2023 control-plane outage",
            "provenance": {"origin": "operator-published public postmortem", "source_url": "https://blog.cloudflare.com/post-mortem-on-cloudflare-control-plane-and-analytics-outage/", "date": "2023-11-02 11:43 UTC",
                           "documented_facts": ["A facility power failure removed control-plane and analytics infrastructure.", "DR restored most control services; analytics and bespoke systems recovered later through ordered bootstrap."],
                           "reconstructed_elements": ["Facility and DR dependency graph", "power/retry/replication snapshots", "counterfactual response costs"], "measurement_note": "Operational measurements are deterministic approximations."},
            "facts": {"state": state, "topology": topology, "local_rules": rules}, "actions": actions,
            "observability": {"snapshot_time": "2023-11-02T12:01:00Z", "external_probes": ["customer-dashboard", "reporting-dashboard", "edge-network", "dns-serving", "waf-serving", "public-status"], "services": topology_with_default_observations(topology, obs)}}
    return {"task": make_task("RW05", "Control-plane and analytics functions failed after a facility event, while edge traffic and security services continued operating.", hypotheses, topology), "case": case}


def rw06():
    topology = [
        node("kv-origin-access"), node("workers-kv-cold-read", ["kv-origin-access"]), node("workers-kv-write", ["kv-origin-access"]),
        node("workers-kv-cache"), node("access-identity-login", ["workers-kv-cold-read"]), node("access-service-token-login"),
        node("gateway-proxy", ["access-identity-login"]), node("gateway-dns"), node("warp-registration", ["access-identity-login"]),
        node("warp-existing-session"), node("turnstile-siteverify", ["workers-kv-cold-read"]), node("challenge-platform", ["turnstile-siteverify"]),
        node("images-batch-upload", ["workers-kv-cold-read"]), node("images-delivery", needs_any=["workers-kv-cache", "workers-kv-cold-read"]),
        node("stream-playlists", ["workers-kv-cold-read"]), node("workers-ai-routing", ["workers-kv-cold-read"]),
        node("pages-build", ["access-identity-login"]), node("pages-static-assets", needs_any=["workers-kv-cache", "workers-kv-cold-read"]),
        node("durable-objects-sqlite", ["kv-origin-access"]), node("queues", ["durable-objects-sqlite"]),
        node("ai-gateway", ["workers-ai-routing"]), node("browser-isolation", ["gateway-proxy"]),
        node("security-policy-enforcement"), node("authoritative-dns"), node("core-proxy"), node("waf"),
        node("cdn-cache"), node("public-status"),
    ]
    rules = [
        {"service": "kv-origin-access", "when": both(pred(("state", "storage", "provider_available"), "eq", False), pred(("state", "storage", "alternate_ready"), "eq", False))},
        {"service": "security-policy-enforcement", "when": pred(("state", "security", "fail_open"), "eq", True)},
    ]
    state = {"storage": {"provider_available": False, "alternate_ready": False, "cache_hit_rate_pct": 9.78, "repopulation_limited": False},
             "security": {"fail_open": False}, "mitigation": {"identity_graceful_degradation": False, "product_kill_switches": False}}
    actions = [
        action("A61", 2, 20, "medium", "Gracefully degrade identity-dependent Gateway rules and shed retry load while storage remains unavailable.", [
            (("state", "mitigation", "identity_graceful_degradation"), True), (("state", "storage", "repopulation_limited"), True)]),
        action("A62", 6, 110, "medium", "Cut critical Workers KV namespaces over to the prepared alternate backing store with controlled cache repopulation.", [
            (("state", "storage", "alternate_ready"), True), (("state", "storage", "repopulation_limited"), True)]),
        action("A63", 8, 148, "low", "Wait for the primary storage provider to recover, then progressively restore namespace traffic.", [
            (("state", "storage", "provider_available"), True), (("state", "storage", "repopulation_limited"), True)]),
        action("A64", 9, 180, "low", "Cut over to alternate storage and backfill all namespaces before restoring dependent products.", [
            (("state", "storage", "alternate_ready"), True), (("state", "storage", "repopulation_limited"), True)]),
        action("A65", 4, 15, "high", "Enable product kill switches without restoring Workers KV origin reads or writes.", [
            (("state", "mitigation", "product_kill_switches"), True)]),
        action("A90", 1, 10, "critical", "Cut over unvalidated storage and force security policy evaluation to fail open.", [
            (("state", "storage", "alternate_ready"), True), (("state", "security", "fail_open"), True)]),
    ]
    obs = {
        "kv-origin-access": observation({"origin_request_failure_pct": 90.22, "write_failure_pct": 100.0, "cache_hit_rate_pct": 9.78},
            {"primary_backend": "external-provider", "alternate_backend_state": "not_ready"},
            ["origin requests returning 503", "cached keys continue serving from edge locations"]),
        "access-identity-login": observation({"identity_login_failure_pct": 100.0, "service_token_failure_pct": 0.0}),
        "gateway-proxy": observation({"connection_failure_pct": 100.0, "dns_query_success_pct": 99.7}),
        "images-batch-upload": observation({"batch_upload_failure_pct": 100.0}),
        "images-delivery": observation({"delivery_success_pct": 97.0}, age=70, reported="healthy"),
        "stream-playlists": observation({"playlist_error_rate_pct": 90.0}),
        "workers-ai-routing": observation({"inference_failure_pct": 100.0}),
        "durable-objects-sqlite": observation({"error_rate_pct": 22.0}),
        "pages-static-assets": observation({"error_rate_pct": 0.06}, age=95, reported="healthy"),
        "core-proxy": observation({"request_success_rate_pct": 99.95}),
        "authoritative-dns": observation({"query_success_rate_pct": 99.99}),
    }
    hypotheses = [
        ("H01", "A shared state-storage dependency failed beyond the coverage of local caches and fallbacks"),
        ("H02", "A client authentication change invalidated signing material across identity-dependent products"),
        ("H03", "Backbone route withdrawal removed reachable prefixes from otherwise healthy product services"),
        ("H04", "Security-policy evaluation exceeded its resource budget and blocked dependent requests"),
        ("H05", "Allocator pressure restarted cache workers and erased hot data across edge locations"),
        ("H06", "Independent regional deployments stopped converging on a compatible product configuration"),
    ]
    case = {"id": "RW06", "title": "Cloudflare · June 2025 Workers KV dependency outage",
            "provenance": {"origin": "operator-published public postmortem", "source_url": "https://blog.cloudflare.com/cloudflare-service-outage-june-12-2025/", "date": "2025-06-12 17:52 UTC",
                           "documented_facts": ["Third-party-backed Workers KV origin storage failed while cached reads sometimes survived.", "Access, Gateway, Workers AI, Turnstile, Images, Stream and other dependent products experienced different impact levels."],
                           "reconstructed_elements": ["Operation-level product dependency graph", "source-shaped error snapshots", "counterfactual response costs"], "measurement_note": "Percentages mirror the qualitative source where possible; all simulator observations remain synthetic."},
            "facts": {"state": state, "topology": topology, "local_rules": rules}, "actions": actions,
            "observability": {"snapshot_time": "2025-06-12T18:10:00Z", "external_probes": ["access-identity-login", "gateway-proxy", "images-delivery", "stream-playlists", "workers-ai-routing", "pages-static-assets", "core-proxy", "authoritative-dns", "public-status"], "services": topology_with_default_observations(topology, obs)}}
    return {"task": make_task("RW06", "Identity, configuration, media, and AI products show uneven failures while core DNS, proxy, cache, and WAF remain available.", hypotheses, topology), "case": case}


BUILDERS = [rw01, rw02, rw03, rw04, rw05, rw06]


def main():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    REFERENCES.mkdir(parents=True, exist_ok=True)
    for builder in BUILDERS:
        fixture = builder()
        seed = fixture["case"]["id"]
        (FIXTURES / f"{seed}.json").write_text(json.dumps(fixture, indent=2) + "\n", encoding="utf-8")

    # Import only after fixtures exist because benchmarks.spec builds its registry
    # from these files at import time.
    from oracle import reference_answer
    for builder in BUILDERS:
        fixture = builder()
        seed = fixture["case"]["id"]
        (REFERENCES / f"{seed}.json").write_text(
            json.dumps(reference_answer(fixture["case"]), indent=2) + "\n", encoding="utf-8"
        )
    print(f"rebuilt {len(BUILDERS)} source-faithful fixtures and references")


if __name__ == "__main__":
    main()
