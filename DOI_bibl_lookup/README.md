# DOI bibliographic lookup (Lens Scholarly)

This folder contains only reusable code, not research data or credentials.

## Purpose
Append Lens bibliographic metadata to the CGIAR topical review's source-faithful CSV using its DOI column. Existing data columns remain unchanged. Each lookup is verified against the DOI in the returned Lens `external_ids` array; ambiguous or absent matches are flagged. The output has the same rows and nine additional metadata fields plus a match-status field.

## Run
Install `requests` and make the token available to the **process running this code** as `LENS_API_TOKEN`.

```bash
python -m pip install requests
python DOI_bibl_lookup/enrich.py /path/input.csv /path/output_enriched.csv
```

Do not upload the token, the actual input CSV, or enriched output to GitHub. Keep them on your local computer or in a restricted workflow artifact. The script refuses to overwrite existing enrichment columns.

## Access boundary
The `LENS_API_TOKEN` held as a GitHub Actions secret in `thesalmonandthetomato/LivingEvidenceMap` is usable by that repository's workflows, but cannot be read via the GitHub connector or used directly by workflows in `ILRI-CGIAR/topicalreview`. It cannot be transferred between organisations automatically. Running this script requires a token in the executing environment or an existing authorised credential-bearing workflow. Do not add temporary validation workflows to the salmon project.

## Match statuses
`EXACT_DOI_MATCH`, `NO_EXACT_DOI_MATCH`, `MISSING_DOI`, `MULTIPLE_EXACT_MATCHES_REVIEW`. No fallback matching on title is attempted.
