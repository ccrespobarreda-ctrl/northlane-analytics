#!/usr/bin/env python3
"""
Northlane Supply Co. -- synthetic dataset generator.

Produces the RAW layer: deliberately messy CSVs that look like real platform
exports. The dbt/SQL pipeline is responsible for cleaning them.

    python src/generate_data.py --out data/raw --seed 42

A reference copy of the pre-corruption frames is written to data/reference/
when --emit-reference is passed. That copy exists ONLY so that
validate_findings.py can assert the planted findings landed at the intended
magnitude. It is a build-time self-test, not an analytical shortcut -- the
dashboard is built from data/raw via the transformation layer, like any real
project.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from datagen import config as C
from datagen import catalog, customers, dirty, marketing, orders as orders_mod, returns as returns_mod

log = logging.getLogger("northlane")


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )


def generate(seed: int = C.SEED) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    t0 = time.time()

    log.info("Building geography dimension")
    geo = catalog.build_geography()

    log.info("Building product catalog with SCD2 cost history")
    products = catalog.build_products(rng)
    log.info("  %d SKUs -> %d cost versions", products["sku"].nunique(), len(products))

    log.info("Building customer base")
    cust = customers.build_customers(rng, geo)
    log.info("  %s customers", f"{len(cust):,}")

    log.info("Building order calendar")
    cal = customers.build_order_calendar(rng, cust)
    log.info("  %s orders", f"{len(cal):,}")

    log.info("Building order lines and landed-cost model")
    orders, lines = orders_mod.build_order_lines(rng, cal, cust, products, geo)
    log.info("  %s order lines", f"{len(lines):,}")

    log.info("Building returns")
    rets = returns_mod.build_returns(rng, lines, products)
    log.info("  %s return records (%.1f%% of units)", f"{len(rets):,}",
             100 * rets["quantity_returned"].sum() / lines["quantity"].sum())

    log.info("Building ad spend")
    ads = marketing.build_ad_spend(rng, cust, orders, lines)
    log.info("  %s campaign-days, $%s total spend",
             f"{len(ads):,}", f"{ads['spend'].sum():,.0f}")

    log.info("Generation complete in %.1fs", time.time() - t0)
    return {"geography": geo, "products": products, "customers": cust,
            "orders": orders, "lines": lines, "returns": rets, "ad_spend": ads}


def write(frames: dict[str, pd.DataFrame], out_dir: Path, reference: bool) -> None:
    raw_dir = out_dir
    raw_dir.mkdir(parents=True, exist_ok=True)

    if reference:
        ref_dir = raw_dir.parent / "reference"
        ref_dir.mkdir(parents=True, exist_ok=True)
        for name, df in frames.items():
            df.to_parquet(ref_dir / f"{name}.parquet", index=False)
        log.info("Reference (pre-corruption) frames -> %s", ref_dir)

    rng = np.random.default_rng(C.SEED + 1)
    dirtied = dirty.corrupt(frames["orders"], frames["lines"], frames["returns"],
                            frames["products"], frames["customers"], rng)

    export = {
        "raw_orders": dirtied["orders"],
        "raw_order_lines": dirtied["lines"],
        "raw_returns": dirtied["returns"],
        "raw_products": dirtied["products"],
        "raw_customers": dirtied["customers"],
        "raw_ad_spend": frames["ad_spend"],
        "raw_geography": frames["geography"],
    }
    for name, df in export.items():
        path = raw_dir / f"{name}.csv"
        df.to_csv(path, index=False)
        log.info("  %-20s %8s rows  %6.1f MB", name, f"{len(df):,}",
                 path.stat().st_size / 1e6)

    dirtied["quality_log"].to_csv(raw_dir.parent / "injected_defects.csv", index=False)
    log.info("Injected-defect manifest -> %s", raw_dir.parent / "injected_defects.csv")


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate the Northlane raw dataset")
    ap.add_argument("--out", default=C.OUTPUT_DIR, type=Path)
    ap.add_argument("--seed", default=C.SEED, type=int)
    ap.add_argument("--emit-reference", action="store_true",
                    help="also write pre-corruption frames for validate_findings.py")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    _setup_logging(args.verbose)
    frames = generate(args.seed)
    write(frames, args.out, args.emit_reference)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
