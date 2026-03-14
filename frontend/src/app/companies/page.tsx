// filepath: frontend/src/app/companies/page.tsx
"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Building2, Plus, Search, ArrowUpDown } from "lucide-react";
import Link from "next/link";
import { companiesApi, type Company, type CompanyCreate } from "@/lib/api-client";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { ErrorBanner } from "@/components/ui/error-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDate } from "@/lib/format";

export default function CompaniesPage() {
  const [search, setSearch] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const queryClient = useQueryClient();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["companies", search],
    queryFn: () => companiesApi.list({ search: search || undefined, limit: 100 }),
  });

  const companies = data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Companies"
        description={`${data?.total ?? 0} companies tracked`}
        actions={
          <Button onClick={() => setShowAdd(true)}>
            <Plus className="h-4 w-4" />
            Add Company
          </Button>
        }
      />

      {/* Search bar */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <Input
          placeholder="Search by ticker or name…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Add company modal */}
      {showAdd && (
        <AddCompanyModal
          onClose={() => setShowAdd(false)}
          onSuccess={() => {
            setShowAdd(false);
            queryClient.invalidateQueries({ queryKey: ["companies"] });
          }}
        />
      )}

      {/* Company table */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Spinner className="h-8 w-8" />
        </div>
      ) : error ? (
        <ErrorBanner message="Failed to load companies." onRetry={() => refetch()} />
      ) : companies.length === 0 ? (
        <EmptyState
          icon={<Building2 className="h-12 w-12" />}
          title={search ? "No matches" : "No companies yet"}
          description={
            search
              ? "Try a different search term."
              : "Add your first company to get started."
          }
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50 text-left">
                <th className="px-4 py-3 font-medium text-gray-600">Ticker</th>
                <th className="px-4 py-3 font-medium text-gray-600">Name</th>
                <th className="hidden sm:table-cell px-4 py-3 font-medium text-gray-600">Sector</th>
                <th className="px-4 py-3 font-medium text-gray-600 text-right">Docs</th>
                <th className="px-4 py-3 font-medium text-gray-600">Status</th>
                <th className="hidden sm:table-cell px-4 py-3 font-medium text-gray-600">Added</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {companies.map((c) => (
                <tr
                  key={c.id}
                  className="hover:bg-gray-50 transition-colors cursor-pointer"
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/companies/${c.id}`}
                      className="font-semibold text-blue-600 hover:underline"
                    >
                      {c.ticker}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-gray-700">{c.name}</td>
                  <td className="hidden sm:table-cell px-4 py-3 text-gray-500">{c.sector ?? "—"}</td>
                  <td className="px-4 py-3 text-right text-gray-700">
                    {c.doc_count ?? 0}
                  </td>
                  <td className="px-4 py-3">
                    <ReadinessBadge pct={c.readiness_pct ?? 0} />
                  </td>
                  <td className="hidden sm:table-cell px-4 py-3 text-gray-500">
                    {formatDate(c.created_at)}
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

function ReadinessBadge({ pct }: { pct: number }) {
  if (pct >= 100)
    return <Badge variant="success">Ready</Badge>;
  if (pct > 0)
    return <Badge variant="warning">{pct.toFixed(0)}%</Badge>;
  return <Badge variant="secondary">New</Badge>;
}

function AddCompanyModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [ticker, setTicker] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const mutation = useMutation({
    mutationFn: (data: CompanyCreate) => companiesApi.create(data),
    onSuccess: () => onSuccess(),
    onError: (err: Error) => setErrorMsg(err.message),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <Card className="w-full max-w-md">
        <CardContent className="p-6 space-y-4">
          <h2 className="text-lg font-semibold">Add Company</h2>
          <p className="text-sm text-gray-500">
            Enter a ticker symbol. Company name and CIK will be resolved
            automatically from SEC EDGAR.
          </p>
          <Input
            placeholder="e.g. AAPL"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            onKeyDown={(e) => {
              if (e.key === "Enter" && ticker.trim()) {
                mutation.mutate({ ticker: ticker.trim() });
              }
            }}
            autoFocus
          />
          {errorMsg && <ErrorBanner message={errorMsg} />}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button
              disabled={!ticker.trim() || mutation.isPending}
              onClick={() => mutation.mutate({ ticker: ticker.trim() })}
            >
              {mutation.isPending ? <Spinner className="h-4 w-4" /> : "Add"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
