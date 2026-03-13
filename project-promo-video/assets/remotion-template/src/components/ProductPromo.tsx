import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {SCENES, TOTAL_FRAMES} from "../audio-config";
import {PromoShot, promoMeta, shots} from "../promo-data";

const clamp = {
  extrapolateLeft: "clamp" as const,
  extrapolateRight: "clamp" as const,
};

const justifyByAlign: Record<
  "left" | "center" | "right",
  "flex-start" | "center" | "flex-end"
> = {
  left: "flex-start",
  center: "center",
  right: "flex-end",
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

const IntroScene: React.FC<{durationInFrames: number}> = ({durationInFrames}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const settle = spring({fps, frame, config: {damping: 18, mass: 0.9}});
  const opacity = interpolate(
    frame,
    [0, 12, durationInFrames - 12, durationInFrames],
    [0, 1, 1, 0],
    clamp,
  );
  const accentWidth = interpolate(frame, [0, 24], [0, 240], clamp);

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(circle at top left, ${promoMeta.accent}33 0%, transparent 35%), linear-gradient(135deg, ${promoMeta.background} 0%, #050a15 100%)`,
        color: "white",
        justifyContent: "center",
        padding: "120px",
      }}
    >
      <div
        style={{
          maxWidth: 1200,
          opacity,
          transform: `translateY(${48 - settle * 48}px) scale(${0.94 + settle * 0.06})`,
        }}
      >
        <div
          style={{
            fontSize: 20,
            letterSpacing: 6,
            textTransform: "uppercase",
            color: "#dbe7ff",
            marginBottom: 24,
          }}
        >
          Product Trailer
        </div>
        <div
          style={{
            width: accentWidth,
            height: 6,
            borderRadius: 999,
            background: promoMeta.accent,
            marginBottom: 28,
            boxShadow: `0 0 32px ${promoMeta.accent}88`,
          }}
        />
        <h1
          style={{
            fontSize: 112,
            lineHeight: 1,
            margin: 0,
            fontWeight: 800,
            letterSpacing: -4,
          }}
        >
          {promoMeta.projectName}
        </h1>
        <p
          style={{
            fontSize: 34,
            lineHeight: 1.35,
            maxWidth: 960,
            marginTop: 28,
            marginBottom: 0,
            color: "#d0d9e9",
          }}
        >
          {promoMeta.tagline}
        </p>
      </div>
    </AbsoluteFill>
  );
};

type ShotSceneProps = {
  shot: PromoShot;
  durationInFrames: number;
  index: number;
  totalShots: number;
};

const ShotScene: React.FC<ShotSceneProps> = ({
  shot,
  durationInFrames,
  index,
  totalShots,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const align = shot.align ?? "left";
  const settle = spring({fps, frame, config: {damping: 18, mass: 0.95}});
  const opacity = interpolate(
    frame,
    [0, 10, durationInFrames - 14, durationInFrames],
    [0, 1, 1, 0],
    clamp,
  );
  const screenshotScale = interpolate(frame, [0, durationInFrames], [1.08, 1], clamp);
  const textLift = interpolate(frame, [0, 18], [42, 0], clamp);
  const progress = interpolate(frame, [0, durationInFrames], [0, 1], clamp);

  let captionPosition: React.CSSProperties;
  if (align === "right") {
    captionPosition = {
      right: 120,
      alignItems: "flex-end",
      textAlign: "right",
      maxWidth: 560,
    };
  } else if (align === "center") {
    captionPosition = {
      left: 0,
      right: 0,
      margin: "0 auto",
      alignItems: "center",
      textAlign: "center",
      maxWidth: 980,
    };
  } else {
    captionPosition = {
      left: 120,
      alignItems: "flex-start",
      textAlign: "left",
      maxWidth: 560,
    };
  }

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(135deg, ${promoMeta.background} 0%, #050a14 100%)`,
        color: "white",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(circle at 14% 18%, ${promoMeta.accent}2e 0%, transparent 30%), radial-gradient(circle at 85% 14%, #ffffff10 0%, transparent 24%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: "88px 120px 188px",
          display: "flex",
          justifyContent: justifyByAlign[align],
          alignItems: "center",
        }}
      >
        <div
          style={{
            width: "72%",
            maxWidth: 1480,
            opacity,
            transform: `translateY(${18 - settle * 18}px) scale(${0.97 + settle * 0.03})`,
          }}
        >
          <div
            style={{
              position: "relative",
              aspectRatio: "16 / 9",
              overflow: "hidden",
              borderRadius: 44,
              background: "#050b16",
              border: `1px solid ${promoMeta.accent}33`,
              boxShadow: "0 38px 120px rgba(0, 0, 0, 0.45)",
            }}
          >
            <Img
              src={staticFile(shot.src.replace(/^\/+/, ""))}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                transform: `scale(${screenshotScale})`,
              }}
            />
            <div
              style={{
                position: "absolute",
                inset: 0,
                background:
                  "linear-gradient(180deg, rgba(0, 0, 0, 0) 35%, rgba(0, 0, 0, 0.22) 100%)",
              }}
            />
          </div>
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          bottom: 96,
          display: "flex",
          flexDirection: "column",
          gap: 14,
          opacity,
          transform: `translateY(${textLift}px)`,
          ...captionPosition,
        }}
      >
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 14,
            fontSize: 18,
            letterSpacing: 4,
            textTransform: "uppercase",
            color: "#d7e3f4",
          }}
        >
          <span>{`${String(index + 1).padStart(2, "0")} / ${String(totalShots).padStart(2, "0")}`}</span>
          <span
            style={{
              width: 56,
              height: 2,
              borderRadius: 999,
              background: promoMeta.accent,
            }}
          />
        </div>
        <h2
          style={{
            margin: 0,
            fontSize: 62,
            lineHeight: 1.02,
            letterSpacing: -2,
          }}
        >
          {shot.title}
        </h2>
        <p
          style={{
            margin: 0,
            fontSize: 28,
            lineHeight: 1.35,
            color: "#d0d9e9",
          }}
        >
          {shot.subtitle}
        </p>
        <div
          style={{
            width: 240,
            height: 6,
            borderRadius: 999,
            overflow: "hidden",
            background: "rgba(255, 255, 255, 0.12)",
          }}
        >
          <div
            style={{
              width: `${progress * 100}%`,
              height: "100%",
              borderRadius: 999,
              background: promoMeta.accent,
            }}
          />
        </div>
      </div>
    </AbsoluteFill>
  );
};

