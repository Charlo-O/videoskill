import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import {SCENES, TOTAL_FRAMES} from "../audio-config";
import {promoMeta, pptScenes, renderedSlides} from "../promo-data";
import {PptDomSceneView} from "./PptDomScene";

const clamp = {
  extrapolateLeft: "clamp" as const,
  extrapolateRight: "clamp" as const,
};

const SceneAudio: React.FC<{audioFile: string | null}> = ({audioFile}) => {
  if (!audioFile) {
    return null;
  }

  return <Audio src={staticFile(audioFile)} />;
};

const buildSceneRanges = () => {
  let cursor = 0;
  return SCENES.map((scene) => {
    const range = {
      from: cursor,
      to: cursor + scene.durationInFrames,
      hasVoiceover: Boolean(scene.audioFile),
    };
    cursor += scene.durationInFrames;
    return range;
  });
};

const sceneRanges = buildSceneRanges();

const getDuckingFactor = (frame: number) => {
  return sceneRanges.reduce((lowestFactor, scene) => {
    if (!scene.hasVoiceover) {
      return lowestFactor;
    }

    const attack = interpolate(frame, [scene.from - 12, scene.from + 12], [1, 0.32], clamp);
    const release = interpolate(frame, [scene.to - 18, scene.to + 18], [0.32, 1], clamp);
    return Math.min(lowestFactor, attack, release);
  }, 1);
};

const getBackgroundMusicVolume = (frame: number) => {
  const baseVolume = promoMeta.backgroundMusic.volume;
  const fadeIn = interpolate(frame, [0, 24], [0, baseVolume], clamp);
  const fadeOut = interpolate(
    frame,
    [Math.max(TOTAL_FRAMES - 36, 0), TOTAL_FRAMES],
    [baseVolume, 0],
    clamp,
  );
  return Math.min(fadeIn, fadeOut) * getDuckingFactor(frame);
};

type RenderedSlideSceneProps = {
  src: string;
  durationInFrames: number;
  transition?: "fade" | "cut" | "push";
};

const RenderedSlideScene: React.FC<RenderedSlideSceneProps> = ({
  src,
  durationInFrames,
  transition = "fade",
}) => {
  const frame = useCurrentFrame();
  const fadeOpacity =
    transition === "cut"
      ? 1
      : interpolate(
          frame,
          [0, 10, Math.max(durationInFrames - 10, 10), durationInFrames],
          [0, 1, 1, 0],
          clamp,
        );
  const pushX =
    transition === "push"
      ? interpolate(frame, [0, 18], [28, 0], clamp)
      : 0;
  const scale = interpolate(frame, [0, durationInFrames], [1.012, 1], clamp);

  return (
    <AbsoluteFill style={{background: promoMeta.background}}>
      <AbsoluteFill
        style={{
          opacity: fadeOpacity,
          transform: `translateX(${pushX}px) scale(${scale})`,
          transformOrigin: "center center",
        }}
      >
        <Img
          src={staticFile(src.replace(/^\/+/, ""))}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
          }}
        />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const buildOffsets = () => {
  return SCENES.reduce<number[]>((offsets, scene, index) => {
    if (index === 0) {
      offsets.push(0);
      return offsets;
    }

    offsets.push(offsets[index - 1] + SCENES[index - 1].durationInFrames);
    return offsets;
  }, []);
};

const offsets = buildOffsets();

export const ProductPromo: React.FC = () => {
  return (
    <AbsoluteFill style={{background: promoMeta.background}}>
      {promoMeta.backgroundMusic.file ? (
        <Audio
          src={staticFile(promoMeta.backgroundMusic.file)}
          volume={getBackgroundMusicVolume}
        />
      ) : null}

      {SCENES.map((scene, index) => {
        const slide = renderedSlides[index] ?? renderedSlides[renderedSlides.length - 1];
        if (!slide) {
          return null;
        }

        const pptScene = pptScenes[index];
        const usePptDom = promoMeta.renderMode === "ppt-dom" && pptScene?.html;

        return (
          <Sequence
            key={scene.id}
            from={offsets[index]}
            durationInFrames={scene.durationInFrames}
          >
            <>
              {usePptDom ? (
                <PptDomSceneView
                  html={pptScene.html}
                  durationInFrames={scene.durationInFrames}
                  beats={scene.beats}
                  motionUnits={scene.motionUnits}
                  transition={slide.transition}
                  background={promoMeta.background}
                />
              ) : (
                <RenderedSlideScene
                  src={slide.src}
                  durationInFrames={scene.durationInFrames}
                  transition={slide.transition}
                />
              )}
              <SceneAudio audioFile={scene.audioFile} />
            </>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
