"use client";

import {
  Shield,
  AlertTriangle,
  CheckCircle,
  XCircle,
  FileSearch,
  Activity,
} from "lucide-react";
import { Stats } from "@/lib/api";

interface StatsCardsProps {
  stats?: Stats;
  loading?: boolean;
}

export function StatsCards({ stats, loading }: StatsCardsProps) {
  const cards = [
    {
      title: "Total Jobs",
      value: stats?.jobs?.total ?? 0,
      icon: FileSearch,
      color: "text-blue-500",
      bgColor: "bg-blue-500/10",
    },
    {
      title: "Completed",
      value: stats?.jobs?.completed ?? 0,
      icon: CheckCircle,
      color: "text-green-500",
      bgColor: "bg-green-500/10",
    },
    {
      title: "Failed",
      value: stats?.jobs?.failed ?? 0,
      icon: XCircle,
      color: "text-red-500",
      bgColor: "bg-red-500/10",
    },
    {
      title: "Total Findings",
      value: stats?.findings?.total ?? 0,
      icon: Activity,
      color: "text-purple-500",
      bgColor: "bg-purple-500/10",
    },
    {
      title: "Critical",
      value: stats?.findings?.critical ?? 0,
      icon: AlertTriangle,
      color: "text-red-500",
      bgColor: "bg-red-500/10",
    },
    {
      title: "High",
      value: stats?.findings?.high ?? 0,
      icon: Shield,
      color: "text-orange-500",
      bgColor: "bg-orange-500/10",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      {cards.map((card) => (
        <div
          key={card.title}
          className="bg-card border border-border rounded-lg p-4"
        >
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${card.bgColor}`}>
              <card.icon className={`h-5 w-5 ${card.color}`} />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{card.title}</p>
              {loading ? (
                <div className="h-7 w-12 bg-muted animate-pulse rounded" />
              ) : (
                <p className="text-2xl font-bold">{card.value}</p>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
