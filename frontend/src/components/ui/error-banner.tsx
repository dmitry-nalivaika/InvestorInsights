// filepath: frontend/src/components/ui/error-banner.tsx
"use client";

import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "./button";

/** Inline error banner with optional retry (T714). */
export function ErrorBanner({
  message,
  onRetry,
  className,
}: {
  message: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 p-4",
        className,
      )}
    >
      <AlertTriangle className="h-5 w-5 flex-shrink-0 text-red-500" />
      <p className="flex-1 text-sm text-red-800">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}
