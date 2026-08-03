// The whole loop, in jsdom: manifest → home → practice → wrong answer → hint → solve →
// complete → replay. The same path the Playwright run walks in a real browser; this one is
// here to fail fast and to assert the things a browser test cannot see cheaply, like which
// shards were fetched.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { strings } from "./strings/en";
import { BASE, fixtureManifest, readFixture, serveFixtureBank } from "./test/fixtures";
import type { Puzzle } from "./types/generated/puzzle";

afterEach(() => vi.unstubAllGlobals());

const easy = (): Puzzle => {
  const shard = fixtureManifest().shards.find((s) => s.band === "easy");
  if (!shard) throw new Error("the fixture bank has no easy band");
  const puzzles = JSON.parse(readFixture(shard.file)) as Puzzle[];
  const first = puzzles[0];
  if (!first) throw new Error("the easy shard is empty");
  return first;
};

const start = async () => {
  serveFixtureBank();
  const user = userEvent.setup();
  render(<App base={BASE} />);
  await screen.findByText(strings.home.practice);
  return user;
};

const typeAnswer = async (user: ReturnType<typeof userEvent.setup>, digits: string) => {
  for (const digit of digits) await user.click(screen.getByRole("button", { name: digit }));
  await user.click(screen.getByRole("button", { name: strings.player.submit }));
};

describe("loading", () => {
  it("shows the bands the manifest declares", async () => {
    await start();
    for (const band of Object.keys(fixtureManifest().by_band)) {
      const label = strings.bands[band as keyof typeof strings.bands];
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("says a preview bank is a preview", async () => {
    // The manifest's `shippable: false` has to reach the screen, not just the file.
    await start();
    expect(screen.getByText(strings.settings.bankPreview)).toBeInTheDocument();
  });

  it("explains a missing bank instead of showing an empty app", async () => {
    vi.stubGlobal("fetch", () => Promise.resolve(new Response("", { status: 404 })));
    render(<App base={BASE} />);
    expect(await screen.findByText(strings.status.bankMissing)).toBeInTheDocument();
  });

  it("does not fetch a shard until a puzzle is opened", async () => {
    const served = serveFixtureBank();
    render(<App base={BASE} />);
    await screen.findByText(strings.home.practice);
    // The daily card resolves one puzzle, so exactly one shard is warranted — not all four.
    await waitFor(() => expect(served.requested.length).toBeGreaterThan(1));
    expect(served.requested.length).toBeLessThanOrEqual(2);
  });
});

describe("playing a puzzle", () => {
  it("walks wrong answer → hint → solve → complete → replay", async () => {
    const puzzle = easy();
    const user = await start();

    await user.click(screen.getByRole("button", { name: new RegExp(strings.bands.easy) }));
    expect(await screen.findByText(puzzle.goal.question)).toBeInTheDocument();

    // The givens the bank wrote, verbatim.
    for (const given of puzzle.given) {
      expect(screen.getByRole("button", { name: given.display })).toBeInTheDocument();
    }

    const wrong = String(Number(puzzle.goal.answer.exact) + 1);
    await typeAnswer(user, wrong);
    expect(screen.getByText(strings.player.wrong)).toBeInTheDocument();
    expect(screen.getByText(strings.player.attemptsOne)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^Hint 1 of/ }));
    const step = puzzle.solution[0];
    expect(screen.getByText(step?.text ?? "")).toBeInTheDocument();

    await typeAnswer(user, puzzle.goal.answer.exact);

    expect(await screen.findByText(strings.complete.solved)).toBeInTheDocument();
    expect(
      screen.getByText(`The answer is ${puzzle.goal.answer.display}.`),
    ).toBeInTheDocument();

    // Replay is opt-in for a solve, and shows every step when asked for.
    expect(screen.queryByText(puzzle.solution[puzzle.solution.length - 1]?.text ?? "")).toBeNull();
    await user.click(screen.getByRole("button", { name: strings.complete.replay }));
    for (const s of puzzle.solution) expect(screen.getByText(s.text)).toBeInTheDocument();
  });

  it("highlights the elements a given names", async () => {
    const puzzle = easy();
    const given = puzzle.given.find((g) => (g.highlights ?? []).length > 0);
    if (!given) throw new Error("no given in the fixture carries highlights");
    const user = await start();
    await user.click(screen.getByRole("button", { name: new RegExp(strings.bands.easy) }));
    await screen.findByText(puzzle.goal.question);

    const figure = screen.getByRole("img");
    expect(figure.querySelectorAll(".is-on")).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: given.display }));
    expect(figure.querySelectorAll(".is-on").length).toBeGreaterThan(0);
  });

  it("counts a solve towards the band, and the streak only for the daily", async () => {
    const user = await start();
    await user.click(screen.getByRole("button", { name: new RegExp(strings.bands.easy) }));
    await typeAnswer(user, easy().goal.answer.exact);
    await screen.findByText(strings.complete.solved);
    await user.click(screen.getByRole("button", { name: strings.complete.home }));

    const practice = screen.getByRole("region", { name: strings.home.practice });
    expect(within(practice).getByText(/1 of/)).toBeInTheDocument();
    const streak = screen.getByText(strings.home.streak).previousSibling;
    expect(streak).toHaveTextContent("0");
  });

  it("marks a solve assisted once every hint was taken", async () => {
    const puzzle = easy();
    const user = await start();
    await user.click(screen.getByRole("button", { name: new RegExp(strings.bands.easy) }));
    await screen.findByText(puzzle.goal.question);
    for (let i = 0; i < puzzle.solution.length; i++) {
      await user.click(screen.getByRole("button", { name: /^Hint \d+ of/ }));
    }
    await typeAnswer(user, puzzle.goal.answer.exact);
    expect(await screen.findByText(strings.complete.assisted)).toBeInTheDocument();
  });

  it("shows the solution on give-up without calling it a solve", async () => {
    const puzzle = easy();
    const user = await start();
    await user.click(screen.getByRole("button", { name: new RegExp(strings.bands.easy) }));
    await screen.findByText(puzzle.goal.question);
    await user.click(screen.getByRole("button", { name: strings.player.giveUp }));
    expect(await screen.findByText(strings.complete.revealed)).toBeInTheDocument();
    for (const s of puzzle.solution) expect(screen.getByText(s.text)).toBeInTheDocument();
  });
});

