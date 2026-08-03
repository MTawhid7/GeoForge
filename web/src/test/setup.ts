import "@testing-library/jest-dom/vitest";
import { JSDOM } from "jsdom";
import { afterEach } from "vitest";

// Node 22+ ships its own `localStorage` global, and it is already defined by the time vitest's
// jsdom environment installs the window — so the app's bare `localStorage` reaches an object
// with no `getItem`/`clear` at all. Pin a real jsdom `Storage` over it, rather than a
// hand-rolled stub, so what the store is tested against is a spec implementation.
// The browser's own storage is exercised end to end by the Playwright run.
const { window: storageWindow } = new JSDOM("", { url: "https://geoforge.test/" });
Object.defineProperty(globalThis, "localStorage", {
  value: storageWindow.localStorage,
  configurable: true,
  writable: true,
});

afterEach(() => {
  localStorage.clear();
});
