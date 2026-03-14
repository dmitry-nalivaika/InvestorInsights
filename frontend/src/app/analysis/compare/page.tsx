// filepath: frontend/src/app/analysis/compare/page.tsx
"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  GitCompareArrows,
  Play,
  Check,
  X,
} from "lucide-react";
import {
  analysisApi,
  companiesApi,
  type ComparisonResponse,
  type ComparisonRanking,
} from "@/lib/api-client";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { ErrorBanner } from "@/components/ui/error-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { formatPercent, gradeBgColor } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function ComparePage() {
  const [selectedCompanyIds, setSelectedCompanyIds] = useState<string[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [result, setResult] = useState<ComparisonResponse | null>(null);

  // Load companies
  const { data: companiesData } = useQuery({
    queryKey: ["companies"],
    queryFn: () => companiesApi.list({ limit: 100 }),
  });
  const companies = companiesData?.items ?? [];

  // Load profiles
  const { data: profilesData } = useQuery({
    queryKey: ["analysis-profiles"],
    queryFn: () => analysisApi.listProfiles(),
  });
  const profiles = profilesData?.items ?? [];

  // Run comparison
  const compareMutation = useMutation({
    mutationFn: () =>
      analysisApi.compare({
        company_ids: selectedCompanyIds,
        profile_id: selectedProfileId!,
        generate_summary: true,
      }),
    onSuccess: (data) => setResult(data),
  });

  const toggleCompany = (id: string) => {
    setSelectedCompanyIds((prev) =>
      prev.includes(id)
        ? prev.filter((c) => c !== id)
        : prev.length < 10
          ? [...prev, id]
          : prev,
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Compare Companies"
        description="Run the same analysis profile against multiple companies"
      />

      {/* Controls */}
      <Card>
        <CardContent className="p-5 space-y-4">
          {/* Company selector */}
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-2">
              Select companies (2–10)
            </label>
            <div className="flex flex-wrap gap-2">
              {companies.map((c) => {
                const selected = selectedCompanyIds.includes(c.id);
                return (
                  <button
                    key={c.id}
                    onClick={() => toggleCompany(c.id)}
                    className={cn(
                      "rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors",
                      selected
                        ? "border-blue-500 bg-blue-50 text-blue-700"
                        : "border-gray-200 bg-white text-gray-600 hover:border-gray-300",
                    )}
                  >
                    {c.ticker}
                  </button>
                );
              })}
            </div>
            <p className="mt-1 text-xs text-gray-400">
              {selectedCompanyIds.length} selected
            </p>
          </div>

          {/* Profile selector + run */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <select
              value={selectedProfileId ?? ""}
              onChange={(e) => setSelectedProfileId(e.target.value || null)}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select profile…</option>
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <Button
              disabled={
                selectedCompanyIds.length < 2 ||
                !selectedProfileId ||
                compareMutation.isPending
              }
              onClick={() => compareMutation.mutate()}
            >
              {compareMutation.isPending ? (
                <Spinner className="h-4 w-4" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Compare
            </Button>
          </div>
          {compareMutation.isError && (
            <ErrorBanner message={compareMutation.error.message} />
          )}
        </CardContent>
      </Card>

      {/* Results */}
      {result ? (
        <ComparisonResult data={result} />
      ) : (
        <EmptyState
          icon={<GitCompareArrows className="h-12 w-12" />}
          title="No comparison yet"
          description="Select companies and a profile, then click Compare."
        />
      )}
    </div>
  );
}

function ComparisonResult({ data }: { data: ComparisonResponse }) {
  return (
    <div className="space-y-4">
      {/* Rankings summary */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {data.rankings.map((r) => (
          <RankingCard key={r.company_id} ranking={r} />
        ))}
      </div>

      {/* Comparison matrix */}
      {data.criteria_names.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="sticky left-0 z-10 bg-gray-50 px-4 py-3 text-left font-medium text-gray-600">
                  Criterion
                </th>
                {data.rankings.map((r) => (
                  <th
                    key={r.company_id}
                    className="px-4 py-3 text-center font-medium text-gray-600 whitespace-nowrap"
                  >
                    <div>{r.company_ticker ?? "?"}</div>
                    <Badge className={`mt-0.5 ${gradeBgColor(r.grade)}`}>
                      {r.grade}
                    </Badge>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.criteria_names.map((criteriaName) => (
                <tr key={criteriaName} className="hover:bg-gray-50">
                  <td className="sticky left-0 z-10 bg-white px-4 py-2.5 font-medium text-gray-700 whitespace-nowrap">
                    {criteriaName}
                  </td>
                  {data.rankings.map((r) => {
                    const cell = r.criteria_results.find(
                      (c) => c.criteria_name === criteriaName,
                    );
                    return (
                      <td
                        key={r.company_id}
                        className="px-4 py-2.5 text-center"
                      >
                        {cell ? (
                          <CriterionCell cell={cell} />
                        ) : (
                          <span className="text-gray-300">—</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function RankingCard({ ranking }: { ranking: ComparisonRanking }) {
  return (
    <Card
      className={cn(
        ranking.rank === 1 && "ring-2 ring-blue-500",
      )}
    >
      <CardContent className="p-4 text-center">
        <p className="text-xs text-gray-400">#{ranking.rank}</p>
        <p className="text-lg font-bold text-gray-900">
          {ranking.company_ticker ?? "?"}
        </p>
        <p className="text-xs text-gray-500 truncate">
          {ranking.company_name}
        </p>
        <div className="mt-2">
          <span
            className={`inline-block text-2xl font-bold px-2 py-0.5 rounded ${gradeBgColor(ranking.grade)}`}
          >
            {ranking.grade}
          </span>
        </div>
        <p className="mt-1 text-sm text-gray-600">
          {formatPercent(ranking.pct_score / 100, { isRatio: true })}
        </p>
        <p className="text-xs text-gray-400">
          {ranking.passed_count}/{ranking.criteria_count} passed
        </p>
        {ranking.status === "no_data" && (
          <Badge variant="warning" className="mt-2">
            No Data
          </Badge>
        )}
      </CardContent>
    </Card>
  );
}

function CriterionCell({
  cell,
}: {
  cell: ComparisonRanking["criteria_results"][number];
}) {
  if (!cell.has_data) {
    return <span className="text-xs text-gray-300">No data</span>;
  }
  return (
    <div className="flex flex-col items-center gap-0.5">
      {cell.passed ? (
        <Check className="h-4 w-4 text-emerald-500" />
      ) : (
        <X className="h-4 w-4 text-red-500" />
      )}
      <span className="text-xs text-gray-500">
        {cell.latest_value != null ? cell.latest_value.toFixed(2) : "—"}
      </span>
    </div>
  );
}
