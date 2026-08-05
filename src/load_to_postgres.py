#!/usr/bin/env python3
"""
Load the raw CSVs into Postgres.

Design decision worth defending in an interview: **every raw column lands as
TEXT.** The raw layer is a faithful, lossless copy of what the source system
emitted. If `order_date` contains three date formats, that is a fact about the
source, and forcing a DATE type here would either crash the load or silently
discard rows. Casting is the staging layer's job, where it is visible, tested,
and reversible.

The load is idempotent: the `raw` schema is dropped and rebuilt each run, so a
failed load never leaves half a table behind.

    python src/load_to_postgres.py --dir data/raw

Connection comes from DATABASE_URL, e.g.
    postgresql://USER:PASSWORD@HOST:5432/northlane
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
import time
from pathlib import Path

import psycopg2
from psycopg2 import sql

log = logging.getLogger("loader")

RAW_SCHEMA = "raw"
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2.0


def _connect(dsn: str):
    """Connect with bounded retries -- cloud Postgres (Neon) cold-starts."""
    last: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            conn = psycopg2.connect(dsn, connect_timeout=15)
            log.info("Connected on attempt %d", attempt)
            return conn
        except psycopg2.OperationalError as exc:
            last = exc
            wait = RETRY_BACKOFF_SECONDS * attempt
            log.warning("Connection attempt %d/%d failed (%s); retrying in %.0fs",
                        attempt, MAX_ATTEMPTS, exc.__class__.__name__, wait)
            time.sleep(wait)
    raise SystemExit(f"Could not connect after {MAX_ATTEMPTS} attempts: {last}")


def _read_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    seen: dict[str, int] = {}
    cols = []
    for raw_name in header:
        name = raw_name.strip().lower().replace(" ", "_").replace("-", "_")
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        cols.append(name)
    return cols


def _count_data_rows(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as fh:
        return max(sum(1 for _ in csv.reader(fh)) - 1, 0)


def load_file(cur, path: Path) -> tuple[int, int]:
    table = path.stem.lower()
    cols = _read_header(path)

    cur.execute(sql.SQL("DROP TABLE IF EXISTS {}.{} CASCADE").format(
        sql.Identifier(RAW_SCHEMA), sql.Identifier(table)))
    cur.execute(sql.SQL("CREATE TABLE {}.{} ({})").format(
        sql.Identifier(RAW_SCHEMA), sql.Identifier(table),
        sql.SQL(", ").join(
            sql.SQL("{} TEXT").format(sql.Identifier(c)) for c in cols)))

    copy_stmt = sql.SQL(
        "COPY {}.{} ({}) FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')"
    ).format(sql.Identifier(RAW_SCHEMA), sql.Identifier(table),
             sql.SQL(", ").join(sql.Identifier(c) for c in cols))

    with path.open("r", encoding="utf-8") as fh:
        cur.copy_expert(copy_stmt.as_string(cur), fh)

    cur.execute(sql.SQL("SELECT count(*) FROM {}.{}").format(
        sql.Identifier(RAW_SCHEMA), sql.Identifier(table)))
    loaded = cur.fetchone()[0]
    return _count_data_rows(path), loaded


def main() -> int:
    ap = argparse.ArgumentParser(description="Load raw CSVs into Postgres")
    ap.add_argument("--dir", default="data/raw", type=Path)
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s", datefmt="%H:%M:%S")

    if not args.dsn:
        log.error("No DSN. Set DATABASE_URL or pass --dsn.")
        return 2

    files = sorted(args.dir.glob("*.csv"))
    if not files:
        log.error("No CSVs in %s -- run generate_data.py first", args.dir)
        return 2

    t0 = time.time()
    conn = _connect(args.dsn)
    conn.autocommit = False
    mismatches = 0

    try:
        with conn, conn.cursor() as cur:
            cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                sql.Identifier(RAW_SCHEMA)))
            cur.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(RAW_SCHEMA)))
            log.info("Rebuilt schema %s", RAW_SCHEMA)

            for path in files:
                expected, loaded = load_file(cur, path)
                status = "ok" if expected == loaded else "MISMATCH"
                if expected != loaded:
                    mismatches += 1
                log.info("  %-22s %9s rows  %s", path.stem, f"{loaded:,}", status)
                if expected != loaded:
                    log.error("    file had %s rows, table has %s",
                              f"{expected:,}", f"{loaded:,}")
    finally:
        conn.close()

    log.info("Load complete in %.1fs", time.time() - t0)
    if mismatches:
        log.error("%d table(s) failed row reconciliation", mismatches)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
