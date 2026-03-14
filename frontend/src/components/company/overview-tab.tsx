// filepath: frontend/src/components/company/overview-tab.tsx
"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatDate, formatNumber } from "@/lib/format";
import type { CompanyDetail } from "@/lib/api-client";
import { FileText, BarChart3, MessageSquare } from "lucide-react";

export function OverviewTab({ company }: { company: CompanyDetail }) {
  const docSummary = company.documents_summary;
  const finSummary = company.financials_summary;

  return (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      {/* Company Info */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Company Info</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <Row label="Ticker" value={company.ticker} />
          <Row label="Name" value={company.name} />
          <Row label="CIK" value={company.cik ?? "—"} />
          <Row label="Sector" value={company.sector ?? "—"} />
          <Row label="Industry" value={company.industry ?? "—"} />
          <Row label="Added" value={formatDate(company.created_at)} />
        </CardContent>
      </Card>

      {/* Filing Summary */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-blue-600" />
            <CardTitle className="text-base">Documents</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <Row
            label="Total"
            value={formatNumber(docSummary?.total ?? 0)}
          />
          {docSummary?.by_status && (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {Object.entries(docSummary.by_status).map(([status, count]) => (
                <Badge
                  key={status}
                  variant={
                    status === "ready"
                      ? "success"
                      : status === "error"
                        ? "destructive"
                        : "secondary"
                  }
                >
                  {status}: {count}
                </Badge>
              ))}
            </div>
          )}
          {docSummary?.year_range && (
            <Row
              label="Years"
              value={`${docSummary.year_range.min}–${docSummary.year_range.max}`}
            />
          )}
        </CardContent>
      </Card>

      {/* Financial Summary */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-emerald-600" />
            <CardTitle className="text-base">Financials</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <Row
            label="Periods"
            value={formatNumber(finSummary?.periods_available ?? 0)}
          />
          {finSummary?.year_range && (
            <Row
              label="Coverage"
              value={`${finSummary.year_range.min}–${finSummary.year_range.max}`}
            />
          )}
          {!finSummary?.periods_available && (
            <p className="text-gray-400 italic">No financial data yet</p>
          )}
        </CardContent>
      </Card>

      {/* Recent Chat Sessions */}
      {company.recent_sessions && company.recent_sessions.length > 0 && (
        <Card className="md:col-span-2 lg:col-span-3">
          <CardHeader>
            <div className="flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-purple-600" />
              <CardTitle className="text-base">Recent Chat Sessions</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="divide-y divide-gray-100">
              {company.recent_sessions.map((session) => (
                <div
                  key={session.id}
                  className="flex items-center justify-between py-2"
                >
                  <span className="text-sm text-gray-700 truncate">
                    {session.title}
                  </span>
                  <span className="text-xs text-gray-400">
                    {formatDate(session.updated_at)}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-500">{label}</span>
      <span className="font-medium text-gray-900">{value}</span>
    </div>
  );
}
