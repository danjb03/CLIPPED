"use client";

import { useState } from "react";
import {
  api,
  CaptionStyle,
  Clip,
  DEFAULT_STYLE,
  fileUrl,
} from "../lib/api";

function fmt(t: number) {
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function ClipCard({
  jobId,
  index,
  clip,
  onClipChange,
}: {
  jobId: string;
  index: number;
  clip: Clip;
  onClipChange: (index: number, clip: Clip) => void;
}) {
  const [style, setStyle] = useState<CaptionStyle>(DEFAULT_STYLE);
  const [copyText, setCopyText] = useState(clip.copy ?? "");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  // cache-buster so the <video> reloads after a re-render
  const [v, setV] = useState(Date.now());

  const src = `${fileUrl(jobId, `renders/clip_${index}.mp4`)}?v=${v}`;

  async function applyStyle() {
    setErr(null);
    setBusy("Re-rendering…");
    try {
      await api.renderOne(jobId, index, style);
      setV(Date.now());
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(null);
    }
  }

  async function regenerate() {
    setErr(null);
    setBusy("Picking a new moment…");
    try {
      const { clip: next } = await api.regenerate(jobId, index);
      onClipChange(index, { ...next, copy: clip.copy });
      setBusy("Re-rendering…");
      await api.renderOne(jobId, index, style);
      setV(Date.now());
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(null);
    }
  }

  const set = (patch: Partial<CaptionStyle>) =>
    setStyle((s) => ({ ...s, ...patch }));

  return (
    <div className="card">
      <video className="preview" src={src} controls playsInline />

      <div className="meta">
        <span className="badge">#{index + 1}</span>
        <span className="time">
          {fmt(clip.start)}–{fmt(clip.end)} ({Math.round(clip.end - clip.start)}s)
        </span>
        <span className="focus">focus: {clip.speaker_focus}</span>
      </div>

      {clip.hook ? <p className="hook">“{clip.hook}”</p> : null}

      <label className="lbl">Caption</label>
      <textarea
        className="copy"
        value={copyText}
        onChange={(e) => setCopyText(e.target.value)}
        rows={3}
        placeholder="(run Generate copy)"
      />
      <button
        className="ghost"
        onClick={() => navigator.clipboard.writeText(copyText)}
      >
        Copy to clipboard
      </button>

      <details className="styler">
        <summary>Style</summary>
        <div className="row">
          <label>Text</label>
          <input
            type="color"
            value={style.color}
            onChange={(e) => set({ color: e.target.value })}
          />
          <label>Highlight</label>
          <input
            type="color"
            value={style.highlightColor}
            onChange={(e) => set({ highlightColor: e.target.value })}
          />
        </div>
        <div className="row">
          <label>Size {style.fontSize}</label>
          <input
            type="range"
            min={40}
            max={140}
            value={style.fontSize}
            onChange={(e) => set({ fontSize: Number(e.target.value) })}
          />
        </div>
        <div className="row">
          <label>X {Math.round(style.position.x * 100)}</label>
          <input
            type="range"
            min={0}
            max={100}
            value={Math.round(style.position.x * 100)}
            onChange={(e) =>
              set({ position: { ...style.position, x: Number(e.target.value) / 100 } })
            }
          />
        </div>
        <div className="row">
          <label>Y {Math.round(style.position.y * 100)}</label>
          <input
            type="range"
            min={0}
            max={100}
            value={Math.round(style.position.y * 100)}
            onChange={(e) =>
              set({ position: { ...style.position, y: Number(e.target.value) / 100 } })
            }
          />
        </div>
        <button className="ghost" onClick={applyStyle} disabled={!!busy}>
          Apply style &amp; re-render
        </button>
      </details>

      <div className="actions">
        <button onClick={regenerate} disabled={!!busy}>
          Regenerate clip
        </button>
      </div>

      {busy ? <p className="status busy">{busy}</p> : null}
      {err ? <p className="status err">{err}</p> : null}
    </div>
  );
}
