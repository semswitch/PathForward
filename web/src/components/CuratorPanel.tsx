// Curator Panel (Fluent UI v9 + Griffel).
// Shows the Curator agent's gap reasoning: the ranked admissible CertGap
// skills with per-skill rationale, the chosen target, and whether the
// deterministic admissibility gate had to correct the agent's proposal.
import {
  Card,
  Badge,
  Subtitle1,
  Body1,
  Caption1,
  Text,
  mergeClasses,
} from "@fluentui/react-components";
import type { Fixture } from "../lib/contracts";
import type { VisibleState } from "../lib/visibleState";
import { useStyles } from "./CuratorPanel.styles";
import { useRevealStyles } from "./reveal.styles";

export interface CuratorPanelProps {
  fixture: Fixture;
  visible: VisibleState["curator"];
}

export function CuratorPanel({ fixture, visible }: CuratorPanelProps) {
  const styles = useStyles();
  const reveal = useRevealStyles();
  const { curator } = fixture;
  return (
    <Card>
      <Subtitle1>Curator — Which gap first?</Subtitle1>
      {visible.showRanking && (
        <>
          <Body1 className={reveal.fadeIn}>
            {curator.admissible_skill_ids.length} admissible gap skills, ranked by adjacency and
            certification coverage. Only assessable gaps are admissible — a deterministic gate, not
            the agent, enforces that.
          </Body1>
          <ul className={mergeClasses(styles.list, reveal.fadeIn)} aria-label="curator ranking">
            {curator.ranking.map((skillId, i) => {
              const chosen = visible.showChoice && skillId === curator.chosen_skill_id;
              return (
                <li
                  key={skillId}
                  className={mergeClasses(styles.item, chosen && styles.chosen)}
                >
                  <Caption1 className={styles.rank} aria-hidden>
                    {i + 1}.
                  </Caption1>
                  <Text font="monospace">{skillId}</Text>
                  {chosen && (
                    <Badge appearance="filled" color="brand" role="img" aria-label={`${skillId} chosen`}>
                      chosen
                    </Badge>
                  )}
                  <Caption1 className={styles.rationale}>
                    {curator.rationale[skillId] ?? ""}
                  </Caption1>
                </li>
              );
            })}
          </ul>
        </>
      )}
      {visible.showChoice && (
        <div className={mergeClasses(styles.row, reveal.fadeIn)}>
          <Body1>
            Driving edge: <Text font="monospace">{curator.chosen_edge_id}</Text>
          </Body1>
          {curator.corrected && (
            <Badge
              appearance="tint"
              color="warning"
              role="img"
              aria-label="curator proposal corrected by the deterministic admissibility gate"
            >
              admissibility-corrected
            </Badge>
          )}
        </div>
      )}
    </Card>
  );
}
