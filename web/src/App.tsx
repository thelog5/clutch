import { lazy, Suspense } from "react";
import { BrowserRouter, Link, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api";
import { Brand } from "./components/Logo";
import { useAsync } from "./hooks/useAsync";
import { MetaContext } from "./meta";
import { SNAPSHOT } from "./snapshot";
import { GamePage } from "./pages/GamePage";
import { HomePage } from "./pages/HomePage";
import { HowPage } from "./pages/HowPage";

// The Film Room carries the Markdown renderer, so it loads only when someone opens it.
const FilmRoomPage = lazy(() => import("./pages/FilmRoomPage").then((m) => ({ default: m.FilmRoomPage })));
const FilmRoomPost = lazy(() => import("./pages/FilmRoomPage").then((m) => ({ default: m.FilmRoomPost })));

const NAV = [
  { to: "/#live", label: "Live", match: (path: string, hash: string) => path === "/" && (hash === "" || hash === "#live") },
  { to: "/#tonight", label: "Tonight", match: (path: string, hash: string) => path === "/" && hash === "#tonight" },
  { to: "/#past", label: "Past games", match: (path: string, hash: string) => path === "/" && hash === "#past" },
  { to: "/how", label: "How it's built", match: (path: string) => path === "/how" },
  { to: "/film-room", label: "Film Room", match: (path: string) => path.startsWith("/film-room") },
];

function Header() {
  const { pathname, hash } = useLocation();
  return (
    <header className="site-header">
      <div className="wrap">
        <Link to="/" className="brand" aria-label="Clutch, home">
          <Brand />
        </Link>
        <nav className="nav" aria-label="Sections">
          {NAV.map((n) => (
            <Link key={n.to} to={n.to} aria-current={n.match(pathname, hash) ? "page" : undefined}>
              {n.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}

export function App() {
  // Seasons and teams change rarely: the saved copy serves until the API answers.
  const meta = useAsync((s) => api.meta(s), []);

  return (
    <MetaContext.Provider value={meta.data ?? SNAPSHOT.meta}>
      <BrowserRouter>
        <Header />
        <main>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/game/:id" element={<GamePage />} />
            <Route path="/how" element={<HowPage />} />
            <Route
              path="/film-room"
              element={
                <Suspense fallback={<div className="wrap" />}>
                  <FilmRoomPage />
                </Suspense>
              }
            />
            <Route
              path="/film-room/:slug"
              element={
                <Suspense fallback={<div className="wrap" />}>
                  <FilmRoomPost />
                </Suspense>
              }
            />
            <Route
              path="*"
              element={
                <div className="wrap">
                  <p className="notice" style={{ marginTop: 32 }}>
                    <strong>There's nothing at this address.</strong> Go back to the <Link to="/">games list</Link>.
                  </p>
                </div>
              }
            />
          </Routes>
        </main>
        <footer className="site-footer">
          <div className="wrap">
            <p>
              Clutch is a sports analytics project. Win probabilities come from a model trained on three seasons of NBA play-by-play and
              tested on a later season it never saw.
            </p>
            <p>Play-by-play from NBA.com via nba_api. Not affiliated with the NBA or its teams.</p>
            <p className="signature">made by the log ✝</p>
          </div>
        </footer>
      </BrowserRouter>
    </MetaContext.Provider>
  );
}
