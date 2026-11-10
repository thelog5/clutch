import { useEffect } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import { Link, useParams } from "react-router-dom";
import remarkGfm from "remark-gfm";
import { findPost, POSTS, type Post } from "../filmroom";

const longDate = (iso: string) =>
  iso
    ? new Date(`${iso}T12:00:00`).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })
    : "";

function useTitle(title: string) {
  useEffect(() => {
    document.title = title;
    return () => {
      document.title = "Clutch";
    };
  }, [title]);
}

// Markdown is rendered as React elements; raw HTML in a post is dropped, never injected.
const MD: Components = {
  a: ({ href = "", children }) =>
    /^https?:\/\//.test(href) ? (
      <a href={href} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    ) : (
      <a href={href}>{children}</a>
    ),
  img: ({ src = "", alt = "" }) => <img src={typeof src === "string" ? src : ""} alt={alt} loading="lazy" decoding="async" />,
  table: ({ children }) => (
    <div className="film-table">
      <table>{children}</table>
    </div>
  ),
};

function PostMeta({ post }: { post: Post }) {
  return (
    <p className="film-meta num">
      <time dateTime={post.date}>{longDate(post.date)}</time> · {post.minutes} min read
      {post.draft && <span className="pill">Draft, only visible locally</span>}
    </p>
  );
}

export function FilmRoomPage() {
  useTitle("Film Room · Clutch");
  return (
    <div className="wrap film">
      <section className="hero">
        <h1 className="hero-title display">Film Room</h1>
        <p className="lede">
          Notes from building Clutch: what broke, what I tried, and what the numbers said. Like game tape, the misses teach the
          most.
        </p>
      </section>
      {POSTS.length === 0 ? (
        <p className="notice">
          <strong>No posts yet.</strong> The first one is on its way.
        </p>
      ) : (
        <ol className="film-list">
          {POSTS.map((p) => (
            <li key={p.slug}>
              <Link to={`/film-room/${p.slug}`} className="card film-card">
                <h2 className="film-card-title">{p.title}</h2>
                {p.summary && <p className="film-summary">{p.summary}</p>}
                <PostMeta post={p} />
              </Link>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

export function FilmRoomPost() {
  const { slug = "" } = useParams();
  const post = findPost(slug);
  useTitle(post ? `${post.title} · Film Room` : "Film Room · Clutch");

  if (!post) {
    return (
      <div className="wrap film">
        <p className="notice" style={{ marginTop: 32 }}>
          <strong>There's no post at this address.</strong> See all posts in the <Link to="/film-room">Film Room</Link>.
        </p>
      </div>
    );
  }
  return (
    <div className="wrap film">
      <Link to="/film-room" className="back">
        Film Room
      </Link>
      <article className="film-post">
        <header>
          <h1 className="page-title display">{post.title}</h1>
          <PostMeta post={post} />
        </header>
        <div className="film-body">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD}>
            {post.body}
          </ReactMarkdown>
        </div>
      </article>
    </div>
  );
}
