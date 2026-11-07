import { useEffect, useState } from "react";

export interface ThemeColors {
  paper: string;
  surface: string;
  ink: string;
  ink2: string;
  ink3: string;
  line: string;
  lineSoft: string;
  shade: string;
  ball: string;
  up: string;
  down: string;
}

function read(): { dark: boolean; colors: ThemeColors } {
  const s = getComputedStyle(document.documentElement);
  const v = (name: string) => s.getPropertyValue(name).trim();
  return {
    dark: window.matchMedia("(prefers-color-scheme: dark)").matches,
    colors: {
      paper: v("--paper"),
      surface: v("--surface"),
      ink: v("--ink"),
      ink2: v("--ink-2"),
      ink3: v("--ink-3"),
      line: v("--line"),
      lineSoft: v("--line-soft"),
      shade: v("--shade"),
      ball: v("--ball"),
      up: v("--up"),
      down: v("--down"),
    },
  };
}

/** Resolved CSS color tokens (SVG attributes need real values, not var()). */
export function useTheme() {
  const [theme, setTheme] = useState(read);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setTheme(read());
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return theme;
}

export function useMediaQuery(query: string): boolean {
  const [match, setMatch] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const onChange = () => setMatch(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [query]);
  return match;
}
