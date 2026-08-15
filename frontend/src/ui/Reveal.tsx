import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
  /** Spring delay in seconds before the entrance starts. */
  delay?: number;
  /** Rise distance in px. */
  y?: number;
  className?: string;
}

/** Fade + rise spring entrance. Renders a plain div under reduced motion. */
export function Reveal({ children, delay = 0, y = 14, className }: Props) {
  const reduce = useReducedMotion();
  if (reduce) return <div className={className}>{children}</div>;
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 260, damping: 26, delay }}
    >
      {children}
    </motion.div>
  );
}