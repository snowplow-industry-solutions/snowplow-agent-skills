#!/usr/bin/env python3
"""
Generate the recovery INSERT statement for the recover-failed-events skill (Databricks path).

Why this exists: the in-warehouse generator builds the whole INSERT as one
string literal inside a generator query, so every single quote in the payload
has to be backslash-escaped (\'). Spark has no '' escape -- a doubled quote
coalesces into nothing and the quote silently vanishes, producing an
unparseable INSERT with no error. This script assembles the INSERT locally in
Python and writes the bytes directly, so there is no SQL string-literal layer
to escape. Mirrors the Athena path (generate_insert_athena.py).

Non-interactive. Reads its inputs from files and prints the INSERT to stdout
(or writes it with --out). Standard library only — runs on any local Python 3.6+.

Usage:
    python3 generate_insert.py \
        --config config.json \
        --good-columns good_columns.txt \
        --failed-columns failed_columns.txt \
        --recovery-expr recovery_expression.sql \
        [--out recovery.sql]

config.json keys (all three-part Unity Catalog names):
    GOOD_CATALOG, GOOD_SCHEMA, GOOD_TABLE,
    FAILED_CATALOG, FAILED_SCHEMA, FAILED_TABLE,
    RECOVERY_COLUMN            — the contexts_<vendor>_<name>_<major> (or
                                 unstruct_event_<vendor>_<name>_<major>) column name
    FAILING_SCHEMA_URI         — the iglu: URI being recovered
    APP_ID
    FAILURE_SOURCE  (optional) — 'contexts' or 'unstruct'. When set, scopes prep to
                                 rows whose failure source matches, so a schema that
                                 failed both ways recovers one source per run into its
                                 own column. Omit only when the schema fails one way.
    DAYS_LOOKBACK              — integer lookback, OR set a bounded range with
    LOAD_TSTAMP_START [, LOAD_TSTAMP_END]   — 'YYYY-MM-DD' (or full timestamp)
    TARGET_CATALOG, TARGET_SCHEMA, TARGET_TABLE  (optional) — where the INSERT
        writes. Default to GOOD_*. Set to a staging table for the staging path;
        column classification still comes from the good-table columns, so the
        staging table must mirror the good table's schema.

The two column files are raw pastes of:
    SELECT column_name, full_data_type
    FROM <catalog>.information_schema.columns
    WHERE table_schema = '<schema>' AND table_name = '<table>'
    ORDER BY ordinal_position;
(paste them in ordinal order — the INSERT is positional). Tab-, pipe-, or
whitespace-separated all parse; a `column_name / full_data_type` header row is
skipped automatically.

The recovery-expr file is the validated Phase-4 expression, reading the payload from
`f.data` (the exploded failure element that prep matches on schema):
    ARRAY(NAMED_STRUCT('_schema_version','1-0-0', 'field', CAST(GET_JSON_OBJECT(f.data,'$.field') AS T), ...))
WITHOUT a trailing "AS <column>" (the script adds it). Single quotes stay single
here — this file is read locally and dropped straight into the SELECT, not
embedded in another string literal, so it needs none of the backslash escaping
the in-warehouse generator does.

Prints a sanity summary (column counts, pass-through, nulled) to stderr.
"""

import argparse
import csv
import json
import re
import sys

FAILURE_COL = "contexts_com_snowplowanalytics_snowplow_failure_1"


def parse_columns(output):
    """Parse a two-column (column_name, full_data_type) paste, preserving order.

    full_data_type routinely contains commas and spaces (`decimal(18,2)`,
    `array<struct<a:string, b:bigint>>`). Databricks copy/download gives CSV with
    such types quoted, so comma output is parsed with the csv module (quoted fields
    stay intact). Tab-, pipe-, and whitespace-separated output also parse. A
    `column_name / full_data_type` header row and markdown separator lines are
    skipped.
    """
    raw = [l for l in output.splitlines() if l.strip() and not l.strip().startswith("#")]
    if not raw:
        return []

    # Detect the delimiter from the first non-empty line: prefer tab, then comma,
    # then pipe; fall back to whitespace.
    head = raw[0]
    if "\t" in head:
        delim = "\t"
    elif "," in head:
        delim = ","
    elif "|" in head:
        delim = "|"
    else:
        delim = None

    def keep(name, dtype):
        if name.lower() == "column_name" or set(name) <= set("-:| "):
            return  # header row or markdown separator
        columns.append((name, dtype))

    columns = []
    overflow = 0
    if delim in ("\t", ",", "|"):
        # csv.reader handles quoted types that themselves contain the delimiter.
        for row in csv.reader(raw, delimiter=delim):
            cells = [c.strip() for c in row if c.strip() != ""]
            if len(cells) > 2:
                overflow += 1  # a type containing the delimiter wasn't quoted -> truncated
            if len(cells) >= 2:
                keep(cells[0], cells[1])
    else:
        for line in raw:
            parts = line.strip().split(None, 1)  # split name from type on first ws
            if len(parts) >= 2:
                keep(parts[0].strip(), parts[1].strip())
    if overflow:
        sys.stderr.write(
            "WARNING: %d row(s) split into more than two %s-delimited fields; only the first two "
            "were kept, so a type containing the delimiter (e.g. an unquoted 'array<struct<a,b>>') was "
            "truncated. Re-paste with such types quoted, or copy the query result as CSV/tab.\n"
            % (overflow, "tab" if delim == "\t" else delim)
        )
    return columns


