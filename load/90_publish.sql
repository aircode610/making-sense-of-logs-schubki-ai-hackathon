-- After a load: publish pending writes and compact, so every query sees all rows at once.
-- The inverted index is eventually consistent (background refresh every ~1 s); right after a bulk insert, counts can be
-- off (seen: off by one, doubled) until a refresh. docs/serenedb/rendered/sql/indexes/inverted/maintenance.md
\timing on
VACUUM (REFRESH_TABLE) logs;
VACUUM (REFRESH_TABLE) labels;
VACUUM (COMPACT_TABLE) logs;
VACUUM (REFRESH_TABLE) logs;
