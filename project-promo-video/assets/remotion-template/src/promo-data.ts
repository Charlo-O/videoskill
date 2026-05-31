export const FPS = 30;

export type RenderedSlide = {
  id: string;
  layoutId: string;
  src: string;
  title: string;
  subtitle?: string;
  durationInFrames: number;
  transition?: "fade" | "cut" | "push";
};

export type PptScene = RenderedSlide & {
  html: string;
};

export const promoMeta = {
  projectName: "Project Name",
  tagline: "A clear one-line promise for the product.",
  closingLine: "Show the product in motion and end on a clear promise.",
  accent: "#14b8a6",
  background: "#081226",
  layoutStyle: "editorial",
  renderMode: "ppt-dom" as "ppt-dom" | "slides",
  backgroundMusic: {
    file: null as string | null,
    volume: 0.18,
  },
};

export const renderedSlides: RenderedSlide[] = [
  {
    id: "cover",
    layoutId: "A01",
    src: "slides/001-cover.png",
    title: "Open Strong",
    subtitle: "Generated from the PPT layout renderer.",
    durationInFrames: 90,
    transition: "fade",
  },
  {
    id: "proof",
    layoutId: "A04",
    src: "slides/002-proof.png",
    title: "Show The Core Flow",
    subtitle: "Use a PPT layout instead of a free-form video card.",
    durationInFrames: 90,
    transition: "push",
  },
  {
    id: "closing",
    layoutId: "A07",
    src: "slides/003-closing.png",
    title: "End On Proof",
    subtitle: "Close with the same layout language as the deck.",
    durationInFrames: 90,
    transition: "fade",
  },
];

export const pptScenes: PptScene[] = renderedSlides.map((slide) => ({
  ...slide,
  html: `<section class="slide light" data-layout="${slide.layoutId}" data-scene-id="${slide.id}" data-title="${slide.title}"><div class="frame"><h1 data-anim>${slide.title}</h1><p data-anim>${slide.subtitle ?? ""}</p></div></section>`,
}));
