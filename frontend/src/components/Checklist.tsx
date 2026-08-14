import type { CheckResult } from "../types";

const LEVEL_CLASS: Record<string, string> = {
  pass: "pass",
  warn: "warn",
  fail: "fail",
};

export function Checklist({ checks }: { checks: CheckResult[] }) {
  if (checks.length === 0) return null;
  return (
    <ul className="checklist" aria-label="Verification checklist">
      {checks.map((check) => (
        <li key={check.name} className="check-row">
          <span className={`badge ${LEVEL_CLASS[check.result] ?? "fail"}`}>
            {check.result.toUpperCase()}
          </span>
          <span className="check-name">{check.name.replace("_", " ")}</span>
          <span className="check-detail muted" title={check.detail}>
            {check.detail}
          </span>
        </li>
      ))}
    </ul>
  );
}