def time_filter(cfg):
    """Bounded load_tstamp range if LOAD_TSTAMP_START is set, else a lookback."""
    start = cfg.get("LOAD_TSTAMP_START")
    end = cfg.get("LOAD_TSTAMP_END")
    if start:
        clause = "load_tstamp >= TIMESTAMP('%s')" % start.replace("'", "\\'")
        if end:
            clause += "\n      AND load_tstamp < TIMESTAMP('%s')" % end.replace("'", "\\'")
        return clause
    return "DATE(load_tstamp) > DATE_SUB(CURRENT_DATE(), %s)" % int(cfg["DAYS_LOOKBACK"])


def make_insert(good_columns, failed_col_names, cfg, recovery_expr):
    """Build a positional INSERT (no column list) that lines up with the good
    table's column order. Every good column is emitted in ordinal order:
      - failure context column -> CAST(NULL AS <full_data_type>)  (keeps position)
      - load_tstamp            -> CURRENT_TIMESTAMP()             (fresh for reprocess)
      - recovery column        -> the validated recovery expression
      - present in failed table-> passed through by name
      - good-only column       -> CAST(NULL AS <full_data_type>)
    """
    recovery_col = cfg["RECOVERY_COLUMN"].lower()
    select_exprs = []
    passthrough = nulled = 0
    recovery_seen = False

    for name, dtype in good_columns:
        low = name.lower()
        if low == FAILURE_COL:
            select_exprs.append("CAST(NULL AS %s) AS %s" % (dtype, name))
            nulled += 1
        elif low == "load_tstamp":
            select_exprs.append("-- fresh timestamp for reprocessed rows\n    CURRENT_TIMESTAMP() AS load_tstamp")
        elif low == recovery_col:
            select_exprs.append("%s AS %s" % (recovery_expr, name))
            recovery_seen = True
        elif low in failed_col_names:
            select_exprs.append(name)
            passthrough += 1
        else:
            select_exprs.append("CAST(NULL AS %s) AS %s" % (dtype, name))
            nulled += 1

    app_id_safe = cfg["APP_ID"].replace("'", "\\'")
    schema_safe = cfg["FAILING_SCHEMA_URI"].replace("'", "\\'")
    target_cat = cfg.get("TARGET_CATALOG") or cfg["GOOD_CATALOG"]
    target_sch = cfg.get("TARGET_SCHEMA") or cfg["GOOD_SCHEMA"]
    target_tbl = cfg.get("TARGET_TABLE") or cfg["GOOD_TABLE"]

    # Optional source scoping: a schema can fail as both a context entity and the
    # self-describing event; each is a separate run into its own column. Read source
    # from the exploded matching element f, so it stays correct when the target entry
    # isn't the first in the array.
    source_predicate = ""
    if cfg.get("FAILURE_SOURCE"):
        source_predicate = (
            "      AND GET_JSON_OBJECT(f.errors[0], '$.source') = '%s'\n"
            % cfg["FAILURE_SOURCE"].replace("'", "\\'")
        )

    # prep EXPLODEs the failure array and keeps the element whose schema matches the one
    # being recovered (aliased f). One event can fail on several entities at once; reading
    # [0] would drop events whose target failure isn't first. The target schema appears
    # once per event, so the explode yields one row per recovered event (no fan-out), and
    # the recovery expression reads its payload from f.data.
    sql = (
        "INSERT INTO %s.%s.%s\n" % (target_cat, target_sch, target_tbl)
        + "WITH prep AS (\n    SELECT *\n    FROM %s.%s.%s\n"
        % (cfg["FAILED_CATALOG"], cfg["FAILED_SCHEMA"], cfg["FAILED_TABLE"])
        + "    LATERAL VIEW explode(contexts_com_snowplowanalytics_snowplow_failure_1) t AS f\n"
        + "    WHERE %s\n" % time_filter(cfg)
        + "      AND app_id = '%s'\n" % app_id_safe
        + "      AND f.schema = '%s'\n" % schema_safe
        + source_predicate
        + ")\n"
        + "SELECT\n    " + ",\n    ".join(select_exprs) + "\nFROM prep;"
    )
    return sql, select_exprs, passthrough, nulled, recovery_seen


