export function RiskDial({
  value,
  label,
  note,
}: {
  value: number | null;
  label: string;
  note?: string;
}) {
  const radius = 36;
  const circ = 2 * Math.PI * radius;
  const ratio =
    value == null
      ? 0
      : value > 1
        ? Math.min(value / 100, 1)
        : Math.min(Math.max(value, 0), 1);
  const offset = circ * (1 - ratio);
  const missing = value == null;

  return (
    <figure className={`dial${missing ? " dial--muted" : ""}`}>
      <svg viewBox="0 0 96 96" width="96" height="96" aria-hidden>
        <circle className="dial__track" cx="48" cy="48" r={radius} />
        <circle
          className="dial__arc"
          cx="48"
          cy="48"
          r={radius}
          strokeDasharray={circ}
          strokeDashoffset={offset}
          transform="rotate(-90 48 48)"
        />
      </svg>
      <figcaption>
        <span className="dial__value mono">
          {value == null ? "n/a" : value > 1 ? `${value}%` : value}
        </span>
        <span className="dial__label">{label}</span>
        {note ? <span className="dial__note muted">{note}</span> : null}
      </figcaption>
    </figure>
  );
}
