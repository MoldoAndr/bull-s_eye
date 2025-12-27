"use client";

import { useState, useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { X, Loader2, Sparkles, ChevronDown } from "lucide-react";
import { api, CreateJobRequest, Model } from "@/lib/api";

interface NewJobDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function NewJobDialog({
  open,
  onOpenChange,
  onSuccess,
}: NewJobDialogProps) {
  const [name, setName] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("main");
  const [selectedModel, setSelectedModel] = useState("deepseek-r1:70b");
  const [showModelDropdown, setShowModelDropdown] = useState(false);
  const [apiKey, setApiKey] = useState("");

  // Fetch available models
  const { data: models = [] } = useQuery({
    queryKey: ["models"],
    queryFn: api.getModels,
  });

  const createMutation = useMutation({
    mutationFn: (data: CreateJobRequest) => api.createJob(data),
    onSuccess: () => {
      setName("");
      setRepoUrl("");
      setBranch("main");
      setApiKey("");
      onSuccess();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const repoName = repoUrl.split("/").pop()?.replace(".git", "") || "Analysis";
    
    const trimmedApiKey = apiKey.trim();
    const data: CreateJobRequest = {
      repo_url: repoUrl,
      branch: branch,
      name: name || `Analysis of ${repoName}`,
      model: selectedModel,
      ...(trimmedApiKey ? { ollama_api_key: trimmedApiKey } : {}),
    };

    createMutation.mutate(data);
  };

  const selectedModelInfo = models.find((m) => m.id === selectedModel);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
      />

      {/* Dialog */}
      <div className="relative bg-card border border-border rounded-xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-border bg-gradient-to-r from-primary/5 to-transparent">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-primary/10">
              <Sparkles className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">New Analysis</h2>
              <p className="text-xs text-muted-foreground">Configure your codebase scan</p>
            </div>
          </div>
          <button
            onClick={() => onOpenChange(false)}
            className="p-2 hover:bg-accent rounded-lg transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-5">
          {/* Repository URL */}
          <div>
            <label className="block text-sm font-medium mb-2">
              Repository URL <span className="text-destructive">*</span>
            </label>
            <input
              type="url"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/user/repo.git"
              required
              className="w-full px-4 py-3 bg-background border border-input rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
            />
          </div>

          {/* Branch */}
          <div>
            <label className="block text-sm font-medium mb-2">Branch</label>
            <input
              type="text"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              placeholder="main"
              className="w-full px-4 py-3 bg-background border border-input rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
            />
          </div>

          {/* Analysis Name */}
          <div>
            <label className="block text-sm font-medium mb-2">
              Analysis Name <span className="text-muted-foreground">(optional)</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Auto-generated from repo name"
              className="w-full px-4 py-3 bg-background border border-input rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
            />
          </div>

          {/* Model Selection */}
          <div>
            <label className="block text-sm font-medium mb-2">
              AI Model <span className="text-destructive">*</span>
            </label>
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowModelDropdown(!showModelDropdown)}
                className="w-full px-4 py-3 bg-background border border-input rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all text-left flex items-center justify-between"
              >
                <div>
                  <div className="font-medium">{selectedModelInfo?.name || selectedModel}</div>
                  <div className="text-xs text-muted-foreground">
                    {selectedModelInfo?.description || "Select a model"}
                  </div>
                </div>
                <ChevronDown className={`h-5 w-5 text-muted-foreground transition-transform ${showModelDropdown ? 'rotate-180' : ''}`} />
              </button>

              {/* Dropdown */}
              {showModelDropdown && (
                <div className="absolute z-10 w-full mt-2 bg-popover border border-border rounded-lg shadow-lg max-h-64 overflow-y-auto">
                  {models.map((model) => (
                    <button
                      key={model.id}
                      type="button"
                      onClick={() => {
                        setSelectedModel(model.id);
                        setShowModelDropdown(false);
                      }}
                      className={`w-full px-4 py-3 text-left hover:bg-accent transition-colors ${
                        selectedModel === model.id ? "bg-primary/10 border-l-2 border-primary" : ""
                      }`}
                    >
                      <div className="font-medium">{model.name}</div>
                      <div className="text-xs text-muted-foreground">{model.description}</div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* API Key */}
          <div>
            <label className="block text-sm font-medium mb-2">
              Ollama API Key <span className="text-muted-foreground">(optional)</span>
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-..."
              autoComplete="off"
              className="w-full px-4 py-3 bg-background border border-input rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
            />
          </div>

          {/* Error Message */}
          {createMutation.isError && (
            <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-lg text-sm text-destructive">
              {createMutation.error instanceof Error
                ? createMutation.error.message
                : "Failed to create analysis job"}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={() => onOpenChange(false)}
              className="flex-1 px-4 py-3 border border-border rounded-lg hover:bg-accent transition-colors font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending || !repoUrl}
              className="flex-1 px-4 py-3 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {createMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Starting...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  Start Analysis
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
