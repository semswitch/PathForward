# PathForward MCP Mint Function

Azure Functions HTTP adapter for PathForward MCP tools.

Endpoints after deployment:

```text
https://<function-app>.azurewebsites.net/api/mcp
https://<function-app>.azurewebsites.net/api/gate-mcp
https://<function-app>.azurewebsites.net/api/fabric-mcp
https://<function-app>.azurewebsites.net/api/route-mcp
```

Required app settings:

```text
PATHFORWARD_MINT_SIGNING_KEY=<secret>
PATHFORWARD_MINT_REPLAY_TABLE_CONNECTION=<storage connection string>
PATHFORWARD_MINT_REPLAY_TABLE=PathForwardMintReplay
AZURE_SEARCH_ENDPOINT=<search endpoint>
AZURE_SEARCH_INDEX=pathforward-iq
APPLICATIONINSIGHTS_CONNECTION_STRING=<pathforward-telemetry connection string>
PYTHON_APPLICATIONINSIGHTS_ENABLE_TELEMETRY=true
```

MCP connection (mint — attached directly to the orchestrator):

```text
type: mcp
server_label: pathforward-mint
server_url: https://<function-app>.azurewebsites.net/api/mcp
require_approval: always
allowed_tools: pathforward_mint_credential
```

The MCP tool accepts only `mint_request_token`. It does not accept raw credential facts, verified
flags, worker readiness, or Evidence Gate verdicts.

MCP connection (gate issuer):

```text
type: mcp
server_label: pathforward-gate
server_url: https://<function-app>.azurewebsites.net/api/gate-mcp
require_approval: never
allowed_tools: verify_assessment_and_issue_mint_request
```

The gate issuer verifies the assessment item in code and returns a signed mint request token only
when the Evidence Gate passes.

MCP connection (route-facts resolver):

```text
type: mcp
server_label: pathforward-route
server_url: https://<function-app>.azurewebsites.net/api/route-mcp
require_approval: never
allowed_tools: resolve_route_facts
```

The route-facts resolver returns deterministic route facts for a worker (target role, existing
skills, admissible certification-gap skills, driving edge ids, approved grounding refs) so the
Orchestrator can run `/pathforward` from a minimal prompt without injected facts. It is read-only:
it never mints, verifies, or issues a token.

The Function emits non-secret custom events:

```text
pathforward.mcp.gate
pathforward.mcp.mint
pathforward.mcp.fabric
pathforward.mcp.route
```

These events exclude request bodies, prompts, citations, credential evidence, and
`mint_request_token` values.

Approval execution uses the Responses API MCP approval flow:

```text
previous_response_id=<response containing mcp_approval_request>
model=reasoning
agent_reference=pathforward-orchestrator
input=[{"type":"mcp_approval_response","approval_request_id":"<id>","approve":true}]
```
