-- ============================================================
-- OSINT Supplier Search System — Initial Schema
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- search_jobs
-- ============================================================
CREATE TABLE search_jobs (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          UUID REFERENCES auth.users(id),
    query            TEXT NOT NULL,
    filters          JSONB DEFAULT '{}',
    -- filters example: {"countries": ["DE","TR"], "supplier_types": ["importer","trader"], "adapters": ["kompass"]}
    status           TEXT NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending','running','partial','complete','failed')),
    adapters_total   INT DEFAULT 0,
    adapters_done    INT DEFAULT 0,
    candidates_found INT DEFAULT 0,
    error_message    TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    completed_at     TIMESTAMPTZ
);

CREATE INDEX idx_search_jobs_user    ON search_jobs(user_id, created_at DESC);
CREATE INDEX idx_search_jobs_status  ON search_jobs(status);

-- ============================================================
-- raw_candidates
-- ============================================================
CREATE TABLE raw_candidates (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id           UUID NOT NULL REFERENCES search_jobs(id) ON DELETE CASCADE,
    adapter          TEXT NOT NULL,
    source_url       TEXT NOT NULL,
    raw_name         TEXT,
    raw_address      TEXT,
    raw_country      TEXT,
    raw_phone        TEXT,
    raw_email        TEXT,
    raw_website      TEXT,
    raw_description  TEXT,
    raw_tin          TEXT,
    raw_lei          TEXT,
    supplier_type    TEXT CHECK (supplier_type IN (
                         'manufacturer','distributor','importer',
                         'exporter','wholesaler','trader',NULL)),
    extra_fields     JSONB DEFAULT '{}',
    cluster_id       UUID,   -- FK added after entity_clusters created
    scraped_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_rc_job      ON raw_candidates(job_id);
CREATE INDEX idx_rc_cluster  ON raw_candidates(cluster_id);
CREATE INDEX idx_rc_adapter  ON raw_candidates(adapter);
CREATE INDEX idx_rc_name_trgm ON raw_candidates USING GIN (raw_name gin_trgm_ops);

-- ============================================================
-- entity_clusters
-- ============================================================
CREATE TABLE entity_clusters (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id              UUID NOT NULL REFERENCES search_jobs(id) ON DELETE CASCADE,
    canonical_name      TEXT NOT NULL,
    canonical_address   TEXT,
    canonical_country   TEXT,               -- ISO 3166-1 alpha-2
    canonical_phone     TEXT,               -- E.164
    canonical_email     TEXT,
    canonical_website   TEXT,               -- registered domain only
    canonical_tin       TEXT,
    canonical_lei       TEXT,
    supplier_types      TEXT[] DEFAULT '{}',
    industry_tags       TEXT[] DEFAULT '{}',
    employee_range      TEXT,
    founding_year       INT,
    description         TEXT,
    sanction_flag       BOOLEAN DEFAULT FALSE,   -- OFAC hit
    -- Resolution metadata
    source_count        INT DEFAULT 1,
    confidence_score    FLOAT NOT NULL DEFAULT 0,
    resolution_methods  TEXT[] DEFAULT '{}',     -- ['lei_match','name_fuzzy',...]
    -- Ranking
    rank_score          FLOAT DEFAULT 0,
    -- Embedding for ANN dedup
    name_embedding      vector(384),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cluster_job        ON entity_clusters(job_id, rank_score DESC);
CREATE INDEX idx_cluster_country    ON entity_clusters(canonical_country);
CREATE INDEX idx_cluster_confidence ON entity_clusters(confidence_score DESC);
CREATE INDEX idx_cluster_name_trgm  ON entity_clusters USING GIN (canonical_name gin_trgm_ops);
CREATE INDEX idx_cluster_embedding  ON entity_clusters
    USING hnsw (name_embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Add FK from raw_candidates to entity_clusters
ALTER TABLE raw_candidates
    ADD CONSTRAINT fk_rc_cluster
    FOREIGN KEY (cluster_id) REFERENCES entity_clusters(id);

-- ============================================================
-- evidence_links
-- ============================================================
CREATE TABLE evidence_links (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cluster_id        UUID NOT NULL REFERENCES entity_clusters(id) ON DELETE CASCADE,
    raw_candidate_id  UUID REFERENCES raw_candidates(id),
    adapter           TEXT NOT NULL,
    source_url        TEXT NOT NULL,
    matched_fields    TEXT[] DEFAULT '{}',
    field_scores      JSONB DEFAULT '{}',   -- {"name": 0.92, "address": 0.85}
    snippet           TEXT,
    scraped_at        TIMESTAMPTZ
);

CREATE INDEX idx_evidence_cluster ON evidence_links(cluster_id);

-- ============================================================
-- adapter_cache
-- ============================================================
CREATE TABLE adapter_cache (
    cache_key      TEXT PRIMARY KEY,    -- SHA256(adapter + normalized_query)
    adapter        TEXT NOT NULL,
    response_data  JSONB NOT NULL,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    expires_at     TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_cache_expires ON adapter_cache(expires_at);

-- ============================================================
-- adapter_rate_limits
-- ============================================================
CREATE TABLE adapter_rate_limits (
    adapter              TEXT PRIMARY KEY,
    requests_per_minute  INT DEFAULT 10,
    requests_per_day     INT DEFAULT 500,
    enabled              BOOLEAN DEFAULT TRUE,
    notes                TEXT
);

-- Seed adapter configs
INSERT INTO adapter_rate_limits (adapter, requests_per_minute, requests_per_day, notes) VALUES
    ('opencorporates',   5,  50,   'Free tier: 50/day'),
    ('gleif',           60, 5000,  'Open API, generous limits'),
    ('kompass',          5,  200,  'Playwright, slow'),
    ('europages',       10,  500,  'httpx'),
    ('alibaba',          3,  100,  'Playwright+stealth, strict'),
    ('thomasnet',        8,  300,  'httpx'),
    ('panjiva',          5,  200,  'Playwright'),
    ('importyeti',      10,  500,  'httpx'),
    ('volza',            5,  200,  'httpx'),
    ('yellowpages',     10,  500,  'httpx'),
    ('google_places',   10, 1000,  'Paid API'),
    ('made_in_china',    5,  200,  'Playwright'),
    ('global_sources',   5,  200,  'Playwright'),
    ('exporters_india',  5,  200,  'Playwright'),
    ('tradeindia',       5,  200,  'Playwright'),
    ('ec21',            10,  500,  'httpx'),
    ('exporthub',       10,  500,  'httpx'),
    ('tradekey',        10,  500,  'httpx'),
    ('go4worldbusiness',10,  500,  'httpx'),
    ('tridge',           5,  200,  'httpx'),
    ('direct_website',  20, 1000,  'trafilatura, fast'),
    ('ofac',             1,    5,  'CSV bulk, rarely refreshed');

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE search_jobs      ENABLE ROW LEVEL SECURITY;
ALTER TABLE entity_clusters  ENABLE ROW LEVEL SECURITY;
ALTER TABLE raw_candidates   ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence_links   ENABLE ROW LEVEL SECURITY;

CREATE POLICY "user_owns_job"
    ON search_jobs FOR ALL
    USING (user_id = auth.uid());

CREATE POLICY "user_owns_cluster"
    ON entity_clusters FOR ALL
    USING (job_id IN (SELECT id FROM search_jobs WHERE user_id = auth.uid()));

CREATE POLICY "user_owns_candidate"
    ON raw_candidates FOR ALL
    USING (job_id IN (SELECT id FROM search_jobs WHERE user_id = auth.uid()));

CREATE POLICY "user_owns_evidence"
    ON evidence_links FOR ALL
    USING (cluster_id IN (
        SELECT ec.id FROM entity_clusters ec
        JOIN search_jobs sj ON sj.id = ec.job_id
        WHERE sj.user_id = auth.uid()
    ));

-- ============================================================
-- Auto-update updated_at on search_jobs
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_search_jobs_updated_at
    BEFORE UPDATE ON search_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
