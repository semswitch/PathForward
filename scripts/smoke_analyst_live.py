"""Live smoke for the NON-GATING Code Interpreter analyst (agents/analyst.py -> CodeInterpreterAnalyst).

Proves the analyst works on live Azure AND stays off the trust path:
  - it is NOT a NumericChecker (structural: the gate could never accept it as its oracle),
  - a numeric second opinion (the model writes-and-runs Python) AGREES with the deterministic
    LocalNumericChecker on a real claim -- and a disagreement would be advisory only,
  - a calibration report produces an explainability artifact (a chart file), the analyst's real value.

The model writes-and-runs the Python, so this is inherently non-deterministic -- that is exactly why
it can never be the credential gate. Code Interpreter is billed per session.

    python scripts/smoke_analyst_live.py

Exit 0 = the live analyst ran, its second opinion agreed with the deterministic oracle, and it is
structurally non-gating.
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # for generate_data

from pathforward.agents.analyst import CodeInterpreterAnalyst        # noqa: E402
from pathforward.agents.calibration import cold_start_calibrate      # noqa: E402
from pathforward.agents.numeric import LocalNumericChecker, NumericChecker  # noqa: E402
from pathforward.config import load_settings                         # noqa: E402
from pathforward.iq.seed import build_seed                           # noqa: E402
from generate_data import _learner_responses                        # noqa: E402

ANALYST_AGENT = "pathforward-analyst"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    s = load_settings(os.path.join(_ROOT, ".env"))

    out_dir = os.path.join(_ROOT, ".agents", "temp")
    os.makedirs(out_dir, exist_ok=True)
    stats = cold_start_calibrate(_learner_responses(build_seed()))
    claim = "18 + 6 == 24"

    analyst = CodeInterpreterAnalyst(endpoint=s.foundry_project_endpoint, model=s.model_deployment,
                                     agent_name=ANALYST_AGENT, out_dir=out_dir)
    rc = 1
    try:
        # Structural: the analyst can never be the gate's numeric oracle.
        not_a_checker = not isinstance(analyst, NumericChecker)

        # Live numeric second opinion (model writes-and-runs Python) vs the deterministic oracle.
        so = analyst.second_opinion(claim)
        gate_oracle_ok = LocalNumericChecker().check(claim).ok
        print(f"[ANALYST] second opinion on '{claim}': agrees={so.agrees}")
        print(f"  summary: {so.summary}")
        print(f"  deterministic gate oracle (LocalNumericChecker) says ok={gate_oracle_ok}")
        second_opinion_concord = (so.agrees is True) and gate_oracle_ok

        # Live calibration explainability artifact (a chart the model generates).
        rep = analyst.calibration_report({k: v for k, v in stats.items() if k.startswith("item-")})
        print(f"\n[ANALYST] calibration: {rep.summary}")
        print(f"  generated files: {list(rep.figures) or '(none)'}")
        produced_chart = len(rep.figures) > 0

        checks = {
            "analyst is NOT a NumericChecker (non-gating by shape)": not_a_checker,
            "live second opinion agrees with the deterministic oracle": second_opinion_concord,
            "calibration produced an explainability artifact": produced_chart,
        }
        print("\n=== checks ===")
        for name, ok in checks.items():
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        # The chart artifact is best-effort (model/file behavior varies); gate the exit on the two
        # load-bearing claims (non-gating + concord), and report the chart separately.
        rc = 0 if (not_a_checker and second_opinion_concord) else 1
        print("\nLIVE ANALYST", "PASS" if rc == 0 else "FAIL",
              "(chart artifact: " + ("yes" if produced_chart else "not produced") + ")")
    finally:
        try:
            analyst.close()
        except Exception:  # noqa: BLE001
            pass
        print("agent deleted")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
