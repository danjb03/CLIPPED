import React from "react";
import { AbsoluteFill } from "remotion";

export type CarouselSlideProps = {
  text: string;
  index: number; // 1-based
  total: number;
  background: string;
  color: string;
  accent: string;
  fontFamily: string;
};

export const CAROUSEL_WIDTH = 1080;
export const CAROUSEL_HEIGHT = 1350;

export const DEFAULT_CAROUSEL_PROPS: CarouselSlideProps = {
  text: "Your slide text goes here. It flows as a story.",
  index: 1,
  total: 4,
  background: "#111317",
  color: "#ffffff",
  accent: "#ffe600",
  fontFamily: "Inter, Arial, sans-serif",
};

export const CarouselSlide: React.FC<CarouselSlideProps> = ({
  text,
  index,
  total,
  background,
  color,
  accent,
  fontFamily,
}) => {
  const isLast = index >= total;
  return (
    <AbsoluteFill
      style={{
        backgroundColor: background,
        fontFamily,
        padding: 96,
        justifyContent: "space-between",
      }}
    >
      {/* top: slide counter */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          color,
          fontSize: 34,
          fontWeight: 700,
          opacity: 0.85,
        }}
      >
        <span style={{ color: accent }}>●●●</span>
        <span>
          {index} / {total}
        </span>
      </div>

      {/* middle: the slide text */}
      <div
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
        }}
      >
        <div
          style={{
            color,
            fontSize: 70,
            fontWeight: 800,
            lineHeight: 1.18,
            letterSpacing: "-0.01em",
          }}
        >
          <span
            style={{
              display: "block",
              width: 96,
              height: 10,
              borderRadius: 6,
              backgroundColor: accent,
              marginBottom: 40,
            }}
          />
          {text}
        </div>
      </div>

      {/* bottom: swipe hint (not on last slide) */}
      <div
        style={{
          color: accent,
          fontSize: 34,
          fontWeight: 700,
          textAlign: "right",
          opacity: isLast ? 0 : 1,
        }}
      >
        swipe →
      </div>
    </AbsoluteFill>
  );
};
