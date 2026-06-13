import { memo } from "react";
import type { Node, NodeProps } from "@xyflow/react";
import { cn } from "../../lib/cn";
import type { TourNodeData } from "../graph";
import { StatusChip, TourHandles } from "./parts";

/** LLM agents reason: rounded, brand-luminous. */
export const AgentNode = memo(function AgentNode({
  data,
}: NodeProps<Node<TourNodeData>>) {
  return (
    <div
      data-status={data.status}
      className={cn(
        "w-[230px] rounded-agent border bg-surface-raised px-4 py-3 transition-[border-color,opacity] duration-300",
        data.status === "dormant" && !data.focused
          ? "border-line opacity-75"
          : "border-brand-400/70",
        data.focused && "pf-node-pulse border-brand-400"
      )}
    >
      <p className="font-mono text-[9px] uppercase tracking-widest text-brand-300">
        {data.tag}
      </p>
      <p className="mt-1 text-[13px] leading-tight font-semibold">{data.label}</p>
      {data.sublabel ? (
        <p className="mt-1 text-[11px] leading-snug text-ink-muted">
          {data.sublabel}
        </p>
      ) : null}
      <StatusChip status={data.status} />
      <TourHandles handles={data.handles} />
    </div>
  );
});
