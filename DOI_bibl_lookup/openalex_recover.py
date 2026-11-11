#!/usr/bin/env python3
"""Exact DOI recovery from OpenAlex. Never infer a match from title alone."""
import csv, json, os, re, sys, time, urllib.parse
from pathlib import Path
import requests

def normalize_doi(value):
    return re.sub(r"^https?://(?:dx\\.)?doi\\.org/", "", str(value or "").strip(), flags=re.I).lower().rstrip(".,;")

def abstract_from_index(idx):
    if not isinstance(idx, dict) or not idx:
        return ""
    positions = [(int(p), word) for word, offsets in idx.items() for p in offsets]
    if not positions:
        return ""
    words = [""] * (max(p for p, _ in positions) + 1)
    for p, word in positions:
        words[p] = word
    return " ".join(words).strip()

def retrieve(session, doi, key):
    url = "https://api.openalex.org/works/doi:" + urllib.parse.quote(doi, safe="/:()")
    for attempt in range(5):
        response = session.get(url, params={"api_key":key}, timeout=40)
        if response.status_code == 404:
            return None
        if response.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** attempt)
            continue
        if not response.ok:
            raise RuntimeError(f"OpenAlex HTTP {response.status_code} for DOI {doi}: {response.text[:300]}")
        return response.json()
    raise RuntimeError(f"OpenAlex request failed after retries: {doi}")

def main():
    key = os.environ.get("OPENALEX_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENALEX_API_KEY secret missing")
    src = Path(sys.argv[1]); out = Path(sys.argv[2])
    with src.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 11, f"Expected 11 unresolved DOIs, got {len(rows)}"
    fields = ["excel_row","doi","openalex_match_status","openalex_id",
              "openalex_title","openalex_authors","openalex_publication_year",
              "openalex_source_journal","openalex_volume","openalex_issue",
              "openalex_pages","openalex_abstract"]
    session = requests.Session()
    session.headers["User-Agent"] = "CGIAR-topical-review-bibliographic-enrichment/1.0"
    output=[]
    for row in rows:
        doi = normalize_doi(row["doi"])
        work=retrieve(session,doi,key)
        item={"excel_row":row["excel_row"],"doi":row["doi"]}
        if work is None:
            item["openalex_match_status"]="NO_EXACT_DOI_MATCH"
        elif normalize_doi(work.get("doi")) != doi:
            item["openalex_match_status"]="RETURNED_DOI_MISMATCH_REVIEW"
        else:
            authors = [a.get("author",{}).get("display_name","") for a in work.get("authorships",[])]
            source = ((work.get("primary_location") or {}).get("source") or {}).get("display_name","")
            bib = work.get("biblio") or {}
            first,last=bib.get("first_page") or "", bib.get("last_page") or ""
            item.update({
                "openalex_match_status":"EXACT_DOI_MATCH",
                "openalex_id":work.get("id",""),
                "openalex_title":work.get("title") or work.get("display_name") or "",
                "openalex_authors":"; ".join(a for a in authors if a),
                "openalex_publication_year":work.get("publication_year") or "",
                "openalex_source_journal":source,
                "openalex_volume":bib.get("volume") or "",
                "openalex_issue":bib.get("issue") or "",
                "openalex_pages":str(first)+"-"+str(last) if first and last and first != last else str(first or last),
                "openalex_abstract":abstract_from_index(work.get("abstract_inverted_index"))
            })
        output.append(item)
        print(f"Row {row['excel_row']}: {item['openalex_match_status']}", flush=True)
        time.sleep(0.1)
    with out.open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(output)
    print("TOTAL",len(output),"EXACT",sum(r["openalex_match_status"]=="EXACT_DOI_MATCH" for r in output))

if __name__ == "__main__":
    main()
