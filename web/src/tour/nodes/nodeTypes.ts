import type { NodeTypes } from "@xyflow/react";
import { AgentNode } from "./AgentNode";
import { CodeNode } from "./CodeNode";
import { ServiceNode } from "./ServiceNode";
import { UserNode } from "./UserNode";

/** Module-scope (identity-stable) — React Flow re-mounts nodes if this changes per render. */
export const nodeTypes: NodeTypes = {
  agent: AgentNode,
  code: CodeNode,
  service: ServiceNode,
  user: UserNode,
};
