#!/usr/bin/env python3
"""Enrich a local CGIAR CSV from Lens Scholarly by exact DOI (no silent overwrites).

Usage:
  LENS_API_TOKEN=... python DOI_bibl_lookup/enrich.py input.csv output.csv

Requirements: pip install requests
The source file is not altered. Raw inputs/outputs and API tokens must stay outside Git.
"""
import argparse
import csv
import os
import re
import sys
import time
from collections import Counter, defaultdict

import requests

API = "https://api.lens.org/scholarly/search"
NEW = ["lens_title", "lens_authors", "lens_publication_year",
       "lens_source_journal", "lens_volume", "lens_issue", "lens_pages",
       "lens_abstract", "lens_id", "lens_match_status"]

def doi_norm(value):
    value = (value or "").strip().lower()
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value)
    value = re.sub(r"^doi\s*:\s*", "", value)
    return value.strip().rstrip(".,;")

def doi_set(hit):
    values = set()
    for ext in hit.get("external_ids") or []:
        if isinstance(ext, dict) and str(ext.get("type", "")).lower() == "doi":
            values.add(doi_norm(str(ext.get("value", ""))))
    return values

def authors(hit):
    names = []
    for author in hit.get("authors") or []:
        if not isinstance(author, dict):
            continue
        name = author.get("display_name") or author.get("collective_name")
        if not name:
            name = " ".join(str(author.get(k) or "") for k in ("first_name", "last_name")).strip()
        if name:
            names.append(name)
    return "; ".join(names)

def details(hit):
    source = hit.get("source") or {}
    if not isinstance(source, dict):
        source = {}
    start, end = str(hit.get("start_page") or ""), str(hit.get("end_page") or "")
    pages = (start + "-" + end) if start and end and start != end else start or end
    return dict(zip(NEW[:-1], [
        hit.get("title") or "", authors(hit), hit.get("year_published") or "",
        source.get("title") or "", hit.get("volume") or "", hit.get("issue") or "",
        pages, hit.get("abstract") or "", hit.get("lens_id") or ""
    ]))

def query(session, dois):
    body = {
        "query": {"terms": {"ids.doi": dois}},
        "size": 500,
        "include": ["lens_id", "title", "authors", "year_published", "source",
                    "volume", "issue", "start_page", "end_page", "abstract",
                    "external_ids"]
    }
    for attempt in range(6):
        try:
            response = session.post(API, json=body, timeout=90)
            if response.status_code == 429 or response.status_code >= 500:
                retry = int(response.headers.get("x-rate-limit-retry-after-seconds", "5"))
                time.sleep(min(90, max(retry, 3 * (attempt + 1))))
                continue
            if response.status_code == 400:
                raise RuntimeError("Lens query rejected (400): " + response.text[:400])
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            if attempt == 5:
                raise
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("Lens API did not respond after retries")

def run(source, destination):
    token = os.environ.get("LENS_API_TOKEN", "").strip()
    if not token:
        sys.exit("LENS_API_TOKEN unavailable: no lookups executed")
    with open(source, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        if not fields or "DOI" not in fields:
            sys.exit("Input CSV requires a DOI column")
        if any(field in fields for field in NEW):
            sys.exit("Input already contains enrichment columns: refusing to overwrite")
        rows = list(reader)
    unique = sorted({doi_norm(row.get("DOI")) for row in rows if doi_norm(row.get("DOI"))})
    matches = {doi: [] for doi in unique}
    session = requests.Session()
    session.headers.update({"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    for offset in range(0, len(unique), 50):
        group = unique[offset:offset + 50]
        payload = query(session, group)
        if payload.get("total", 0) > 500:
            raise RuntimeError("Lens batch exceeded response limit; reduce batch size")
        if os.environ.get("LENS_DEBUG") == "1" and offset == 0:
            print("Lens batch diagnostic:", {"requested": len(group),
                "total": payload.get("total"),
                "returned": len(payload.get("data") or [])}, flush=True)
        for hit in payload.get("data") or []:
            lens_id = hit.get("lens_id")
            if not lens_id:
                continue
            for d in doi_set(hit).intersection(group):
                if not any(h.get("lens_id") == lens_id for h in matches.get(d, [])):
                    matches.setdefault(d, []).append(hit)
        if offset == 0 and not any(matches.get(d) for d in group):
            raise RuntimeError("First Lens terms batch returned no exact DOI matches")
        print(f"Queried {min(offset+len(group),len(unique))}/{len(unique)} unique DOIs (batched)", flush=True)
        time.sleep(0.15)
    if not any(matches.values()):
        raise RuntimeError("All DOI lookups returned zero matches; refusing an empty enrichment output")
    for row in rows:
        row.update({field: "" for field in NEW})
        doi = doi_norm(row.get("DOI"))
        if not doi:
            status = "MISSING_DOI"
        elif not matches[doi]:
            status = "NO_EXACT_DOI_MATCH"
        elif len(matches[doi]) > 1:
            status = "MULTIPLE_EXACT_MATCHES_REVIEW"
        else:
            row.update(details(matches[doi][0]))
            status = "EXACT_DOI_MATCH"
        row["lens_match_status"] = status
    with open(destination, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields + NEW)
        writer.writeheader()
        writer.writerows(rows)
    print("Rows:", len(rows), "| Unique queried DOIs:", len(unique))
    print("Statuses:", dict(Counter(row["lens_match_status"] for row in rows)))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv")
    parser.add_argument("output_csv")
    args = parser.parse_args()
    run(args.input_csv, args.output_csv)
