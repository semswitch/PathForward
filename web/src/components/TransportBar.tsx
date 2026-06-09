// Replay transport: play/pause/step/restart/skip controls, a chapter scrubber,
// the current narration caption, and the fixture-provenance badge (honesty:
// "offline rehearsal" vs "live foundry replay").
import {
  Badge,
  Button,
  Caption1,
  Tab,
  TabList,
  type SelectTabEventHandler,
} from "@fluentui/react-components";
import {
  ArrowCounterclockwise20Regular,
  FastForward20Filled,
  Next20Filled,
  Pause20Filled,
  Play20Filled,
  Previous20Filled,
} from "@fluentui/react-icons";
import type { Beat, ChapterId } from "../lib/director";
import type { ReplayControls, ReplayState } from "../lib/useReplay";
import { useStyles } from "./TransportBar.styles";

const CHAPTER_LABELS: Record<ChapterId, string> = {
  graph: "Glass Box",
  curator: "Curator",
  loop: "The Loop",
  decision: "Mint",
  plan: "Plan",
  trust: "Trust",
};

export interface TransportBarProps {
  replay: ReplayState & ReplayControls;
  beats: Beat[];
  provenanceMode: string;
}

function provenanceBadge(mode: string) {
  if (mode === "offline-rehearsal") {
    return (
      <Badge appearance="tint" color="warning" role="img" aria-label="provenance: offline rehearsal">
        offline rehearsal
      </Badge>
    );
  }
  if (mode === "live-foundry") {
    return (
      <Badge appearance="tint" color="brand" role="img" aria-label="provenance: live foundry replay">
        live foundry replay
      </Badge>
    );
  }
  return (
    <Badge appearance="tint" color="subtle" role="img" aria-label={`provenance: ${mode}`}>
      {mode}
    </Badge>
  );
}

export function TransportBar({ replay, beats, provenanceMode }: TransportBarProps) {
  const styles = useStyles();
  const chapters = beats.reduce<ChapterId[]>(
    (acc, b) => (acc.includes(b.chapter) ? acc : [...acc, b.chapter]),
    [],
  );
  const currentChapter = replay.beat?.chapter ?? chapters[0];

  const onTabSelect: SelectTabEventHandler = (_e, data) => {
    const chapter = data.value as ChapterId;
    const first = beats.findIndex((b) => b.chapter === chapter);
    if (first >= 0) replay.jumpTo(first);
  };

  const onPlayPause = () => {
    if (replay.atEnd && !replay.playing) {
      replay.restart();
      replay.play();
      return;
    }
    replay.toggle();
  };

  return (
    <div className={styles.bar}>
      <div className={styles.buttons}>
        <Button
          appearance="subtle"
          icon={<ArrowCounterclockwise20Regular />}
          aria-label="restart replay"
          onClick={replay.restart}
        />
        <Button
          appearance="subtle"
          icon={<Previous20Filled />}
          aria-label="previous beat"
          onClick={replay.stepBack}
        />
        <Button
          appearance="primary"
          icon={replay.playing ? <Pause20Filled /> : <Play20Filled />}
          aria-label={replay.playing ? "pause replay" : "play replay"}
          onClick={onPlayPause}
        />
        <Button
          appearance="subtle"
          icon={<Next20Filled />}
          aria-label="next beat"
          onClick={replay.stepForward}
        />
        <Button
          appearance="subtle"
          icon={<FastForward20Filled />}
          aria-label="skip to end"
          onClick={replay.skipToEnd}
        />
      </div>
      <TabList
        selectedValue={currentChapter}
        onTabSelect={onTabSelect}
        size="small"
        aria-label="replay chapters"
      >
        {chapters.map((c) => (
          <Tab key={c} value={c} aria-label={`chapter: ${CHAPTER_LABELS[c]}`}>
            {CHAPTER_LABELS[c]}
          </Tab>
        ))}
      </TabList>
      <Caption1 className={styles.caption} aria-hidden>
        {replay.beat ? `${replay.beatIndex + 1}/${beats.length} · ${replay.beat.caption}` : ""}
      </Caption1>
      <div className={styles.provenance}>{provenanceBadge(provenanceMode)}</div>
    </div>
  );
}
