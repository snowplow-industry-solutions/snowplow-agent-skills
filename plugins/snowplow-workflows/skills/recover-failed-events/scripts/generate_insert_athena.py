#!/usr/bin/env python3
"""
Generate the recovery INSERT statement for the recover-failed-events skill (Athena path).

Non-interactive. Reads its inputs from files and prints the INSERT to stdout
(or writes it with --out). Standard library only — runs on any local Python 3.6+.

Usage:
    python3 generate_insert.py \
        --config config.json \
        --good-describe good_describe.txt \
        --failed-describe failed_describe.txt \
        --recovery-expr recovery_expression.sql \
        [--out recovery.sql]

config.json keys:
    GOOD_DATABASE, GOOD_TABLE, FAILED_DATABASE, FAILED_TABLE,
    RECOVERY_COLUMN, FAILED_SCHEMA, APP_ID, DAYS_LOOKBACK
    FAILURE_SOURCE  (optional) — 'contexts' or 'unstruct'. When set, scopes the recovery
        to the matched failure element whose source matches (failure_ctx.errors[1].source,
        applied after the UNNEST), so a schema that failed both ways recovers one source
        per run into its own column. Omit for a single-source schema. RECOVERY_COLUMN is
        the contexts_* column for a contexts run or the unstruct_event_* column for an
        unstruct run.
    TARGET_DATABASE, TARGET_TABLE  (optional) — where the INSERT writes. Defaults to
        GOOD_DATABASE/GOOD_TABLE. Set these to a staging table when using the staging path;
        column classification still comes from the good-table DESCRIBE, so the staging table
        must mirror the good table's schema.

The three text files are raw pastes:
    good-describe / failed-describe : the DESCRIBE output for each table
    recovery-expr                   : the CAST(ARRAY[ROW(...)] AS ARRAY(ROW(...)))
                                      expression, WITHOUT a trailing "AS <column>"

Prints a sanity summary (column counts, pass-through, nulled) to stderr.
"""

import argparse
import json
import re
import sys

FAILURE_COL = "contexts_com_snowplowanalytics_snowplow_failure_1"


def strip_partition_spec(text):
    lines = []
    for line in text.splitlines():
        low = line.strip().lower()
        if low.startswith("# partition spec") or low.startswith("# partition information"):
            break
        lines.append(line)
    return "\n".join(lines)


def parse_describe(output):
    columns = []
    for line in strip_partition_spec(output).splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split("\t") if "\t" in s else s.split(None, 1)
        if len(parts) < 2:
            continue
        name, dtype = parts[0].strip(), parts[1].strip()
        if name and dtype:
            columns.append((name, dtype))
    return columns


def hive_to_athena_type(hive_type):
    # Hive DESCRIBE type -> Trino/Athena type. Rewrite the container keywords and
    # the angle brackets, quote every struct field name, then translate the scalar
    # keywords that differ (string->varchar, int->integer).
    t = re.sub(r'\barray<', 'array(', hive_type)
    t = re.sub(r'\bstruct<', 'row(', t)
    t = re.sub(r'\bmap<', 'map(', t)
    t = t.replace('>', ')')
    # struct field "name:type" -> quote the name, drop the colon. Quoting *every*
    # field name unconditionally is always safe in a Trino row type and protects a
    # field named after a reserved word or a type keyword (e.g. date, float, int).
    t = re.sub(r'([A-Za-z_][A-Za-z0-9_]*)\s*:', r'"\1" ', t)
    # Scalar keyword translation, skipping anything inside the quotes just added so
    # a field literally named "int"/"string" is left alone.
    t = re.sub(r'(?<!")\bstring\b(?!")', 'varchar', t)
    t = re.sub(r'(?<!")\bint\b(?!")', 'integer', t)
    t = re.sub(r'  +', ' ', t)
    return t


def time_filter(cfg):
    """Bounded load_tstamp range if LOAD_TSTAMP_START is set (prunes partitions), else lookback."""
    start = cfg.get("LOAD_TSTAMP_START")
    end = cfg.get("LOAD_TSTAMP_END")
    if start:
        clause = f"load_tstamp >= TIMESTAMP '{start.replace(chr(39), chr(39) * 2)}'"
        if end:
            clause += f"\n      AND load_tstamp < TIMESTAMP '{end.replace(chr(39), chr(39) * 2)}'"
        return clause
    return f"load_tstamp > current_timestamp - interval '{cfg['DAYS_LOOKBACK']}' day"


