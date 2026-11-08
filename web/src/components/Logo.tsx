// The Clutch mark: a basketball with a rising win-probability line breaking out of it.
// Ball strokes use currentColor; the line is the brand orange. The line is drawn twice,
// first wide in the background color (--logo-knockout) so it cuts cleanly through the ball.

const LINE = "M3 39.5 L16.5 30.5 L23 34.5 L37.6 16.2";
const HEAD = "M45.5 6.5 L43.4 18.4 L33.6 10.4 Z";

export function Mark({ size = 32, className }: { size?: number; className?: string }) {
  return (
    <svg viewBox="0 0 48 48" width={size} height={size} className={className} aria-hidden focusable="false">
      <g fill="none" stroke="currentColor" strokeWidth="3.4" strokeLinecap="round">
        <circle cx="21" cy="27" r="16" />
        <path d="M21 11 L21 43" />
        <path d="M10 15 C17 21 17 33 10 39" />
        <path d="M32 15 C25 21 25 33 32 39" />
      </g>
      <g stroke="var(--logo-knockout)" strokeLinejoin="round">
        <path d={LINE} fill="none" strokeWidth="9" strokeLinecap="round" />
        <path d={HEAD} fill="var(--logo-knockout)" strokeWidth="5" />
      </g>
      <g stroke="var(--brand)" strokeLinejoin="round">
        <path d={LINE} fill="none" strokeWidth="4.2" strokeLinecap="round" />
        <path d={HEAD} fill="var(--brand)" strokeWidth="1.2" />
      </g>
    </svg>
  );
}

/** Mark + wordmark, as used in the header. */
export function Brand() {
  return (
    <span className="brand-lockup">
      <Mark size={38} />
      <span className="wordmark">Clutch</span>
    </span>
  );
}
