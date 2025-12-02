-- =========================================
-- World Cup Qualifiers – Scraper & Probability Schema (PostgreSQL)
-- =========================================

-- 1) Current Team Slot Probabilities (from team_slot_probabilities.csv)
-- This table stores the current/latest standings with calculated probabilities
CREATE TABLE team_slot_probabilities (
    id                      SERIAL PRIMARY KEY,
    team                    VARCHAR(255) NOT NULL,
    confederation           VARCHAR(50) NOT NULL,
    qualification_status    VARCHAR(50) NOT NULL,  -- 'Qualified', 'In Progress'
    prob_fill_slot          NUMERIC(5,2) NOT NULL,  -- 0.0 to 100.0
    current_group           VARCHAR(255),
    position                INTEGER,
    points                  INTEGER,
    played                  INTEGER,
    goal_diff               INTEGER,
    form                    TEXT,                   -- Currently empty, reserved for future
    
    -- Metadata
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint: one record per team per group
    CONSTRAINT uniq_team_group UNIQUE (team, confederation, current_group)
);

CREATE INDEX idx_team_slot_prob_confed ON team_slot_probabilities(confederation);
CREATE INDEX idx_team_slot_prob_status ON team_slot_probabilities(qualification_status);
CREATE INDEX idx_team_slot_prob_prob ON team_slot_probabilities(prob_fill_slot DESC);
CREATE INDEX idx_team_slot_prob_updated ON team_slot_probabilities(updated_at);


-- 2) Historical Standings Archive (from historical_standings.csv)
-- Stores historical qualifying data from past World Cup cycles (1990-2025)
CREATE TABLE historical_standings (
    id                      SERIAL PRIMARY KEY,
    season                  INTEGER NOT NULL,       -- World Cup year (e.g., 2006, 2010, 2014, 2018, 2022)
    confederation           VARCHAR(50) NOT NULL,
    stage                   VARCHAR(255) NOT NULL,  -- e.g., "Second Round", "Group Stage", "Third Round"
    group_name              VARCHAR(255),
    team                    VARCHAR(255) NOT NULL,
    rank                    INTEGER,
    points                  INTEGER,
    games_played            INTEGER,
    wins                    INTEGER,
    draws                   INTEGER,
    losses                  INTEGER,
    goals_for               INTEGER,
    goals_against           INTEGER,
    goal_difference         INTEGER,
    qualified               BOOLEAN,                -- Did this team eventually qualify?
    note                    TEXT,                   -- ESPN note (e.g., "Qualifies for World Cup")
    source_url              TEXT,                   -- ESPN API URL
    
    -- Derived features for probability calculations
    rank_bucket             VARCHAR(20),            -- '1', '2', '3-4', '5', '6+'
    points_per_game         NUMERIC(5,2),
    ppg_bucket              VARCHAR(20),            -- '>=2', '1.5-1.99', '1.0-1.49', '<1.0'
    goal_diff_bucket        VARCHAR(20),           -- e.g., '>=10', '5-9', '0-4', '-4- -0', etc.
    
    -- Metadata
    scraped_at              TIMESTAMPTZ DEFAULT NOW(),
    
    -- Prevent duplicate entries
    CONSTRAINT uniq_historical_entry UNIQUE (season, confederation, stage, group_name, team)
);

CREATE INDEX idx_historical_season ON historical_standings(season);
CREATE INDEX idx_historical_confed ON historical_standings(confederation);
CREATE INDEX idx_historical_stage ON historical_standings(stage);
CREATE INDEX idx_historical_qualified ON historical_standings(qualified);
CREATE INDEX idx_historical_rank ON historical_standings(rank);
CREATE INDEX idx_historical_rank_bucket ON historical_standings(rank_bucket);
CREATE INDEX idx_historical_ppg_bucket ON historical_standings(ppg_bucket);


-- 3) Historical Probability Lookup (from historical_probability_lookup.csv)
-- Pre-computed probabilities: P(qualify | confederation, stage, rank/bucket)
-- Used to blend historical baselines into current probability calculations
CREATE TABLE historical_probability_lookup (
    id                      SERIAL PRIMARY KEY,
    confederation           VARCHAR(50) NOT NULL,
    stage                   VARCHAR(255) NOT NULL,
    rank                    INTEGER,                -- NULL if using bucket-level lookup
    rank_bucket             VARCHAR(20),             -- NULL if using rank-level lookup
    ppg_bucket              VARCHAR(20),            -- NULL if using rank-level lookup
    lookup_level            VARCHAR(20) NOT NULL,    -- 'rank' or 'bucket'
    historical_qual_prob    NUMERIC(5,4) NOT NULL,  -- 0.0 to 1.0 (probability)
    
    -- Metadata
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint: one probability per lookup key
    CONSTRAINT uniq_prob_lookup UNIQUE (confederation, stage, rank, rank_bucket, ppg_bucket, lookup_level)
);

CREATE INDEX idx_prob_lookup_confed_stage ON historical_probability_lookup(confederation, stage);
CREATE INDEX idx_prob_lookup_level ON historical_probability_lookup(lookup_level);
CREATE INDEX idx_prob_lookup_rank ON historical_probability_lookup(rank);
CREATE INDEX idx_prob_lookup_bucket ON historical_probability_lookup(rank_bucket, ppg_bucket);


