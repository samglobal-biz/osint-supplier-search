export type SupplierType =
  | "manufacturer"
  | "distributor"
  | "importer"
  | "exporter"
  | "wholesaler"
  | "trader";

export type JobStatus = "pending" | "running" | "partial" | "complete" | "failed";

export interface SearchFilters {
  countries: string[];
  supplier_types: SupplierType[];
  adapters: string[];
}

export interface JobProgress {
  adapters_done: number;
  adapters_total: number;
  candidates_found: number;
}

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  query: string;
  progress: JobProgress;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  error_message?: string;
}

export interface EvidenceLink {
  adapter: string;
  source_url: string;
  matched_fields: string[];
  field_scores: Record<string, number>;
  snippet?: string;
  scraped_at?: string;
}

export interface SupplierResult {
  rank: number;
  cluster_id: string;
  canonical_name: string;
  canonical_country?: string;
  canonical_address?: string;
  canonical_phone?: string;
  canonical_email?: string;
  canonical_website?: string;
  canonical_tin?: string;
  canonical_lei?: string;
  supplier_types: SupplierType[];
  industry_tags: string[];
  sanction_flag: boolean;
  confidence_score: number;
  rank_score: number;
  source_count: number;
  resolution_methods: string[];
  evidence: EvidenceLink[];
}

export interface SearchResultsResponse {
  job_id: string;
  query: string;
  status: JobStatus;
  total_candidates_scraped: number;
  total_clusters: number;
  results: SupplierResult[];
  completed_at?: string;
}
