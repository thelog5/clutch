import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { api } from "./api";
import { useAsync } from "./hooks/useAsync";
import { GamePage } from "./pages/GamePage";
import { HomePage } from "./pages/HomePage";

function Logo() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="7" fill="currentColor" />
      <path d="M5 21 L11 17 L15 19 L20 9 L27 12" fill="none" stroke="var(--ball)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function App() {
  const meta = useAsync((s) => api.meta(s), []);
  const synthetic = meta.data?.data_source === "synthetic";

  return (
    <BrowserRouter>
      {synthetic && (
        <div className="demo-banner" role="note">
          <div className="wrap">Demo data: these games are simulated by Clutch's development generator, not real NBA results.</div>
        </div>
      )}
      <header className="site-header">
        <div className="wrap">
          <Link to="/" className="brand">
            <Logo />
            Clutch
          </Link>
          <nav className="nav" aria-label="Sections">
            <Link to="/#tonight">Tonight</Link>
            <Link to="/#past">Past games</Link>
          </nav>
        </div>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<HomePage meta={meta.data} />} />
          <Route path="/game/:id" element={<GamePage />} />
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
        </div>
      </footer>
    </BrowserRouter>
  );
}
