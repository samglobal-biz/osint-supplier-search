import ky from "ky";
import type { JobStatusResponse, SearchResultsResponse, SupplierResult } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/v1";

function apiClient(token?: string) {
  return ky.create({
    prefixUrl: API_URL,
    timeout: 60000,
    retry: { limit: 2, delay: () => 1000 },
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
}

export async function createSearch(
  query: string,
  filters: { countries: string[]; supplier_types: string[]; adapters: string[] },
  token: string
): Promise<{ job_id: string }> {
  return apiClient(token).post("search", { json: { query, filters } }).json();
}

export async function getJobStatus(jobId: string, token: string): Promise<JobStatusResponse> {
  return apiClient(token).get(`jobs/${jobId}`).json();
}

export async function getJobResults(jobId: string, token: string): Promise<SearchResultsResponse> {
  return apiClient(token).get(`jobs/${jobId}/results`).json();
}

export async function getSupplierProfile(clusterId: string, token: string): Promise<SupplierResult> {
  return apiClient(token).get(`suppliers/${clusterId}`).json();
}

export function getExportUrl(jobId: string): string {
  return `${API_URL}/jobs/${jobId}/export`;
}
