// One real-browser happy path, plus the two things jsdom cannot measure: whether the SVG the
// renderer emits actually lays out at 360 px, and how long the first puzzle takes to become
// interactive over real HTTP (docs/06 §6.5 asks for under 2 s on a mid-range phone over
// 3G-fast; this run is neither, so it is recorded as a floor, not as proof of the budget).
//
// Served from the committed fixture bank — see playwright.config.ts.
//
// The English here is written out rather than imported from the string table on purpose: this
// is the one suite that asserts what a person actually reads on screen. Importing the table
// would make a renamed label pass silently in the only test positioned to notice it.

import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { Manifest, Puzzle } from "../src/types/generated/puzzle";

const dir = resolve(process.cwd(), "fixtures/bank");
const manifest = JSON.parse(readFileSync(resolve(dir, "manifest.json"), "utf8")) as Manifest;
const easyShard = manifest.shards.find((s) => s.band === "easy");
if (!easyShard) throw new Error("the fixture bank has no easy band");
const easy = (JSON.parse(readFileSync(resolve(dir, easyShard.file), "utf8")) as Puzzle[])[0];
if (!easy) throw new Error("the easy shard is empty");

test("the server is serving the fixture bank", async ({ request }) => {
  // Runs first for a reason. `reuseExistingServer` will happily hand these tests a preview
  // server someone left running against `banks/v2`, and every assertion below then fails on a
  // puzzle it was never given — which reads as a renderer bug for as long as it takes to
  // notice. Checking the manifest turns that into one obvious failure.
  const served = await (await request.get("/bank/manifest.json")).json();
  expect(served.puzzles).toBe(manifest.puzzles);
  expect(served.shards.map((s: { sha256: string }) => s.sha256)).toEqual(
    manifest.shards.map((s) => s.sha256),
  );
});

test("solve a puzzle: wrong answer, hint, correct answer, replay", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: /Easy/ }).click();
  // `.goal-question` rather than a text match: the figure's accessible name also names the
  // goal, and both matching is the point of having it there.
  await expect(page.locator(".goal-question")).toHaveText(easy.goal.question);
  await expect(page.getByRole("img")).toBeVisible();

  const wrong = String(Number(easy.goal.answer.exact) + 1);
  for (const digit of wrong) await page.getByRole("button", { name: digit, exact: true }).click();
  await page.getByRole("button", { name: "Check" }).click();
  await expect(page.getByText("Not quite.")).toBeVisible();

  await page.getByRole("button", { name: /^Hint 1 of/ }).click();
  await expect(page.getByText(easy.solution[0]?.text ?? "")).toBeVisible();

  for (const digit of easy.goal.answer.exact) {
    await page.getByRole("button", { name: digit, exact: true }).click();
  }
  await page.getByRole("button", { name: "Check" }).click();

  await expect(page.getByText("Solved", { exact: true })).toBeVisible();
  await expect(page.getByText(`The answer is ${easy.goal.answer.display}.`)).toBeVisible();

  await page.getByRole("button", { name: "Walk through the solution" }).click();
  const last = easy.solution[easy.solution.length - 1];
  await expect(page.getByText(last?.text ?? "")).toBeVisible();
});

test("the streak survives a reload", async ({ page }) => {
  // localStorage in a real browser, which is the part the jsdom suite substitutes for.
  await page.goto("/");
  await page.getByRole("button", { name: /Easy/ }).click();
  for (const digit of easy.goal.answer.exact) {
    await page.getByRole("button", { name: digit, exact: true }).click();
  }
  await page.getByRole("button", { name: "Check" }).click();
  await page.getByRole("button", { name: "Back to home" }).click();

  await page.reload();
  await expect(page.getByRole("region", { name: "Practice" }).getByText(/1 of/)).toBeVisible();
});

test("the figure fits a 360 px viewport", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  await page.goto("/");
  await page.getByRole("button", { name: /Easy/ }).click();

  const figure = page.getByRole("img");
  const box = await figure.boundingBox();
  expect(box).not.toBeNull();
  expect(box?.width).toBeLessThanOrEqual(360);
  // A figure squeezed to nothing renders but cannot be read.
  expect(box?.width).toBeGreaterThan(280);

  // Nothing may scroll sideways — the classic phone-layout failure.
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);

  // The goal mark has to be legible, not just present.
  const goal = page.locator(".fig-arc.is-goal text");
  await expect(goal).toHaveText("?");
  const goalBox = await goal.boundingBox();
  expect(goalBox?.height ?? 0).toBeGreaterThan(8);
});

test("first puzzle is interactive quickly", async ({ page }) => {
  const started = Date.now();
  await page.goto("/");
  await page.getByRole("button", { name: /Easy/ }).click();
  await expect(page.getByRole("button", { name: "Check" })).toBeVisible();
  const elapsed = Date.now() - started;
  // Local preview over loopback, so this is a regression guard rather than the docs/06 budget:
  // it catches a bundle or a fetch waterfall that has grown by an order of magnitude.
  console.log(`first puzzle interactive in ${elapsed} ms (loopback, desktop-class CPU)`);
  expect(elapsed).toBeLessThan(4000);
});
