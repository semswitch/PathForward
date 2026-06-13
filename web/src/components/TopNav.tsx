import { NavLink } from "react-router";

const LINKS = [
  { to: "/", label: "Home" },
  { to: "/tour", label: "Architecture Tour" },
  { to: "/technical", label: "How it works" },
];

export function TopNav() {
  return (
    <header className="border-b border-line bg-surface-raised">
      <nav
        aria-label="Primary"
        className="mx-auto flex h-14 max-w-5xl items-center gap-6 px-6"
      >
        <span className="text-base font-semibold tracking-tight">
          PathForward<span className="text-brand-500">.</span>
        </span>
        <div className="flex items-center gap-1">
          {LINKS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                [
                  "rounded-full px-3 py-1.5 text-sm transition-colors",
                  isActive
                    ? "bg-brand-500/10 font-medium text-brand-600"
                    : "text-ink-muted hover:text-ink",
                ].join(" ")
              }
            >
              {label}
            </NavLink>
          ))}
        </div>
      </nav>
    </header>
  );
}
