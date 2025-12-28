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
  const { data: job, isLoading: jobLoading, error: jobError, refetch: refetchJob } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.getJob(jobId),
    retry: 3,
    retryDelay: 1000,
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
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto mb-4" />
          <p className="text-sm text-muted-foreground">Loading job details...</p>
        </div>
      </div>
    );
  }

  if (jobError) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center max-w-md">
          <AlertTriangle className="h-12 w-12 text-destructive mx-auto mb-4" />
          <h2 className="text-xl font-semibold mb-2">Failed to load job</h2>
          <p className="text-sm text-muted-foreground mb-4">
            {jobError instanceof Error ? jobError.message : "An error occurred while loading the job details"}
          </p>
          <div className="flex gap-2 justify-center">
            <button
              onClick={() => refetchJob()}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 flex items-center gap-2"
            >
              <RefreshCw className="h-4 w-4" />
              Retry
            </button>
            <Link
              href="/"
              className="px-4 py-2 border border-border rounded-lg hover:bg-accent flex items-center gap-2"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to home
            </Link>
          </div>
        </div>
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
      <header className="border-b border-primary/30 bg-black/40 backdrop-blur-md sticky top-0 z-10">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push("/")}
              className="p-2 hover:bg-primary/10 rounded-lg transition-colors text-primary"
            >
              <ArrowLeft className="h-5 w-5" />
            </button>
            <div className="flex-1">
              <h1 className="text-xl font-bold tracking-tighter uppercase italic">{job.name}</h1>
              <p className="text-[10px] text-primary/70 font-mono uppercase tracking-widest">
                {job.repo_url} • {job.branch}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Model:</span>
              <span className="text-[10px] font-mono font-bold px-2 py-1 bg-primary/20 border border-primary/30 text-primary rounded">
                {job.model}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Progress Status Bar */}
      <div className="border-b border-primary/20 bg-black/20">
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
        <div className="border-b border-primary/20 bg-black/40">
          <div className="container mx-auto px-4 py-3">
            <div className="flex items-center gap-4 flex-wrap">
              <span className="text-[10px] font-bold uppercase tracking-widest text-primary/80">Findings:</span>
              {findingsSummary.critical > 0 && (
                <span className="px-2 py-1 rounded-none text-[10px] font-bold uppercase bg-red-500/10 text-red-500 border border-red-500/30 font-mono">
                  {findingsSummary.critical} Critical
                </span>
              )}
              {findingsSummary.high > 0 && (
                <span className="px-2 py-1 rounded-none text-[10px] font-bold uppercase bg-orange-500/10 text-orange-500 border border-orange-500/30 font-mono">
                  {findingsSummary.high} High
                </span>
              )}
              {findingsSummary.medium > 0 && (
                <span className="px-2 py-1 rounded-none text-[10px] font-bold uppercase bg-yellow-500/10 text-yellow-500 border border-yellow-500/30 font-mono">
                  {findingsSummary.medium} Medium
                </span>
              )}
              {findingsSummary.low > 0 && (
                <span className="px-2 py-1 rounded-none text-[10px] font-bold uppercase bg-blue-500/10 text-blue-500 border border-blue-500/30 font-mono">
                  {findingsSummary.low} Low
                </span>
              )}
              {findingsSummary.info > 0 && (
                <span className="px-2 py-1 rounded-none text-[10px] font-bold uppercase bg-gray-500/10 text-gray-400 border border-gray-500/30 font-mono">
                  {findingsSummary.info} Info
                </span>
              )}
              <span className="text-[10px] text-primary/60 ml-auto font-mono uppercase tracking-widest">
                Total: {findingsSummary.total}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-primary/20 bg-black/60 sticky top-[73px] z-10 backdrop-blur-md">
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
                  "flex items-center gap-2 px-6 py-4 text-[10px] font-bold uppercase tracking-[0.2em] transition-all relative",
                  activeTab === tab.key
                    ? "text-primary"
                    : "text-muted-foreground hover:text-primary/70"
                )}
              >
                <tab.icon className="h-3 w-3" />
                {tab.label}
                {activeTab === tab.key && (
                  <div className="absolute bottom-0 left-0 w-full h-[2px] bg-primary shadow-[0_0_10px_rgba(4,6,89,0.8)]" />
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <main className="container mx-auto px-4 py-8">
        {/* Overview Tab */}
        {activeTab === "overview" && (
          <div className="space-y-8">
            {/* Job Info */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="cyber-card p-6">
                <h3 className="text-xs font-bold uppercase tracking-widest mb-6 text-primary border-b border-primary/20 pb-2">Job Information</h3>
                <dl className="space-y-4 text-[11px] font-mono">
                  <div className="flex justify-between items-center border-b border-primary/5 pb-2">
                    <dt className="text-muted-foreground uppercase tracking-tighter">Repository</dt>
                    <dd className="text-primary truncate max-w-[250px]">{job.repo_url}</dd>
                  </div>
                  <div className="flex justify-between items-center border-b border-primary/5 pb-2">
                    <dt className="text-muted-foreground uppercase tracking-tighter">Branch</dt>
                    <dd className="text-primary">{job.branch}</dd>
                  </div>
                  <div className="flex justify-between items-center border-b border-primary/5 pb-2">
                    <dt className="text-muted-foreground uppercase tracking-tighter">Model</dt>
                    <dd className="text-primary">{job.model}</dd>
                  </div>
                  <div className="flex justify-between items-center border-b border-primary/5 pb-2">
                    <dt className="text-muted-foreground uppercase tracking-tighter">Created</dt>
                    <dd className="text-primary">{formatDate(job.created_at)}</dd>
                  </div>
                  {job.started_at && (
                    <div className="flex justify-between items-center border-b border-primary/5 pb-2">
                      <dt className="text-muted-foreground uppercase tracking-tighter">Started</dt>
                      <dd className="text-primary">{formatDate(job.started_at)}</dd>
                    </div>
                  )}
                  {job.completed_at && (
                    <div className="flex justify-between items-center border-b border-primary/5 pb-2">
                      <dt className="text-muted-foreground uppercase tracking-tighter">Completed</dt>
                      <dd className="text-primary">{formatDate(job.completed_at)}</dd>
                    </div>
                  )}
                </dl>
              </div>

              {/* Status Log */}
              <div className="cyber-card p-6 max-h-[400px] overflow-y-auto">
                <h3 className="text-xs font-bold uppercase tracking-widest mb-6 text-primary border-b border-primary/20 pb-2">Activity Log</h3>
                <div className="space-y-4">
                  {statusUpdates?.updates.slice(0, 20).map((update, idx) => (
                    <div key={idx} className="text-[11px] border-l-2 border-primary/30 pl-4 py-1 font-mono">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-primary/90 uppercase tracking-tighter">{update.message}</span>
                        <span className="text-[9px] text-muted-foreground">
                          {new Date(update.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      {update.details && (
                        <p className="text-muted-foreground mt-1 italic text-[10px]">&gt; {update.details}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Error display */}
            {job.error_message && (
              <div className="bg-red-500/10 border border-red-500/30 p-6 font-mono">
                <h3 className="text-xs font-bold text-red-500 uppercase tracking-widest mb-2">Critical Error</h3>
                <p className="text-sm text-red-400">&gt; {job.error_message}</p>
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
