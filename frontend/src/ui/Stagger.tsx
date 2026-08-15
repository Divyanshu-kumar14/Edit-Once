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
  "aria-label"?: string;
  role?: string;
}

/**
 * Stagger — cascades a spring fade+rise entrance across its children,
 * one after another. Renders a plain div under reduced motion.
 */
export function Stagger({ children, gap = 0.08, startDelay = 0, className, ...rest }: Props) {
  const reduce = useReducedMotion();
  if (reduce) return <div className={className} {...rest}>{children}</div>;
  return (
    <div className={className} {...rest}>
      {Children.map(children, (child, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            type: "spring",
            stiffness: 240,
            damping: 28,
            delay: startDelay + i * gap,
          }}
        >
          {child}
        </motion.div>
      ))}
    </div>
  );
}