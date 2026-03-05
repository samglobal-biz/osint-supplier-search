"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { CheckCircle, Loader2, XCircle, ArrowRight } from "lucide-react";
import { getJobStatus } from "@/lib/api";
import { getToken } from "@/lib/supabase";
import type { JobStatusResponse } from "@/lib/types";
import { useQuery } from "@tanstack/react-query";

export default function JobProgressPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    getToken().then(setToken);
  }, []);

  const { data: job } = useQuery<JobStatusResponse>({
    queryKey: ["job", id],
    queryFn: () => getJobStatus(id, token!),
    enabled: !!token,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "complete" || status === "failed") return false;
      return 2000;
    },
  });

  // Auto-redirect on complete
  useEffect(() => {
    if (job?.status === "complete") {
      setTimeout(() => router.push(`/jobs/${id}/results`), 1000);
    }
  }, [job?.status]);

  const progress = job?.progress;
  const pct = progress?.adapters_total
    ? Math.round((progress.adapters_done / progress.adapters_total) * 100)
    : 0;

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="max-w-lg w-full space-y-6">
        <h1 className="text-2xl font-bold">
          {job?.query ? `Ищем: "${job.query}"` : "Запускаем поиск..."}
        </h1>

        {/* Progress bar */}
        <div>
          <div className="flex justify-between text-sm text-gray-500 mb-1">
            <span>Источники: {progress?.adapters_done ?? 0} / {progress?.adapters_total ?? "?"}</span>
            <span>{pct}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2.5">
            <div
              className="bg-blue-600 h-2.5 rounded-full transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>

        {/* Candidates count */}
        <div className="text-center text-gray-600">
          Найдено кандидатов: <span className="font-semibold text-gray-900">{progress?.candidates_found ?? 0}</span>
        </div>

        {/* Status */}
        <div className="flex items-center justify-center gap-2">
          {(!job || job.status === "pending" || job.status === "running") && (
            <><Loader2 className="w-5 h-5 animate-spin text-blue-600" /><span>Идёт поиск...</span></>
          )}
          {job?.status === "partial" && (
            <><Loader2 className="w-5 h-5 animate-spin text-yellow-500" /><span>Склеиваем дубли...</span></>
          )}
          {job?.status === "complete" && (
            <><CheckCircle className="w-5 h-5 text-green-600" /><span className="text-green-700">Готово! Переходим к результатам...</span></>
          )}
          {job?.status === "failed" && (
            <><XCircle className="w-5 h-5 text-red-500" /><span className="text-red-600">Ошибка: {job.error_message}</span></>
          )}
        </div>

        {/* View partial results */}
        {(job?.status === "partial" || job?.status === "complete") && (
          <button
            onClick={() => router.push(`/jobs/${id}/results`)}
            className="w-full flex items-center justify-center gap-2 border border-blue-600 text-blue-600 py-2.5 rounded-lg hover:bg-blue-50 transition-colors"
          >
            Смотреть результаты <ArrowRight className="w-4 h-4" />
          </button>
        )}
      </div>
    </main>
  );
}
