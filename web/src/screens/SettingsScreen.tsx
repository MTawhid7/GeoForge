import { useState } from "react";
import type { Bank } from "../bank/load";
import { fill, strings } from "../strings/en";
import type { Settings, Theme } from "../store/local";

export interface SettingsScreenProps {
  bank: Bank;
  settings: Settings;
  onChange: (settings: Settings) => void;
  onReset: () => void;
  onBack: () => void;
}

const THEMES: { value: Theme; label: string }[] = [
  { value: "system", label: strings.settings.themeSystem },
  { value: "light", label: strings.settings.themeLight },
  { value: "dark", label: strings.settings.themeDark },
];

export function SettingsScreen({
  bank,
  settings,
  onChange,
  onReset,
  onBack,
}: SettingsScreenProps) {
  const [confirming, setConfirming] = useState(false);
  const [done, setDone] = useState(false);
  const manifest = bank.manifest;

  return (
    <div className="screen settings-screen">
      <header className="bar">
        <button type="button" className="bar-button" onClick={onBack}>
          {strings.nav.back}
        </button>
        <span className="bar-title">{strings.settings.title}</span>
        <span className="bar-spacer" />
      </header>

      <div className="settings-body">
        <fieldset className="setting">
          <legend>{strings.settings.theme}</legend>
          <div className="choice-row">
            {THEMES.map((theme) => (
              <button
                key={theme.value}
                type="button"
                className={`choice${settings.theme === theme.value ? " is-active" : ""}`}
                aria-pressed={settings.theme === theme.value}
                onClick={() => onChange({ ...settings, theme: theme.value })}
              >
                {theme.label}
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset className="setting">
          <legend>{strings.settings.labels}</legend>
          <div className="choice-row">
            <button
              type="button"
              className={`choice${settings.showLabels ? " is-active" : ""}`}
              aria-pressed={settings.showLabels}
              onClick={() => onChange({ ...settings, showLabels: true })}
            >
              {strings.settings.labelsOn}
            </button>
            <button
              type="button"
              className={`choice${!settings.showLabels ? " is-active" : ""}`}
              aria-pressed={!settings.showLabels}
              onClick={() => onChange({ ...settings, showLabels: false })}
            >
              {strings.settings.labelsOff}
            </button>
          </div>
        </fieldset>

        <section className="setting">
          <h2>{strings.settings.about}</h2>
          <dl className="about">
            <div>
              <dt>{strings.settings.bankPuzzles}</dt>
              <dd>{manifest.puzzles}</dd>
            </div>
            <div>
              <dt>{strings.settings.bankSeed}</dt>
              <dd>{manifest.seed}</dd>
            </div>
            <div>
              <dt>{strings.settings.bankEngines}</dt>
              <dd>
                {manifest.generation_engine} / {manifest.validator_engine}
              </dd>
            </div>
            <div>
              <dt>{strings.settings.bankGenerator}</dt>
              <dd>{manifest.generator_version}</dd>
            </div>
          </dl>
          {/* A preview bank says so on the screen, not only in a file nobody opens. */}
          {!manifest.shippable && (
            <p className="preview-note">
              {strings.settings.bankPreview}
              <br />
              {fill(strings.settings.bankMissing, {
                list: manifest.missing_for_shippable.join(", "),
              })}
            </p>
          )}
        </section>

        <section className="setting">
          <h2>{strings.settings.reset}</h2>
          <p className="muted">{strings.settings.resetHint}</p>
          {done ? (
            <p role="status">{strings.settings.resetDone}</p>
          ) : confirming ? (
            <button
              type="button"
              className="danger"
              onClick={() => {
                onReset();
                setConfirming(false);
                setDone(true);
              }}
            >
              {strings.settings.resetConfirm}
            </button>
          ) : (
            <button type="button" className="secondary" onClick={() => setConfirming(true)}>
              {strings.settings.reset}
            </button>
          )}
        </section>
      </div>
    </div>
  );
}
