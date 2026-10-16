import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";

type Motion = { animate: boolean; replayKey: number; print: boolean; toggle: () => void; replay: () => void };

const Ctx = createContext<Motion>({ animate: true, replayKey: 0, print: false, toggle: () => {}, replay: () => {} });

export function MotionProvider({ children, print = false }: { children: ReactNode; print?: boolean }) {
  const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const [animate, setAnimate] = useState(() => {
    if (print || reduced) return false;
    try {
      return localStorage.getItem("dv-motion") !== "off";
    } catch {
      return true;
    }
  });
  const [replayKey, setReplay] = useState(0);
  useEffect(() => {
    document.documentElement.classList.toggle("motion-off", !animate);
  }, [animate]);
  const toggle = () =>
    setAnimate((a) => {
      try {
        localStorage.setItem("dv-motion", a ? "off" : "on");
      } catch {
        /* storage unavailable */
      }
      return !a;
    });
  return <Ctx.Provider value={{ animate, replayKey, print, toggle, replay: () => setReplay((k) => k + 1) }}>{children}</Ctx.Provider>;
}

export const useMotion = () => useContext(Ctx);

/** Adds .in when the element scrolls into view (CSS handles the motion). */
export function useReveal<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const { replayKey, print } = useMotion();
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (print) {
      el.classList.add("in");
      return;
    }
    el.classList.remove("in");
    const io = new IntersectionObserver(
      (es) => {
        if (es.some((e) => e.isIntersecting)) {
          el.classList.add("in");
          io.disconnect();
        }
      },
      { threshold: 0.12 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [replayKey, print]);
  return ref;
}

/** Counts a number up from 0 when it first appears. */
export function useCountUp(target: number | null | undefined, duration = 1100): number | null {
  const { animate, replayKey } = useMotion();
  const [v, setV] = useState<number | null>(animate ? 0 : (target ?? null));
  useEffect(() => {
    if (target === null || target === undefined || !Number.isFinite(target)) {
      setV(target ?? null);
      return;
    }
    if (!animate) {
      setV(target);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const tick = (t: number) => {
      const k = Math.min(1, (t - start) / duration);
      const e = 1 - Math.pow(1 - k, 3);
      setV(target * e);
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, animate, replayKey, duration]);
  return v;
}
