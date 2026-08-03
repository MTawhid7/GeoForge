// The app shell: bank loading, which screen is showing, and the persistence around a result.
//
// Screen state is a plain discriminated union in `useState` — no router and no state library
// (docs/06 §6.5). Four screens with no shareable URLs do not need either, and the constraint
// is worth keeping until something actually needs breaking it.

import { useCallback, useEffect, useMemo, useState } from "react";
import { Bank, BankError, loadManifest } from "./bank/load";
import { dailyIndex, dayKey } from "./bank/daily";
import { CompleteScreen } from "./screens/CompleteScreen";
import { HomeScreen } from "./screens/HomeScreen";
import { PlayerScreen } from "./screens/PlayerScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import type { PlayerState } from "./player/state";
import { strings } from "./strings/en";
import { defaultSeen, defaultSettings, defaultStats, recordResult, store } from "./store/local";
import type { Outcome, Settings } from "./store/local";
import type { Puzzle } from "./types/generated/puzzle";

type Screen =
  | { name: "home" }
  | { name: "settings" }
  | { name: "player"; puzzle: Puzzle; daily: boolean; band: string; index: number }
  | { name: "complete"; puzzle: Puzzle; outcome: Outcome; result: PlayerState; daily: boolean };

type Load =
  | { state: "loading" }
  | { state: "ready"; bank: Bank }
  | { state: "failed"; kind: "missing" | "unreadable" };

export interface AppProps {
  /** Overridden in tests so a fixture bank can be served from anywhere. */
  base?: string;
  now?: () => Date;
}

export function App({ base, now = () => new Date() }: AppProps = {}) {
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [screen, setScreen] = useState<Screen>({ name: "home" });
  // localStorage is synchronous, so it is read while initialising rather than in an effect —
  // an effect would render the home screen once with a zeroed streak and then correct it.
  const [stats, setStats] = useState(store.stats);
  const [settings, setSettings] = useState(store.settings);
  const [seen, setSeen] = useState(store.seen);
  const [daily, setDaily] = useState<Puzzle | null>(null);

  useEffect(() => {
    let live = true;
    void (async () => {
      try {
        const manifest = await loadManifest(base);
        if (live) setLoad({ state: "ready", bank: new Bank(manifest, base) });
      } catch (error) {
        const kind = error instanceof BankError ? error.kind : "missing";
        if (live) setLoad({ state: "failed", kind });
      }
    })();
    return () => {
      live = false;
    };
  }, [base]);

  const today = useMemo(() => dayKey(now()), [now]);

  useEffect(() => {
    if (load.state !== "ready") return;
    let live = true;
    const index = dailyIndex(today, load.bank.manifest.puzzles);
    if (index === null) return;
    // A shard that fails to load leaves the daily card in its loading state; practice still
    // works, because one unreachable file should not take the app down.
    void load.bank
      .atGlobal(index)
      .then((puzzle) => {
        if (live) setDaily(puzzle);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [load, today]);

  useEffect(() => {
    const root = document.documentElement;
    if (settings.theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", settings.theme);
  }, [settings.theme]);

  const saveSettings = (next: Settings) => {
    setSettings(next);
    store.saveSettings(next);
  };

  const playBand = useCallback(
    async (band: string) => {
      if (load.state !== "ready") return;
      const total = load.bank.countIn(band);
      if (total === 0) return;
      const index = (seen.next[band] ?? 0) % total;
      const puzzle = await load.bank.at(band, index);
      if (puzzle) setScreen({ name: "player", puzzle, daily: false, band, index });
    },
    [load, seen],
  );

  const finish = (outcome: Outcome, result: PlayerState) => {
    if (screen.name !== "player") return;
    const { puzzle, daily: isDaily, band, index } = screen;
    const nextStats = recordResult(stats, puzzle.id, outcome, {
      daily: isDaily,
      day: today,
      band: puzzle.difficulty.band,
    });
    setStats(nextStats);
    store.saveStats(nextStats);

    const ids = seen.ids.includes(puzzle.id) ? seen.ids : [...seen.ids, puzzle.id];
    const nextSeen = isDaily
      ? { ...seen, ids }
      : { ...seen, ids, next: { ...seen.next, [band]: index + 1 } };
    setSeen(nextSeen);
    store.saveSeen(nextSeen);

    setScreen({ name: "complete", puzzle, outcome, result, daily: isDaily });
  };

  const nextAfterComplete = () => {
    if (screen.name !== "complete") return;
    const band = screen.puzzle.difficulty.band;
    setScreen({ name: "home" });
    void playBand(band);
  };

  if (load.state === "loading") {
    return <p className="status">{strings.status.loading}</p>;
  }
  if (load.state === "failed") {
    return (
      <div className="status">
        <p>
          {load.kind === "unreadable" ? strings.status.bankUnreadable : strings.status.bankMissing}
        </p>
        {load.kind === "missing" && <p className="muted">{strings.status.bankMissingHint}</p>}
      </div>
    );
  }

  switch (screen.name) {
    case "player":
      return (
        <PlayerScreen
          puzzle={screen.puzzle}
          showLabels={settings.showLabels}
          onFinish={finish}
          onExit={() => setScreen({ name: "home" })}
        />
      );
    case "complete":
      return (
        <CompleteScreen
          puzzle={screen.puzzle}
          outcome={screen.outcome}
          result={screen.result}
          showLabels={settings.showLabels}
          onNext={nextAfterComplete}
          onHome={() => setScreen({ name: "home" })}
        />
      );
    case "settings":
      return (
        <SettingsScreen
          bank={load.bank}
          settings={settings}
          onChange={saveSettings}
          onReset={() => {
            store.reset();
            setStats(defaultStats);
            setSettings(defaultSettings);
            setSeen(defaultSeen);
          }}
          onBack={() => setScreen({ name: "home" })}
        />
      );
    case "home":
      return (
        <HomeScreen
          bank={load.bank}
          stats={stats}
          daily={daily}
          onPlayDaily={() => {
            if (daily) {
              setScreen({
                name: "player",
                puzzle: daily,
                daily: true,
                band: daily.difficulty.band,
                index: 0,
              });
            }
          }}
          onPlayBand={(band) => void playBand(band)}
          onSettings={() => setScreen({ name: "settings" })}
        />
      );
  }
}
