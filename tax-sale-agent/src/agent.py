#!/usr/bin/env python3
import os, json, asyncio, argparse
import pandas as pd
from pathlib import Path

from .adapters import HCTaxNetAdapter, estimate_values
from .liens import summarize_liens, deal_score
from .utils import parse_money
from .scrapers import ClerkScraper, MunicipalScraper

def fetch_harris(out_csv: str) -> str:
    recs = HCTaxNetAdapter().fetch()
    recs = estimate_values(recs)
    df = pd.DataFrame([r.to_row() for r in recs])
    df.to_csv(out_csv, index=False)
    print(f"[+] Saved Harris tax sale list -> {out_csv} (rows={len(df)})")
    return out_csv

async def scrape_clerk_from_csv(step2_csv: str, query_field: str, out_csv: str, limit: int = 50):
    df = pd.read_csv(step2_csv)
    queries = df[query_field].dropna().astype(str).unique().tolist()[:limit]
    all_rows = []
    scraper = ClerkScraper()
    for q in queries:
        print(f"[clerk] Searching: {q}")
        d = await scraper.search(q)
        if not d.empty:
            d["AddressQuery"] = q
            all_rows.append(d)
    out = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    out.to_csv(out_csv, index=False)
    print(f"[+] Saved Clerk results -> {out_csv} (rows={len(out)})")
    return out_csv

async def scrape_muni(config_path: str, out_csv: str):
    d = await MunicipalScraper(config_path).scrape()
    d.to_csv(out_csv, index=False)
    print(f"[+] Saved Municipal liens -> {out_csv} (rows={len(d)})")
    return out_csv

def enrich(step2_csv: str, clerk_csv: str, municipal_csv: str, out_csv: str):
    s2 = pd.read_csv(step2_csv)
    clerk = pd.read_csv(clerk_csv) if Path(clerk_csv).exists() and Path(clerk_csv).stat().st_size>0 else None
    muni = pd.read_csv(municipal_csv) if Path(municipal_csv).exists() and Path(municipal_csv).stat().st_size>0 else None

    # We do not attempt to perfectly join by address—data varies.
    # We apply lien summaries globally as a rough estimate or you can subgroup by Address later.
    items, survive_total, flags = summarize_liens(pd.concat([clerk, muni], ignore_index=True) if clerk is not None or muni is not None else None)

    rows = []
    for _, r in s2.iterrows():
        score = deal_score(parse_money(r.get("est_value")), parse_money(r.get("min_bid")), survive_total, flags)
        out = dict(r)
        out["survive_total"] = survive_total
        out["risk_flags"] = ",".join(flags)
        out["deal_score"] = score
        rows.append(out)
    pd.DataFrame(rows).to_csv(out_csv, index=False)
    print(f"[+] Enriched -> {out_csv} (rows={len(rows)})")
    return out_csv

def main():
    ap = argparse.ArgumentParser(description="Tax Sale Deal Finder Agent — Orchestrator")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_fetch = sub.add_parser("fetch-harris", help="Fetch Harris County tax sale list + estimates")
    p_fetch.add_argument("--out", default="harris_tax_sale.csv")

    p_clerk = sub.add_parser("scrape-clerk", help="Scrape Clerk records from Step2 list")
    p_clerk.add_argument("--from-csv", required=True, help="CSV produced by fetch-harris")
    p_clerk.add_argument("--query-field", default="address", help="Column to query Clerk (address or owner)")
    p_clerk.add_argument("--out", default="clerk_results.csv")
    p_clerk.add_argument("--limit", type=int, default=50, help="Limit number of queries to avoid blocking")

    p_muni = sub.add_parser("scrape-muni", help="Scrape municipal liens using config")
    p_muni.add_argument("--config", required=True, help="config/houston_example.json")
    p_muni.add_argument("--out", default="municipal_liens.csv")

    p_enrich = sub.add_parser("enrich", help="Enrich Step2 with Clerk/Municipal liens and score")
    p_enrich.add_argument("--step2", required=True)
    p_enrich.add_argument("--clerk", default="clerk_results.csv")
    p_enrich.add_argument("--municipal", default="municipal_liens.csv")
    p_enrich.add_argument("--out", default="harris_tax_sale_enriched.csv")

    p_all = sub.add_parser("run-all", help="Run everything end-to-end")
    p_all.add_argument("--out", default="harris_tax_sale_enriched.csv")
    p_all.add_argument("--municipal-config", default="config/houston_example.json")

    args = ap.parse_args()

    if args.cmd == "fetch-harris":
        fetch_harris(args.out)

    elif args.cmd == "scrape-clerk":
        asyncio.run(scrape_clerk_from_csv(args.from_csv, args.query_field, args.out, limit=args.limit))

    elif args.cmd == "scrape-muni":
        asyncio.run(scrape_muni(args.config, args.out))

    elif args.cmd == "enrich":
        enrich(args.step2, args.clerk, args.municipal, args.out)

    elif args.cmd == "run-all":
        step2_csv = fetch_harris("harris_tax_sale.csv")
        asyncio.run(scrape_clerk_from_csv(step2_csv, "address", "clerk_results.csv", limit=40))
        asyncio.run(scrape_muni(args.municipal_config, "municipal_liens.csv"))
        enrich(step2_csv, "clerk_results.csv", "municipal_liens.csv", args.out)

if __name__ == "__main__":
    main()
