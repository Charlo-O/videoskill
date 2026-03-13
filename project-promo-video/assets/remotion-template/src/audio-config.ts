import {INTRO_FRAMES, OUTRO_FRAMES, shots} from "./promo-data";

export interface SceneConfig {
  id: string;
  title: string;
  durationInFrames: number;
  audioFile: string | null;
}

export const SCENES: SceneConfig[] = [
  {
    id: "intro",
    title: "Intro",
    durationInFrames: INTRO_FRAMES,
    audioFile: null,
  },
  ...shots.map((shot) => ({
    id: "shot-" + shot.id,
    title: shot.title,
    durationInFrames: shot.durationInFrames,
    audioFile: null,
  })),
  {
    id: "outro",
    title: "Outro",
    durationInFrames: OUTRO_FRAMES,
    audioFile: null,
  },
];

export const TOTAL_FRAMES = SCENES.reduce(
  (sum, scene) => sum + scene.durationInFrames,
  0,
);

export const FPS = 30;
