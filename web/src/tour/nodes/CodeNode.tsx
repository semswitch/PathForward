import { memo } from "react";
import type { Node, NodeProps } from "@xyflow/react";
import { cn } from "../../lib/cn";
import type { TourNodeData } from "../graph";
import { StatusChip, TourHandles } from "./parts";

/** Deterministic code notarizes: sharp corners, mint accent, monochrome body. */
export const CodeNode = memo(function CodeNode({
  data,
}: NodeProps<Node<TourNodeData>>) {
  return (
    <div
      data-status={data.status}
      className={cn(
        "w-[230px] rounded-code border border-l-4 bg-surface-raised px-4 py-3 transition-[border-color,opacity] duration-300",
        data.status === "dormant" && !data.focused
          ? "border-line border-l-mint-500/50 opacity-75"
          : "border-line border-l-mint-400",
        data.focused && "pf-node-pulse border-mint-300/70 border-l-mint-300"
      )}
    >
      <p className="font-mono text-[9px] uppercase tracking-widest text-mint-300">
        {data.tag}
      </p>
      <p className="mt-1 font-mono text-[12px] leading-tight font-semibold">
        {data.label}
      </p>
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
