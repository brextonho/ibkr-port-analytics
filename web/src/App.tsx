import { useState } from "react";
import { setThemePref, useThemePref, type ThemePref } from "./theme";
import { Fx } from "./views/Fx";
import { Journal } from "./views/Journal";
import { Ops } from "./views/Ops";
import { Overview } from "./views/Overview";
import { Positions } from "./views/Positions";
import { Statistics } from "./views/Statistics";

const VIEWS = {
  Overview: Overview,
  Statistics: Statistics,
  FX: Fx,
  Positions: Positions,
  "Closed trades": Journal,
  Ops: Ops,
} as const;

type ViewName = keyof typeof VIEWS;

const THEMES: { value: ThemePref; label: string }[] = [
  { value: "system", label: "Auto" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

export default function App() {
  const [active, setActive] = useState<ViewName>("Overview");
  const ActiveView = VIEWS[active];
  const theme = useThemePref();
  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">IBKR Portfolio Analytics</span>
        <nav className="tabs">
          {(Object.keys(VIEWS) as ViewName[]).map((name) => (
            <button
              key={name}
              className={name === active ? "tab active" : "tab"}
              onClick={() => setActive(name)}
            >
              {name}
            </button>
          ))}
        </nav>
        <div className="period-picker theme-toggle" role="group" aria-label="Theme">
          {THEMES.map((t) => (
            <button
              key={t.value}
              className={t.value === theme ? "period active" : "period"}
              onClick={() => setThemePref(t.value)}
            >
              {t.label}
            </button>
          ))}
        </div>
      </header>
      <main className="content">
        <ActiveView />
      </main>
    </div>
  );
}
