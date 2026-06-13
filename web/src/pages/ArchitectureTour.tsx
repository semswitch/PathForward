import { useEffect, useMemo, useRef } from "react";
import { ReactFlowProvider } from "@xyflow/react";
import { TourCanvas } from "../tour/TourCanvas";
import { CaptionRail } from "../tour/CaptionRail";
import { ChapterList } from "../tour/ChapterList";
import { TransportBar } from "../tour/TransportBar";
import { buildTourScript, CHAPTER_LABELS } from "../tour/script";
import { deriveTourState } from "../tour/deriveTourState";
import { useTour } from "../tour/useTour";

const KEY_OWNING_TAGS = new Set(["INPUT", "BUTTON", "SELECT", "TEXTAREA", "A"]);

export function ArchitectureTour() {
  const beats = useMemo(() => buildTourScript(), []);
  const transport = useTour(beats, { autoplay: true });
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
    <div
      data-theme="dark"
      className="flex h-full min-h-0 flex-1 flex-col bg-surface text-ink"
    >
      <p className="sr-only">
        Architecture tour player. Space plays or pauses, left and right arrows
        step between beats, Home restarts, End skips to the finished state.
      </p>
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
    </div>
  );
}
