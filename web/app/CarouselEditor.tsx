"use client";

import { useState } from "react";
import {
  api,
  CarouselManifest,
  fileUrl,
  SlideEntry,
} from "../lib/api";

function SlideCard({
  jobId,
  number,
  slide,
}: {
  jobId: string;
  number: number;
  slide: SlideEntry;
}) {
  const [top, setTop] = useState(slide.top_text);
  const [bottom, setBottom] = useState(slide.bottom_text);
  const [tTop, setTTop] = useState(slide.t_top);
  const [tBottom, setTBottom] = useState(slide.t_bottom);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [v, setV] = useState(Date.now());

  const src = `${fileUrl(jobId, slide.file)}?v=${v}`;

  async function apply(over?: { tTop?: number; tBottom?: number }) {
    setErr(null);
    setBusy(true);
    const nt = over?.tTop ?? tTop;
    const nb = over?.tBottom ?? tBottom;
    if (over?.tTop !== undefined) setTTop(nt);
    if (over?.tBottom !== undefined) setTBottom(nb);
    try {
      await api.renderSlide(jobId, {
        number,
        index: slide.index,
        top_text: top,
        bottom_text: bottom,
        t_top: nt,
        t_bottom: nb,
      });
      setV(Date.now());
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="slidecard">
      <a href={src} download={`carousel_${number}_slide_${slide.index}.png`}>
        <img className="slideimg" src={src} alt={`slide ${slide.index}`} />
      </a>
      <div className="slidefields">
        <label className="lbl">Top sentence</label>
        <textarea value={top} rows={2} onChange={(e) => setTop(e.target.value)} />
        <div className="framerow">
          <span>top frame @ {tTop.toFixed(1)}s</span>
          <button className="ghost sm" onClick={() => apply({ tTop: Math.max(0, tTop - 0.5) })} disabled={busy}>−</button>
          <button className="ghost sm" onClick={() => apply({ tTop: tTop + 0.5 })} disabled={busy}>+</button>
        </div>

        <label className="lbl">Bottom sentence</label>
        <textarea value={bottom} rows={2} onChange={(e) => setBottom(e.target.value)} />
        <div className="framerow">
          <span>bottom frame @ {tBottom.toFixed(1)}s</span>
          <button className="ghost sm" onClick={() => apply({ tBottom: Math.max(0, tBottom - 0.5) })} disabled={busy}>−</button>
          <button className="ghost sm" onClick={() => apply({ tBottom: tBottom + 0.5 })} disabled={busy}>+</button>
        </div>

        <button className="primary sm" onClick={() => apply()} disabled={busy}>
          {busy ? "Rendering…" : "Apply text & re-render"}
        </button>
        <a className="dl sm" href={src} download={`carousel_${number}_slide_${slide.index}.png`}>
          ⬇ Download
        </a>
        {err ? <p className="status err">{err}</p> : null}
      </div>
    </div>
  );
}

export function CarouselEditor({
  jobId,
  carousels,
}: {
  jobId: string;
  carousels: CarouselManifest[];
}) {
  return (
    <section className="carousels">
      <h2>Carousels</h2>
      <p className="hint">
        Edit any sentence or nudge the frame (− / +), then re-render. Each slide
        downloads as a post-ready 1080×1920 PNG.
      </p>
      {carousels.map((c) => (
        <div key={c.number} className="carousel">
          <p className="ctitle">
            Carousel {c.number}: {c.title}
          </p>
          <div className="slidegrid">
            {c.slides.map((s) => (
              <SlideCard key={s.index} jobId={jobId} number={c.number} slide={s} />
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}
