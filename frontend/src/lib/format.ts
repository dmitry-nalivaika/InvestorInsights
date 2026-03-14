// filepath: frontend/src/lib/format.ts
/**
 * Number & date formatting utilities (T715).
 *
 * Examples:
 *   formatCurrency(394_300_000_000) → "$394.3B"
 *   formatPercent(0.482)            → "48.2%"
 *   formatNumber(1_234_567)         → "1,234,567"
 */

// ── Currency ────────────────────────────────────────────────────

const CURRENCY_THRESHOLDS: [number, string][] = [
  [1_000_000_000_000, "T"],
  [1_000_000_000, "B"],
  [1_000_000, "M"],
  [1_000, "K"],
];

/**
 * Format a number as a compact USD string.
 *  - `394_300_000_000` → `"$394.3B"`
 *  - `12_500_000`      → `"$12.5M"`
 *  - `850`             → `"$850"`
 */
export function formatCurrency(
  value: number | null | undefined,
  fallback = "—",
): string {
  if (value == null || Number.isNaN(value)) return fallback;

  const absValue = Math.abs(value);
  const sign = value < 0 ? "-" : "";

  for (const [threshold, suffix] of CURRENCY_THRESHOLDS) {
    if (absValue >= threshold) {
      const scaled = absValue / threshold;
      const formatted =
        scaled >= 100 ? scaled.toFixed(0) : scaled.toFixed(1).replace(/\.0$/, "");
      return `${sign}$${formatted}${suffix}`;
    }
  }

  return `${sign}$${absValue.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

// ── Percentage ──────────────────────────────────────────────────

/**
 * Format a ratio (0–1) or raw percentage as "48.2%".
 * If `isRatio` is true (default) the value is multiplied by 100.
 */
export function formatPercent(
  value: number | null | undefined,
  { isRatio = true, decimals = 1, fallback = "—" } = {},
): string {
  if (value == null || Number.isNaN(value)) return fallback;
  const pct = isRatio ? value * 100 : value;
  return `${pct.toFixed(decimals)}%`;
}

// ── Plain number ────────────────────────────────────────────────

/**
 * Format a number with commas: `1234567` → `"1,234,567"`.
 */
export function formatNumber(
  value: number | null | undefined,
  { decimals = 0, fallback = "—" } = {},
): string {
  if (value == null || Number.isNaN(value)) return fallback;
  return value.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

// ── Multiplier (e.g. "5.2x") ───────────────────────────────────

export function formatMultiple(
  value: number | null | undefined,
  { decimals = 1, fallback = "—" } = {},
): string {
  if (value == null || Number.isNaN(value)) return fallback;
  return `${value.toFixed(decimals)}x`;
}

// ── Date ────────────────────────────────────────────────────────

/**
 * Format an ISO datetime string as a human-friendly date.
 *   `"2024-06-15T12:00:00Z"` → `"Jun 15, 2024"`
 */
export function formatDate(
  iso: string | null | undefined,
  fallback = "—",
): string {
  if (!iso) return fallback;
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return fallback;
  }
}

/**
 * Relative time: "2 hours ago", "3 days ago", etc.
 */
export function formatRelativeTime(
  iso: string | null | undefined,
  fallback = "—",
): string {
  if (!iso) return fallback;
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const seconds = Math.floor(diff / 1000);
    if (seconds < 60) return "just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}d ago`;
    return formatDate(iso, fallback);
  } catch {
    return fallback;
  }
}

// ── Grade color ─────────────────────────────────────────────────

export function gradeColor(grade: string): string {
  switch (grade) {
    case "A":
      return "text-emerald-600";
    case "B":
      return "text-blue-600";
    case "C":
      return "text-yellow-600";
    case "D":
      return "text-orange-600";
    case "F":
      return "text-red-600";
    default:
      return "text-gray-500";
  }
}

export function gradeBgColor(grade: string): string {
  switch (grade) {
    case "A":
      return "bg-emerald-100 text-emerald-800";
    case "B":
      return "bg-blue-100 text-blue-800";
    case "C":
      return "bg-yellow-100 text-yellow-800";
    case "D":
      return "bg-orange-100 text-orange-800";
    case "F":
      return "bg-red-100 text-red-800";
    default:
      return "bg-gray-100 text-gray-800";
  }
}
