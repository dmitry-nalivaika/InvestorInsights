// filepath: frontend/src/app/settings/page.tsx
"use client";

import { Brain, Database, Cpu, Key, Layers } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

/**
 * Settings page — read-only display of current configuration (T712).
 *
 * Values come from NEXT_PUBLIC_* build-time environment variables.
 * Per spec US7-AS6: LLM model name, embedding model name, chunk size,
 * chunk overlap, default top-K, score threshold, API key status.
 */

function getEnv(key: string, fallback: string): string {
  return process.env[key] ?? fallback;
}

const CONFIG_SECTIONS = [
  {
    title: "LLM Model",
    icon: Brain,
    items: [
      {
        label: "Model Name",
        value: getEnv("NEXT_PUBLIC_LLM_MODEL", "gpt-4o-mini"),
      },
    ],
  },
  {
    title: "Embedding Model",
    icon: Layers,
    items: [
      {
        label: "Model Name",
        value: getEnv(
          "NEXT_PUBLIC_EMBEDDING_MODEL",
          "text-embedding-3-large",
        ),
      },
    ],
  },
  {
    title: "Ingestion Settings",
    icon: Database,
    items: [
      {
        label: "Chunk Size (tokens)",
        value: getEnv("NEXT_PUBLIC_CHUNK_SIZE", "512"),
      },
      {
        label: "Chunk Overlap (tokens)",
        value: getEnv("NEXT_PUBLIC_CHUNK_OVERLAP", "50"),
      },
    ],
  },
  {
    title: "Retrieval Settings",
    icon: Cpu,
    items: [
      {
        label: "Default Top-K",
        value: getEnv("NEXT_PUBLIC_DEFAULT_TOP_K", "15"),
      },
      {
        label: "Score Threshold",
        value: getEnv("NEXT_PUBLIC_SCORE_THRESHOLD", "0.65"),
      },
    ],
  },
  {
    title: "Authentication",
    icon: Key,
    items: [
      {
        label: "API Key Status",
        value: process.env.NEXT_PUBLIC_API_KEY ? "Configured" : "Not Configured",
        isBadge: true,
        badgeVariant: (process.env.NEXT_PUBLIC_API_KEY
          ? "success"
          : "destructive") as "success" | "destructive",
      },
    ],
  },
];

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="Read-only system configuration. Managed via environment variables."
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {CONFIG_SECTIONS.map((section) => (
          <Card key={section.title}>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <section.icon className="h-4 w-4 text-blue-600" />
                <CardTitle className="text-base">{section.title}</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {section.items.map((item) => (
                <div key={item.label} className="flex justify-between text-sm">
                  <span className="text-gray-500">{item.label}</span>
                  {"isBadge" in item && item.isBadge ? (
                    <Badge variant={item.badgeVariant}>{item.value}</Badge>
                  ) : (
                    <span className="font-medium text-gray-900">
                      {item.value}
                    </span>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
