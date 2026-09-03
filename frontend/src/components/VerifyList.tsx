import { AlertTriangle, Check, XCircle } from "lucide-react";
import type { CheckResult } from "../types";
import { RESULT_LABEL } from "../types";

function VerifyIcon({ level }: { level: CheckResult["result"] }) {
  if (level === "pass") return <Check size={14} />;
  if (level === "warn") return <AlertTriangle size={14} />;
  return <XCircle size={14} />;
}

/** The per-version verification checklist — the product's core differentiator,
 *  surfaced as a status list (icon + name + pass/review/fail), so state is
 *  never conveyed by color alone. */
export function VerifyList({ checks, label }: { checks: CheckResult[]; label: string }) {
  if (!checks.length) return null;
  return (
    <div className="verify" aria-label={`${label} verification checks`}>
      <span className="verify-title">Verification</span>
      <ul className="verify-list">
        {checks.map((c, i) => (
          <li className={`verify-item ${c.result}`} key={i}>
            <span className={`verify-icon ${c.result}`} aria-hidden="true">
              <VerifyIcon level={c.result} />
            </span>
            <span className="verify-name">{c.name}</span>
            <span className={`badge ${c.result}`}>{RESULT_LABEL[c.result]}</span>
            {c.detail && <span className="verify-detail">{c.detail}</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}
