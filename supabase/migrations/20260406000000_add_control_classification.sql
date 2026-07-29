-- Migration: add_control_classification
-- Adds frequency, derived testing requirement fields, narrative fields,
-- normalises control_type (it_dependent_manual → itdm), and updates
-- the status vocabulary to match the SOC 2 examination workflow.
--
-- Apply manually: psql $DATABASE_URL -f this_file.sql
-- Do NOT auto-apply — review before running against production.

-- ============================================================
-- 1. New columns
-- ============================================================

ALTER TABLE controls ADD COLUMN IF NOT EXISTS frequency            TEXT;
ALTER TABLE controls ADD COLUMN IF NOT EXISTS requires_population  BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE controls ADD COLUMN IF NOT EXISTS requires_sample      BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE controls ADD COLUMN IF NOT EXISTS suggested_sample_size INT;
ALTER TABLE controls ADD COLUMN IF NOT EXISTS narrative            TEXT;
ALTER TABLE controls ADD COLUMN IF NOT EXISTS narrative_approved_at TIMESTAMPTZ;
ALTER TABLE controls ADD COLUMN IF NOT EXISTS narrative_flags      JSONB DEFAULT '[]';

-- ============================================================
-- 2. Normalise control_type: it_dependent_manual → itdm
-- ============================================================

ALTER TABLE controls DROP CONSTRAINT IF EXISTS controls_control_type_check;

UPDATE controls
SET control_type = 'itdm'
WHERE control_type = 'it_dependent_manual';

ALTER TABLE controls
  ADD CONSTRAINT controls_control_type_check
  CHECK (control_type IN ('manual', 'automated', 'itdm'));

-- ============================================================
-- 3. Frequency constraint
-- ============================================================

ALTER TABLE controls
  ADD CONSTRAINT controls_frequency_check
  CHECK (frequency IN (
    'annual', 'semi_annual', 'quarterly', 'monthly',
    'weekly', 'daily', 'continuous', 'adhoc / as needed'
  ));

-- ============================================================
-- 4. Update status vocabulary
-- ============================================================

ALTER TABLE controls DROP CONSTRAINT IF EXISTS controls_status_check;

UPDATE controls
SET status = CASE
  WHEN status IN ('not_started', 'in_progress', 'implemented') THEN 'not_tested'
  WHEN status = 'tested'                                        THEN 'tested_no_exceptions'
  ELSE 'not_tested'
END;

ALTER TABLE controls ALTER COLUMN status SET DEFAULT 'not_tested';

ALTER TABLE controls
  ADD CONSTRAINT controls_status_check
  CHECK (status IN ('not_tested', 'exception_noted', 'cleared', 'tested_no_exceptions'));

-- ============================================================
-- 5. Backfill derived fields for rows that already have
--    both control_type and frequency populated.
-- ============================================================

UPDATE controls
SET
  requires_population = CASE
    WHEN control_type = 'automated'                          THEN false
    WHEN control_type = 'manual' AND frequency = 'annual'   THEN false
    ELSE true
  END,
  requires_sample = CASE
    WHEN control_type = 'automated'                          THEN false
    WHEN control_type = 'manual' AND frequency = 'annual'   THEN false
    ELSE true
  END,
  suggested_sample_size = CASE
    WHEN control_type = 'automated'                          THEN NULL
    WHEN frequency = 'annual'                                THEN 1
    WHEN frequency = 'semi_annual'                           THEN 2
    WHEN frequency = 'quarterly'                             THEN 2
    WHEN frequency = 'monthly'                               THEN 5
    WHEN frequency = 'weekly'                                THEN 15
    WHEN frequency IN ('daily', 'continuous', 'adhoc')       THEN 25
    ELSE NULL
  END
WHERE control_type IS NOT NULL
  AND frequency    IS NOT NULL;
