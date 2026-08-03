// CLAUDE.md: "no hardcoded UI strings (string table only)".
//
// Enforced by reading the source rather than by a lint rule, because a rule cannot tell a
// user-visible label from an ARIA role name or a CSS class. This scans the JSX text nodes —
// the things a player actually reads — and requires each to be an expression, not a literal.

import { readFileSync, readdirSync, statSync } from "node:fs";
import { basename, join, resolve } from "node:path";
import ts from "typescript";
import { describe, expect, it } from "vitest";
import { fill, strings } from "./en";

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) return sources(path);
    const scan = path.endsWith(".tsx") && !path.endsWith(".test.tsx");
    // `probe-literal.tsx` holds deliberate offenders for the self-check below.
    return scan && !path.endsWith("probe-literal.tsx") ? [path] : [];
  });
}

/** Attributes a screen reader or tooltip will read out loud. */
const SPOKEN = new Set(["aria-label", "title", "placeholder", "alt"]);

/**
 * Literal user-visible text in one component.
 *
 * Parsed with the TypeScript compiler rather than matched with a regex: `Map<string, number>`
 * and `a > b` both look exactly like JSX text to a regex, and the first version of this test
 * reported six of them.
 */
function literals(file: string): string[] {
  const source = ts.createSourceFile(
    file,
    readFileSync(file, "utf8"),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  const found: string[] = [];
  const visit = (node: ts.Node): void => {
    if (ts.isJsxText(node) && /[A-Za-z]/.test(node.text)) {
      found.push(node.text.trim());
    }
    if (ts.isJsxAttribute(node) && SPOKEN.has(node.name.getText())) {
      const value = node.initializer;
      if (value && ts.isStringLiteral(value)) found.push(`${node.name.getText()}="${value.text}"`);
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return found;
}

describe("no hardcoded UI strings", () => {
  const files = sources(resolve(process.cwd(), "src"));

  it("finds the components to check", () => {
    // The near-miss: a broken glob would make every assertion below vacuously true.
    expect(files.length).toBeGreaterThan(5);
  });

  it("has no literal text in any component", () => {
    const offenders = files.flatMap((file) =>
      literals(file).map((text) => `${basename(file)}: ${text}`),
    );
    expect(offenders).toEqual([]);
  });

  it("would notice one if it were there", () => {
    // Proves the parser is looking where it claims to.
    const probe = resolve(process.cwd(), "src/test/probe-literal.tsx");
    expect(literals(probe)).toEqual(['aria-label="Close the dialog"', "Save"]);
  });
});

describe("fill", () => {
  it("substitutes named placeholders", () => {
    expect(fill(strings.home.bandProgress, { solved: 3, total: 20 })).toBe("3 of 20");
  });

  it("leaves an unknown placeholder visible rather than blanking it", () => {
    expect(fill("{a} and {b}", { a: "x" })).toBe("x and {b}");
  });
});

describe("the table", () => {
  it("names every band the scorer can emit", () => {
    // Adding a band offline without adding its label here would ship a blank practice row.
    expect(Object.keys(strings.bands)).toEqual(["easy", "medium", "hard", "expert"]);
  });

  it("has no empty entries", () => {
    const walk = (node: unknown, path: string): string[] =>
      typeof node === "string"
        ? node.trim() === ""
          ? [path]
          : []
        : Object.entries(node as Record<string, unknown>).flatMap(([key, value]) =>
            walk(value, `${path}.${key}`),
          );
    expect(walk(strings, "strings")).toEqual([]);
  });
});
