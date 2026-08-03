// A component with hardcoded strings on purpose, so `strings.test.ts` can prove its scanner
// finds them. Never rendered, never imported by the app — the file exists to be read.
//
// It also carries the two shapes that broke the first version of that scanner: a generic type
// argument and a comparison, both of which a regex reads as JSX text and this must not.

const compare = (a: number, b: number): boolean => a > b;
const table = new Map<string, number>();

export function ProbeLiteral({ open }: { open: boolean }) {
  return (
    <div hidden={!open} data-size={table.size} data-cmp={compare(1, 2)}>
      <button type="button" aria-label="Close the dialog">
        Save
      </button>
    </div>
  );
}
