# PathForward — create & publish the Fabric data agent
# =====================================================
# RUN THIS INSIDE A MICROSOFT FABRIC NOTEBOOK (it cannot run locally).
#
# Two routes to create + publish a PathForward Fabric data agent:
#   (A) THIS notebook (fastest supported path): the `fabric-data-agent-sdk` runs ONLY inside Fabric
#       notebooks (Microsoft: "not supported for local execution"), and `publish()` is a notebook
#       action — so this script must run in a Fabric notebook, not locally.
#   (B) Fabric DataAgent REST API (more automated, heavier payload): POST
#       https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/dataAgents with a public
#       definition (draft/ + published/ datasource.json + stage_config.json + publish_info.json,
#       each InlineBase64). Supports user / service principal / managed identity; caller needs the
#       Contributor workspace role + Item.ReadWrite.All. Building the definition payload is more work
#       and riskier than (A). Refs (verified 2026-06-08):
#         https://learn.microsoft.com/rest/api/fabric/dataagent/items/create-data-agent
#         https://learn.microsoft.com/rest/api/fabric/articles/item-management/definitions/data-agent-definition
#   This file is route (A) — the recommended fast path to get the artifact_id today.
#
# Setup before running:
#   1. Open the PathForward-IQ workspace (id 1568f5b8-3d1f-460b-8a74-bebb59a15a62).
#   2. New notebook; attach PathForwardLH as the default lakehouse.
#   3. Paste this whole file into one cell and Run.
#
# After it runs, get the artifact_id (we already know the workspace_id):
#   Open the data agent -> Settings -> copy the published URL:
#     https://<env>.fabric.microsoft.com/groups/<workspace_id>/aiskills/<artifact_id>
#   workspace_id = 1568f5b8-3d1f-460b-8a74-bebb59a15a62
#   Hand back <artifact_id>; the Foundry "Microsoft Fabric" connection is wired from there.
#
# Verified API (Learn MCP, 2026-06-08): fabric.dataagent.client.create_data_agent /
# add_datasource / get_datasources()[0].select(schema, table) / update_configuration / publish.

%pip install fabric-data-agent-sdk --quiet

from fabric.dataagent.client import create_data_agent, delete_data_agent

AGENT_NAME = "pathforward-cohort"
LAKEHOUSE = "PathForwardLH"
# The 10 OneLake star-schema tables confirmed present in PathForwardLH.
TABLES = [
    "workers", "skills", "roles", "certifications",
    "worker_has_skill", "role_requires_skill", "worker_targets_role",
    "cert_certifies_skill", "certgap", "readiness",
]

# Idempotent: drop any prior agent of this name so re-runs are clean.
try:
    delete_data_agent(AGENT_NAME)
    print("removed prior:", AGENT_NAME)
except Exception as exc:  # noqa: BLE001
    print("no prior to remove:", type(exc).__name__)

da = create_data_agent(AGENT_NAME)
da.add_datasource(LAKEHOUSE, type="lakehouse")

ds = da.get_datasources()[0]
for t in TABLES:
    ds.select("dbo", t)   # lakehouse SQL schema is 'dbo'; adjust if your SQL endpoint differs

ds.update_configuration(
    instructions=(
        "This is the PathForward reskilling ontology, materialized as a star schema. "
        "Entities: workers, skills, roles, certifications. "
        "Edges: worker_has_skill, role_requires_skill, worker_targets_role, cert_certifies_skill. "
        "Derived: certgap = role-required skills a worker lacks; "
        "readiness = (covered required skills / total required) per worker+target role. "
        "Answer COHORT / PROGRAM questions only: per-role readiness distributions, the biggest skill "
        "bottlenecks across a role cohort, and how one worker compares to peers targeting the same role. "
        "These numbers are authoritative; do not invent figures the tables do not support."
    )
)

da.publish()
print("PUBLISHED data agent:", AGENT_NAME)
print("workspace_id = 1568f5b8-3d1f-460b-8a74-bebb59a15a62")
print("Now copy the artifact_id from the data agent Settings -> published URL (.../aiskills/<artifact_id>).")
ds.pretty_print()
