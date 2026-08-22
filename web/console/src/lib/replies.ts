import type { PublicConfig } from "./api";
import { lookup } from "./i18n";

export function typeLabel(cfg: PublicConfig | null, id: string): string {
  const value = cfg?.[`response.label.${id}`];
  return typeof value === "string" && value.trim() ? value : id;
}

export function viaLabel(t: (key: string) => string, code: string): string {
  const key = `reply.via.${code}`;
  const got = t(key);
  return got === key ? lookup(t, "channel", code) : got;
}

export function saidLabel(
  cfg: PublicConfig | null,
  type: string,
  freeText: string | null | undefined,
): string {
  const label = typeLabel(cfg, type);
  if (freeText && (type === "other" || !label)) return freeText;
  if (freeText && freeText !== label) return `${label} — ${freeText}`;
  return label;
}
