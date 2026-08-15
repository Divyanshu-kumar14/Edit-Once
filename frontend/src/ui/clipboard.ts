import { useCallback, useState } from "react";

export const copy = async (text: string): Promise<boolean> => {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
};

export function useCopied(resetMs = 1500): [string | null, (key: string) => void] {
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
