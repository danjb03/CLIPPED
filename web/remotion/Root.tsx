import React from "react";
import { Composition } from "remotion";
import { Captions } from "./Captions";
import { CaptionProps, DEFAULT_PROPS, HEIGHT, WIDTH } from "./types";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Captions"
      component={Captions}
      durationInFrames={150}
      fps={30}
      width={WIDTH}
      height={HEIGHT}
      defaultProps={DEFAULT_PROPS}
      calculateMetadata={({ props }: { props: CaptionProps }) => ({
        durationInFrames: Math.max(
          1,
          Math.round(props.durationInSeconds * props.fps)
        ),
        fps: props.fps,
      })}
    />
  );
};
