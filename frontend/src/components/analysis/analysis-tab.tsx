// filepath: frontend/src/components/analysis/analysis-tab.tsx
"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { BarChart3, Play, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { analysisApi, type AnalysisResult, type AnalysisProfile } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { ErrorBanner } from "@/components/ui/error-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { formatPercent, gradeBgColor, formatDate } from "@/lib/format";

export function AnalysisTab({
  companyId,
  companyTicker,
}: {
  companyId: string;
  companyTicker: string;
}) {
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [latestResult, setLatestResult] = useState<AnalysisResult | null>(null);

  // Load profiles
  const { data: profilesData } = useQuery({
    queryKey: ["analysis-profiles"],
    queryFn: () => analysisApi.listProfiles(),
  });
  const profiles = profilesData?.items ?? [];

  // Load past results
  const { data: resultsData, isLoading: loadingResults, refetch: refetchResults } = useQuery({
    queryKey: ["analysis-results", companyId],
    queryFn: () => analysisApi.listResults({ company_id: companyId, limit: 10 }),
  });
  const pastResults = resultsData?.items ?? [];

  // Run analysis
  const runMutation = useMutation({
    mutationFn: () =>
      analysisApi.runAnalysis({
        company_ids: [companyId],
        profile_id: selectedProfileId!,
        generate_summary: true,
      }),
    onSuccess: (data) => {
      if (data.results.length > 0) {
        setLatestResult(data.results[0]);
      }
      refetchResults();
    },
  });

  const result = latestResult ?? pastResults[0] ?? null;

  return (
    <div className="space-y-6">
      {/* Run controls */}
      <Card>
        <CardContent className="p-5">
          <div className="flex flex-wrap items-center gap-3">
            <select
              value={selectedProfileId ?? ""}
              onChange={(e) => setSelectedProfileId(e.target.value || null)}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select profile…</option>
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} (v{p.version})
                </option>
              ))}
            </select>
            <Button
              disabled={!selectedProfileId || runMutation.isPending}
              onClick={() => runMutation.mutate()}
            >
              {runMutation.isPending ? (
                <Spinner className="h-4 w-4" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Run Analysis
            </Button>
            {runMutation.isError && (
              <span className="text-sm text-red-600">
                {runMutation.error.message}
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Score card */}
      {result ? (
        <div className="space-y-6">
          <ScoreCard result={result} />
          <CriteriaTable result={result} />
          {result.summary && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">AI Summary</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-gray-700 whitespace-pre-wrap">
                  {result.summary}
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      ) : loadingResults ? (
        <div className="flex justify-center py-8">
          <Spinner className="h-6 w-6" />
        </div>
      ) : (
        <EmptyState
          icon={<BarChart3 className="h-10 w-10" />}
          title="No analysis results"
          description="Select a profile and run an analysis to see results."
        />
      )}

      {/* Historical results */}
      {pastResults.length > 1 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Past Results</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {pastResults.map((r) => (
                <button
                  key={r.id}
                  onClick={() => setLatestResult(r)}
                  className="flex w-full items-center justify-between rounded-lg border border-gray-100 p-3 text-left hover:bg-gray-50 transition-colors"
                >
                  <div>
                    <span className="text-sm font-medium text-gray-900">
                      {formatPercent(r.pct_score / 100, { isRatio: true })}
                    </span>
                    <Badge className={`ml-2 ${gradeBgColor(r.grade)}`}>
                      {r.grade}
                    </Badge>
                  </div>
                  <span className="text-xs text-gray-400">
                    {formatDate(r.run_at)}
                  </span>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function ScoreCard({ result }: { result: AnalysisResult }) {
  return (
    <div className="grid gap-4 sm:grid-cols-4">
      <Card>
        <CardContent className="p-5 text-center">
          <p className="text-sm text-gray-500">Grade</p>
          <p className={`mt-1 text-4xl font-bold ${gradeBgColor(result.grade)} inline-block px-3 py-1 rounded-lg`}>
            {result.grade}
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="p-5 text-center">
          <p className="text-sm text-gray-500">Score</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">
            {formatPercent(result.pct_score / 100, { isRatio: true })}
          </p>
          <p className="text-xs text-gray-400">
            {result.overall_score} / {result.max_score}
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="p-5 text-center">
          <p className="text-sm text-gray-500">Passed</p>
          <p className="mt-1 text-2xl font-bold text-emerald-600">
            {result.passed_count}
          </p>
          <p className="text-xs text-gray-400">
            of {result.criteria_count} criteria
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="p-5 text-center">
          <p className="text-sm text-gray-500">Failed</p>
          <p className="mt-1 text-2xl font-bold text-red-600">
            {result.failed_count}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function TrendIcon({ trend }: { trend: string | null }) {
  if (trend === "improving")
    return <TrendingUp className="h-3.5 w-3.5 text-emerald-500" />;
  if (trend === "declining")
    return <TrendingDown className="h-3.5 w-3.5 text-red-500" />;
  return <Minus className="h-3.5 w-3.5 text-gray-400" />;
}

function CriteriaTable({ result }: { result: AnalysisResult }) {
  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50 text-left">
            <th className="px-4 py-3 font-medium text-gray-600">Criterion</th>
            <th className="px-4 py-3 font-medium text-gray-600">Category</th>
            <th className="px-4 py-3 font-medium text-gray-600">Value</th>
            <th className="px-4 py-3 font-medium text-gray-600">Threshold</th>
            <th className="px-4 py-3 font-medium text-gray-600">Trend</th>
            <th className="px-4 py-3 font-medium text-gray-600">Result</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {result.criteria_results.map((cr, i) => (
            <tr key={i} className="hover:bg-gray-50">
              <td className="px-4 py-2.5 font-medium text-gray-900">
                {cr.criteria_name}
              </td>
              <td className="px-4 py-2.5">
                <Badge variant="secondary">{cr.category}</Badge>
              </td>
              <td className="px-4 py-2.5 text-gray-700">
                {cr.latest_value != null ? cr.latest_value.toFixed(4) : "—"}
              </td>
              <td className="px-4 py-2.5 text-gray-500">{cr.threshold}</td>
              <td className="px-4 py-2.5">
                <TrendIcon trend={cr.trend} />
              </td>
              <td className="px-4 py-2.5">
                <Badge variant={cr.passed ? "success" : "destructive"}>
                  {cr.passed ? "Pass" : "Fail"}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
