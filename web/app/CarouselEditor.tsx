"use client";

import { useEffect, useState } from "react";
import {
  api,
  CarouselManifest,
  fileUrl,
  SlideEntry,
} from "../lib/api";

const MAX_CHARS = 80;

// Cross-origin download: fetch as blob then trigger save. Browsers ignore the
// `download` attribute on cross-origin links (worker is on a different domain
// than the UI), so this is the only way that actually saves the file.
async function downloadFile(url: string, name: string) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`download ${res.status}`);
  const blob = await res.blob();
  const obj = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = obj;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(obj), 1000);
}

function CharCount({ value, max }: { value: string; max: number }) {
  const over = value.length > max;
  return (
    <span className={`charcount${over ? " over" : ""}`}>
      {value.length}/{max}
    </span>
  );
}

function SlideCard({
  jobId,
  number,
  slide,
  onOpen,
}: {
  jobId: string;
  number: number;
  slide: SlideEntry;
  onOpen: () => void;
}) {
  const [top, setTop] = useState(slide.top_text);
  const [bottom, setBottom] = useState(slide.bottom_text);
  const [tTop, setTTop] = useState(slide.t_top);
  const [tBottom, setTBottom] = useState(slide.t_bottom);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [v, setV] = useState(Date.now());

  const src = `${fileUrl(jobId, slide.file)}?v=${v}`;
  const fileName = `carousel_${number}_slide_${slide.index}.png`;

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
        top_text: top.slice(0, MAX_CHARS),
        bottom_text: bottom.slice(0, MAX_CHARS),
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
      <button className="thumbbtn" onClick={onOpen} title="Open full size">
        <img className="slideimg" src={src} alt={`slide ${slide.index}`} />
      </button>
      <div className="slidefields">
        <div className="labelrow">
          <label className="lbl">Top sentence</label>
          <CharCount value={top} max={MAX_CHARS} />
        </div>
        <textarea
          value={top}
          rows={2}
          maxLength={MAX_CHARS}
          onChange={(e) => setTop(e.target.value)}
        />
        <div className="framerow">
          <span>top frame @ {tTop.toFixed(1)}s</span>
          <button className="ghost sm" onClick={() => apply({ tTop: Math.max(0, tTop - 0.5) })} disabled={busy}>−</button>
          <button className="ghost sm" onClick={() => apply({ tTop: tTop + 0.5 })} disabled={busy}>+</button>
        </div>

        <div className="labelrow">
          <label className="lbl">Bottom sentence</label>
          <CharCount value={bottom} max={MAX_CHARS} />
        </div>
        <textarea
          value={bottom}
          rows={2}
          maxLength={MAX_CHARS}
          onChange={(e) => setBottom(e.target.value)}
        />
        <div className="framerow">
          <span>bottom frame @ {tBottom.toFixed(1)}s</span>
          <button className="ghost sm" onClick={() => apply({ tBottom: Math.max(0, tBottom - 0.5) })} disabled={busy}>−</button>
          <button className="ghost sm" onClick={() => apply({ tBottom: tBottom + 0.5 })} disabled={busy}>+</button>
        </div>

        <div className="actionrow">
          <button className="primary sm" onClick={() => apply()} disabled={busy}>
            {busy ? "Rendering…" : "Apply & re-render"}
          </button>
          <button
            className="ghost sm"
            onClick={() => downloadFile(src, fileName)}
            disabled={busy}
          >
            ⬇ Download
          </button>
        </div>
        {err ? <p className="status err">{err}</p> : null}
      </div>
    </div>
  );
}

function Lightbox({
  jobId,
  carousel,
  startIndex,
  onClose,
}: {
  jobId: string;
  carousel: CarouselManifest;
  startIndex: number;
  onClose: () => void;
}) {
  const [idx, setIdx] = useState(startIndex);
  const slide = carousel.slides[idx];

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight") setIdx((i) => Math.min(i + 1, carousel.slides.length - 1));
      if (e.key === "ArrowLeft") setIdx((i) => Math.max(i - 1, 0));
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [carousel.slides.length, onClose]);

  if (!slide) return null;
  const src = `${fileUrl(jobId, slide.file)}?v=${Date.now()}`;
  const fileName = `carousel_${carousel.number}_slide_${slide.index}.png`;

  return (
    <div className="lightbox" onClick={onClose}>
      <div className="lbinner" onClick={(e) => e.stopPropagation()}>
        <button className="lbclose" onClick={onClose} title="Close (Esc)">✕</button>
        <button
          className="lbnav prev"
          onClick={() => setIdx((i) => Math.max(i - 1, 0))}
          disabled={idx === 0}
          title="Previous (←)"
        >
          ‹
        </button>
        <img className="lbimg" src={src} alt={`slide ${slide.index}`} />
        <button
          className="lbnav next"
          onClick={() => setIdx((i) => Math.min(i + 1, carousel.slides.length - 1))}
          disabled={idx === carousel.slides.length - 1}
          title="Next (→)"
        >
          ›
        </button>
        <div className="lbbar">
          <span>
            Carousel {carousel.number} · Slide {slide.index} of {carousel.slides.length}
          </span>
          <button className="ghost sm" onClick={() => downloadFile(src, fileName)}>
            ⬇ Download
          </button>
        </div>
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
  const [open, setOpen] = useState<{ ci: number; si: number } | null>(null);

  async function downloadCarousel(c: CarouselManifest) {
    for (const s of c.slides) {
      const url = `${fileUrl(jobId, s.file)}?v=${Date.now()}`;
      await downloadFile(url, `carousel_${c.number}_slide_${s.index}.png`);
    }
  }

  return (
    <>
      <section className="carousels">
        <h2>Carousels</h2>
        <p className="hint">
          Click any image to view full size and arrow through the carousel. Edit a
          sentence (80 char max), nudge the frame, then re-render. Downloads as a
          post-ready 1080×1920 PNG.
        </p>
        {carousels.map((c, ci) => (
          <div key={c.number} className="carousel">
            <div className="chead">
              <p className="ctitle">
                Carousel {c.number}: {c.title}
              </p>
              <button className="ghost sm" onClick={() => downloadCarousel(c)}>
                ⬇ Download all {c.slides.length}
              </button>
            </div>
            <div className="slidegrid">
              {c.slides.map((s, si) => (
                <SlideCard
                  key={s.index}
                  jobId={jobId}
                  number={c.number}
                  slide={s}
                  onOpen={() => setOpen({ ci, si })}
                />
              ))}
            </div>
          </div>
        ))}
      </section>
      {open ? (
        <Lightbox
          jobId={jobId}
          carousel={carousels[open.ci]}
          startIndex={open.si}
          onClose={() => setOpen(null)}
        />
      ) : null}
    </>
  );
}
