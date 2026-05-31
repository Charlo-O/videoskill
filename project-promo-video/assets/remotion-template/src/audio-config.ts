import {renderedSlides} from "./promo-data";

export interface BeatConfig {
  id: string;
  text: string;
  target: string;
  motion: string;
  startFrame: number;
  durationInFrames: number;
}

export interface MotionUnitConfig {
  id: string;
  kind: string;
  group: string;
  motion: string;
  text?: string;
  beatId?: string;
  startFrame: number;
  durationInFrames: number;
}

export interface SceneConfig {
  id: string;
  title: string;
  durationInFrames: number;
  audioFile: string | null;
  beats: BeatConfig[];
  motionUnits: MotionUnitConfig[];
}

export const SCENES: SceneConfig[] = renderedSlides.map((slide) => ({
  id: slide.id,
  title: slide.title,
  durationInFrames: slide.durationInFrames,
  audioFile: null,
  beats: [
    {
      id: `${slide.id}-beat-1`,
      text: slide.title,
      target: "title",
      motion: "title-reveal",
      startFrame: 0,
      durationInFrames: Math.max(18, Math.round(slide.durationInFrames * 0.34)),
    },
    {
      id: `${slide.id}-beat-2`,
      text: slide.subtitle ?? "",
      target: "body",
      motion: "content-follow",
      startFrame: Math.max(18, Math.round(slide.durationInFrames * 0.34)),
      durationInFrames: Math.max(18, slide.durationInFrames - Math.max(18, Math.round(slide.durationInFrames * 0.34))),
    },
  ],
  motionUnits: [],
}));

export const TOTAL_FRAMES = SCENES.reduce(
  (sum, scene) => sum + scene.durationInFrames,
  0,
);

export const FPS = 30;
