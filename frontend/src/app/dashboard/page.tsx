// filepath: frontend/src/app/dashboard/page.tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Building2,
  FileText,
  BarChart3,
  Plus,
  ArrowRight,
} from "lucide-react";
import Link from "next/link";
import { companiesApi, type Company } from "@/lib/api-client";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { ErrorBanner } from "@/components/ui/error-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDate, formatPercent } from "@/lib/format";

export default function DashboardPage() {
  const {
    data,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["companies"],
    queryFn: () => companiesApi.list({ limit: 50 }),
  });

  const companies = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Overview of your company portfolio"
        actions={
          <Link href="/companies">
            <Button>
              <Plus className="h-4 w-4" />
              Add Company
            </Button>
          </Link>
        }
      />

      {/* Summary cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          title="Companies"
          value={total}
          icon={<Building2 className="h-5 w-5 text-blue-600" />}
        />
        <SummaryCard
          title="Total Documents"
          value={companies.reduce((s, c) => s + (c.doc_count ?? 0), 0)}
          icon={<FileText className="h-5 w-5 text-emerald-600" />}
        />
        <SummaryCard
          title="Ready for Analysis"
          value={companies.filter((c) => (c.readiness_pct ?? 0) >= 100).length}
          icon={<BarChart3 className="h-5 w-5 text-purple-600" />}
        />
        <SummaryCard
          title="Avg Readiness"
          value={
            companies.length > 0
              ? formatPercent(
                  companies.reduce((s, c) => s + (c.readiness_pct ?? 0), 0) /
                    companies.length / 100,
                  { isRatio: true },
                )
              : "—"
          }
          icon={<BarChart3 className="h-5 w-5 text-yellow-600" />}
          isText
        />
      </div>

      {/* Company grid */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Spinner className="h-8 w-8" />
        </div>
      ) : error ? (
        <ErrorBanner
          message="Failed to load companies."
          onRetry={() => refetch()}
        />
      ) : companies.length === 0 ? (
        <EmptyState
          icon={<Building2 className="h-12 w-12" />}
          title="No companies yet"
          description="Add your first company to get started with financial analysis."
          action={
            <Link href="/companies">
              <Button>
                <Plus className="h-4 w-4" />
                Add Company
              </Button>
            </Link>
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {companies.map((company) => (
            <CompanyCard key={company.id} company={company} />
          ))}
        </div>
      )}
    </div>
  );
}

function SummaryCard({
  title,
  value,
  icon,
  isText = false,
}: {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  isText?: boolean;
}) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-500">{title}</p>
            <p className="mt-1 text-2xl font-bold text-gray-900">
              {isText ? value : typeof value === "number" ? value.toLocaleString() : value}
            </p>
          </div>
          <div className="rounded-lg bg-gray-50 p-2.5">{icon}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function CompanyCard({ company }: { company: Company }) {
  const readiness = company.readiness_pct ?? 0;
  return (
    <Link href={`/companies/${company.id}`}>
      <Card className="transition-shadow hover:shadow-md cursor-pointer">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">{company.ticker}</CardTitle>
            <Badge
              variant={readiness >= 100 ? "success" : readiness > 0 ? "warning" : "secondary"}
            >
              {readiness >= 100 ? "Ready" : `${readiness.toFixed(0)}%`}
            </Badge>
          </div>
          <p className="text-sm text-gray-500 truncate">{company.name}</p>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="flex items-center justify-between text-sm text-gray-500">
            <span>{company.doc_count ?? 0} docs</span>
            {company.sector && (
              <span className="truncate ml-2">{company.sector}</span>
            )}
          </div>
          <div className="mt-2 flex items-center justify-between text-xs text-gray-400">
            <span>Added {formatDate(company.created_at)}</span>
            <ArrowRight className="h-3 w-3" />
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
