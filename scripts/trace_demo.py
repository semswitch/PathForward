"""Print the assessment loop as an OpenTelemetry trace — the glass box, timed.

Runs the propose->verify->(reject->regenerate)->mint flow with the Console exporter so the span
tree prints to your terminal, and (if AZURE_MONITOR_CONNECTION_STRING is set) also ships the trace to
Azure Monitor / the Foundry Tracing tab. Offline by default (deterministic FakeLLM refuse->regenerate);
`--live` drives the real gpt-5.5 agent.

    python scripts/trace_demo.py            # offline, deterministic span tree
    python scripts/trace_demo.py --live     # real agent (needs Azure)
"""
from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from pathforward.agents.client import FakeLLMClient        # noqa: E402
from pathforward.agents.generator import Generator         # noqa: E402
from pathforward.agents.loop import run_assessment_loop     # noqa: E402
from pathforward.agents.numeric import LocalNumericChecker  # noqa: E402
from pathforward.agents.verifier import Verifier            # noqa: E402
from pathforward.config import load_settings                # noqa: E402
from pathforward.credential.mint import mint                # noqa: E402
from pathforward.iq import derivation as dv                 # noqa: E402
from pathforward.iq import traversal                        # noqa: E402
from pathforward.iq.seed import build_seed, HERO_WORKER_ID  # noqa: E402
from pathforward.obs import tracing                         # noqa: E402


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="Trace the assessment loop (Console + optional Azure).")
    ap.add_argument("--live", action="store_true", help="drive the real gpt-5.5 agent")
    args = ap.parse_args()
    s = load_settings(os.path.join(_ROOT, ".env"))

    active = tracing.configure_tracing(
        console=True, azure_connection_string=(s.azure_monitor_connection_string or None))
    print(f"tracing active={active}  azure_export={'on' if s.azure_monitor_connection_string else 'off'}\n")

    onto = build_seed()
    worker = onto.workers[HERO_WORKER_ID]
    role = onto.roles[worker.target_role_id]
    edges = dv.build_all_edges(onto)
    driving = traversal.cert_gap_edges(worker, onto, edges)[0]
    skill = onto.skills[driving.target_id]
    allowed = traversal.approved_refs(worker, skill, onto)

    if args.live:
        from pathforward.agents.foundry import FoundryLLMClient
        client = FoundryLLMClient(endpoint=s.foundry_project_endpoint, model=s.model_deployment,
                                  index_name=s.search_index)
    else:
        client = FakeLLMClient()

    rc = 0
    try:
        with tracing.span("assessment.session", **{"pf.worker": worker.id, "pf.skill": skill.id}):
            result = run_assessment_loop(driving, skill, allowed, Generator(client),
                                         Verifier(LocalNumericChecker()))
            if result.status == "verified":
                cred = mint(worker, role, driving.id, skill.id, result)
                print(f"\nminted: cited_edge_id={cred.credential_subject['cited_edge_id']} "
                      f"readiness={cred.credential_subject['readiness']}")
            else:
                print("\nabstained (fail-closed) — no credential")
                rc = 0
    finally:
        if args.live:
            client.close()
        tracing.flush()
    print(f"\nloop status: {result.status} (attempts: {result.attempts})")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
