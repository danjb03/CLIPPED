import React from "react";
import {
  AbsoluteFill,
  OffthreadVideo,
  staticFile,
  useCurrentFrame,
} from "remotion";
import {
  CaptionProps,
  HEIGHT,
  WIDTH,
  activeGroupIndex,
  groupWords,
} from "./types";

export const Captions: React.FC<CaptionProps> = ({
  videoSrc,
  words,
  style,
  fps,
}) => {
  const frame = useCurrentFrame();
  const t = frame / fps;

  const groups = React.useMemo(() => groupWords(words), [words]);
  const idx = activeGroupIndex(groups, t);
  const group = idx >= 0 ? groups[idx] : null;

  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      {videoSrc ? (
        <OffthreadVideo src={staticFile(videoSrc)} />
      ) : null}

      {group ? (
        <div
          style={{
            position: "absolute",
            left: `${style.position.x * 100}%`,
            top: `${style.position.y * 100}%`,
            transform: "translate(-50%, -50%)",
            maxWidth: WIDTH * style.maxWidth,
            textAlign: "center",
            fontFamily: style.fontFamily,
            fontSize: style.fontSize,
            fontWeight: 800,
            lineHeight: 1.1,
            color: style.color,
            WebkitTextStroke: `${style.strokeWidth}px ${style.strokeColor}`,
            // keep the fill painted on top of the stroke
            paintOrder: "stroke fill",
            textShadow: "0 4px 14px rgba(0,0,0,0.55)",
            textTransform: "uppercase",
            letterSpacing: "0.5px",
          }}
        >
          {group.map((w, i) => {
            const isActive = t >= w.start && t <= w.end;
            return (
              <span
                key={i}
                style={{
                  color: isActive ? style.highlightColor : style.color,
                  marginRight: "0.28em",
                  display: "inline-block",
                }}
              >
                {w.word}
              </span>
            );
          })}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

export const COMPOSITION = {
  id: "Captions",
  width: WIDTH,
  height: HEIGHT,
};
