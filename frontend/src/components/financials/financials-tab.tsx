// filepath: frontend/src/components/financials/financials-tab.tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { Download, DollarSign } from "lucide-react";
import { financialsApi, type FinancialPeriod } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { ErrorBanner } from "@/components/ui/error-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { formatCurrency, formatPercent, formatMultiple, formatNumber } from "@/lib/format";

/** Metrics we display as rows (label → key path). */
const METRICS: { label: string; section: string; key: string; format: "currency" | "pct" | "number" | "multiple" }[] = [
  { label: "Revenue", section: "income_statement", key: "revenue", format: "currency" },
  { label: "Gross Profit", section: "income_statement", key: "gross_profit", format: "currency" },
  { label: "Operating Income", section: "income_statement", key: "operating_income", format: "currency" },
  { label: "Net Income", section: "income_statement", key: "net_income", format: "currency" },
  { label: "Total Assets", section: "balance_sheet", key: "total_assets", format: "currency" },
  { label: "Total Liabilities", section: "balance_sheet", key: "total_liabilities", format: "currency" },
  { label: "Total Equity", section: "balance_sheet", key: "total_stockholders_equity", format: "currency" },
  { label: "Operating Cash Flow", section: "cash_flow", key: "operating_cash_flow", format: "currency" },
  { label: "Capital Expenditures", section: "cash_flow", key: "capital_expenditure", format: "currency" },
  { label: "Free Cash Flow", section: "cash_flow", key: "free_cash_flow", format: "currency" },
];

function formatMetricValue(value: number | null | undefined, fmt: string): string {
  if (value == null) return "—";
  switch (fmt) {
    case "currency":
      return formatCurrency(value);
    case "pct":
      return formatPercent(value, { isRatio: true });
    case "multiple":
      return formatMultiple(value);
    default:
      return formatNumber(value);
  }
}

export function FinancialsTab({
  companyId,
}: {
  companyId: string;
  companyTicker: string;
}) {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["financials", companyId],
    queryFn: () => financialsApi.get(companyId, { period: "annual" }),
  });

  const periods = (data?.periods ?? []).sort(
    (a, b) => a.fiscal_year - b.fiscal_year,
  );

  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  if (error) {
    return (
      <ErrorBanner message="Failed to load financial data." onRetry={() => refetch()} />
    );
  }

  if (periods.length === 0) {
    return (
      <EmptyState
        icon={<DollarSign className="h-10 w-10" />}
        title="No financial data"
        description="Financial data will appear after documents are processed."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <a
          href={financialsApi.exportCsvUrl(companyId)}
          download
        >
          <Button variant="outline" size="sm">
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </Button>
        </a>
      </div>

      <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              <th className="sticky left-0 z-10 bg-gray-50 px-4 py-3 text-left font-medium text-gray-600">
                Metric
              </th>
              {periods.map((p) => (
                <th
                  key={p.fiscal_year}
                  className="px-4 py-3 text-right font-medium text-gray-600 whitespace-nowrap"
                >
                  FY{p.fiscal_year}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {METRICS.map((metric) => (
              <tr key={metric.key} className="hover:bg-gray-50">
                <td className="sticky left-0 z-10 bg-white px-4 py-2.5 font-medium text-gray-700 whitespace-nowrap">
                  {metric.label}
                </td>
                {periods.map((p) => {
                  const section = p[metric.section as keyof FinancialPeriod] as
                    | Record<string, number | null>
                    | undefined;
                  const value = section?.[metric.key] ?? null;
                  return (
                    <td
                      key={p.fiscal_year}
                      className="px-4 py-2.5 text-right text-gray-700 whitespace-nowrap"
                    >
                      {formatMetricValue(value, metric.format)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
