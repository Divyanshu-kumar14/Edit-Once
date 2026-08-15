import { motion } from "motion/react";
import type { CheckResult } from "../types";
import { RESULT_LABEL } from "../types";

const LEVEL_CLASS: Record<string, string> = {
  pass: "pass",
  warn: "warn",
  fail: "fail",
};

export function Checklist({ checks }: { checks: CheckResult[] }) {
  if (checks.length === 0) return null;
  return (
    <ul className="checklist" aria-label="Verification checklist">
      {checks.map((check, i) => (
        <motion.li
          key={check.name}
          className="check-row"
          initial={{ opacity: 0, x: -6 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ type: "spring", stiffness: 260, damping: 26, delay: 0.05 * i }}
        >
          <span className={`badge ${LEVEL_CLASS[check.result] ?? "fail"}`}>
            {RESULT_LABEL[check.result]}
          </span>
          <span className="check-name">{check.name.replace("_", " ")}</span>
          <span className="check-detail muted" title={check.detail}>
            {check.detail}
          </span>
        </motion.li>
      ))}
    </ul>
  );
}