/** Time formatting for the desk.
 *
 * This lived as three near-copies — LiveOps, ReplyInbox, and a raw ISO string
 * on the Command Board. The copies drifted: one of them signed the elapsed
 * minutes and printed them raw, so a thunderstorm forecast eight hours ahead
 * rendered as "-8h" and read as eight hours stale. Fixing one copy left the
 * other wrong, which is the argument for there being one.
 */

const MINUTE_MS = 60_000;
const MINUTES_PER_HOUR = 60;
const HOURS_PER_DAY = 24;
// Past two days, hours stop being the useful unit.
const DAY_CUTOFF_HOURS = 48;

/** Elapsed for something that happened, lead time for something forecast.
 *
 *  The desk holds both directions at once: an earthquake is reported after it
 *  happens, a nowcast is issued hours before. The sign chooses the wording;
 *  the magnitude is always positive, so nothing ever reads as negative time.
 */
export function relative(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / MINUTE_MS);
  const ahead = mins < 0;
  const magnitude = Math.abs(mins);
  const label = (() => {
    if (magnitude < MINUTES_PER_HOUR) return `${magnitude}m`;
    const hrs = Math.round(magnitude / MINUTES_PER_HOUR);
    if (hrs < DAY_CUTOFF_HOURS) return `${hrs}h`;
    return `${Math.round(hrs / HOURS_PER_DAY)}d`;
  })();
  return ahead ? `in ${label}` : label;
}

/** Wall-clock for a table cell, in the reader's own timezone.
 *
 *  The Command Board printed the column straight from the API, so an officer
 *  read "2026-08-23T07:02:31.741228+00:00". Microseconds and an offset are for
 *  the audit ledger, not for a person deciding what to look at next.
 */
export function shortDateTime(iso: string): string {
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return iso;
  return when.toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}
