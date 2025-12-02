-- =========================================
-- World Cup 2026 Matches Schema (PostgreSQL)
-- =========================================

-- 1) Match Schedule (from slot_to_city_mapping.csv)
-- Stores the complete match schedule with venues and timing
CREATE TABLE match_schedule (
    id                      SERIAL PRIMARY KEY,
    match_number            INTEGER NOT NULL UNIQUE,  -- FIFA match number (1-104)
    group_name              VARCHAR(50),              -- Group letter (A-H) or round name (Round of 32, etc.)
    stage                   VARCHAR(50) NOT NULL,    -- 'Group Stage', 'Knockout Stage'
    round                   VARCHAR(50) NOT NULL,    -- 'Matchday 1', 'Round of 32', 'Round of 16', 'Quarter-final', 'Semi-final', 'Third-Place Playoff', 'Final'
    
    -- Date and time
    match_date              DATE NOT NULL,
    match_time              TIME NOT NULL,
    timezone                VARCHAR(50) NOT NULL,    -- 'EST', 'PST', 'CST', etc.
    match_datetime_utc      TIMESTAMPTZ,             -- Normalized UTC timestamp
    
    -- Venue information (links to cities table)
    city_id                 INTEGER REFERENCES cities(id),  -- Link to schema_blck_supply.cities
    city_name               VARCHAR(255) NOT NULL,    -- Denormalized for quick access
    stadium                 VARCHAR(255) NOT NULL,
    venue_capacity          INTEGER,
    transportation_notes     TEXT,                    -- Public transit info
    
    -- Teams (initially TBD, populated as teams qualify)
    team1_id                INTEGER,                 -- References team_slot_probabilities or teams table
    team1_name              VARCHAR(255),             -- Denormalized team name
    team1_confederation     VARCHAR(50),              -- Denormalized confederation
    team2_id                INTEGER,
    team2_name              VARCHAR(255),
    team2_confederation     VARCHAR(50),
    
    -- Match status
    match_status            VARCHAR(50) DEFAULT 'scheduled',  -- 'scheduled', 'live', 'finished', 'postponed', 'cancelled'
    
    -- Metadata
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_stage CHECK (stage IN ('Group Stage', 'Knockout Stage')),
    CONSTRAINT valid_status CHECK (match_status IN ('scheduled', 'live', 'finished', 'postponed', 'cancelled'))
);

CREATE INDEX idx_match_schedule_date ON match_schedule(match_date);
CREATE INDEX idx_match_schedule_stage ON match_schedule(stage);
CREATE INDEX idx_match_schedule_round ON match_schedule(round);
CREATE INDEX idx_match_schedule_group ON match_schedule(group_name);
CREATE INDEX idx_match_schedule_city ON match_schedule(city_id);
CREATE INDEX idx_match_schedule_status ON match_schedule(match_status);
CREATE INDEX idx_match_schedule_datetime ON match_schedule(match_datetime_utc);


-- 2) Match Results
-- Stores actual match results and statistics
CREATE TABLE match_results (
    id                      SERIAL PRIMARY KEY,
    match_schedule_id       INTEGER NOT NULL REFERENCES match_schedule(id) ON DELETE CASCADE,
    
    -- Score
    team1_score             INTEGER,
    team2_score             INTEGER,
    team1_score_penalties    INTEGER,                 -- Penalty shootout score (if applicable)
    team2_score_penalties    INTEGER,
    
    -- Match outcome
    winner_id               INTEGER,                 -- Team ID of winner (NULL if draw)
    winner_name             VARCHAR(255),             -- Denormalized
    result_type             VARCHAR(50),              -- 'win', 'draw', 'penalties'
    
    -- Match statistics
    attendance              INTEGER,                  -- Actual attendance
    weather_conditions      VARCHAR(50),              -- 'clear', 'rain', 'snow', etc.
    temperature_celsius     NUMERIC(4,1),
    
    -- Timing
    kickoff_time            TIMESTAMPTZ,             -- Actual kickoff time
    full_time_end           TIMESTAMPTZ,             -- When match ended
    duration_minutes        INTEGER,                 -- Total match duration
    
    -- Match events summary
    team1_yellow_cards      INTEGER DEFAULT 0,
    team1_red_cards         INTEGER DEFAULT 0,
    team2_yellow_cards      INTEGER DEFAULT 0,
    team2_red_cards         INTEGER DEFAULT 0,
    team1_corners           INTEGER DEFAULT 0,
    team2_corners           INTEGER DEFAULT 0,
    team1_offsides          INTEGER DEFAULT 0,
    team2_offsides          INTEGER DEFAULT 0,
    team1_possession_pct    NUMERIC(5,2),            -- Possession percentage
    team2_possession_pct    NUMERIC(5,2),
    
    -- Shots statistics
    team1_shots_total       INTEGER DEFAULT 0,
    team1_shots_on_target   INTEGER DEFAULT 0,
    team2_shots_total       INTEGER DEFAULT 0,
    team2_shots_on_target   INTEGER DEFAULT 0,
    
    -- Metadata
    referee                 VARCHAR(255),
    assistant_referees      TEXT[],                  -- Array of referee names
    video_assistant_referee VARCHAR(255),
    notes                   TEXT,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint: one result per match
    CONSTRAINT uniq_match_result UNIQUE (match_schedule_id)
);

