// filepath: frontend/src/app/analysis/profiles/page.tsx
"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, Plus, Trash2, Edit, Star } from "lucide-react";
import { analysisApi, type AnalysisProfile } from "@/lib/api-client";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { ErrorBanner } from "@/components/ui/error-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDate } from "@/lib/format";

export default function AnalysisProfilesPage() {
  const queryClient = useQueryClient();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["analysis-profiles"],
    queryFn: () => analysisApi.listProfiles(),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => analysisApi.deleteProfile(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["analysis-profiles"] });
    },
  });

  const profiles = data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analysis Profiles"
        description="Manage scoring profiles with custom criteria"
      />

      {isLoading ? (
        <div className="flex justify-center py-12">
          <Spinner className="h-8 w-8" />
        </div>
      ) : error ? (
        <ErrorBanner message="Failed to load profiles." onRetry={() => refetch()} />
      ) : profiles.length === 0 ? (
        <EmptyState
          icon={<ClipboardList className="h-12 w-12" />}
          title="No profiles"
          description="Create your first analysis profile or seed the default one."
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {profiles.map((profile) => (
            <ProfileCard
              key={profile.id}
              profile={profile}
              onDelete={() => {
                if (confirm(`Delete profile "${profile.name}"?`)) {
                  deleteMutation.mutate(profile.id);
                }
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ProfileCard({
  profile,
  onDelete,
}: {
  profile: AnalysisProfile;
  onDelete: () => void;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-base">{profile.name}</CardTitle>
            {profile.description && (
              <CardDescription className="mt-1 line-clamp-2">
                {profile.description}
              </CardDescription>
            )}
          </div>
          {profile.is_default && (
            <Badge variant="default" className="flex-shrink-0">
              <Star className="mr-1 h-3 w-3" />
              Default
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="pt-2">
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-500">
            Version {profile.version} · {formatDate(profile.updated_at)}
          </span>
          <Button
            variant="ghost"
            size="icon"
            onClick={onDelete}
            className="h-8 w-8 text-gray-400 hover:text-red-500"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
