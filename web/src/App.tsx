import { Suspense, lazy } from "react";
import { Outlet, Route, Routes } from "react-router";
import { MotionConfig } from "motion/react";
import { TopNav } from "./components/TopNav";
import { Home } from "./pages/Home";
import { Technical } from "./pages/Technical";

// The tour carries React Flow — split it out of the shell chunk.
const ArchitectureTour = lazy(() =>
  import("./pages/ArchitectureTour").then((m) => ({
    default: m.ArchitectureTour,
  }))
);

function Layout() {
  return (
    <div className="flex h-dvh flex-col bg-surface font-sans text-ink">
      <TopNav />
      <main className="flex min-h-0 flex-1 flex-col overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}

export function App() {
  return (
    <MotionConfig reducedMotion="user">
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="technical" element={<Technical />} />
          <Route
          path="tour"
          element={
            <Suspense
              fallback={
                <div
                  data-theme="dark"
                  className="flex min-h-0 flex-1 items-center justify-center bg-surface text-ink-muted"
                >
                  Loading the tour…
                </div>
              }
            >
              <ArchitectureTour />
            </Suspense>
          }
        />
        </Route>
      </Routes>
    </MotionConfig>
  );
}
