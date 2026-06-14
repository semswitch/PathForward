# Fabric IQ — infrastructure artifacts

## `ontology-definition.json`
The full exported definition of the **PathForward ontology** (4 entity types —
Worker/Skill/Role/Certification — + 6 relationships incl. the derived `certgap`
and `readiness` edges, with their lakehouse data bindings). Captured via the
Fabric REST `items/getDefinition` API.

> Note: this file embeds **workspace-scoped internal artifact IDs** (EntityType IDs,
> DataBinding/Contextualization GUIDs) — real identifiers for this tenant's Fabric items, not
> credentials. It is kept as a **local, gitignored backup** (not tracked in the public repo) and is
> required for the recovery import below.

This is our **version backup**: Fabric IQ Ontology (preview) has no native
versioning, so a deleted ontology or its backing "Graph in Microsoft Fabric"
child item is otherwise only recoverable via the workspace recycle bin (off by
default) or Git. This file makes recovery a one-shot — no UI re-modeling.

### Recover the ontology from this file
As the service principal (workspace Admin), POST a new Ontology item from the
saved definition (Fabric auto-creates a fresh graph child):

```powershell
$tok = az account get-access-token --resource "https://api.fabric.microsoft.com" --query accessToken -o tsv
$h = @{ Authorization = "Bearer $tok"; "Content-Type" = "application/json" }
$ws  = $env:FABRIC_WORKSPACE_ID   # PathForward-IQ workspace ID (set in .env — gitignored)
$def = (Get-Content infra/fabric/ontology-definition.json -Raw | ConvertFrom-Json).definition
$body = @{ displayName = "PathForwardOntology"; type = "Ontology"; definition = $def } | ConvertTo-Json -Depth 40
Invoke-WebRequest -Uri "https://api.fabric.microsoft.com/v1/workspaces/$ws/items" -Headers $h -Method POST -Body $body
# then: open the new ontology's GraphModel -> ... -> Schedule -> Refresh now (to re-ingest instance data)
```
> Do NOT reuse the name of an existing (e.g. broken) item — name collisions block
> both create and recycle-bin restore. Rename/delete the old item first.

## Environment
- Workspace `PathForward-IQ` = `<FABRIC_WORKSPACE_ID>` (real value in `.env`, gitignored)
- Lakehouse `PathForwardLH` = `<FABRIC_LAKEHOUSE_ID>` (10 Delta tables; real value in `.env`)
- Capacity `<fabric-capacity>` (F2)
- Tables loaded by `scripts/load_fabric_lakehouse.py`; rebuild source CSVs with `scripts/export_fabric_tables.py`.

> Bindings reference lakehouse table GUIDs in **this** workspace; restoring into a
> different workspace requires re-pointing the data bindings.
