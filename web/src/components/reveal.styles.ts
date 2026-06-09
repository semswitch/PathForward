// Shared replay-reveal styling: fade+rise on newly revealed content, staggered
// delays for the five gate criteria, and the causal-spine highlight pulse.
// All motion is gated behind prefers-reduced-motion; reduced motion gets the
// same pacing with instant state changes.
import { makeStyles, tokens } from "@fluentui/react-components";

const fadeRise = {
  from: { opacity: 0, transform: "translateY(6px)" },
  to: { opacity: 1, transform: "translateY(0)" },
};

const spinePulseFrames = {
  from: { boxShadow: `0 0 0 0 ${tokens.colorBrandStroke1}` },
  to: { boxShadow: "0 0 0 10px transparent" },
};

export const useRevealStyles = makeStyles({
  fadeIn: {
    '@media (prefers-reduced-motion: no-preference)': {
      animationName: fadeRise,
      animationDuration: tokens.durationSlower,
      animationTimingFunction: tokens.curveDecelerateMid,
      animationFillMode: "backwards",
    },
  },
  delay0: {
    '@media (prefers-reduced-motion: no-preference)': { animationDelay: "0ms" },
  },
  delay1: {
    '@media (prefers-reduced-motion: no-preference)': { animationDelay: "150ms" },
  },
  delay2: {
    '@media (prefers-reduced-motion: no-preference)': { animationDelay: "300ms" },
  },
  delay3: {
    '@media (prefers-reduced-motion: no-preference)': { animationDelay: "450ms" },
  },
  delay4: {
    '@media (prefers-reduced-motion: no-preference)': { animationDelay: "600ms" },
  },
  // The causal-spine link: applied simultaneously to the driving-edge row in the
  // Glass-Box table and the credential's cited-edge chip in the Trust Console.
  spineHighlight: {
    backgroundColor: tokens.colorBrandBackground2,
    '@media (prefers-reduced-motion: no-preference)': {
      animationName: spinePulseFrames,
      animationDuration: tokens.durationUltraSlow,
      animationTimingFunction: tokens.curveEasyEase,
      animationIterationCount: "3",
    },
  },
  // A struck attempt stays on screen — rejection is evidence of rigor.
  struck: {
    opacity: 0.6,
  },
  struckStem: {
    textDecorationLine: "line-through",
  },
});

export const CRITERIA_DELAYS = ["delay0", "delay1", "delay2", "delay3", "delay4"] as const;
