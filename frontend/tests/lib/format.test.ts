// filepath: frontend/tests/lib/format.test.ts
import { describe, it, expect } from "vitest";
import {
  formatCurrency,
  formatPercent,
  formatNumber,
  formatMultiple,
  formatDate,
  formatRelativeTime,
  gradeColor,
  gradeBgColor,
} from "@/lib/format";

// ── formatCurrency ──────────────────────────────────────────────

describe("formatCurrency", () => {
  it("formats trillions", () => {
    expect(formatCurrency(1_200_000_000_000)).toBe("$1.2T");
  });

  it("formats billions", () => {
    // ≥100 → toFixed(0), so 394.3B rounds to $394B
    expect(formatCurrency(394_300_000_000)).toBe("$394B");
  });

  it("formats sub-100 billions with one decimal", () => {
    expect(formatCurrency(12_300_000_000)).toBe("$12.3B");
  });

  it("formats millions", () => {
    expect(formatCurrency(12_500_000)).toBe("$12.5M");
  });

  it("formats thousands", () => {
    expect(formatCurrency(45_000)).toBe("$45K");
  });

  it("formats small values without suffix", () => {
    expect(formatCurrency(850)).toBe("$850");
  });

  it("handles negative values", () => {
    expect(formatCurrency(-5_000_000)).toBe("-$5M");
  });

  it("returns fallback for null", () => {
    expect(formatCurrency(null)).toBe("—");
  });

  it("returns fallback for undefined", () => {
    expect(formatCurrency(undefined)).toBe("—");
  });

  it("returns fallback for NaN", () => {
    expect(formatCurrency(NaN)).toBe("—");
  });

  it("uses custom fallback", () => {
    expect(formatCurrency(null, "N/A")).toBe("N/A");
  });

  it("drops trailing .0 for clean numbers", () => {
    expect(formatCurrency(5_000_000_000)).toBe("$5B");
  });

  it("formats large trillions compactly", () => {
    expect(formatCurrency(150_000_000_000_000)).toBe("$150T");
  });
});

// ── formatPercent ───────────────────────────────────────────────

describe("formatPercent", () => {
  it("converts ratio to percentage by default", () => {
    expect(formatPercent(0.482)).toBe("48.2%");
  });

  it("handles isRatio=false", () => {
    expect(formatPercent(48.2, { isRatio: false })).toBe("48.2%");
  });

  it("supports custom decimals", () => {
    expect(formatPercent(0.12345, { decimals: 2 })).toBe("12.35%");
  });

  it("returns fallback for null", () => {
    expect(formatPercent(null)).toBe("—");
  });

  it("returns fallback for NaN", () => {
    expect(formatPercent(NaN)).toBe("—");
  });

  it("uses custom fallback", () => {
    expect(formatPercent(undefined, { fallback: "N/A" })).toBe("N/A");
  });

  it("formats 0 correctly", () => {
    expect(formatPercent(0)).toBe("0.0%");
  });

  it("formats 1 (100%) correctly", () => {
    expect(formatPercent(1)).toBe("100.0%");
  });
});

// ── formatNumber ────────────────────────────────────────────────

describe("formatNumber", () => {
  it("adds commas", () => {
    expect(formatNumber(1234567)).toBe("1,234,567");
  });

  it("supports decimals option", () => {
    expect(formatNumber(1234.5678, { decimals: 2 })).toBe("1,234.57");
  });

  it("returns fallback for null", () => {
    expect(formatNumber(null)).toBe("—");
  });

  it("returns fallback for NaN", () => {
    expect(formatNumber(NaN)).toBe("—");
  });

  it("formats zero", () => {
    expect(formatNumber(0)).toBe("0");
  });
});

// ── formatMultiple ──────────────────────────────────────────────

describe("formatMultiple", () => {
  it("formats as multiplier", () => {
    expect(formatMultiple(5.2)).toBe("5.2x");
  });

  it("supports custom decimals", () => {
    expect(formatMultiple(3.456, { decimals: 2 })).toBe("3.46x");
  });

  it("returns fallback for null", () => {
    expect(formatMultiple(null)).toBe("—");
  });

  it("returns fallback for NaN", () => {
    expect(formatMultiple(NaN)).toBe("—");
  });
});

// ── formatDate ──────────────────────────────────────────────────

describe("formatDate", () => {
  it("formats ISO string to readable date", () => {
    const result = formatDate("2024-06-15T12:00:00Z");
    expect(result).toBe("Jun 15, 2024");
  });

  it("returns fallback for null", () => {
    expect(formatDate(null)).toBe("—");
  });

  it("returns fallback for undefined", () => {
    expect(formatDate(undefined)).toBe("—");
  });

  it("returns fallback for empty string", () => {
    expect(formatDate("")).toBe("—");
  });

  it("uses custom fallback", () => {
    expect(formatDate(null, "N/A")).toBe("N/A");
  });
});

// ── formatRelativeTime ──────────────────────────────────────────

describe("formatRelativeTime", () => {
  it("returns 'just now' for very recent times", () => {
    const now = new Date().toISOString();
    expect(formatRelativeTime(now)).toBe("just now");
  });

  it("returns minutes ago", () => {
    const fiveMinAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    expect(formatRelativeTime(fiveMinAgo)).toBe("5m ago");
  });

  it("returns hours ago", () => {
    const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString();
    expect(formatRelativeTime(twoHoursAgo)).toBe("2h ago");
  });

  it("returns days ago", () => {
    const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString();
    expect(formatRelativeTime(threeDaysAgo)).toBe("3d ago");
  });

  it("returns fallback for null", () => {
    expect(formatRelativeTime(null)).toBe("—");
  });

  it("returns fallback for undefined", () => {
    expect(formatRelativeTime(undefined)).toBe("—");
  });
});

// ── gradeColor ──────────────────────────────────────────────────

describe("gradeColor", () => {
  it("returns emerald for A", () => {
    expect(gradeColor("A")).toBe("text-emerald-600");
  });

  it("returns blue for B", () => {
    expect(gradeColor("B")).toBe("text-blue-600");
  });

  it("returns yellow for C", () => {
    expect(gradeColor("C")).toBe("text-yellow-600");
  });

  it("returns orange for D", () => {
    expect(gradeColor("D")).toBe("text-orange-600");
  });

  it("returns red for F", () => {
    expect(gradeColor("F")).toBe("text-red-600");
  });

  it("returns gray for unknown grade", () => {
    expect(gradeColor("X")).toBe("text-gray-500");
  });
});

// ── gradeBgColor ────────────────────────────────────────────────

describe("gradeBgColor", () => {
  it("returns emerald bg for A", () => {
    expect(gradeBgColor("A")).toBe("bg-emerald-100 text-emerald-800");
  });

  it("returns blue bg for B", () => {
    expect(gradeBgColor("B")).toBe("bg-blue-100 text-blue-800");
  });

  it("returns yellow bg for C", () => {
    expect(gradeBgColor("C")).toBe("bg-yellow-100 text-yellow-800");
  });

  it("returns orange bg for D", () => {
    expect(gradeBgColor("D")).toBe("bg-orange-100 text-orange-800");
  });

  it("returns red bg for F", () => {
    expect(gradeBgColor("F")).toBe("bg-red-100 text-red-800");
  });

  it("returns gray bg for unknown grade", () => {
    expect(gradeBgColor("X")).toBe("bg-gray-100 text-gray-800");
  });
});
