-- The signals raised by the focused call that follows the main reading (D-075).
-- A JSON array of reason codes. The main reading's own signals stay in raw_response.
ALTER TABLE classifications ADD COLUMN focused_signals TEXT NOT NULL DEFAULT '[]';
