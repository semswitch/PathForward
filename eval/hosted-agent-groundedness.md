# PathForward - Hosted Agent Groundedness & Approval Hold (live)

Metric: hosted response verified, grounded, skill-loaded, fabric-live, no credential without approval
Passed: 2/3 (66.7%)

- **PASS** `hosted_grounded_EMP-001`: worker=EMP-001 status=verified retrieved=8 cited=4 approval=True
- **FAIL** `hosted_grounded_EMP-004`: worker=EMP-004 status=None retrieved=0 cited=0 approval=False
- **PASS** `hosted_grounded_EMP-006`: worker=EMP-006 status=verified retrieved=10 cited=4 approval=True

Scope note: this scorecard targets the Foundry Hosted Agent endpoint. It is separate from the older prompt-agent Orchestrator scorecards.

Failure note: `hosted_grounded_EMP-004` was re-run once and the Hosted Agent completed, but the
Fabric data-agent run failed before returning the PathForward proof JSON:
`LastError(code='server_error', message='An attempt was made to transition a task to a final state when it had already completed.')`.
