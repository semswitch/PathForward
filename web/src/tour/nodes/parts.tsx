import { Handle, Position } from "@xyflow/react";
import { cn } from "../../lib/cn";
import type { HandleSpec, NodeStatus } from "../graph";

export function TourHandles({ handles }: { handles: HandleSpec[] }) {
  return (
    <>
      {handles.map((h) => (
        <Handle
          key={h.id}
          id={h.id}
          type={h.type}
          position={h.position}
          isConnectable={false}
          style={
            h.offset
              ? h.position === Position.Top || h.position === Position.Bottom
                ? { left: h.offset }
                : { top: h.offset }
              : undefined
          }
        />
      ))}
    </>
  );
}

const CHIP_CLASSES: Partial<Record<NodeStatus, string>> = {
  rejected: "border-rose-400/40 bg-rose-500/20 text-rose-300",
  verified: "border-mint-400/40 bg-mint-500/20 text-mint-300",
  minted: "border-mint-400/40 bg-mint-500/20 text-mint-300",
  abstained: "border-amber-400/40 bg-amber-500/20 text-amber-300",
};

export function StatusChip({ status }: { status: NodeStatus }) {
  const classes = CHIP_CLASSES[status];
  if (!classes) return null;
  return (
    <span
      className={cn(
        "mt-1.5 inline-block rounded-full border px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider",
        classes
      )}
    >
      {status}
    </span>
  );
}