CREATE INDEX idx_match_results_schedule ON match_results(match_schedule_id);
CREATE INDEX idx_match_results_winner ON match_results(winner_id);
CREATE INDEX idx_match_results_date ON match_results(full_time_end);


-- 3) Match Events (Goals, Cards, Substitutions, etc.)
-- Detailed timeline of match events
CREATE TABLE match_events (
    id                      SERIAL PRIMARY KEY,
    match_schedule_id       INTEGER NOT NULL REFERENCES match_schedule(id) ON DELETE CASCADE,
    match_result_id         INTEGER REFERENCES match_results(id) ON DELETE SET NULL,
    
    -- Event details
    event_type              VARCHAR(50) NOT NULL,     -- 'goal', 'yellow_card', 'red_card', 'substitution', 'penalty', 'own_goal', 'var_decision', etc.
    minute                  INTEGER NOT NULL,         -- Minute of match (0-120+)
    stoppage_time          INTEGER DEFAULT 0,         -- Stoppage time added (e.g., 45+3)
    period                  VARCHAR(20) DEFAULT '1H', -- '1H', '2H', 'ET1', 'ET2', 'PEN'
    
    -- Team and player
    team_id                 INTEGER,                 -- Team that the event relates to
    team_name               VARCHAR(255),             -- Denormalized
    player_id               INTEGER,                  -- Player involved (if applicable)
    player_name             VARCHAR(255),            -- Denormalized
    player_jersey_number    INTEGER,
    
    -- Event-specific data
    event_description      TEXT,                     -- Human-readable description
    event_data              JSONB,                    -- Flexible JSON for event-specific details
    -- Examples:
    -- Goal: {"assist_player": "John Doe", "goal_type": "open_play", "body_part": "foot"}
    -- Card: {"card_reason": "foul", "fouled_player": "Jane Smith"}
    -- Substitution: {"player_out": "Player A", "player_in": "Player B", "position": "forward"}
    
    -- VAR/Review information
    var_reviewed            BOOLEAN DEFAULT FALSE,
    var_decision            VARCHAR(50),             -- 'upheld', 'overturned', 'no_review'
    
    -- Metadata
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_match_events_match ON match_events(match_schedule_id);
CREATE INDEX idx_match_events_type ON match_events(event_type);
CREATE INDEX idx_match_events_minute ON match_events(minute);
CREATE INDEX idx_match_events_team ON match_events(team_id);
CREATE INDEX idx_match_events_player ON match_events(player_id);


-- 4) Group Stage Standings
-- Tracks group stage standings as matches are played
CREATE TABLE group_standings (
    id                      SERIAL PRIMARY KEY,
    group_name              VARCHAR(10) NOT NULL,     -- 'A', 'B', 'C', etc.
    team_id                 INTEGER,                  -- References team_slot_probabilities
    team_name               VARCHAR(255) NOT NULL,
    team_confederation      VARCHAR(50) NOT NULL,
    
    -- Match statistics
    matches_played          INTEGER DEFAULT 0,
    wins                    INTEGER DEFAULT 0,
    draws                   INTEGER DEFAULT 0,
    losses                  INTEGER DEFAULT 0,
    
    -- Goals
    goals_for               INTEGER DEFAULT 0,
    goals_against           INTEGER DEFAULT 0,
    goal_difference         INTEGER DEFAULT 0,
    
    -- Points
    points                  INTEGER DEFAULT 0,
    
    -- Position
    position                INTEGER,                  -- Current position in group
    
    -- Fair play (tiebreaker)
    yellow_cards            INTEGER DEFAULT 0,
    red_cards               INTEGER DEFAULT 0,
    fair_play_points        INTEGER DEFAULT 0,        -- Calculated from cards
    
    -- Metadata
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint: one record per team per group
    CONSTRAINT uniq_group_team UNIQUE (group_name, team_id)
);

CREATE INDEX idx_group_standings_group ON group_standings(group_name);
CREATE INDEX idx_group_standings_position ON group_standings(group_name, position);
CREATE INDEX idx_group_standings_points ON group_standings(group_name, points DESC);


