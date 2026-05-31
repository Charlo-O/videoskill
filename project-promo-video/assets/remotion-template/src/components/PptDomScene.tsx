import React, {useMemo} from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import "../ppt-template.css";
import "../ppt-video-motion.css";

const clamp = {
  extrapolateLeft: "clamp" as const,
  extrapolateRight: "clamp" as const,
};

type Transition = "fade" | "cut" | "push";

export type BeatConfig = {
  id: string;
  text: string;
  target: string;
  motion: string;
  startFrame: number;
  durationInFrames: number;
};

export type MotionUnitConfig = {
  id: string;
  kind: string;
  group: string;
  motion: string;
  text?: string;
  beatId?: string;
  startFrame: number;
  durationInFrames: number;
};

type EnhancedHtml = {
  html: string;
};

const targetAliases: Record<string, string[]> = {
  title: ["title", "headline", "hook", "left", "split-left"],
  body: ["body", "copy", "lead", "caption", "voice", "audio", "right", "split-right"],
  image: ["image", "screen", "visual", "proof"],
  cards: ["cards", "card", "matrix", "system"],
  diagram: ["diagram", "svg", "dom"],
  kpi: ["kpi", "metric", "spec", "proof"],
  bars: ["bar", "chart", "growth"],
  line: ["line", "rule", "closing"],
};

const selectorsByTarget: Record<string, string[]> = {
  title: [
    '[data-anim="title"]',
    '[data-anim="line"] h2',
    '[data-anim="title-block"]',
    '[data-anim="left"]',
    ".h-hero",
  ],
  body: [
    '[data-anim="bottom"]',
    '[data-anim="right"]',
    '[data-anim="kpi"] > div:first-child',
    ".lead",
    ".body",
    ".body-sm",
  ],
  image: [
    '[data-anim="img"] img',
    ".frame-img img",
  ],
  cards: [
    ".sub-card",
    ".card-fill",
    ".card-accent",
    ".card-ink",
  ],
  diagram: [
    "svg circle",
    "svg path",
    "svg line",
  ],
  kpi: [
    ".image-hero-stats > div",
    ".kpi-cell",
    ".kpi-num",
  ],
  bars: [
    ".row-fill",
    ".bar-tower .body-block",
    '[data-anim="bars"] .vbar',
  ],
  line: [
    '[data-anim="line"] .rule',
    ".hr-hairline",
    ".canvas-card::after",
  ],
};

const round = (value: number, digits = 3) => Number(value.toFixed(digits));
const clamp01 = (value: number) => Math.max(0, Math.min(1, value));

const delayedSpring = (
  frame: number,
  fps: number,
  delay: number,
  config = {damping: 18, mass: 0.7, stiffness: 120},
) => {
  if (frame <= delay) {
    return 0;
  }

  return clamp01(
    spring({
      frame: frame - delay,
      fps,
      config,
    }),
  );
};

const delayedEase = (frame: number, start: number, duration: number) => {
  const raw = interpolate(frame, [start, start + Math.max(1, duration)], [0, 1], clamp);
  return 1 - Math.pow(1 - clamp01(raw), 3);
};

