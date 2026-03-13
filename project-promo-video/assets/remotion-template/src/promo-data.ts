export const FPS = 30;
export const INTRO_FRAMES = 60;
export const OUTRO_FRAMES = 60;

export type PromoShot = {
  id: string;
  src: string;
  title: string;
  subtitle: string;
  durationInFrames: number;
  align?: "left" | "center" | "right";
};

export const promoMeta = {
  projectName: "Project Name",
  tagline: "A clear one-line promise for the product.",
  closingLine: "Show the product in motion and end on a clear promise.",
  accent: "#14b8a6",
  background: "#081226",
  backgroundMusic: {
    file: null as string | null,
    volume: 0.18,
  },
};

export const shots: PromoShot[] = [
  {
    id: "home",
    src: "screenshots/01-home.png",
    title: "Open Strong",
    subtitle: "Show the most recognizable or persuasive screen first.",
    durationInFrames: 90,
    align: "left",
  },
  {
    id: "workflow",
    src: "screenshots/02-workflow.png",
    title: "Show The Core Flow",
    subtitle: "Use the second beat to explain the main user action.",
    durationInFrames: 90,
    align: "center",
  },
  {
    id: "results",
    src: "screenshots/03-results.png",
    title: "End On Proof",
    subtitle: "Close the trailer with a result, payoff, or clear CTA.",
    durationInFrames: 90,
    align: "right",
  },
];
