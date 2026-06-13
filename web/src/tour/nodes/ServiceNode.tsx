import { memo } from "react";
import type { Node, NodeProps } from "@xyflow/react";
import { cn } from "../../lib/cn";
import type { TourNodeData } from "../graph";
import { StatusChip, TourHandles } from "./parts";

/** Azure substrate services: muted, quiet, supporting cast. */
export const ServiceNode = memo(function ServiceNode({
  data,
}: NodeProps<Node<TourNodeData>>) {
  return (
    <div
      data-status={data.status}
      className={cn(
        "w-[210px] rounded-lg border bg-surface-raised/60 px-4 py-3 transition-[border-color,opacity] duration-300",
        data.status === "dormant" && !data.focused
          ? "border-line opacity-65"
          : "border-ink-muted/50",
        data.focused && "pf-node-pulse"
      )}
    >
      <p className="font-mono text-[9px] uppercase tracking-widest text-ink-muted">
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
