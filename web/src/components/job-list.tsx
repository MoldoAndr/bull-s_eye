"use client";

import Link from "next/link";
import {
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  ExternalLink,
  AlertTriangle,
} from "lucide-react";
import { JobSummary } from "@/lib/api";
import { formatDate, getStatusColor, cn } from "@/lib/utils";

interface JobListProps {
  jobs: JobSummary[];
  loading?: boolean;
}

export function JobList({ jobs, loading }: JobListProps) {
  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="bg-card border border-border rounded-lg p-4 animate-pulse"
          >
            <div className="flex items-center justify-between">
              <div className="space-y-2">
                <div className="h-5 w-48 bg-muted rounded" />
                <div className="h-4 w-32 bg-muted rounded" />
              </div>
              <div className="h-8 w-24 bg-muted rounded" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="bg-card border border-border rounded-lg p-12 text-center">
        <Clock className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
        <h3 className="text-lg font-medium mb-2">No analysis jobs yet</h3>
        <p className="text-muted-foreground">
          Create a new analysis to get started
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {jobs.map((job) => (
        <JobCard key={job.id} job={job} />
      ))}
    </div>
  );
}

function JobCard({ job }: { job: JobSummary }) {
  const isRunning = [
    "pending",
    "queued",
    "cloning",
    "detecting_components",
    "scanning",
    "analyzing",
    "generating_report",
  ].includes(
    job.status.toLowerCase()
  );

  const StatusIcon = isRunning
    ? Loader2
    : job.status === "completed"
    ? CheckCircle
    : job.status === "failed"
    ? XCircle
    : Clock;

  const totalFindings = job.findings_count.total;

  const criticalAndHigh = job.findings_count
    ? (job.findings_count.critical || 0) + (job.findings_count.high || 0)
    : 0;

  return (
    <Link href={`/jobs/${job.id}`}>
      <div className="bg-card border border-border rounded-lg p-4 hover:border-primary/50 transition-colors cursor-pointer">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-medium truncate">{job.name}</h3>
              <span
                className={cn(
                  "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium",
                  getStatusColor(job.status)
                )}
              >
                <StatusIcon
                  className={cn("h-3 w-3", isRunning && "animate-spin")}
                />
                {job.status}
              </span>
            </div>

            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              {job.repo_url && (
                <span className="truncate max-w-[200px]">{job.repo_url}</span>
              )}
              <span>{formatDate(job.created_at)}</span>
            </div>

            {isRunning && (
              <div className="mt-2">
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="text-muted-foreground">Progress</span>
                  <span className="font-medium">{job.progress}%</span>
                </div>
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary transition-all duration-500"
                    style={{ width: `${job.progress}%` }}
                  />
                </div>
              </div>
            )}
          </div>

          {job.status === "completed" && (
            <div className="flex items-center gap-4 ml-4">
              <div className="text-right">
                <div className="text-sm text-muted-foreground">Findings</div>
                <div className="text-lg font-semibold">{totalFindings}</div>
              </div>
              {criticalAndHigh > 0 && (
                <div className="flex items-center gap-1 text-orange-500">
                  <AlertTriangle className="h-5 w-5" />
                  <span className="font-semibold">{criticalAndHigh}</span>
                </div>
              )}
              <ExternalLink className="h-5 w-5 text-muted-foreground" />
            </div>
          )}
        </div>
      </div>
    </Link>
  );
}
