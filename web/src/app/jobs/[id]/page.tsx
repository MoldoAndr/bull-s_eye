"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Target,
  Shield,
  FileCode,
  AlertTriangle,
  CheckCircle,
  Clock,
  Loader2,
  Download,
  ExternalLink,
  Activity,
  GitBranch,
  Cpu,
  RefreshCw,
} from "lucide-react";
import { api, Job, Component, Finding, subscribeToJobStatus } from "@/lib/api";
import { formatDate, cn } from "@/lib/utils";

// Status stages for the progress bar
const STAGES = [
  { key: "pending", label: "Queued", icon: Clock },
  { key: "cloning", label: "Cloning", icon: GitBranch },
  { key: "detecting_components", label: "Detecting", icon: Target },
  { key: "scanning", label: "Scanning", icon: Shield },
  { key: "analyzing", label: "Analyzing", icon: Cpu },
  { key: "generating_report", label: "Reporting", icon: FileCode },
  { key: "completed", label: "Complete", icon: CheckCircle },
];

function getStageIndex(status: string): number {
  const idx = STAGES.findIndex((s) => s.key === status);
  return idx >= 0 ? idx : 0;
}

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.id as string;

  const [activeTab, setActiveTab] = useState<"overview" | "components" | "findings" | "report">("overview");
  const [severityFilter, setSeverityFilter] = useState<string | undefined>();
  const [liveStatus, setLiveStatus] = useState<{
    status: string;
    progress: number;
    message?: string;
    detail?: string;
  } | null>(null);

  // Main job query
  const { data: job, isLoading: jobLoading, refetch: refetchJob } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.getJob(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "completed" || status === "failed" ? false : 5000;
    },
  });

  // Status updates query
  const { data: statusUpdates } = useQuery({
    queryKey: ["status-updates", jobId],
    queryFn: () => api.getJobStatusUpdates(jobId, 100),
    refetchInterval: job?.status === "completed" || job?.status === "failed" ? false : 3000,
  });

  // Components query
  const { data: components } = useQuery({
    queryKey: ["components", jobId],
    queryFn: () => api.getComponents(jobId),
    enabled: !!job && (job.status === "completed" || job.status === "analyzing"),
  });

  // Findings query
  const { data: findings } = useQuery({
    queryKey: ["findings", jobId, severityFilter],
    queryFn: () => api.getFindings(jobId, { severity: severityFilter }),
    enabled: !!job && job.status === "completed",
  });

  // Findings summary
  const { data: findingsSummary } = useQuery({
    queryKey: ["findings-summary", jobId],
    queryFn: () => api.getFindingsSummary(jobId),
    enabled: !!job,
    refetchInterval: job?.status === "completed" ? false : 5000,
  });

  // Report query
  const { data: report } = useQuery({
    queryKey: ["report", jobId],
    queryFn: () => api.getReport(jobId),
    enabled: !!job && job.status === "completed" && activeTab === "report",
  });

  // SSE subscription for real-time updates
  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") return;

    const unsubscribe = subscribeToJobStatus(
      jobId,
      (data) => {
        setLiveStatus(data);
        if (data.status === "completed" || data.status === "failed") {
          refetchJob();
        }
      },
      () => refetchJob()
    );

    return unsubscribe;
  }, [jobId, job?.status, refetchJob]);

  if (jobLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-semibold mb-2">Job not found</h2>
          <Link href="/" className="text-primary hover:underline">
            Back to home
          </Link>
        </div>
      </div>
    );
  }

  const currentStatus = liveStatus?.status || job.status;
  const currentProgress = liveStatus?.progress ?? job.progress;
  const currentMessage = liveStatus?.message || job.status_message;
  const currentDetail = liveStatus?.detail || job.progress_detail;
  const isRunning = !["completed", "failed"].includes(currentStatus);
  const stageIndex = getStageIndex(currentStatus);

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card sticky top-0 z-10">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push("/")}
              className="p-2 hover:bg-accent rounded-lg transition-colors"
            >
              <ArrowLeft className="h-5 w-5" />
            </button>
            <div className="flex-1">
              <h1 className="text-xl font-bold">{job.name}</h1>
              <p className="text-sm text-muted-foreground">
                {job.repo_url} • {job.branch}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Model:</span>
              <span className="text-xs font-medium px-2 py-1 bg-primary/10 rounded">
                {job.model}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Progress Status Bar */}
      <div className="border-b border-border bg-card/50">
        <div className="container mx-auto px-4 py-6">
          {/* Stage Progress */}
          <div className="flex items-center justify-between mb-4">
            {STAGES.map((stage, idx) => {
              const Icon = stage.icon;
              const isActive = idx === stageIndex;
              const isComplete = idx < stageIndex || currentStatus === "completed";
              const isFailed = currentStatus === "failed" && idx === stageIndex;

              return (
                <div key={stage.key} className="flex flex-col items-center flex-1">
                  <div className="flex items-center w-full">
                    {idx > 0 && (
                      <div
                        className={cn(
                          "flex-1 h-1 rounded-full transition-colors",
                          isComplete ? "bg-green-500" : "bg-border"
                        )}
                      />
                    )}
                    <div
                      className={cn(
                        "w-10 h-10 rounded-full flex items-center justify-center transition-all",
                        isActive && isRunning && "ring-4 ring-primary/30 bg-primary text-primary-foreground animate-pulse",
                        isComplete && "bg-green-500 text-white",
                        isFailed && "bg-destructive text-destructive-foreground",
                        !isActive && !isComplete && !isFailed && "bg-muted text-muted-foreground"
                      )}
                    >
                      {isActive && isRunning ? (
                        <Loader2 className="h-5 w-5 animate-spin" />
                      ) : (
                        <Icon className="h-5 w-5" />
                      )}
                    </div>
                    {idx < STAGES.length - 1 && (
                      <div
                        className={cn(
                          "flex-1 h-1 rounded-full transition-colors",
                          idx < stageIndex ? "bg-green-500" : "bg-border"
                        )}
                      />
                    )}
                  </div>
                  <span className={cn(
                    "text-xs mt-2 font-medium",
                    isActive ? "text-foreground" : "text-muted-foreground"
                  )}>
                    {stage.label}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Current Status Detail */}
          <div className="bg-background rounded-lg p-4 border border-border">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                {isRunning && <Activity className="h-4 w-4 text-primary animate-pulse" />}
                <span className="font-medium">{currentMessage || currentStatus}</span>
              </div>
              <span className="text-sm text-muted-foreground">
                {currentProgress}%
              </span>
            </div>
            
            {/* Progress Bar */}
            <div className="h-2 bg-muted rounded-full overflow-hidden mb-2">
              <div
                className={cn(
                  "h-full transition-all duration-500 rounded-full",
                  currentStatus === "failed" ? "bg-destructive" : "bg-primary"
                )}
                style={{ width: `${currentProgress}%` }}
              />
            </div>
            
            {/* Detail */}
            {currentDetail && (
              <p className="text-xs text-muted-foreground">{currentDetail}</p>
            )}
          </div>
        </div>
      </div>

      {/* Findings Summary Bar */}
      {findingsSummary && findingsSummary.total > 0 && (
        <div className="border-b border-border bg-card/30">
          <div className="container mx-auto px-4 py-3">
            <div className="flex items-center gap-4 flex-wrap">
              <span className="text-sm font-medium">Findings:</span>
              {findingsSummary.critical > 0 && (
                <span className="px-2 py-1 rounded text-xs font-medium bg-red-500/10 text-red-600 border border-red-500/20">
                  {findingsSummary.critical} Critical
                </span>
              )}
              {findingsSummary.high > 0 && (
                <span className="px-2 py-1 rounded text-xs font-medium bg-orange-500/10 text-orange-600 border border-orange-500/20">
                  {findingsSummary.high} High
                </span>
              )}
              {findingsSummary.medium > 0 && (
                <span className="px-2 py-1 rounded text-xs font-medium bg-yellow-500/10 text-yellow-600 border border-yellow-500/20">
                  {findingsSummary.medium} Medium
                </span>
              )}
              {findingsSummary.low > 0 && (
                <span className="px-2 py-1 rounded text-xs font-medium bg-blue-500/10 text-blue-600 border border-blue-500/20">
                  {findingsSummary.low} Low
                </span>
              )}
              {findingsSummary.info > 0 && (
                <span className="px-2 py-1 rounded text-xs font-medium bg-gray-500/10 text-gray-600 border border-gray-500/20">
                  {findingsSummary.info} Info
                </span>
              )}
              <span className="text-sm text-muted-foreground ml-auto">
                Total: {findingsSummary.total}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-border bg-card/30">
        <div className="container mx-auto px-4">
          <div className="flex gap-1">
            {[
              { key: "overview", label: "Overview", icon: Target },
              { key: "components", label: "Components", icon: FileCode },
              { key: "findings", label: "Findings", icon: AlertTriangle },
              { key: "report", label: "Report", icon: Download },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key as any)}
                className={cn(
                  "flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors",
                  activeTab === tab.key
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                )}
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <main className="container mx-auto px-4 py-6">
        {/* Overview Tab */}
        {activeTab === "overview" && (
          <div className="space-y-6">
            {/* Job Info */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-card rounded-lg border border-border p-4">
                <h3 className="font-medium mb-3">Job Information</h3>
                <dl className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Repository</dt>
                    <dd className="font-mono text-xs">{job.repo_url}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Branch</dt>
                    <dd>{job.branch}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Model</dt>
                    <dd>{job.model}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Created</dt>
                    <dd>{formatDate(job.created_at)}</dd>
                  </div>
                  {job.started_at && (
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Started</dt>
                      <dd>{formatDate(job.started_at)}</dd>
                    </div>
                  )}
                  {job.completed_at && (
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Completed</dt>
                      <dd>{formatDate(job.completed_at)}</dd>
                    </div>
                  )}
                </dl>
              </div>

              {/* Status Log */}
              <div className="bg-card rounded-lg border border-border p-4 max-h-80 overflow-y-auto">
                <h3 className="font-medium mb-3">Activity Log</h3>
                <div className="space-y-2">
                  {statusUpdates?.updates.slice(0, 20).map((update, idx) => (
                    <div key={idx} className="text-sm border-l-2 border-border pl-3 py-1">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{update.message}</span>
                        <span className="text-xs text-muted-foreground">
                          {new Date(update.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      {update.details && (
                        <p className="text-xs text-muted-foreground mt-1">{update.details}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Error display */}
            {job.error_message && (
              <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4">
                <h3 className="font-medium text-destructive mb-2">Error</h3>
                <p className="text-sm">{job.error_message}</p>
              </div>
            )}
          </div>
        )}

        {/* Components Tab */}
        {activeTab === "components" && (
          <div className="space-y-4">
            {components && components.length > 0 ? (
              components.map((comp) => (
                <div key={comp.id} className="bg-card rounded-lg border border-border p-4">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <h3 className="font-medium">{comp.name}</h3>
                      <p className="text-sm text-muted-foreground">{comp.path}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs px-2 py-1 bg-muted rounded">{comp.language}</span>
                      <span className="text-xs px-2 py-1 bg-muted rounded">{comp.component_type}</span>
                      {comp.health_score !== null && comp.health_score !== undefined && (
                        <span className={cn(
                          "text-xs px-2 py-1 rounded font-medium",
                          comp.health_score >= 80 ? "bg-green-500/10 text-green-600" :
                          comp.health_score >= 50 ? "bg-yellow-500/10 text-yellow-600" :
                          "bg-red-500/10 text-red-600"
                        )}>
                          Health: {comp.health_score}%
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <span>{comp.file_count} files</span>
                    <span>{comp.line_count.toLocaleString()} lines</span>
                  </div>
                  {comp.analysis_summary && (
                    <p className="mt-2 text-sm">{comp.analysis_summary}</p>
                  )}
                </div>
              ))
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                {isRunning ? "Components will appear as they are detected..." : "No components found"}
              </div>
            )}
          </div>
        )}

        {/* Findings Tab */}
        {activeTab === "findings" && (
          <div className="space-y-4">
            {/* Severity Filter */}
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => setSeverityFilter(undefined)}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                  !severityFilter ? "bg-primary text-primary-foreground" : "bg-muted hover:bg-accent"
                )}
              >
                All
              </button>
              {["critical", "high", "medium", "low", "info"].map((sev) => (
                <button
                  key={sev}
                  onClick={() => setSeverityFilter(sev)}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-sm font-medium capitalize transition-colors",
                    severityFilter === sev ? "bg-primary text-primary-foreground" : "bg-muted hover:bg-accent"
                  )}
                >
                  {sev}
                </button>
              ))}
            </div>

            {/* Findings List */}
            {findings && findings.length > 0 ? (
              findings.map((finding) => (
                <div key={finding.id} className="bg-card rounded-lg border border-border p-4">
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="font-medium">{finding.title}</h3>
                    <span className={cn(
                      "text-xs px-2 py-1 rounded font-medium capitalize",
                      finding.severity === "critical" && "bg-red-500/10 text-red-600 border border-red-500/20",
                      finding.severity === "high" && "bg-orange-500/10 text-orange-600 border border-orange-500/20",
                      finding.severity === "medium" && "bg-yellow-500/10 text-yellow-600 border border-yellow-500/20",
                      finding.severity === "low" && "bg-blue-500/10 text-blue-600 border border-blue-500/20",
                      finding.severity === "info" && "bg-gray-500/10 text-gray-600 border border-gray-500/20",
                    )}>
                      {finding.severity}
                    </span>
                  </div>
                  {finding.description && (
                    <p className="text-sm text-muted-foreground mb-2">{finding.description}</p>
                  )}
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <span>Scanner: {finding.scanner}</span>
                    {finding.file_path && <span>File: {finding.file_path}</span>}
                    {finding.line_start && <span>Line: {finding.line_start}</span>}
                  </div>
                  {finding.suggestion && (
                    <div className="mt-3 p-3 bg-muted/50 rounded text-sm">
                      <strong>Suggestion:</strong> {finding.suggestion}
                    </div>
                  )}
                  {finding.llm_explanation && (
                    <div className="mt-2 p-3 bg-primary/5 rounded text-sm border-l-2 border-primary">
                      <strong>AI Analysis:</strong> {finding.llm_explanation}
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                {isRunning ? "Findings will appear as analysis progresses..." : "No findings found"}
              </div>
            )}
          </div>
        )}

        {/* Report Tab */}
        {activeTab === "report" && (
          <div className="space-y-6">
            {report ? (
              <>
                <div className="bg-card rounded-lg border border-border p-6">
                  <h2 className="text-xl font-bold mb-4">Executive Summary</h2>
                  <div className="prose prose-sm dark:prose-invert max-w-none">
                    <p className="whitespace-pre-wrap">{report.executive_summary}</p>
                  </div>
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = `report-${jobId}.json`;
                      a.click();
                    }}
                    className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 flex items-center gap-2"
                  >
                    <Download className="h-4 w-4" />
                    Download JSON
                  </button>
                </div>
              </>
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                {isRunning ? "Report will be generated when analysis completes..." : "Report not available"}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