-- 5) Knockout Stage Bracket
-- Tracks knockout stage progression
CREATE TABLE knockout_bracket (
    id                      SERIAL PRIMARY KEY,
    round                   VARCHAR(50) NOT NULL,     -- 'Round of 32', 'Round of 16', 'Quarter-final', 'Semi-final', 'Third-Place Playoff', 'Final'
    match_schedule_id       INTEGER NOT NULL REFERENCES match_schedule(id),
    
    -- Bracket position
    bracket_position        VARCHAR(50),              -- e.g., "A1", "B2", "W1" (winner of match 1), etc.
    bracket_side            VARCHAR(20),              -- 'left', 'right' (for visualization)
    
    -- Teams (populated based on previous round results)
    team1_source            VARCHAR(100),             -- e.g., "Winner of Match 1", "Group A Winner", "Group B Runner-up"
    team1_id                INTEGER,
    team1_name               VARCHAR(255),
    team2_source             VARCHAR(100),
    team2_id                INTEGER,
    team2_name               VARCHAR(255),
    
    -- Winner advances to
    winner_advances_to      VARCHAR(100),            -- Next round match identifier
    
    -- Metadata
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_knockout_bracket_round ON knockout_bracket(round);
CREATE INDEX idx_knockout_bracket_match ON knockout_bracket(match_schedule_id);


-- 6) Match Predictions / Betting Odds (Optional)
-- Stores predictions, odds, or probability forecasts for matches
CREATE TABLE match_predictions (
    id                      SERIAL PRIMARY KEY,
    match_schedule_id       INTEGER NOT NULL REFERENCES match_schedule(id) ON DELETE CASCADE,
    
    -- Prediction source
    source_type             VARCHAR(50),              -- 'model', 'odds', 'expert', 'user'
    source_name             VARCHAR(255),             -- Name of model/bookmaker/expert
    predicted_at            TIMESTAMPTZ DEFAULT NOW(),
    
    -- Predictions
    team1_win_probability   NUMERIC(5,2),             -- 0-100
    draw_probability         NUMERIC(5,2),
    team2_win_probability   NUMERIC(5,2),
    
    -- Score predictions
    predicted_team1_score    INTEGER,
    predicted_team2_score     INTEGER,
    
    -- Odds (if from bookmaker)
    team1_odds               NUMERIC(6,2),            -- Decimal odds
    draw_odds                NUMERIC(6,2),
    team2_odds               NUMERIC(6,2),
    
    -- Confidence/notes
    confidence_score         NUMERIC(5,2),            -- 0-100
    prediction_notes        TEXT,
    
    -- Metadata
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint: one prediction per source per match
    CONSTRAINT uniq_prediction UNIQUE (match_schedule_id, source_type, source_name)
);

CREATE INDEX idx_match_predictions_match ON match_predictions(match_schedule_id);
CREATE INDEX idx_match_predictions_source ON match_predictions(source_type);


-- =========================================
-- Views for Common Queries
-- =========================================

-- View: Upcoming matches
CREATE OR REPLACE VIEW v_upcoming_matches AS
SELECT 
    ms.match_number,
    ms.group_name,
    ms.stage,
    ms.round,
    ms.match_date,
    ms.match_time,
    ms.timezone,
    ms.city_name,
    ms.stadium,
    ms.team1_name,
    ms.team2_name,
    ms.match_status,
    c.timezone AS city_timezone
FROM match_schedule ms
LEFT JOIN cities c ON ms.city_id = c.id
WHERE ms.match_status IN ('scheduled', 'live')
ORDER BY ms.match_date, ms.match_time;

-- View: Match results with details
CREATE OR REPLACE VIEW v_match_results_detail AS
SELECT 
    ms.match_number,
    ms.group_name,
    ms.stage,
    ms.round,
    ms.match_date,
    ms.city_name,
    ms.stadium,
    ms.team1_name,
    ms.team2_name,
    mr.team1_score,
    mr.team2_score,
    mr.team1_score_penalties,
    mr.team2_score_penalties,
    mr.winner_name,
    mr.attendance,
    mr.referee,
    ms.match_status
FROM match_schedule ms
LEFT JOIN match_results mr ON ms.id = mr.match_schedule_id
WHERE ms.match_status = 'finished'
ORDER BY ms.match_date DESC, ms.match_time DESC;

-- View: Group stage standings summary
CREATE OR REPLACE VIEW v_group_standings_summary AS
SELECT 
    group_name,
    team_name,
    team_confederation,
    position,
    matches_played,
    wins,
    draws,
    losses,
    goals_for,
    goals_against,
    goal_difference,
    points,
    updated_at
FROM group_standings
ORDER BY group_name, position;

-- View: Top scorers (from match events)
CREATE OR REPLACE VIEW v_top_scorers AS
SELECT 
    player_name,
    team_name,
    COUNT(*) AS goals,
    COUNT(DISTINCT match_schedule_id) AS matches_scored_in
FROM match_events
WHERE event_type = 'goal' AND player_name IS NOT NULL
GROUP BY player_name, team_name
ORDER BY goals DESC, matches_scored_in DESC;

-- View: Match statistics summary
CREATE OR REPLACE VIEW v_match_statistics AS
SELECT 
    ms.match_number,
    ms.team1_name,
    ms.team2_name,
    mr.team1_score,
    mr.team2_score,
    mr.team1_possession_pct,
    mr.team2_possession_pct,
    mr.team1_shots_total,
    mr.team1_shots_on_target,
    mr.team2_shots_total,
    mr.team2_shots_on_target,
    mr.team1_corners,
    mr.team2_corners,
    mr.team1_yellow_cards,
    mr.team1_red_cards,
    mr.team2_yellow_cards,
    mr.team2_red_cards
FROM match_schedule ms
JOIN match_results mr ON ms.id = mr.match_schedule_id
WHERE ms.match_status = 'finished'
ORDER BY ms.match_date DESC;





