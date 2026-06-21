export type Word = {
  word: string;
  start: number; // clip-relative seconds
  end: number;
  speaker?: string;
};

export type CaptionStyle = {
  fontFamily: string;
  fontSize: number;
  color: string;
  strokeColor: string;
  strokeWidth: number;
  highlightColor: string;
  maxWidth: number; // fraction of width (0..1)
  position: { x: number; y: number }; // fractions of width/height (0..1)
};

export type CaptionProps = {
  videoSrc: string; // path under web/public, e.g. "clips/<job>_<idx>.mp4"
  words: Word[];
  style: CaptionStyle;
  fps: number;
  durationInSeconds: number;
};

export const DEFAULT_STYLE: CaptionStyle = {
  fontFamily: "Inter, Arial, sans-serif",
  fontSize: 84,
  color: "#ffffff",
  strokeColor: "#000000",
  strokeWidth: 10,
  highlightColor: "#ffe600",
  maxWidth: 0.9,
  position: { x: 0.5, y: 0.78 },
};

export const DEFAULT_PROPS: CaptionProps = {
  videoSrc: "",
  words: [],
  style: DEFAULT_STYLE,
  fps: 30,
  durationInSeconds: 5,
};

export const WIDTH = 1080;
export const HEIGHT = 1920;

// Group words into caption chunks: cap at maxWords, break on a long pause.
export function groupWords(
  words: Word[],
  maxWords = 5,
  maxGap = 0.7
): Word[][] {
  const groups: Word[][] = [];
  let cur: Word[] = [];
  for (const w of words) {
    if (cur.length === 0) {
      cur = [w];
      continue;
    }
    const prev = cur[cur.length - 1];
    if (cur.length >= maxWords || w.start - prev.end > maxGap) {
      groups.push(cur);
      cur = [w];
    } else {
      cur.push(w);
    }
  }
  if (cur.length) groups.push(cur);
  return groups;
}

// The group to show at time t: the last group whose start has passed. This holds
// a caption on screen through pauses until the next group begins.
export function activeGroupIndex(groups: Word[][], t: number): number {
  let idx = -1;
  for (let i = 0; i < groups.length; i++) {
    if (groups[i][0].start <= t) idx = i;
  }
  return idx;
}
