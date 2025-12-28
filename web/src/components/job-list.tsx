"use client";

import Link from "next/link";
import {
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  ExternalLink,
  AlertTriangle,
  Square,
  Trash2,
} from "lucide-react";
import { JobSummary } from "@/lib/api";
import { formatDate, getStatusColor, cn } from "@/lib/utils";
import { useState } from "react";
import { api } from "@/lib/api";

interface JobListProps {
  jobs: JobSummary[];
  loading?: boolean;
  onJobUpdate?: () => void;
}

export function JobList({ jobs, loading, onJobUpdate }: JobListProps) {
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
        <JobCard key={job.id} job={job} onJobUpdate={onJobUpdate} />
      ))}
    </div>
  );
}

function JobCard({ job, onJobUpdate }: { job: JobSummary; onJobUpdate?: () => void }) {
  const [isStopping, setIsStopping] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const isRunning = [
    "pending",
    "queued",
    "cloning",
    "detecting_components",
    "scanning",
    "analyzing",
    "generating_report",
  ].includes(job.status.toLowerCase());

  const isCompleted = job.status === "completed";
  const isFailed = job.status === "failed";
  const isCancelled = job.status === "cancelled";

  const StatusIcon = isRunning
    ? Loader2
    : isCompleted
    ? CheckCircle
    : isFailed || isCancelled
    ? XCircle
    : Clock;

  const totalFindings = job.findings_count.total;
  const criticalAndHigh = job.findings_count
    ? (job.findings_count.critical || 0) + (job.findings_count.high || 0)
    : 0;

  const handleStop = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (!confirm("Are you sure you want to stop this job?")) return;
    
    setIsStopping(true);
    try {
      await api.stopJob(job.id);
      onJobUpdate?.();
    } catch (error) {
      console.error("Failed to stop job:", error);
      alert("Failed to stop job");
    } finally {
      setIsStopping(false);
    }
  };

  const handleDelete = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (!confirm("Are you sure you want to delete this job? This action cannot be undone.")) return;
    
    setIsDeleting(true);
    try {
      await api.deleteJob(job.id);
      onJobUpdate?.();
    } catch (error: any) {
      console.error("Failed to delete job:", error);
      alert(error.response?.data?.detail || "Failed to delete job");
    } finally {
      setIsDeleting(false);
    }
  };

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

          <div className="flex items-center gap-2 ml-4">
            {/* Action buttons */}
            {isRunning && (
              <button
                onClick={handleStop}
                disabled={isStopping}
                className="p-2 rounded-md bg-orange-500/10 text-orange-500 hover:bg-orange-500/20 transition-colors disabled:opacity-50"
                title="Stop job"
              >
                <Square className="h-4 w-4" />
              </button>
            )}
            
            {(isCompleted || isFailed || isCancelled) && (
              <button
                onClick={handleDelete}
                disabled={isDeleting}
                className="p-2 rounded-md bg-red-500/10 text-red-500 hover:bg-red-500/20 transition-colors disabled:opacity-50"
                title="Delete job"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}

            {/* Job details */}
            {isCompleted && (
              <div className="flex items-center gap-4">
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
      </div>
    </Link>
  );
}