const OutroScene: React.FC<{durationInFrames: number}> = ({durationInFrames}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const settle = spring({fps, frame, config: {damping: 16, mass: 0.9}});
  const opacity = interpolate(frame, [0, 12, durationInFrames], [0, 1, 1], clamp);

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(160deg, #050a15 0%, ${promoMeta.background} 100%)`,
        color: "white",
        justifyContent: "center",
        alignItems: "center",
        textAlign: "center",
        padding: "120px",
      }}
    >
      <div
        style={{
          opacity,
          transform: `translateY(${28 - settle * 28}px) scale(${0.96 + settle * 0.04})`,
          maxWidth: 1100,
        }}
      >
        <div
          style={{
            width: 160,
            height: 6,
            borderRadius: 999,
            background: promoMeta.accent,
            margin: "0 auto 24px",
            boxShadow: `0 0 32px ${promoMeta.accent}88`,
          }}
        />
        <h2
          style={{
            margin: 0,
            fontSize: 92,
            lineHeight: 1.02,
            letterSpacing: -3,
          }}
        >
          {promoMeta.closingLine}
        </h2>
        <p
          style={{
            marginTop: 24,
            marginBottom: 0,
            fontSize: 28,
            color: "#d0d9e9",
            lineHeight: 1.4,
          }}
        >
          Replace this line with a CTA, launch date, URL, or one last proof point.
        </p>
      </div>
    </AbsoluteFill>
  );
};

export const ProductPromo: React.FC = () => {
  const introScene = SCENES[0];
  const outroScene = SCENES[SCENES.length - 1];
  const shotScenes = SCENES.slice(1, 1 + shots.length);
  const shotOffsets = shotScenes.reduce<number[]>((acc, scene, index) => {
    if (index === 0) {
      acc.push(introScene.durationInFrames);
      return acc;
    }

    acc.push(acc[index - 1] + shotScenes[index - 1].durationInFrames);
    return acc;
  }, []);
  const outroFrom =
    shotScenes.length === 0
      ? introScene.durationInFrames
      : shotOffsets[shotOffsets.length - 1] +
        shotScenes[shotScenes.length - 1].durationInFrames;

  return (
    <AbsoluteFill style={{background: promoMeta.background}}>
      {promoMeta.backgroundMusic.file ? (
        <Audio
          src={staticFile(promoMeta.backgroundMusic.file)}
          volume={getBackgroundMusicVolume}
        />
      ) : null}

      <Sequence from={0} durationInFrames={introScene.durationInFrames}>
        <>
          <IntroScene durationInFrames={introScene.durationInFrames} />
          <SceneAudio audioFile={introScene.audioFile} />
        </>
      </Sequence>

      {shotScenes.map((scene, index) => {
        return (
          <Sequence
            key={scene.id}
            from={shotOffsets[index]}
            durationInFrames={scene.durationInFrames}
          >
            <>
              <ShotScene
                shot={shots[index]}
                durationInFrames={scene.durationInFrames}
                index={index}
                totalShots={shots.length}
              />
              <SceneAudio audioFile={scene.audioFile} />
            </>
          </Sequence>
        );
      })}

      <Sequence from={outroFrom} durationInFrames={outroScene.durationInFrames}>
        <>
          <OutroScene durationInFrames={outroScene.durationInFrames} />
          <SceneAudio audioFile={outroScene.audioFile} />
        </>
      </Sequence>
    </AbsoluteFill>
  );
};
