import { useEffect, useRef } from "react";
import { animate } from "animejs";

interface Props {
  value: number;
  /** Animation duration in ms. */
  duration?: number;
  className?: string;
}

/** Animates a number from 0 to `value` on mount. Renders instantly under reduced motion. */
export function CountUp({ value, duration = 900, className }: Props) {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      el.textContent = String(value);
      return;
    }
    // anime.js can tween plain objects; onUpdate writes the rounded value.
    const proxy = { v: 0 };
    const anim = animate(proxy, {
      v: value,
      duration,
      easing: "out(2)",
      onUpdate: () => {
        el.textContent = String(Math.round(proxy.v));
      },
    });
    return () => {
      anim.pause();
    };
  }, [value, duration]);

  return (
    <span ref={ref} className={className}>
      {value}
    </span>
  );
}