def make_insert(good_columns, failed_col_names, cfg, recovery_expr):
    insert_cols, select_exprs = [], []
    recovery_col = cfg["RECOVERY_COLUMN"]
    passthrough = nulled = 0

    for name, dtype in good_columns:
        if name == FAILURE_COL:
            continue
        insert_cols.append(name)
        if name == "load_tstamp":
            select_exprs.append("-- fresh timestamp for reprocessed rows\n    current_timestamp AS load_tstamp")
        elif name == recovery_col:
            # recovery_expr already had any trailing "AS <alias>" stripped in read_expr_file.
            select_exprs.append(f"{recovery_expr}\n    AS {name}")
        elif name in failed_col_names:
            # Present in the failed table (atomic columns and any materialised sibling
            # entity) -> copy it straight through. Membership is the classifier; no
            # hardcoded atomic-column list needed, matching the Databricks sibling.
            select_exprs.append(name)
            passthrough += 1
        else:
            select_exprs.append(f"CAST(NULL AS {hive_to_athena_type(dtype)}) AS {name}")
            nulled += 1

    app_id_safe = cfg["APP_ID"].replace("'", "''")
    schema_safe = cfg["FAILED_SCHEMA"].replace("'", "''")
    target_db = cfg.get("TARGET_DATABASE") or cfg["GOOD_DATABASE"]
    target_tbl = cfg.get("TARGET_TABLE") or cfg["GOOD_TABLE"]

    # Optional source scoping (contexts vs unstruct). A schema can fail both as a
    # context entity and as the self-describing event; each is a separate run into
    # its own column. This is applied AFTER the UNNEST, on the matched failure element,
    # so it stays correct when the target entry isn't the first in the array. errors is
    # array(varchar) of JSON strings (1-based), so read source with json_extract_scalar.
    unnested_source = ""
    if cfg.get("FAILURE_SOURCE"):
        source_safe = cfg["FAILURE_SOURCE"].replace("'", "''")
        unnested_source = (
            "      AND json_extract_scalar(failure_ctx.errors[1], '$.source')"
            f" = '{source_safe}'\n"
        )

    # Scope the unnested failure entries to the schema (and source) being recovered,
    # so an event with a multi-entry failure array doesn't fan out into duplicate
    # event_id rows built from another entry's payload.
    unnested_where = f"    WHERE failure_ctx.schema = '{schema_safe}'\n" + unnested_source

    sql = (
        f"INSERT INTO {target_db}.{target_tbl} (\n    "
        + ",\n    ".join(insert_cols)
        + "\n)\nWITH prep AS (\n    SELECT *\n    FROM "
        + f"{cfg['FAILED_DATABASE']}.{cfg['FAILED_TABLE']}\n"
        + f"    WHERE {time_filter(cfg)}\n"
        + f"      AND app_id = '{app_id_safe}'\n"
        + "      AND any_match(contexts_com_snowplowanalytics_snowplow_failure_1,\n"
        + f"                    x -> x.schema = '{schema_safe}')\n"
        + "),\n"
        + "unnested AS (\n    SELECT\n        prep.*,\n        failure_ctx.data AS failure_data\n    FROM prep\n"
        + "    CROSS JOIN UNNEST(contexts_com_snowplowanalytics_snowplow_failure_1) AS t(failure_ctx)\n"
        + unnested_where
        + ")\n"
        + "SELECT\n    " + ",\n    ".join(select_exprs) + "\nFROM unnested;"
    )
    return sql, insert_cols, passthrough, nulled


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
    ap = argparse.ArgumentParser(description="Generate the recovery INSERT statement.")
    ap.add_argument("--config", required=True, help="config.json path")
    ap.add_argument("--good-describe", required=True)
    ap.add_argument("--failed-describe", required=True)
    ap.add_argument("--recovery-expr", required=True)
    ap.add_argument("--out", help="write SQL here; otherwise print to stdout")
    args = ap.parse_args()

    try:
        cfg = json.loads(read_file(args.config))
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: {args.config} is not valid JSON ({e}).")

    required = ["GOOD_DATABASE", "GOOD_TABLE", "FAILED_DATABASE", "FAILED_TABLE",
                "RECOVERY_COLUMN", "FAILED_SCHEMA", "APP_ID"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        sys.exit(f"ERROR: config missing keys: {', '.join(missing)}")
    # Time window: need either a bounded start or a lookback.
    if not cfg.get("LOAD_TSTAMP_START") and not cfg.get("DAYS_LOOKBACK"):
        sys.exit("ERROR: config needs either LOAD_TSTAMP_START (bounded range) or DAYS_LOOKBACK (lookback).")

    good_columns = parse_describe(read_file(args.good_describe))
    failed_col_names = {c for c, _ in parse_describe(read_file(args.failed_describe))}
    recovery_expr = read_expr_file(args.recovery_expr)

    if not good_columns:
        sys.exit("ERROR: no columns parsed from good-describe. Check the file.")
    if not failed_col_names:
        sys.exit("ERROR: no columns parsed from failed-describe. Check the file. "
                 "(An empty failed-columns paste would null every sibling entity that "
                 "should have passed through.)")
    if not recovery_expr:
        sys.exit("ERROR: recovery-expr is empty.")

    rec = cfg["RECOVERY_COLUMN"]
    sql, insert_cols, passthrough, nulled = make_insert(good_columns, failed_col_names, cfg, recovery_expr)

    if args.out:
        with open(args.out, "w") as f:
            f.write(sql)

    # Sanity summary -> stderr so stdout stays pure SQL when piped.
    print(f"good columns:   {len(good_columns)}", file=sys.stderr)
    print(f"failed columns: {len(failed_col_names)}", file=sys.stderr)
    print(f"insert columns: {len(insert_cols)}  (failure col excluded)", file=sys.stderr)
    print(f"pass-through:   {passthrough}", file=sys.stderr)
    print(f"nulled:         {nulled}", file=sys.stderr)
    if not any(c == rec for c, _ in good_columns):
        print(f"WARNING: recovery column '{rec}' not found in good DESCRIBE.", file=sys.stderr)
    if args.out:
        print(f"written to {args.out}", file=sys.stderr)

    if not args.out:
        print(sql)


if __name__ == "__main__":
    main()
