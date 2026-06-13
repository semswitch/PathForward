import { useEffect, useMemo, useRef } from "react";
import { ReactFlowProvider } from "@xyflow/react";
import { TourCanvas } from "./TourCanvas";
import { CaptionRail } from "./CaptionRail";
import { ChapterList } from "./ChapterList";
import { TransportBar } from "./TransportBar";
import { CHAPTER_LABELS } from "./script";
import type { TourBeat } from "./script";
import type { TourClock } from "./clock";
import { deriveTourState } from "./deriveTourState";
import { useTour } from "./useTour";

const KEY_OWNING_TAGS = new Set(["INPUT", "BUTTON", "SELECT", "TEXTAREA", "A"]);

interface TourPlayerProps {
  beats: TourBeat[];
  /** Timer clock by default; the narration audio clock in narrated mode. */
  clock?: TourClock;
}

export function TourPlayer({ beats, clock }: TourPlayerProps) {
  const transport = useTour(beats, { clock, autoplay: true });
  const frame = useMemo(
    () => deriveTourState(beats, transport.beatIndex),
    [beats, transport.beatIndex]
  );
  const chapterLabel = CHAPTER_LABELS[frame.chapter];

  const transportRef = useRef(transport);
  useEffect(() => {
    transportRef.current = transport;
  });

  // Page-scoped media keys; form controls and links keep their own key handling.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && (KEY_OWNING_TAGS.has(target.tagName) || target.isContentEditable)) {
        return;
      }
      const current = transportRef.current;
      switch (event.key) {
        case " ":
          event.preventDefault();
          current.toggle();
          break;
        case "ArrowLeft":
          event.preventDefault();
          current.stepBack();
          break;
        case "ArrowRight":
          event.preventDefault();
          current.stepForward();
          break;
        case "Home":
          event.preventDefault();
          current.restart();
          break;
        case "End":
          event.preventDefault();
          current.skipToEnd();
          break;
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <>
      <ReactFlowProvider>
        <div className="relative min-h-0 flex-1">
          <TourCanvas
            nodes={frame.nodes}
            edges={frame.edges}
            camera={frame.camera}
          />
          <ChapterList current={frame.chapter} onJump={transport.jumpToChapter} />
          <CaptionRail caption={frame.caption} chapterLabel={chapterLabel} />
        </div>
      </ReactFlowProvider>
      <TransportBar transport={transport} chapterLabel={chapterLabel} />
    </>
  );
}
