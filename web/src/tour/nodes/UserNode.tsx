import { memo } from "react";
import type { Node, NodeProps } from "@xyflow/react";
import { cn } from "../../lib/cn";
import type { TourNodeData } from "../graph";
import { StatusChip, TourHandles } from "./parts";

/** Humans in the loop: soft full-round, warm. */
export const UserNode = memo(function UserNode({
  data,
}: NodeProps<Node<TourNodeData>>) {
  return (
    <div
      data-status={data.status}
      className={cn(
        "w-[210px] rounded-full border bg-surface-raised px-6 py-3 text-center transition-[border-color,opacity] duration-300",
        data.status === "dormant" && !data.focused
          ? "border-brand-300/30 opacity-80"
          : "border-brand-300/70",
        data.focused && "pf-node-pulse border-brand-300"
      )}
    >
      <p className="font-mono text-[9px] uppercase tracking-widest text-brand-300">
        {data.tag}
      </p>
      <p className="mt-0.5 text-[13px] leading-tight font-semibold">
        {data.label}
      </p>
      {data.sublabel ? (
        <p className="mt-0.5 text-[11px] leading-snug text-ink-muted">
          {data.sublabel}
        </p>
      ) : null}
      <StatusChip status={data.status} />
      <TourHandles handles={data.handles} />
    </div>
  );
});
