import { useCallback, useEffect, useState } from "react";
import { Check, Copy, RefreshCw, Sparkles } from "lucide-react";
import { ApiError, generateSeo } from "../api";
import type { JobState, PlatformId, SeoPack } from "../types";
import { PLATFORM_LABELS, PLATFORM_ORDER } from "../types";
import { Reveal } from "../ui/Reveal";

interface Props {
  job: JobState;
  /** Server-side packs were persisted; merge them into app state. */
  onPacks: (packs: Partial<Record<PlatformId, SeoPack>>, generatedAt: string) => void;
}

const copy = async (text: string): Promise<boolean> => {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
};

function useCopied(resetMs = 1500): [string | null, (key: string) => void] {
  const [copied, setCopied] = useState<string | null>(null);
  const flash = useCallback(
    (key: string) => {
      setCopied(key);
      setTimeout(() => setCopied((c) => (c === key ? null : c)), resetMs);
    },
    [resetMs],
  );
  return [copied, flash];
}

function copyAllText(pack: SeoPack): string {
  const tags = pack.hashtags.map((t) => (t.startsWith("#") ? t : `#${t}`)).join(" ");
  return `Title: ${pack.title}\n\n${pack.description}\n\n${tags}`;
}

function PackCard({
  platform,
  pack,
  copied,
  flash,
}: {
  platform: PlatformId;
  pack: SeoPack;
  copied: string | null;
  flash: (key: string) => void;
}) {
  if (pack.error) {
    return (
      <div className="seo-card glass" data-platform={platform}>
        <div className="seo-card-head">
          <strong>{PLATFORM_LABELS[platform]}</strong>
          <span className="badge failed">Failed</span>
        </div>
        <p className="muted seo-error">{pack.error}</p>
      </div>
    );
  }

  const fields = [
    { key: "title", label: "Title", value: pack.title, rows: 1 },
    { key: "description", label: "Description", value: pack.description, rows: 3 },
    {
      key: "hashtags",
      label: "Hashtags",
      value: pack.hashtags.join(", "),
      rows: 1,
    },
  ] as const;

  const onCopyField = async (key: string, value: string) => {
    if (await copy(value)) flash(`${platform}:${key}`);
  };
  const onCopyAll = async () => {
    if (await copy(copyAllText(pack))) flash(`all:${platform}`);
  };

  return (
    <div className="seo-card glass" data-platform={platform}>
      <div className="seo-card-head">
        <strong>{PLATFORM_LABELS[platform]}</strong>
        <button
          className="btn ghost seo-copy-all"
          onClick={onCopyAll}
          aria-label={`Copy all SEO text for ${PLATFORM_LABELS[platform]}`}
        >
          {copied === `all:${platform}` ? <Check size={13} /> : <Copy size={13} />}
          {copied === `all:${platform}` ? "Copied" : "Copy all"}
        </button>
      </div>
      {fields.map((f) => (
        <label className="seo-field" key={f.key}>
          <span className="muted seo-field-label">
            {f.label}
            <button
              className="seo-copy"
              onClick={() => onCopyField(f.key, f.value)}
              aria-label={`Copy ${f.label}`}
            >
              {copied === `${platform}:${f.key}` ? <Check size={12} /> : <Copy size={12} />}
              {copied === `${platform}:${f.key}` ? "Copied" : "Copy"}
            </button>
          </span>
          <textarea
            className="seo-textarea"
            rows={f.rows}
            defaultValue={f.value}
            aria-label={`${PLATFORM_LABELS[platform]} ${f.label}`}
          />
        </label>
      ))}
    </div>
  );
}

export function SeoSection({ job, onPacks }: Props) {
  const [groqAvailable, setGroqAvailable] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, flash] = useCopied();
  const packs = job.seo_packs ?? {};
  const hasPacks = Object.keys(packs).length > 0;

  // Check once (when there are no packs yet) whether Groq is configured.
  useEffect(() => {
    if (hasPacks) return;
    let cancelled = false;
    fetch("/api/health")
      .then((r) => r.json())
      .then((h: { groq?: boolean }) => {
        if (!cancelled) setGroqAvailable(h.groq === true);
      })
      .catch(() => {
        if (!cancelled) setGroqAvailable(false);
      });
    return () => {
      cancelled = true;
    };
  }, [hasPacks]);

  const handleGenerate = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await generateSeo(job.job_id);
      onPacks(result.packs, result.generated_at);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "SEO generation failed — try again.");
    } finally {
      setLoading(false);
    }
  }, [job.job_id, onPacks]);

  return (
    <Reveal>
      <section className="seo-section" aria-label="SEO packs">
        {hasPacks ? (
          <>
            <div className="seo-head">
              <div>
                <h3>
                  <Sparkles size={16} aria-hidden="true" /> SEO pack
                </h3>
                <p className="muted">
                  Platform-optimized copy, grounded in your transcript. Tweak, copy, post.
                </p>
              </div>
              <button className="btn ghost" onClick={handleGenerate} disabled={loading}>
                <RefreshCw size={14} aria-hidden="true" /> Regenerate
              </button>
            </div>
            <div className="seo-grid">
              {PLATFORM_ORDER.map((pid) =>
                packs[pid] ? (
                  <PackCard key={pid} platform={pid} pack={packs[pid]!} copied={copied} flash={flash} />
                ) : null,
              )}
            </div>
          </>
        ) : groqAvailable === false ? (
          <div className="seo-cta glass">
            <p className="muted">
              Want platform-optimized titles, descriptions and viral hashtags? Add a Groq API key
              (<code>EDITONCE_GROQ_API_KEY</code> in <code>.env</code>) and it appears here.
            </p>
          </div>
        ) : (
          <div className="seo-cta glass">
            <button className="btn primary" onClick={handleGenerate} disabled={loading}>
              <Sparkles size={15} aria-hidden="true" />
              {loading ? "Asking Groq for 4 packs…" : "Generate SEO pack"}
            </button>
            <p className="muted">
              Title, description and viral hashtags for each platform — grounded in what your
              video actually says.
            </p>
            {error && (
              <p className="seo-error" role="alert">
                {error}
              </p>
            )}
          </div>
        )}
      </section>
    </Reveal>
  );
}
