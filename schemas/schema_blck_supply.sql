-- =========================================
-- Blck House Supply – Core Schema (PostgreSQL)
-- =========================================

-- 1) Cities / host locations
CREATE TABLE cities (
    id              SERIAL PRIMARY KEY,
    slug            TEXT UNIQUE NOT NULL,     -- e.g. "new-york", "houston"
    name            TEXT NOT NULL,           -- e.g. "New York"
    country         TEXT NOT NULL,           -- e.g. "USA"
    timezone        TEXT NOT NULL,           -- e.g. "America/New_York"
    fifa_host_city  BOOLEAN DEFAULT FALSE,   -- is this a FIFA host city?
    notes           TEXT
);

-- 2) Partners (hosts / property owners / vendors)
CREATE TABLE partners (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    email           TEXT,
    phone           TEXT,
    partner_type    TEXT NOT NULL,           -- e.g. 'host', 'cleaning', 'experience'
    website         TEXT,
    city_id         INT REFERENCES cities(id),
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 3) Blck Houses (core housing supply)
CREATE TABLE blck_houses (
    id                  SERIAL PRIMARY KEY,
    external_id         TEXT,                -- optional ID from PMS / channel manager
    partner_id          INT REFERENCES partners(id),
    city_id             INT NOT NULL REFERENCES cities(id),

    title               TEXT NOT NULL,       -- "3BR Midtown Balcony Flat"
    description         TEXT,
    address_line_1      TEXT,                -- optional, can keep approx only
    address_line_2      TEXT,
    neighborhood        TEXT,                -- "Midtown", "Bushwick", etc.
    latitude            NUMERIC(9,6),
    longitude           NUMERIC(9,6),

    bedrooms            INT NOT NULL,
    bathrooms           NUMERIC(3,1),
    max_guests          INT NOT NULL,
    desired_capacity     INT,                    -- how many people host wants at home at a time
    min_nights          INT DEFAULT 1,
    max_nights          INT,

    base_price_per_night NUMERIC(10,2) NOT NULL,
    currency            CHAR(3) DEFAULT 'USD',

    -- Feature flags / filters
    kids_friendly       BOOLEAN DEFAULT FALSE,
    pets_allowed        BOOLEAN DEFAULT FALSE,
    smoking_allowed     BOOLEAN DEFAULT FALSE,
    wheelchair_access   BOOLEAN DEFAULT FALSE,

    -- Flexible amenity blob
    amenities           JSONB DEFAULT '{}'::JSONB,
    rules               JSONB DEFAULT '{}'::JSONB,

    verification_status TEXT NOT NULL DEFAULT 'pending', -- 'pending','verified','rejected'
    is_active           BOOLEAN DEFAULT TRUE,

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_blck_houses_city ON blck_houses(city_id);
CREATE INDEX idx_blck_houses_active ON blck_houses(is_active);


-- 4) House availability (date-based inventory)
CREATE TABLE house_availability (
    id              SERIAL PRIMARY KEY,
    house_id        INT NOT NULL REFERENCES blck_houses(id) ON DELETE CASCADE,
    date            DATE NOT NULL,
    is_available    BOOLEAN NOT NULL DEFAULT TRUE,
    price_per_night NUMERIC(10,2),           -- optional override of base price
    min_stay_nights INT,                     -- optional override

    CONSTRAINT uniq_house_date UNIQUE (house_id, date)
);

CREATE INDEX idx_house_availability_house_date
    ON house_availability (house_id, date);


-- 5) House images / media
CREATE TABLE house_images (
    id              SERIAL PRIMARY KEY,
    house_id        INT NOT NULL REFERENCES blck_houses(id) ON DELETE CASCADE,
    url             TEXT NOT NULL,
    sort_order      INT DEFAULT 0,           -- 0 = primary
    caption         TEXT
);


-- 6) Experiences (optional but part of “supply”)
CREATE TABLE experiences (
    id              SERIAL PRIMARY KEY,
    external_id     TEXT,
    partner_id      INT REFERENCES partners(id),
    city_id         INT NOT NULL REFERENCES cities(id),

    name            TEXT NOT NULL,
    description     TEXT,
    category        TEXT NOT NULL,           -- 'restaurant','tour','museum','event', etc.
    address_line_1  TEXT,
    address_line_2  TEXT,
    latitude        NUMERIC(9,6),
    longitude       NUMERIC(9,6),

    black_owned     BOOLEAN DEFAULT TRUE,
    family_friendly BOOLEAN DEFAULT FALSE,
    price_level     TEXT,                    -- '$', '$$', '$$$'
    booking_url     TEXT,
    phone           TEXT,
    website         TEXT,

    tags            TEXT[] DEFAULT '{}',     -- ['brunch','live-music','nightlife']
    hours_json      JSONB DEFAULT '{}'::JSONB,  -- e.g. {"mon":"10-22","tue":"closed",...}

    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_experiences_city ON experiences(city_id);
CREATE INDEX idx_experiences_active ON experiences(is_active);


-- 7) Experience images
CREATE TABLE experience_images (
    id              SERIAL PRIMARY KEY,
    experience_id   INT NOT NULL REFERENCES experiences(id) ON DELETE CASCADE,
    url             TEXT NOT NULL,
    sort_order      INT DEFAULT 0,
    caption         TEXT
);
