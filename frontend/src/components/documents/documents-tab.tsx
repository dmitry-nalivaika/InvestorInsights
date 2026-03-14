// filepath: frontend/src/components/documents/documents-tab.tsx
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FileText, RefreshCw, Download } from "lucide-react";
import { documentsApi } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { ErrorBanner } from "@/components/ui/error-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDate } from "@/lib/format";

const STATUS_VARIANT: Record<string, "success" | "warning" | "destructive" | "secondary" | "default"> = {
  ready: "success",
  parsed: "default",
  parsing: "warning",
  embedding: "warning",
  uploaded: "secondary",
  error: "destructive",
};

export function DocumentsTab({ companyId }: { companyId: string }) {
  const [fetchStatus, setFetchStatus] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const [isFetching, setIsFetching] = useState(false);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["documents", companyId],
    queryFn: () => documentsApi.list(companyId, { limit: 100 }),
  });

  const documents = data?.items ?? [];

  const handleFetchSec = async () => {
    setIsFetching(true);
    setFetchStatus(null);
    try {
      const result = await documentsApi.fetchSec(companyId, {
        filing_types: ["10-K", "10-Q"],
        years_back: 3,
      });
      setFetchStatus({
        message: `${result.message}. Estimated ${result.estimated_filings} filings. Refresh in a minute to see results.`,
        type: "success",
      });
      // Auto-refresh the list after a delay
      setTimeout(() => refetch(), 15000);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to fetch from SEC EDGAR";
      setFetchStatus({ message, type: "error" });
    } finally {
      setIsFetching(false);
    }
  };

  return (
    <div className="space-y-4">
      {fetchStatus && (
        <div
          className={`rounded-lg px-4 py-3 text-sm ${
            fetchStatus.type === "success"
              ? "bg-green-50 text-green-800 border border-green-200"
              : "bg-red-50 text-red-800 border border-red-200"
          }`}
        >
          {fetchStatus.message}
        </div>
      )}

      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          {data?.total ?? 0} documents
        </p>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleFetchSec}
            disabled={isFetching}
          >
            {isFetching ? (
              <Spinner className="h-3.5 w-3.5" />
            ) : (
              <Download className="h-3.5 w-3.5" />
            )}
            {isFetching ? "Fetching…" : "Fetch from SEC"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-8">
          <Spinner className="h-6 w-6" />
        </div>
      ) : error ? (
        <ErrorBanner message="Failed to load documents." onRetry={() => refetch()} />
      ) : documents.length === 0 ? (
        <EmptyState
          icon={<FileText className="h-10 w-10" />}
          title="No documents"
          description="Upload filings or fetch them from SEC EDGAR."
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50 text-left">
                <th className="px-4 py-3 font-medium text-gray-600">Type</th>
                <th className="px-4 py-3 font-medium text-gray-600">Period</th>
                <th className="hidden sm:table-cell px-4 py-3 font-medium text-gray-600">Filing Date</th>
                <th className="px-4 py-3 font-medium text-gray-600">Status</th>
                <th className="hidden sm:table-cell px-4 py-3 font-medium text-gray-600">Added</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {documents.map((doc) => (
                <tr key={doc.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {doc.doc_type}
                  </td>
                  <td className="px-4 py-3 text-gray-700">
                    FY{doc.fiscal_year}
                    {doc.fiscal_quarter ? ` Q${doc.fiscal_quarter}` : ""}
                  </td>
                  <td className="hidden sm:table-cell px-4 py-3 text-gray-500">
                    {formatDate(doc.filing_date)}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={STATUS_VARIANT[doc.status] ?? "secondary"}>
                      {doc.status}
                    </Badge>
                  </td>
                  <td className="hidden sm:table-cell px-4 py-3 text-gray-500">
                    {formatDate(doc.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
