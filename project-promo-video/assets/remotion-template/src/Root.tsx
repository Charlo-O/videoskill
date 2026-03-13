import React from "react";
import {Composition} from "remotion";
import {ProductPromo} from "./components/ProductPromo";
import {FPS, TOTAL_FRAMES} from "./audio-config";

export const Root: React.FC = () => {
  return (
    <Composition
      id="ProductPromo"
      component={ProductPromo}
      durationInFrames={TOTAL_FRAMES}
      fps={FPS}
      width={1920}
      height={1080}
      defaultProps={{}}
    />
  );
};