-- 4) Scraper & Prediction Run Logs
-- Comprehensive logging for all scraper and model prediction runs
CREATE TABLE scraper_jobs (
    id                      SERIAL PRIMARY KEY,
    job_type                VARCHAR(50) NOT NULL,   -- 'current_standings', 'historical_fetch', 'probability_update'
    job_name                VARCHAR(255),           -- Optional human-readable name
    status                  VARCHAR(20) NOT NULL,   -- 'success', 'partial', 'failed', 'running'
    
    -- Input tracking
    input_hash              VARCHAR(64),            -- SHA-256 hash of input parameters (JSON)
    input_params            JSONB,                  -- Full input parameters as JSON
    
    -- Execution metadata
    started_at              TIMESTAMPTZ DEFAULT NOW(),
    completed_at            TIMESTAMPTZ,
    execution_time_seconds  NUMERIC(10,2),
    
    -- Results tracking
    rows_processed          INTEGER DEFAULT 0,      -- Total rows/teams processed
    rows_inserted           INTEGER DEFAULT 0,     -- New rows inserted
    rows_updated            INTEGER DEFAULT 0,     -- Existing rows updated
    rows_failed             INTEGER DEFAULT 0,     -- Rows that failed processing
    
    -- Confederation-specific counts (JSONB for flexibility)
    confederation_counts    JSONB,                 -- {"AFC": 15, "UEFA": 45, ...}
    
    -- Error tracking
    error_message           TEXT,                   -- Primary error message
    error_details           JSONB,                  -- Full error details/stack trace
    warnings                JSONB,                  -- Array of warning messages
    
    -- Output tracking
    output_files            JSONB,                 -- ["team_slot_probabilities.csv", "qualifier_data.json"]
    output_hash             VARCHAR(64),           -- SHA-256 hash of output (for verification)
    
    -- Source tracking
    source_urls             TEXT[],                -- Array of ESPN API URLs scraped
    confederations_scraped  TEXT[],                -- Array of confederations processed
    
    -- Lambda/execution context
    execution_context       VARCHAR(50),           -- 'lambda', 'ec2', 'local', 'manual'
    lambda_request_id       VARCHAR(255),          -- AWS Lambda request ID if applicable
    environment             VARCHAR(50),           -- 'production', 'staging', 'development'
    
    -- Metadata
    notes                   TEXT,                  -- Optional notes about the run
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_scraper_jobs_type ON scraper_jobs(job_type);
CREATE INDEX idx_scraper_jobs_status ON scraper_jobs(status);
CREATE INDEX idx_scraper_jobs_started ON scraper_jobs(started_at DESC);
CREATE INDEX idx_scraper_jobs_input_hash ON scraper_jobs(input_hash);
CREATE INDEX idx_scraper_jobs_completed ON scraper_jobs(completed_at DESC);
CREATE INDEX idx_scraper_jobs_context ON scraper_jobs(execution_context);


-- 5) Prediction Runs (for model/probability calculations)
-- Tracks each time probabilities are calculated/updated
CREATE TABLE prediction_runs (
    id                      SERIAL PRIMARY KEY,
    run_type                VARCHAR(50) NOT NULL,   -- 'full_update', 'incremental', 'historical_recalc'
    status                  VARCHAR(20) NOT NULL,   -- 'success', 'partial', 'failed'
    
    -- Input tracking
    input_data_hash         VARCHAR(64),            -- Hash of input standings data
    historical_lookup_hash  VARCHAR(64),           -- Hash of historical probability lookup used
    model_version           VARCHAR(50),            -- Version/identifier of probability model
    
    -- Execution metadata
    started_at              TIMESTAMPTZ DEFAULT NOW(),
    completed_at            TIMESTAMPTZ,
    execution_time_seconds  NUMERIC(10,2),
    
    -- Results tracking
    teams_processed         INTEGER DEFAULT 0,
    probabilities_updated   INTEGER DEFAULT 0,
    qualified_count         INTEGER DEFAULT 0,     -- Teams marked as qualified
    in_progress_count       INTEGER DEFAULT 0,     -- Teams still in progress
    
    -- Probability statistics
    avg_probability         NUMERIC(5,2),          -- Average probability across all teams
    min_probability         NUMERIC(5,2),
    max_probability         NUMERIC(5,2),
    probability_distribution JSONB,               -- Histogram/buckets of probabilities
    
    -- Historical blending stats
    historical_matches      INTEGER DEFAULT 0,     -- Teams matched to historical data
    rank_level_matches      INTEGER DEFAULT 0,     -- Exact rank matches
    bucket_level_matches    INTEGER DEFAULT 0,     -- Bucket-level matches
    no_historical_match     INTEGER DEFAULT 0,     -- Teams with no historical data
    
    -- Error tracking
    error_message           TEXT,
    error_details           JSONB,
    warnings                JSONB,
    
    -- Output tracking
    output_file            VARCHAR(255),           -- Path to output CSV
    output_hash             VARCHAR(64),           -- Hash of output file
    
    -- Related scraper job
    scraper_job_id          INTEGER REFERENCES scraper_jobs(id),  -- Link to scraper run that triggered this
    
    -- Execution context
    execution_context       VARCHAR(50),
    lambda_request_id       VARCHAR(255),
    environment             VARCHAR(50),
    
    -- Metadata
    notes                   TEXT,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_prediction_runs_type ON prediction_runs(run_type);
CREATE INDEX idx_prediction_runs_status ON prediction_runs(status);
CREATE INDEX idx_prediction_runs_started ON prediction_runs(started_at DESC);
CREATE INDEX idx_prediction_runs_scraper_job ON prediction_runs(scraper_job_id);
CREATE INDEX idx_prediction_runs_input_hash ON prediction_runs(input_data_hash);


-- 6) Raw Scraper Payloads (optional, for debugging/auditing)
-- Stores raw JSON responses from ESPN API for troubleshooting
CREATE TABLE raw_scraper_payloads (
    id                      SERIAL PRIMARY KEY,
    confederation           VARCHAR(50) NOT NULL,
    season                  INTEGER,
    source_url              TEXT NOT NULL,
    payload                 JSONB NOT NULL,
    checksum                VARCHAR(64),            -- SHA-256 hash of payload
    scraped_at              TIMESTAMPTZ DEFAULT NOW(),
    
    -- Prevent storing duplicate payloads
    CONSTRAINT uniq_payload UNIQUE (confederation, season, checksum)
);