def read_file(path):
    with open(path) as f:
        return f.read()


def read_expr_file(path):
    lines = read_file(path).splitlines()
    expr = "\n".join(l.rstrip() for l in lines if not l.strip().startswith("#")).strip()
    # Strip a trailing "AS <alias>" (e.g. copied from the Phase-4 test SELECT's
    # "AS recovered") so the generator's own "AS <column>" doesn't produce the parse
    # error "<expr> AS recovered AS <column>".
    return re.sub(r"\s+AS\s+[`\"]?\w+[`\"]?\s*$", "", expr, flags=re.IGNORECASE)


def main():
    ap = argparse.ArgumentParser(description="Generate the Databricks recovery INSERT statement.")
    ap.add_argument("--config", required=True, help="config.json path")
    ap.add_argument("--good-columns", required=True, help="paste of good-table information_schema.columns")
    ap.add_argument("--failed-columns", required=True, help="paste of failed-table information_schema.columns")
    ap.add_argument("--recovery-expr", required=True, help="validated Phase-4 recovery expression")
    ap.add_argument("--out", help="write SQL here; otherwise print to stdout")
    args = ap.parse_args()

    try:
        cfg = json.loads(read_file(args.config))
    except json.JSONDecodeError as e:
        sys.exit("ERROR: %s is not valid JSON (%s)." % (args.config, e))

    required = ["GOOD_CATALOG", "GOOD_SCHEMA", "GOOD_TABLE",
                "FAILED_CATALOG", "FAILED_SCHEMA", "FAILED_TABLE",
                "RECOVERY_COLUMN", "FAILING_SCHEMA_URI", "APP_ID"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        sys.exit("ERROR: config missing keys: %s" % ", ".join(missing))
    if not cfg.get("LOAD_TSTAMP_START") and not cfg.get("DAYS_LOOKBACK"):
        sys.exit("ERROR: config needs either LOAD_TSTAMP_START (bounded range) or DAYS_LOOKBACK (lookback).")

    good_columns = parse_columns(read_file(args.good_columns))
    failed_col_names = {c.lower() for c, _ in parse_columns(read_file(args.failed_columns))}
    recovery_expr = read_expr_file(args.recovery_expr)

    if not good_columns:
        sys.exit("ERROR: no columns parsed from --good-columns. Check the file.")
    if not failed_col_names:
        sys.exit("ERROR: no columns parsed from --failed-columns. Check the file.")
    if not recovery_expr:
        sys.exit("ERROR: --recovery-expr is empty.")

    rec = cfg["RECOVERY_COLUMN"]
    sql, select_exprs, passthrough, nulled, recovery_seen = make_insert(
        good_columns, failed_col_names, cfg, recovery_expr)

    if args.out:
        with open(args.out, "w") as f:
            f.write(sql)

    # Sanity summary -> stderr so stdout stays pure SQL when piped.
    print("good columns:   %d" % len(good_columns), file=sys.stderr)
    print("failed columns: %d" % len(failed_col_names), file=sys.stderr)
    print("select exprs:   %d  (positional, matches good-table order)" % len(select_exprs), file=sys.stderr)
    print("pass-through:   %d" % passthrough, file=sys.stderr)
    print("nulled:         %d" % nulled, file=sys.stderr)
    if not recovery_seen:
        print("WARNING: recovery column '%s' not found in good columns — the recovery "
              "expression was NOT placed. Check RECOVERY_COLUMN against the good table." % rec,
              file=sys.stderr)
    if args.out:
        print("written to %s" % args.out, file=sys.stderr)

    if not args.out:
        print(sql)


if __name__ == "__main__":
    main()
