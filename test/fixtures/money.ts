/**
 * Parsing helpers for currency/percent text rendered by the frontend, e.g. "$10,000.00",
 * "-$123.45", "+1.23%". Formatting is not fixed by the contract, so these strip everything
 * except digits, a leading minus and a decimal point rather than assuming a specific pattern.
 */

export function parseMoney(text: string | null | undefined): number {
  if (text == null) {
    throw new Error("parseMoney: received null/undefined text");
  }
  const cleaned = text.replace(/[^0-9.\-]/g, "");
  const value = Number(cleaned);
  if (Number.isNaN(value)) {
    throw new Error(`parseMoney: could not parse "${text}" as a number`);
  }
  return value;
}

export function parsePercent(text: string | null | undefined): number {
  return parseMoney(text);
}

/** True when the cell text looks like a numeric value rather than a placeholder (e.g. "—", "N/A"). */
export function looksNumeric(text: string | null | undefined): boolean {
  return !!text && /\d/.test(text);
}