const prepareHtml = (html: string): EnhancedHtml => {
  const withStaticAssets = html.replace(
    /\b(src|href)=(["'])\/?(ppt\/[^"']+)\2/g,
    (_match, attr: string, quote: string, assetPath: string) => {
      return `${attr}=${quote}${staticFile(assetPath)}${quote}`;
    },
  );

  return {html: withStaticAssets};
};

const fallbackBeats = (durationInFrames: number): BeatConfig[] => [
  {
    id: "fallback-title",
    text: "Title",
    target: "title",
    motion: "title-reveal",
    startFrame: 0,
    durationInFrames: Math.max(18, Math.round(durationInFrames * 0.35)),
  },
  {
    id: "fallback-body",
    text: "Content",
    target: "body",
    motion: "content-follow",
    startFrame: Math.max(18, Math.round(durationInFrames * 0.35)),
    durationInFrames: Math.max(18, durationInFrames - Math.max(18, Math.round(durationInFrames * 0.35))),
  },
];

const normalizeBeats = (beats: BeatConfig[] | undefined, durationInFrames: number) => {
  const usable = beats?.length ? beats : fallbackBeats(durationInFrames);
  return usable.map((beat, index) => ({
    ...beat,
    id: beat.id || `beat-${index + 1}`,
    target: beat.target || "body",
    motion: beat.motion || "content-follow",
    startFrame: Number.isFinite(beat.startFrame) ? beat.startFrame : 0,
    durationInFrames: Math.max(1, beat.durationInFrames || durationInFrames),
  }));
};

const targetMatches = (beatTarget: string, target: string) => {
  const normalized = beatTarget.toLowerCase();
  return (targetAliases[target] ?? [target]).some((alias) => normalized.includes(alias));
};

const beatForTarget = (beats: BeatConfig[], target: string, fallbackIndex: number) => {
  return (
    beats.find((beat) => targetMatches(beat.target, target) || targetMatches(beat.motion, target)) ??
    beats[Math.min(fallbackIndex, beats.length - 1)] ??
    beats[0]
  );
};

const activeBeatIndex = (beats: BeatConfig[], frame: number) => {
  const index = beats.findIndex((beat) => {
    return frame >= beat.startFrame && frame < beat.startFrame + beat.durationInFrames;
  });
  if (index !== -1) {
    return index;
  }
  return frame < 0 ? 0 : beats.length - 1;
};

const beatRevealProgress = (
  frame: number,
  fps: number,
  beat: BeatConfig,
  partDelay = 0,
) => {
  const revealFrames = Math.min(72, Math.max(18, Math.round(beat.durationInFrames * 0.55)));
  return delayedSpring(frame, fps, beat.startFrame + partDelay, {
    damping: 19,
    mass: 0.78,
    stiffness: 112,
  }) * delayedEase(frame, beat.startFrame + partDelay, revealFrames);
};

const transformRule = (selector: string, progress: number, y = 18, scaleFrom = 0.985) => {
  const opacity = round(progress);
  const translateY = round((1 - progress) * y, 2);
  const scale = round(scaleFrom + (1 - scaleFrom) * progress, 4);
  return `${selector}{opacity:${opacity};transform:translate3d(0,${translateY}px,0) scale(${scale});}`;
};

const scaleXRule = (selector: string, progress: number) => {
  return `${selector}{opacity:${round(progress)};transform-origin:left center;transform:scaleX(${round(progress, 4)});}`;
};

const scaleYRule = (selector: string, progress: number) => {
  return `${selector}{opacity:${round(progress)};transform-origin:bottom center;transform:scaleY(${round(progress, 4)});}`;
};

const selectorRules = (
  selectors: string[],
  progress: number,
  y = 18,
  scaleFrom = 0.985,
) => {
  return selectors
    .map((selector) => transformRule(`.ppt-dom-scene ${selector}`, progress, y, scaleFrom))
    .join("\n");
};

const nthRules = (
  selector: string,
  frame: number,
  fps: number,
  count: number,
  beat: BeatConfig,
  stagger: number,
  y = 18,
) => {
  const rules: string[] = [];
  for (let index = 1; index <= count; index += 1) {
    const progress = beatRevealProgress(frame, fps, beat, (index - 1) * stagger);
    rules.push(transformRule(`${selector}:nth-child(${index})`, progress, y, 0.97));
  }
  return rules.join("\n");
};

const unitSelector = (id: string) => `.ppt-dom-scene [data-motion-id="${id}"]`;

const unitProgress = (frame: number, fps: number, unit: MotionUnitConfig) => {
  const start = Number.isFinite(unit.startFrame) ? unit.startFrame : 0;
  const duration = Math.max(1, unit.durationInFrames || 18);
  const springProgress = delayedSpring(frame, fps, start, {
    damping: 17,
    mass: 0.72,
    stiffness: unit.kind.startsWith("text-char") ? 150 : 116,
  });
  return springProgress * delayedEase(frame, start, Math.min(60, Math.max(8, duration)));
};

const unitRule = (
  unit: MotionUnitConfig,
  progress: number,
  frame: number,
) => {
  const selector = unitSelector(unit.id);
  const kind = unit.kind || "container";
  const group = unit.group || "body";
  const motion = unit.motion || "";
  const opacity = round(progress);

  if (kind === "line" || group === "line" || motion.includes("rule")) {
    return `${selector}{opacity:${opacity};transform-origin:left center;transform:scaleX(${round(progress, 4)});}`;
  }

  if (kind === "bar" || group === "bars" || motion.includes("bar")) {
    return `${selector}{opacity:${opacity};transform-origin:bottom center;transform:scaleY(${round(progress, 4)});}`;
  }

  if (kind === "container" && group === "image") {
    const scale = round(0.992 + progress * 0.008, 4);
    return `${selector}{opacity:1;transform:scale(${scale});}`;
  }

  if (kind === "image" || group === "image") {
    const drift = round((1 - progress) * 18 - 4 * Math.sin(frame / 24), 2);
    const scale = round(1.075 - progress * 0.045, 4);
    return `${selector}{opacity:${opacity};clip-path:inset(${round((1 - progress) * 9, 2)}%);transform:translate3d(0,${drift}px,0) scale(${scale});}`;
  }

  if (kind === "shape" || group === "diagram") {
    const scale = round(0.68 + progress * 0.32, 4);
    return `${selector}{opacity:${opacity};transform-box:fill-box;transform-origin:center;transform:scale(${scale});}`;
  }

  if (kind === "kpi" || group === "kpi") {
    const y = round((1 - progress) * 14, 2);
    const scale = round(0.9 + progress * 0.1, 4);
    return `${selector}{opacity:${opacity};transform:translate3d(0,${y}px,0) scale(${scale});}`;
  }

  if (kind === "card" || group === "cards") {
    const y = round((1 - progress) * 24, 2);
    const scale = round(0.94 + progress * 0.06, 4);
    return `${selector}{opacity:${opacity};transform:translate3d(0,${y}px,0) scale(${scale});}`;
  }

  if (kind.startsWith("text-char")) {
    const y = round((1 - progress) * 0.42, 3);
    const rotate = round((1 - progress) * 3.5, 3);
    return `${selector}{opacity:${opacity};transform:translate3d(0,${y}em,0) rotate(${rotate}deg);}`;
  }

  if (kind.startsWith("text")) {
    const y = round((1 - progress) * 0.28, 3);
    return `${selector}{opacity:${opacity};transform:translate3d(0,${y}em,0);}`;
  }

  const y = round((1 - progress) * 16, 2);
  const scale = round(0.98 + progress * 0.02, 4);
  return `${selector}{opacity:${opacity};transform:translate3d(0,${y}px,0) scale(${scale});}`;
};

const motionUnitRules = (
  units: MotionUnitConfig[],
  frame: number,
  fps: number,
) => {
  if (!units.length) {
    return "";
  }

  return units
    .map((unit) => unitRule(unit, unitProgress(frame, fps, unit), frame))
    .join("\n");
};

const buildMotionCss = ({
  frame,
  fps,
  durationInFrames,
  beats: rawBeats,
  motionUnits = [],
}: {
  frame: number;
  fps: number;
  durationInFrames: number;
  beats?: BeatConfig[];
  motionUnits?: MotionUnitConfig[];
}) => {
  const beats = normalizeBeats(rawBeats, durationInFrames);
  const rules: string[] = [];
  const activeIndex = activeBeatIndex(beats, frame);
  const activeBeat = beats[activeIndex] ?? beats[0];
  const activeProgress = activeBeat
    ? delayedEase(frame, activeBeat.startFrame, activeBeat.durationInFrames)
    : 0;
  const imageBeat = beatForTarget(beats, "image", 1);
  const titleBeat = beatForTarget(beats, "title", 0);
  const bodyBeat = beatForTarget(beats, "body", Math.min(1, beats.length - 1));
  const cardsBeat = beatForTarget(beats, "cards", Math.min(2, beats.length - 1));
  const diagramBeat = beatForTarget(beats, "diagram", Math.min(1, beats.length - 1));
  const kpiBeat = beatForTarget(beats, "kpi", Math.min(2, beats.length - 1));
  const barsBeat = beatForTarget(beats, "bars", Math.min(3, beats.length - 1));
  const lineBeat = beatForTarget(beats, "line", Math.min(1, beats.length - 1));

  if (motionUnits.length) {
    rules.push(motionUnitRules(motionUnits, frame, fps));
  } else {
    const imageProgress = beatRevealProgress(frame, fps, imageBeat);
    const drift = round(
      interpolate(frame, [imageBeat.startFrame, imageBeat.startFrame + imageBeat.durationInFrames], [8, -12], clamp),
      2,
    );
    const imageScale = round(1.065 - imageProgress * 0.038, 4);
    rules.push(`
.ppt-dom-scene .frame-img img,
.ppt-dom-scene [data-anim="img"] img{
  opacity:${round(imageProgress)};
  transform:translate3d(0,${drift}px,0) scale(${imageScale});
}
.ppt-dom-scene [data-anim="title-block"]{
  transform-origin:left center;
}
`);

    rules.push(selectorRules(selectorsByTarget.title, beatRevealProgress(frame, fps, titleBeat), 22, 0.975));
    rules.push(selectorRules(selectorsByTarget.body, beatRevealProgress(frame, fps, bodyBeat), 16, 0.99));
    rules.push(selectorRules(selectorsByTarget.cards, beatRevealProgress(frame, fps, cardsBeat), 20, 0.965));
    rules.push(selectorRules(selectorsByTarget.kpi, beatRevealProgress(frame, fps, kpiBeat), 14, 0.98));
    rules.push(selectorRules(selectorsByTarget.diagram, beatRevealProgress(frame, fps, diagramBeat), 0, 0.88));

    const lineProgress = beatRevealProgress(frame, fps, lineBeat);
    rules.push(scaleXRule('.ppt-dom-scene [data-anim="line"] .rule', lineProgress));
    rules.push(scaleXRule(".ppt-dom-scene .hr-hairline", lineProgress));
    rules.push(scaleXRule(".ppt-dom-scene .row-fill", beatRevealProgress(frame, fps, barsBeat)));
    rules.push(scaleYRule(".ppt-dom-scene .bar-tower .body-block", beatRevealProgress(frame, fps, barsBeat)));
    rules.push(scaleYRule('.ppt-dom-scene [data-anim="bars"] .vbar', beatRevealProgress(frame, fps, barsBeat)));

    rules.push(
      nthRules(".ppt-dom-scene .sub-card", frame, fps, 18, cardsBeat, 7, 22),
      nthRules(".ppt-dom-scene .card-fill", frame, fps, 18, cardsBeat, 7, 20),
      nthRules(".ppt-dom-scene .kpi-cell", frame, fps, 12, kpiBeat, 7, 12),
      nthRules(".ppt-dom-scene .timeline-h .th-node", frame, fps, 8, lineBeat, 8, 14),
      nthRules(".ppt-dom-scene .ledger-row", frame, fps, 8, kpiBeat, 8, 18),
      nthRules('.ppt-dom-scene [data-anim="up"] > *', frame, fps, 18, bodyBeat, 7, 16),
    );

    const svgProgress = beatRevealProgress(frame, fps, diagramBeat);
    rules.push(`
.ppt-dom-scene svg circle,
.ppt-dom-scene svg path,
.ppt-dom-scene svg line{
  opacity:${round(svgProgress)};
  transform-box:fill-box;
  transform-origin:center;
}
.ppt-dom-scene svg circle{
  transform:scale(${round(0.65 + svgProgress * 0.35, 4)});
}
`);
  }

  const sweepX = round(interpolate(activeProgress, [0, 1], [-120, 120], clamp), 2);
  const pulse = round(0.18 + Math.sin(frame / 11) * 0.035, 3);
  rules.push(`
.ppt-dom-scene .canvas-card::before{
  opacity:${round(0.05 + activeProgress * 0.12)};
  transform:translate3d(${sweepX}%,0,0);
}
.ppt-dom-scene .canvas-card::after{
  opacity:${pulse};
  transform:scaleX(${round(0.2 + activeProgress * 0.8, 4)});
}
`);

  return rules.join("\n");
};

export const PptDomSceneView: React.FC<{
  html: string;
  durationInFrames: number;
  transition?: Transition;
  background: string;
  beats?: BeatConfig[];
  motionUnits?: MotionUnitConfig[];
}> = ({html, durationInFrames, transition = "fade", background, beats, motionUnits}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enhanced = useMemo(() => prepareHtml(html), [html]);
  const motionCss = buildMotionCss({
    frame,
    fps,
    durationInFrames,
    beats,
    motionUnits,
  });

  const fadeOpacity =
    transition === "cut"
      ? 1
      : interpolate(
          frame,
          [0, 8, Math.max(durationInFrames - 12, 12), durationInFrames],
          [0, 1, 1, 0],
          clamp,
        );
  const pushX =
    transition === "push"
      ? interpolate(frame, [0, 18], [46, 0], clamp)
      : 0;

  return (
    <AbsoluteFill style={{background}}>
      <AbsoluteFill
        style={{
          opacity: fadeOpacity,
          transform: `translate3d(${pushX}px,0,0)`,
        }}
      >
        <div className="ppt-dom-scene">
          <style>{motionCss}</style>
          <div
            className="ppt-dom-html"
            dangerouslySetInnerHTML={{__html: enhanced.html}}
          />
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
