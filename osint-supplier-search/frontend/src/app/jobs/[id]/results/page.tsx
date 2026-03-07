"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Download, LayoutList, Layers } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { getJobResults, getExportUrl } from "@/lib/api";
import { getToken } from "@/lib/supabase";
import type { SearchResultsResponse } from "@/lib/types";
import { ResultCard } from "@/components/ResultCard";

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const [token, setToken] = useState<string | null>(null);
  const [showRaw, setShowRaw] = useState(false);

  useEffect(() => { getToken().then(setToken); }, []);

  const { data, isLoading } = useQuery<SearchResultsResponse>({
    queryKey: ["results", id, showRaw],
    queryFn: () => getJobResults(id, token!, showRaw),
    enabled: !!token,
  });

  if (isLoading || !data) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">Загружаем результаты...</p>
      </main>
    );
  }

  const isRawMode = showRaw || data.results.every(r => r.rank_score === 0);

  return (
    <main className="max-w-3xl mx-auto px-4 py-10 space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold">Результаты: &quot;{data.query}&quot;</h1>
          <p className="text-gray-500 text-sm mt-1">
            Просмотрено {data.total_candidates_scraped} кандидатов →{" "}
            {data.total_clusters} уникальных поставщиков
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Raw / Clustered toggle */}
          <div className="flex rounded-lg border border-gray-300 overflow-hidden text-sm">
            <button
              onClick={() => setShowRaw(false)}
              className={`flex items-center gap-1.5 px-3 py-2 transition-colors ${
                !showRaw ? "bg-blue-600 text-white" : "bg-white text-gray-600 hover:bg-gray-50"
              }`}
            >
              <Layers className="w-4 h-4" />
              Кластеры
            </button>
            <button
              onClick={() => setShowRaw(true)}
              className={`flex items-center gap-1.5 px-3 py-2 transition-colors border-l border-gray-300 ${
                showRaw ? "bg-blue-600 text-white" : "bg-white text-gray-600 hover:bg-gray-50"
              }`}
            >
              <LayoutList className="w-4 h-4" />
              Сырые данные
            </button>
          </div>

          <a
            href={getExportUrl(id)}
            download
            className="flex items-center gap-2 border border-gray-300 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-50 transition-colors text-sm"
          >
            <Download className="w-4 h-4" />
            CSV
          </a>
        </div>
      </div>

      {isRawMode && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-2 text-sm text-amber-700">
          Сырые кандидаты — необработанные данные из источников без дедупликации
        </div>
      )}

      <div className="space-y-4">
        {data.results.map(supplier => (
          <ResultCard key={supplier.cluster_id} supplier={supplier} />
        ))}
        {data.results.length === 0 && (
          <p className="text-gray-400 text-center py-12">Поставщики не найдены</p>
        )}
      </div>
    </main>
  );
}
