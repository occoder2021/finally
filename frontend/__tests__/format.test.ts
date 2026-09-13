import { describe, expect, it } from "vitest";
import { formatCurrency, formatPercent, formatSignedCurrency } from "@/lib/format";

describe("format helpers", () => {
  it("formats currency to two decimal places", () => {
    expect(formatCurrency(1915)).toBe("$1,915.00");
  });

  it("signs currency for P&L display", () => {
    expect(formatSignedCurrency(15)).toBe("+$15.00");
    expect(formatSignedCurrency(-15)).toBe("-$15.00");
  });

  it("formats percent with an optional explicit sign", () => {
    expect(formatPercent(0.79, { signed: true })).toBe("+0.79%");
    expect(formatPercent(-1.02, { signed: true })).toBe("-1.02%");
    expect(formatPercent(0.79)).toBe("0.79%");
  });
});
