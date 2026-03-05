"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Download } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { getJobResults, getExportUrl } from "@/lib/api";
import { getToken } from "@/lib/supabase";
import type { SearchResultsResponse } from "@/lib/types";
import { ResultCard } from "@/components/ResultCard";

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => { getToken().then(setToken); }, []);

  const { data, isLoading } = useQuery<SearchResultsResponse>({
    queryKey: ["results", id],
    queryFn: () => getJobResults(id, token!),
    enabled: !!token,
  });

  if (isLoading || !data) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">Загружаем результаты...</p>
      </main>
    );
  }

  return (
    <main className="max-w-3xl mx-auto px-4 py-10 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Результаты: &quot;{data.query}&quot;</h1>
          <p className="text-gray-500 text-sm mt-1">
            Просмотрено {data.total_candidates_scraped} кандидатов →{" "}
            {data.total_clusters} уникальных поставщиков
          </p>
        </div>
        <a
          href={getExportUrl(id)}
          download
          className="flex items-center gap-2 border border-gray-300 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-50 transition-colors text-sm"
        >
          <Download className="w-4 h-4" />
          Экспорт CSV
        </a>
      </div>

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
