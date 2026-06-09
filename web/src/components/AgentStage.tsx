// Agent Stage rail: the cast of the multi-agent run. Two visual identities make
// "agents reason, code notarizes" legible without narration — LLM agents are
// rounded and brand-tinted; the Evidence Gate and Mint are sharp, stamp-like
// code. The chip for the current beat's actor lights up as the replay advances.
import { Fragment } from "react";
import { Badge, Caption1, Caption1Strong, mergeClasses } from "@fluentui/react-components";
import {
  Bot20Regular,
  Certificate20Regular,
  ShieldCheckmark20Regular,
} from "@fluentui/react-icons";
import type { Actor } from "../lib/director";
import { useStyles } from "./AgentStage.styles";

interface Stage {
  actor: Actor;
  label: string;
  kind: "llm" | "code";
}

const STAGES: Stage[] = [
  { actor: "curator", label: "Curator", kind: "llm" },
  { actor: "generator", label: "Generator", kind: "llm" },
  { actor: "critic", label: "Critic", kind: "llm" },
  { actor: "gate", label: "Evidence Gate", kind: "code" },
  { actor: "planner", label: "Planner", kind: "llm" },
  { actor: "insights", label: "Insights", kind: "llm" },
  { actor: "mint", label: "Mint", kind: "code" },
];

export interface AgentStageProps {
  activeActor: Actor | null;
  /** Transcript index of the in-flight attempt (shows "attempt n/3" at the gate). */
  attempt?: number;
  maxAttempts: number;
  loopStatus: "verified" | "abstained";
}

function stageIcon(stage: Stage) {
  if (stage.actor === "gate") return <ShieldCheckmark20Regular aria-hidden />;
  if (stage.actor === "mint") return <Certificate20Regular aria-hidden />;
  return <Bot20Regular aria-hidden />;
}

export function AgentStage({ activeActor, attempt, maxAttempts, loopStatus }: AgentStageProps) {
  const styles = useStyles();
  return (
    <div role="group" aria-label="agent pipeline" className={styles.rail}>
      {STAGES.map((stage, i) => {
        const active = stage.actor === activeActor;
        const Label = stage.kind === "code" ? Caption1Strong : Caption1;
        return (
          <Fragment key={stage.actor}>
            {i > 0 && (
              <Caption1 aria-hidden className={styles.arrow}>
                →
              </Caption1>
            )}
            <div
              aria-current={active ? "step" : undefined}
              aria-label={`${stage.label} — ${stage.kind === "code" ? "deterministic code" : "reasoning agent"}${active ? ", active" : ""}`}
              role="img"
              className={mergeClasses(
                styles.chip,
                stage.kind === "llm" ? styles.llm : styles.code,
                active && (stage.kind === "llm" ? styles.llmActive : styles.codeActive),
                stage.actor === "mint" && loopStatus === "abstained" && styles.dimmed,
              )}
            >
              {stageIcon(stage)}
              <Label>{stage.label}</Label>
              {stage.actor === "gate" && attempt !== undefined && (
                <Badge
                  appearance="filled"
                  color="important"
                  role="img"
                  aria-label={`gate attempt ${attempt + 1} of ${maxAttempts}`}
                >
                  {attempt + 1}/{maxAttempts}
                </Badge>
              )}
            </div>
          </Fragment>
        );
      })}
    </div>
  );
}
