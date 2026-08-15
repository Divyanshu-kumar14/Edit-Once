import { useEffect, useRef, useState } from "react";
import { animate } from "animejs";

interface Props {
  /** Seconds before the sweep starts. */
  delay?: number;
  /** Sweep duration in ms. */
  duration?: number;
}

/** One light sweep across a still/card on mount (anime.js). Nothing under reduced motion. */
export function Shine({ delay = 0, duration = 1100 }: Props) {
  const ref = useRef<HTMLSpanElement>(null);
  const [enabled] = useState(
    () => !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );

  useEffect(() => {
    const el = ref.current;
    if (!el || !enabled) return;
    const anim = animate(el, {
      translateX: ["-140%", "140%"],
      duration,
      easing: "inOut(3)",
      delay,
    });
    return () => {
      anim.pause();
    };
  }, [delay, duration, enabled]);

  if (!enabled) return null;
  return <span ref={ref} className="shine-sweep" aria-hidden="true" />;
}