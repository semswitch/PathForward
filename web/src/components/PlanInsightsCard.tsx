// Plan & Program Insights (Fluent UI v9 + Griffel).
// The Planner's capacity- and accessibility-aware schedule (advisory; the
// deterministic gates own hours, weekly load, and arithmetic) and the
// read-only Program Insights cohort view (all numbers code-computed; the
// agent only narrates).
import {
  Card,
  Badge,
  Subtitle1,
  Subtitle2,
  Body1,
  Text,
  Table,
  TableHeader,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
  mergeClasses,
} from "@fluentui/react-components";
import type { Fixture } from "../lib/contracts";
import type { VisibleState } from "../lib/visibleState";
import { useStyles } from "./PlanInsightsCard.styles";
import { useRevealStyles } from "./reveal.styles";

export interface PlanInsightsCardProps {
  fixture: Fixture;
  visible: { plan: VisibleState["plan"]; insights: VisibleState["insights"] };
}

export function PlanInsightsCard({ fixture, visible }: PlanInsightsCardProps) {
  const styles = useStyles();
  const reveal = useRevealStyles();
  const { plan, insights } = fixture;
  return (
    <Card>
      <Subtitle1>Learning Plan &amp; Program Insights</Subtitle1>
      {visible.plan.visible && (
        <div className={reveal.fadeIn}>
          <div className={styles.row}>
            <Badge appearance="tint" color="brand">{plan.weeks} weeks</Badge>
            <Badge appearance="tint" color="brand">{plan.total_hours} h total</Badge>
            <Badge appearance="outline">{plan.weekly_capacity_hours} h/week capacity</Badge>
            <Badge
              appearance="tint"
              color={plan.capacity_respected ? "success" : "danger"}
              role="img"
              aria-label={`capacity ${plan.capacity_respected ? "respected" : "exceeded"}`}
            >
              capacity {plan.capacity_respected ? "respected" : "exceeded"}
            </Badge>
            {plan.accessibility_adaptations.map((a) => (
              <Badge key={a} appearance="tint" color="success" role="img" aria-label={a}>
                {a}
              </Badge>
            ))}
          </div>
          <Body1 block>{plan.rationale}</Body1>
          <div className={styles.tableWrap}>
            <Table aria-label="Learning plan phases" size="small">
              <TableHeader>
                <TableRow>
                  <TableHeaderCell>Week</TableHeaderCell>
                  <TableHeaderCell>Skill</TableHeaderCell>
                  <TableHeaderCell>Hours</TableHeaderCell>
                  <TableHeaderCell>Certification</TableHeaderCell>
                </TableRow>
              </TableHeader>
              <TableBody>
                {plan.phases.map((p) => (
                  <TableRow key={`${p.week}-${p.skill_id}`}>
                    <TableCell>{p.week}</TableCell>
                    <TableCell><Text font="monospace">{p.skill_id}</Text></TableCell>
                    <TableCell>{p.hours}</TableCell>
                    <TableCell><Text font="monospace">{p.cert_id}</Text></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}
      {visible.insights.visible && insights && (
        <div className={mergeClasses(styles.section, reveal.fadeIn)}>
          <Subtitle2>Program Insights (read-only, advisory)</Subtitle2>
          <div className={styles.row}>
            <Badge appearance="tint" color="informative">
              readiness {Math.round(insights.worker_comparison.worker_readiness * 100)}%
            </Badge>
            <Badge appearance="outline">
              cohort mean {Math.round(insights.worker_comparison.cohort_mean_readiness * 100)}%
            </Badge>
            <Badge appearance="tint" color="brand">
              percentile {insights.worker_comparison.percentile}
            </Badge>
            <Badge appearance="outline">
              rank {insights.worker_comparison.rank}/{insights.worker_comparison.n_cohort}
            </Badge>
            <Badge
              appearance="tint"
              color={insights.source === "fabric-live" ? "brand" : "subtle"}
              role="img"
              aria-label={`insights source ${insights.source}`}
            >
              {insights.source}
            </Badge>
          </div>
          {insights.role_cohort.bottleneck_skills.length > 0 && (
            <Body1 block>
              Cohort bottlenecks:{" "}
              {insights.role_cohort.bottleneck_skills
                .map((s) => `${s.name} (${s.gap_count})`)
                .join(", ")}
            </Body1>
          )}
          <Body1 block className={styles.narrative}>
            {insights.narrative}
          </Body1>
        </div>
      )}
    </Card>
  );
}
