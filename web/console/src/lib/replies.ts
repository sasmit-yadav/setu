import type { CitizenReply, PublicConfig } from "./api";
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

export function isHelpReply(type: string, cfg: PublicConfig | null): boolean {
  const safe = String(cfg?.["response.safe_type"] ?? "safe");
  return type !== safe;
}

export function saidLabel(
  cfg: PublicConfig | null,
  type: string,
  freeText: string | null | undefined,
): string {
  const raw = (freeText ?? "").trim();
  if (type === "other" && /help/i.test(raw)) return typeLabel(cfg, "help");
  const label = typeLabel(cfg, type);
  if (raw && type === "other") return raw.replace(/^(SMS|IVR):\s*/i, "");
  if (raw && raw !== label) return `${label} — ${raw}`;
  return label;
}

export function tallyReplies(rows: CitizenReply[], cfg: PublicConfig | null) {
  let safe = 0;
  let help = 0;
  let sms = 0;
  let ivr = 0;
  let app = 0;
  for (const row of rows) {
    if (isHelpReply(row.response_type, cfg)) help += 1;
    else safe += 1;
    if (row.channel_code === "sms") sms += 1;
    else if (row.channel_code === "ivr") ivr += 1;
    else if (row.channel_code === "fcm") app += 1;
  }
  return { total: rows.length, safe, help, sms, ivr, app };
}

export type ReplyFilter = "all" | "sms" | "ivr" | "fcm" | "safe" | "help";

export function filterReplies(
  rows: CitizenReply[],
  filter: ReplyFilter,
  cfg: PublicConfig | null,
): CitizenReply[] {
  if (filter === "all") return rows;
  if (filter === "safe") return rows.filter((row) => !isHelpReply(row.response_type, cfg));
  if (filter === "help") return rows.filter((row) => isHelpReply(row.response_type, cfg));
  return rows.filter((row) => row.channel_code === filter);
}
