# PathForward MCP Mint Function

Azure Functions HTTP adapter for the governed MCP mint tool.

Endpoint after deployment:

```text
https://<function-app>.azurewebsites.net/api/mcp
```

Required app settings:

```text
PATHFORWARD_MINT_SIGNING_KEY=<secret>
PATHFORWARD_MINT_REPLAY_TABLE_CONNECTION=<storage connection string>
PATHFORWARD_MINT_REPLAY_TABLE=PathForwardMintReplay
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
