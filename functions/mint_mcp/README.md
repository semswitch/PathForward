# PathForward MCP Mint Function

Azure Functions HTTP adapter for PathForward MCP tools.

Endpoints after deployment:

```text
https://<function-app>.azurewebsites.net/api/mcp
https://<function-app>.azurewebsites.net/api/gate-mcp
https://<function-app>.azurewebsites.net/api/fabric-mcp
```

Required app settings:

```text
PATHFORWARD_MINT_SIGNING_KEY=<secret>
PATHFORWARD_MINT_REPLAY_TABLE_CONNECTION=<storage connection string>
PATHFORWARD_MINT_REPLAY_TABLE=PathForwardMintReplay
AZURE_SEARCH_ENDPOINT=<search endpoint>
AZURE_SEARCH_INDEX=pathforward-iq
```

Foundry Toolbox configuration must use:

```text
type: mcp
server_label: pathforward-mint
server_url: https://<function-app>.azurewebsites.net/api/mcp
require_approval: always
allowed_tools: pathforward_mint_credential
```

The MCP tool accepts only `mint_request_token`. It does not accept raw credential facts, verified
flags, worker readiness, or Evidence Gate verdicts.

Gate issuer toolbox configuration:

```text
type: mcp
server_label: pathforward-gate
server_url: https://<function-app>.azurewebsites.net/api/gate-mcp
require_approval: never
allowed_tools: verify_assessment_and_issue_mint_request
```

The gate issuer verifies the assessment item in code and returns a signed mint request token only
when the Evidence Gate passes.

Approval execution uses the Responses API MCP approval flow:

```text
previous_response_id=<response containing mcp_approval_request>
model=reasoning
agent_reference=pathforward-orchestrator
input=[{"type":"mcp_approval_response","approval_request_id":"<id>","approve":true}]
```
