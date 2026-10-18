# lnav log format definitions (vendored)

The 76 `*.json` files are the log format definitions of [lnav](https://github.com/tstack/lnav)
(`src/formats/`, master, fetched 2026-10-18), © Timothy Stack, BSD-2-Clause (see `LICENSE` here). Unchanged.

Used by `scripts/ingest.py` (plan 057 part 3) to detect the format of an unseen log file: every regex is converted from
PCRE to RE2 (named groups kept, unnamed groups made non-capturing, duplicate names renamed; regexes with look-around are
skipped because RE2 cannot run them) and counted on a 2,000-line sample inside SereneDB; lnav's field roles
(`timestamp-field`, `level-field` + `level` map, `body-field`, `module-field`, `opid-field`) map the fields to our columns.
To update: re-download the files from the same folder.