CREATE INDEX idx_raw_payload_confed_season ON raw_scraper_payloads(confederation, season);
CREATE INDEX idx_raw_payload_scraped ON raw_scraper_payloads(scraped_at DESC);


-- =========================================
-- Views for Common Queries
-- =========================================

-- View: Current qualified teams
CREATE OR REPLACE VIEW v_qualified_teams AS
SELECT 
    team,
    confederation,
    current_group,
    position,
    points,
    played,
    goal_diff,
    prob_fill_slot,
    updated_at
FROM team_slot_probabilities
WHERE qualification_status = 'Qualified'
ORDER BY confederation, prob_fill_slot DESC;

-- View: Teams by probability tier
CREATE OR REPLACE VIEW v_teams_by_probability_tier AS
SELECT 
    CASE 
        WHEN prob_fill_slot >= 90 THEN 'Very High (90-100%)'
        WHEN prob_fill_slot >= 70 THEN 'High (70-89%)'
        WHEN prob_fill_slot >= 50 THEN 'Medium (50-69%)'
        WHEN prob_fill_slot >= 25 THEN 'Low (25-49%)'
        ELSE 'Very Low (<25%)'
    END AS probability_tier,
    confederation,
    COUNT(*) AS team_count,
    AVG(prob_fill_slot) AS avg_probability
FROM team_slot_probabilities
WHERE qualification_status = 'In Progress'
GROUP BY probability_tier, confederation
ORDER BY confederation, avg_probability DESC;

-- View: Historical qualification rates by confederation and rank
CREATE OR REPLACE VIEW v_historical_qualification_rates AS
SELECT 
    confederation,
    stage,
    rank,
    COUNT(*) AS total_teams,
    SUM(CASE WHEN qualified THEN 1 ELSE 0 END) AS qualified_teams,
    ROUND(
        SUM(CASE WHEN qualified THEN 1 ELSE 0 END)::NUMERIC / COUNT(*)::NUMERIC, 
        4
    ) AS qualification_rate
FROM historical_standings
WHERE rank IS NOT NULL
GROUP BY confederation, stage, rank
ORDER BY confederation, stage, rank;

-- View: Recent scraper job summary
CREATE OR REPLACE VIEW v_recent_scraper_jobs AS
SELECT 
    id,
    job_type,
    status,
    rows_processed,
    rows_inserted,
    rows_updated,
    execution_time_seconds,
    started_at,
    completed_at,
    error_message,
    confederations_scraped
FROM scraper_jobs
ORDER BY started_at DESC
LIMIT 100;

-- View: Recent prediction runs summary
CREATE OR REPLACE VIEW v_recent_prediction_runs AS
SELECT 
    id,
    run_type,
    status,
    teams_processed,
    probabilities_updated,
    qualified_count,
    avg_probability,
    historical_matches,
    execution_time_seconds,
    started_at,
    completed_at,
    scraper_job_id
FROM prediction_runs
ORDER BY started_at DESC
LIMIT 100;

-- View: Scraper job success rate by type
CREATE OR REPLACE VIEW v_scraper_job_stats AS
SELECT 
    job_type,
    COUNT(*) AS total_runs,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS successful_runs,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_runs,
    SUM(CASE WHEN status = 'partial' THEN 1 ELSE 0 END) AS partial_runs,
    ROUND(
        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END)::NUMERIC / COUNT(*)::NUMERIC * 100,
        2
    ) AS success_rate_pct,
    AVG(execution_time_seconds) AS avg_execution_time,
    AVG(rows_processed) AS avg_rows_processed,
    MAX(started_at) AS last_run
FROM scraper_jobs
GROUP BY job_type
ORDER BY job_type;