describe("settings", () => {
  it("names what the preview bank is still missing", async () => {
    const user = await start();
    await user.click(screen.getByRole("button", { name: strings.nav.settings }));
    const missing = fixtureManifest().missing_for_shippable;
    expect(screen.getByText(new RegExp(missing[0] ?? ""))).toBeInTheDocument();
  });

  it("applies a theme choice to the document", async () => {
    const user = await start();
    await user.click(screen.getByRole("button", { name: strings.nav.settings }));
    await user.click(screen.getByRole("button", { name: strings.settings.themeDark }));
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  });

  it("clears local data on reset", async () => {
    const user = await start();
    await user.click(screen.getByRole("button", { name: new RegExp(strings.bands.easy) }));
    await typeAnswer(user, easy().goal.answer.exact);
    await screen.findByText(strings.complete.solved);
    await user.click(screen.getByRole("button", { name: strings.complete.home }));
    await user.click(screen.getByRole("button", { name: strings.nav.settings }));
    await user.click(screen.getByRole("button", { name: strings.settings.reset }));
    await user.click(screen.getByRole("button", { name: strings.settings.resetConfirm }));
    await user.click(screen.getByRole("button", { name: strings.nav.back }));
    const practice = screen.getByRole("region", { name: strings.home.practice });
    expect(within(practice).queryByText(/1 of/)).toBeNull();
    expect(within(practice).getAllByText(strings.home.bandEmpty)).toHaveLength(
      fixtureManifest().shards.length,
    );
  });
});
