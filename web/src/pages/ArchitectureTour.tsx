import { useEffect, useMemo, useRef, useState } from "react";
import { ReactFlowProvider } from "@xyflow/react";
import { TourCanvas } from "../tour/TourCanvas";
import { TourPlayer } from "../tour/TourPlayer";
import { buildTourScript } from "../tour/script";
import { deriveTourState } from "../tour/deriveTourState";
import { createAudioClock } from "../tour/audioClock";
import type { NarrationManifest } from "../tour/retimeBeats";
import { retimeBeats } from "../tour/retimeBeats";
import manifestJson from "../tour/narration.manifest.json";

const AUDIO_SRC = `${import.meta.env.BASE_URL}narration/tour.mp3`;
const manifest = manifestJson as NarrationManifest;

/**
 * Browsers block audible autoplay without a user gesture, so the tour opens
 * on a start overlay; the click is the gesture that unlocks narration.
 * Narrated mode requires the manifest to match the authored script (see
 * retimeBeats) — otherwise, and on any audio load error, the tour runs the
 * authored silent timings instead of desyncing.
 */
type TourMode = "idle" | "narrated" | "silent";

export function ArchitectureTour() {
  const authored = useMemo(() => buildTourScript(), []);
  const narration = useMemo(() => retimeBeats(authored, manifest), [authored]);
  const [mode, setMode] = useState<TourMode>("idle");
  const [audioAvailable, setAudioAvailable] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // The mastered mix is produced separately from the manifest — only claim
  // narration once the file is really servable (dev servers SPA-fallback
  // unknown paths to HTML, hence the content-type check, not just .ok).
  useEffect(() => {
    if (!narration.matched) return;
    let cancelled = false;
    fetch(AUDIO_SRC, { method: "HEAD" })
      .then((response) => {
        const type = response.headers.get("content-type") ?? "";
        if (!cancelled && response.ok && type.startsWith("audio")) {
          setAudioAvailable(true);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [narration.matched]);

  const narrated = narration.matched && audioAvailable;

  const start = () => {
    if (!narrated) {
      setMode("silent");
      return;
    }
    const audio = new Audio(AUDIO_SRC);
    audio.preload = "auto";
    audio.addEventListener("error", () => {
      audioRef.current = null;
      setMode("silent");
    });
    audioRef.current = audio;
    setMode("narrated");
  };

  const introFrame = useMemo(
    () => deriveTourState(authored, 0),
    [authored]
  );

  return (
    <div
      data-theme="dark"
      className="flex h-full min-h-0 flex-1 flex-col bg-surface text-ink"
    >
      <p className="sr-only">
        Architecture tour player. Space plays or pauses, left and right arrows
        step between beats, Home restarts, End skips to the finished state.
      </p>
      {mode === "idle" ? (
        <ReactFlowProvider>
          <div className="relative min-h-0 flex-1">
            <TourCanvas
              nodes={introFrame.nodes}
              edges={introFrame.edges}
              camera={null}
            />
            <div className="absolute inset-0 z-20 flex items-center justify-center bg-surface/60">
              <div className="flex max-w-md flex-col items-center gap-4 rounded-2xl border border-line bg-surface-raised px-10 py-8 text-center shadow-2xl">
                <p className="font-mono text-[10px] tracking-widest text-brand-300 uppercase">
                  Architecture Tour
                </p>
                <h1 className="text-2xl font-semibold tracking-tight">
                  Watch the real flow think
                </h1>
                <p className="text-sm text-ink-muted">
                  A guided replay of one worker's live run — every node carries
                  its real runtime name.
                </p>
                <button
                  type="button"
                  onClick={start}
                  className="rounded-full bg-brand-500 px-6 py-2.5 font-medium text-white transition-colors hover:bg-brand-400"
                >
                  ▶ Start the tour
                </button>
                <p className="text-xs text-ink-muted">
                  {narrated
                    ? "Plays with narration — about 5 minutes."
                    : "Plays silently with captions — about 3 minutes."}
                </p>
              </div>
            </div>
          </div>
        </ReactFlowProvider>
      ) : (
        <TourPlayer
          key={mode}
          beats={mode === "narrated" ? narration.beats : authored}
          clock={
            mode === "narrated" && audioRef.current
              ? createAudioClock(audioRef.current)
              : undefined
          }
        />
      )}
    </div>
  );
}
