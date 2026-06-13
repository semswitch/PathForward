/** Join class fragments, dropping falsy entries. */
export const cn = (...parts: Array<string | false | null | undefined>): string =>
  parts.filter(Boolean).join(" ");
