"use client";

import { useState, useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { X, Loader2, Sparkles, ChevronDown } from "lucide-react";
import { api, CreateJobRequest, Model } from "@/lib/api";

const DEFAULT_MODELS: Model[] = [
  {
    id: "deepseek-v3.2:cloud",
    name: "DeepSeek V3.2 Cloud",
    description: "Latest DeepSeek model for strong reasoning",
  },
  {
    id: "gpt-oss:120b-cloud",
    name: "GPT-OSS 120B Cloud",
    description: "Powerful open-source model for complex analysis",
  },
  {
    id: "kimi-k2-thinking:cloud",
    name: "Kimi K2 Thinking Cloud",
    description: "Long-form reasoning and deep analysis",
  },
];
const ALLOWED_MODEL_IDS = new Set(DEFAULT_MODELS.map((model) => model.id));

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
  const [selectedModel, setSelectedModel] = useState("");
  const [customModel, setCustomModel] = useState("");
  const [showModelDropdown, setShowModelDropdown] = useState(false);
  const [apiKeys, setApiKeys] = useState<string[]>([""]);

  // Fetch available models
  const { data: models = [] } = useQuery({
    queryKey: ["models"],
    queryFn: api.getModels,
  });
  const allowedModels = models.filter((model) => ALLOWED_MODEL_IDS.has(model.id));
  const modelOptions = allowedModels.length > 0 ? allowedModels : DEFAULT_MODELS;

  // Set default model when models are loaded
  useEffect(() => {
    if (!selectedModel) {
      const fallbackModel = modelOptions[0]?.id;
      if (fallbackModel) setSelectedModel(fallbackModel);
    }
  }, [modelOptions, selectedModel]);

  const createMutation = useMutation({
    mutationFn: (data: CreateJobRequest) => api.createJob(data),
    onSuccess: () => {
      setName("");
      setRepoUrl("");
      setBranch("main");
      setApiKeys([""]);
      setCustomModel("");
      onSuccess();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const repoName = repoUrl.split("/").pop()?.replace(".git", "") || "Analysis";
    
    const trimmedApiKeys = apiKeys.map((key) => key.trim()).filter(Boolean);
    const resolvedModel = customModel.trim() || selectedModel;
    if (!resolvedModel) return;
    const data: CreateJobRequest = {
      repo_url: repoUrl,
      branch: branch,
      name: name || `Analysis of ${repoName}`,
      model: resolvedModel,
      ...(trimmedApiKeys.length ? { ollama_api_keys: trimmedApiKeys } : {}),
    };

    createMutation.mutate(data);
  };

  const selectedModelInfo = modelOptions.find((m) => m.id === selectedModel);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
      />

      {/* Dialog */}
      <div className="relative cyber-card rounded-none shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-primary/30 bg-black/60">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-none bg-primary/20 border border-primary/50">
              <Sparkles className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h2 className="text-lg font-bold uppercase tracking-tighter italic">New Analysis</h2>
              <p className="text-[10px] text-primary/70 uppercase tracking-widest font-mono">Configure your codebase scan</p>
            </div>
          </div>
          <button
            onClick={() => onOpenChange(false)}
            className="p-2 hover:bg-primary/10 rounded-none transition-colors text-primary"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-5 bg-black/40">
          {/* Repository URL */}
          <div>
            <label className="block text-[10px] uppercase tracking-widest font-bold mb-2 text-primary/80">
              Repository URL <span className="text-red-500">*</span>
            </label>
            <input
              type="url"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/user/repo.git"
              required
              className="w-full px-4 py-3 bg-black/60 border border-primary/30 rounded-none focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all font-mono text-sm"
            />
          </div>

          {/* Branch */}
          <div>
            <label className="block text-[10px] uppercase tracking-widest font-bold mb-2 text-primary/80">Branch</label>
            <input
              type="text"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              placeholder="main"
              className="w-full px-4 py-3 bg-black/60 border border-primary/30 rounded-none focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all font-mono text-sm"
            />
          </div>

          {/* Analysis Name */}
          <div>
            <label className="block text-[10px] uppercase tracking-widest font-bold mb-2 text-primary/80">
              Analysis Name <span className="text-muted-foreground lowercase font-normal">(optional)</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Auto-generated from repo name"
              className="w-full px-4 py-3 bg-black/60 border border-primary/30 rounded-none focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all font-mono text-sm"
            />
          </div>

          {/* Model Selection */}
          <div>
            <label className="block text-[10px] uppercase tracking-widest font-bold mb-2 text-primary/80">
              AI Model <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowModelDropdown(!showModelDropdown)}
                className="w-full px-4 py-3 bg-black/60 border border-primary/30 rounded-none focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all text-left flex items-center justify-between"
              >
                <div>
                  <div className="font-bold font-mono text-sm text-primary">{selectedModelInfo?.name || selectedModel || "Select a model"}</div>
                  <div className="text-[10px] text-muted-foreground uppercase tracking-tighter">
                    {selectedModelInfo?.description || "Choose from available models"}
                  </div>
                </div>
                <ChevronDown className={`h-5 w-5 text-primary transition-transform ${showModelDropdown ? "rotate-180" : ""}`} />
              </button>

              {/* Dropdown */}
              {showModelDropdown && (
                <div className="absolute z-20 w-full mt-1 bg-black border border-primary/50 rounded-none shadow-[0_0_20px_rgba(4,6,89,0.8)] max-h-64 overflow-y-auto">
                  {modelOptions.length > 0 ? (
                    modelOptions.map((model) => (
                      <button
                        key={model.id}
                        type="button"
                        onClick={() => {
                          setSelectedModel(model.id);
                          setCustomModel("");
                          setShowModelDropdown(false);
                        }}
                        className={`w-full px-4 py-3 text-left hover:bg-primary/20 transition-colors border-b border-primary/10 last:border-0 ${
                          selectedModel === model.id ? "bg-primary/10 border-l-2 border-primary" : ""
                        }`}
                      >
                        <div className="font-bold font-mono text-sm">{model.name}</div>
                        <div className="text-[10px] text-muted-foreground uppercase tracking-tighter">{model.description}</div>
                      </button>
                    ))
                  ) : (
                    <div className="px-4 py-3 text-[10px] text-muted-foreground uppercase italic">No models found</div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Custom Model */}
          <div>
            <label className="block text-[10px] uppercase tracking-widest font-bold mb-2 text-primary/80">
              Custom Model <span className="text-muted-foreground lowercase font-normal">(optional)</span>
            </label>
            <input
              type="text"
              value={customModel}
              onChange={(e) => setCustomModel(e.target.value)}
              placeholder="Enter model name (e.g. deepseek-v3.2:cloud)"
              className="w-full px-4 py-3 bg-black/60 border border-primary/30 rounded-none focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all font-mono text-sm"
            />
            <p className="mt-2 text-[10px] text-muted-foreground uppercase tracking-widest font-mono">
              Custom entry overrides the list selection.
            </p>
          </div>

          {/* API Key */}
          <div>
            <label className="block text-[10px] uppercase tracking-widest font-bold mb-2 text-primary/80">
              Ollama API Keys <span className="text-muted-foreground lowercase font-normal">(optional)</span>
            </label>
            <div className="space-y-2">
              {apiKeys.map((key, index) => (
                <div key={index} className="flex gap-2">
                  <input
                    type="password"
                    value={key}
                    onChange={(e) => {
                      const nextKeys = [...apiKeys];
                      nextKeys[index] = e.target.value;
                      setApiKeys(nextKeys);
                    }}
                    placeholder="sk-..."
                    autoComplete="off"
                    className="flex-1 px-4 py-3 bg-black/60 border border-primary/30 rounded-none focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all font-mono text-sm"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      if (apiKeys.length === 1) {
                        setApiKeys([""]);
                        return;
                      }
                      setApiKeys(apiKeys.filter((_, idx) => idx !== index));
                    }}
                    className="px-3 border border-primary/30 hover:bg-primary/10 text-[10px] uppercase font-bold"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
            <div className="mt-2 flex items-center justify-between text-[10px] uppercase tracking-widest font-mono text-muted-foreground">
              <span>Multiple keys enable parallel LLM workers.</span>
              <button
                type="button"
                onClick={() => setApiKeys([...apiKeys, ""])}
                className="px-3 py-1 border border-primary/30 hover:bg-primary/10 text-primary font-bold"
              >
                Add Key
              </button>
            </div>
          </div>

          {/* Error Message */}
          {createMutation.isError && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-none text-[10px] uppercase font-bold text-red-500 font-mono">
              &gt; ERROR: {createMutation.error instanceof Error
                ? createMutation.error.message
                : "Failed to create analysis job"}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={() => onOpenChange(false)}
              className="flex-1 px-4 py-3 border border-primary/30 rounded-none hover:bg-primary/10 transition-colors font-bold uppercase text-xs tracking-widest"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending || !repoUrl || !(customModel.trim() || selectedModel)}
              className="cyber-button flex-1 px-4 py-3 bg-primary text-primary-foreground font-bold uppercase text-xs tracking-widest disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {createMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Initializing...
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
