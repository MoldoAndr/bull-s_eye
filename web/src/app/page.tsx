"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Target,
  Plus,
  BarChart3,
  Shield,
  AlertTriangle,
  CheckCircle,
  Clock,
  XCircle,
  RefreshCw,
} from "lucide-react";
import { api, JobSummary, Stats } from "@/lib/api";
import { JobList } from "@/components/job-list";
import { NewJobDialog } from "@/components/new-job-dialog";
import { StatsCards } from "@/components/stats-cards";

export default function Home() {
  const [isNewJobOpen, setIsNewJobOpen] = useState(false);

  const { data: stats, isLoading: statsLoading } = useQuery<Stats>({
    queryKey: ["stats"],
    queryFn: api.getStats,
    refetchInterval: 10000,
  });

  const { data: jobs, isLoading: jobsLoading, refetch: refetchJobs } = useQuery<JobSummary[]>({
    queryKey: ["jobs"],
    queryFn: () => api.getJobs(),
    refetchInterval: 5000,
  });

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary rounded-lg">
                <Target className="h-6 w-6 text-primary-foreground" />
              </div>
              <div>
                <h1 className="text-xl font-bold">Bull's Eye</h1>
                <p className="text-sm text-muted-foreground">
                  Autonomous Codebase Analysis
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => refetchJobs()}
                className="p-2 hover:bg-accent rounded-lg transition-colors"
                title="Refresh"
              >
                <RefreshCw className="h-5 w-5" />
              </button>
              <button
                onClick={() => setIsNewJobOpen(true)}
                className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-lg hover:bg-primary/90 transition-colors"
              >
                <Plus className="h-4 w-4" />
                New Analysis
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        {/* Stats */}
        <section className="mb-8">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Overview
          </h2>
          <StatsCards stats={stats} loading={statsLoading} />
        </section>

        {/* Jobs List */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Analysis Jobs
            </h2>
          </div>
          <JobList jobs={jobs || []} loading={jobsLoading} onJobUpdate={() => refetchJobs()} />
        </section>
      </main>

      {/* New Job Dialog */}
      <NewJobDialog
        open={isNewJobOpen}
        onOpenChange={setIsNewJobOpen}
        onSuccess={() => {
          refetchJobs();
          setIsNewJobOpen(false);
        }}
      />
    </div>
  );
}
