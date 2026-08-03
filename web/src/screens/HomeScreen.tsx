import type { Bank } from "../bank/load";
import { fill, strings } from "../strings/en";
import type { Stats } from "../store/local";
import type { Puzzle } from "../types/generated/puzzle";

export interface HomeScreenProps {
  bank: Bank;
  stats: Stats;
  /** Today's puzzle, or null while it is still being fetched. */
  daily: Puzzle | null;
  onPlayDaily: () => void;
  onPlayBand: (band: string) => void;
  onSettings: () => void;
}

const bandName = (band: string): string =>
  strings.bands[band as keyof typeof strings.bands] ?? band;

export function HomeScreen({
  bank,
  stats,
  daily,
  onPlayDaily,
  onPlayBand,
  onSettings,
}: HomeScreenProps) {
  const dailyResult = daily ? stats.results[daily.id] : undefined;
  const solvedTotal = Object.keys(stats.results).length;

  return (
    <div className="screen home-screen">
      <header className="bar">
        <span className="bar-title bar-brand">{strings.app.name}</span>
        <button type="button" className="bar-button" onClick={onSettings}>
          {strings.nav.settings}
        </button>
      </header>

      <div className="home-body">
        <section className="streaks" aria-label={strings.home.streak}>
          <div className="stat">
            <span className="stat-value">{stats.streak}</span>
            <span className="stat-label">{strings.home.streak}</span>
          </div>
          <div className="stat">
            <span className="stat-value">{stats.bestStreak}</span>
            <span className="stat-label">{strings.home.streakBest}</span>
          </div>
          <div className="stat">
            <span className="stat-value">{solvedTotal}</span>
            <span className="stat-label">{strings.home.solvedCount}</span>
          </div>
        </section>

        <section className="daily-card">
          <h2 className="card-title">{strings.home.daily}</h2>
          {daily === null ? (
            <p className="muted">{strings.status.loading}</p>
          ) : (
            <>
              <p className="daily-line">
                {bandName(daily.difficulty.band)} ·{" "}
                {fill(strings.player.depth, { n: daily.difficulty.depth })}
              </p>
              {dailyResult !== undefined && (
                <p className="muted">
                  {dailyResult === "solved" ? strings.home.dailyDone : strings.home.dailyAssisted}
                </p>
              )}
              <button type="button" className="primary" onClick={onPlayDaily}>
                {dailyResult === undefined ? strings.home.play : strings.home.resume}
              </button>
            </>
          )}
        </section>

        <section className="practice" aria-label={strings.home.practice}>
          <h2 className="card-title">{strings.home.practice}</h2>
          {bank.bands().length === 0 ? (
            <p className="muted">{strings.home.noBand}</p>
          ) : (
            <ul className="band-list">
              {bank.bands().map((band) => {
                const total = bank.countIn(band);
                const solved = stats.byBand[band] ?? 0;
                return (
                  <li key={band}>
                    <button type="button" className="band-row" onClick={() => onPlayBand(band)}>
                      <span className={`band-name band-${band}`}>{bandName(band)}</span>
                      <span className="band-progress">
                        {solved === 0
                          ? strings.home.bandEmpty
                          : fill(strings.home.bandProgress, { solved, total })}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {!bank.manifest.shippable && (
          <p className="preview-note">{strings.settings.bankPreview}</p>
        )}
      </div>
    </div>
  );
}
