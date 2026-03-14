// filepath: frontend/src/app/companies/[id]/page.tsx
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  FileText,
  MessageSquare,
  BarChart3,
  Building2,
  DollarSign,
} from "lucide-react";
import { companiesApi } from "@/lib/api-client";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { ErrorBanner } from "@/components/ui/error-banner";
import { cn } from "@/lib/utils";
import { OverviewTab } from "@/components/company/overview-tab";
import { DocumentsTab } from "@/components/documents/documents-tab";
import { FinancialsTab } from "@/components/financials/financials-tab";
import { ChatTab } from "@/components/chat/chat-tab";
import { AnalysisTab } from "@/components/analysis/analysis-tab";

const TABS = [
  { key: "overview", label: "Overview", icon: Building2 },
  { key: "documents", label: "Documents", icon: FileText },
  { key: "financials", label: "Financials", icon: DollarSign },
  { key: "chat", label: "Chat", icon: MessageSquare },
  { key: "analysis", label: "Analysis", icon: BarChart3 },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export default function CompanyDetailPage() {
  const params = useParams<{ id: string }>();
  const companyId = params.id;
  const [activeTab, setActiveTab] = useState<TabKey>("overview");

  const { data: company, isLoading, error, refetch } = useQuery({
    queryKey: ["company", companyId],
    queryFn: () => companiesApi.get(companyId),
    enabled: !!companyId,
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  if (error || !company) {
    return (
      <ErrorBanner
        message="Failed to load company details."
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={`${company.ticker} — ${company.name}`}
        description={
          [company.sector, company.industry].filter(Boolean).join(" · ") ||
          undefined
        }
        actions={
          <Badge variant={company.doc_count ? "success" : "secondary"}>
            {company.doc_count ?? 0} documents
          </Badge>
        }
      />

      {/* Tabs */}
      <div className="border-b border-gray-200 overflow-x-auto">
        <nav className="-mb-px flex space-x-4 sm:space-x-6 min-w-max">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                "flex items-center gap-2 border-b-2 px-1 pb-3 text-sm font-medium transition-colors",
                activeTab === tab.key
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700",
              )}
            >
              <tab.icon className="h-4 w-4" />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      <div>
        {activeTab === "overview" && (
          <OverviewTab company={company} />
        )}
        {activeTab === "documents" && (
          <DocumentsTab companyId={companyId} />
        )}
        {activeTab === "financials" && (
          <FinancialsTab companyId={companyId} companyTicker={company.ticker} />
        )}
        {activeTab === "chat" && (
          <ChatTab companyId={companyId} />
        )}
        {activeTab === "analysis" && (
          <AnalysisTab companyId={companyId} companyTicker={company.ticker} />
        )}
      </div>
    </div>
  );
}
