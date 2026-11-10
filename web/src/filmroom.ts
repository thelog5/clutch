// Film Room posts: Markdown files in src/film-room/posts/ (format: src/film-room/README.md).
// The film-room plugin in vite.config.ts turns them into this module; drafts are
// only included by the dev server, so production builds never contain them.
import RAW from "virtual:film-room";

export interface Post {
  slug: string;
  title: string;
  date: string; // YYYY-MM-DD
  summary: string;
  draft: boolean;
  body: string; // Markdown
  minutes: number;
}

/** "---\nkey: value\n---\nbody" -> ({key: value}, body). Values are plain strings; quotes are optional. */
function frontMatter(raw: string): { meta: Record<string, string>; body: string } {
  const m = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!m) return { meta: {}, body: raw };
  const meta: Record<string, string> = {};
  for (const line of m[1].split(/\r?\n/)) {
    const i = line.indexOf(":");
    if (i > 0) meta[line.slice(0, i).trim()] = line.slice(i + 1).trim().replace(/^(["'])(.*)\1$/, "$2");
  }
  return { meta, body: m[2] };
}

/** Newest first. Locally this includes drafts (marked as such); in production it doesn't. */
export const POSTS: Post[] = RAW.map(({ slug, raw }) => {
  const { meta, body } = frontMatter(raw);
  return {
    slug,
    title: meta.title || slug,
    date: meta.date || "",
    summary: meta.summary || "",
    draft: meta.draft === "true",
    body,
    minutes: Math.max(1, Math.round(body.split(/\s+/).length / 220)),
  };
}).sort((a, b) => b.date.localeCompare(a.date));

export const findPost = (slug: string): Post | undefined => POSTS.find((p) => p.slug === slug);
