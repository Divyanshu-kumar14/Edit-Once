import { Children } from "react";
import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
  /** Seconds between each child's entrance. */
  gap?: number;
  /** Seconds before the first child starts. */
  startDelay?: number;
  className?: string;
}

/**
 * Stagger — cascades a spring fade+rise entrance across its children,
 * one after another. Renders a plain div under reduced motion.
 */
export function Stagger({ children, gap = 0.08, startDelay = 0, className }: Props) {
  const reduce = useReducedMotion();
  if (reduce) return <div className={className}>{children}</div>;
  return (
    <div className={className}>
      {Children.map(children, (child, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            type: "spring",
            stiffness: 240,
            damping: 24,
            delay: startDelay + i * gap,
          }}
        >
          {child}
        </motion.div>
      ))}
    </div>
  );
}