-- KSP Copilot — synthetic crime-database schema.
-- Mirrors how Indian police records decompose. All data is synthetic (see db/README.md).

DROP TABLE IF EXISTS fir CASCADE;
DROP TABLE IF EXISTS officer CASCADE;
DROP TABLE IF EXISTS crime_type CASCADE;
DROP TABLE IF EXISTS station CASCADE;
DROP TABLE IF EXISTS division CASCADE;
DROP TABLE IF EXISTS district CASCADE;

CREATE TABLE district (
    district_id     SERIAL PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE
);

CREATE TABLE division (
    division_id     SERIAL PRIMARY KEY,
    district_id     INT NOT NULL REFERENCES district(district_id),
    name            TEXT NOT NULL,
    UNIQUE (district_id, name)
);

CREATE TABLE station (
    station_id      SERIAL PRIMARY KEY,
    division_id     INT NOT NULL REFERENCES division(division_id),
    name            TEXT NOT NULL,
    latitude        NUMERIC(9,6) NOT NULL,
    longitude       NUMERIC(9,6) NOT NULL,
    UNIQUE (division_id, name)
);

-- Offence taxonomy. label is user-facing; statute_section is the legal hook
-- (BNS 2023, with legacy IPC noted).
CREATE TABLE crime_type (
    crime_type_id   SERIAL PRIMARY KEY,
    label           TEXT NOT NULL UNIQUE,     -- 'chain snatching'
    category        TEXT NOT NULL,            -- 'property' | 'body' | 'cyber' | 'traffic'
    statute_section TEXT,                     -- 'BNS 304(2)'
    legacy_section  TEXT                      -- 'IPC 379' (nullable)
);

CREATE TABLE officer (
    officer_id      SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    rank            TEXT NOT NULL,            -- 'PSI' | 'PI' | 'ACP' ...
    station_id      INT NOT NULL REFERENCES station(station_id)
);

CREATE TABLE fir (
    fir_id          SERIAL PRIMARY KEY,
    fir_number      TEXT NOT NULL,            -- '0142/2026'
    station_id      INT NOT NULL REFERENCES station(station_id),
    crime_type_id   INT NOT NULL REFERENCES crime_type(crime_type_id),
    registered_on   DATE NOT NULL,
    occurred_on     DATE,
    status          TEXT NOT NULL
                    CHECK (status IN ('open','under_investigation','chargesheeted','closed','disposed')),
    io_officer_id   INT REFERENCES officer(officer_id),
    latitude        NUMERIC(9,6),
    longitude       NUMERIC(9,6),
    summary         TEXT,                     -- 1-2 synthetic sentences
    UNIQUE (station_id, fir_number)
);

CREATE INDEX idx_fir_registered_on ON fir(registered_on);
CREATE INDEX idx_fir_station       ON fir(station_id);
CREATE INDEX idx_fir_crime_type    ON fir(crime_type_id);
CREATE INDEX idx_fir_status        ON fir(status);
