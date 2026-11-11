# DOI bibliographic lookup (Lens Scholarly)

This folder contains only reusable code, not research data or credentials.

## Purpose
Append Lens bibliographic metadata to the CGIAR topical review's source-faithful CSV using its DOI column. Existing data columns remain unchanged. DOIs are queried in validated batches of 50 using the current Lens `ids.doi` field. Every returned record is verified against its DOI in the Lens `external_ids` array; ambiguous or absent matches are flagged. The output has the same rows and nine bibliographic metadata fields plus a match-status field.

## Run
Install `requests` and make the token available to the **process running this code** as `LENS_API_TOKEN`.

```bash
python -m pip install requests
python DOI_bibl_lookup/enrich.py /path/input.csv /path/output_enriched.csv
```

Do not upload the token, the actual input CSV, or enriched output to GitHub. Keep them on your local computer or in a restricted workflow artifact. The script refuses to overwrite existing enrichment columns.

## Access boundary
This repository has its own `LENS_API_TOKEN` GitHub Actions secret. Secrets are accessed by the workflow at runtime and must never be included in source files or exported artifacts. The salmon farming repository is not required for this workflow.

## Match statuses
`EXACT_DOI_MATCH`, `NO_EXACT_DOI_MATCH`, `MISSING_DOI`, `MULTIPLE_EXACT_MATCHES_REVIEW`. No fallback matching on title is attempted.

## GitHub Actions run with repository secret

A manually triggered workflow is available at `.github/workflows/doi_lens_enrichment.yml`. To avoid committing research data to Git history:

1. In this private repository, create a **temporary release** tagged `doi-lookup-input` and attach `CGIAR_Lens_enrichment_input.csv` as a release asset. Do not mark the release public; the repository must remain private.
2. Open **Actions → DOI bibliographic lookup (Lens) → Run workflow** and retain the defaults.
3. Download the `cgiar-lens-enrichment` artifact from the run after success. Artifacts expire after seven days.
4. Delete the temporary release and its asset when the output has been verified. This does not change Git history.

The workflow reads `secrets.LENS_API_TOKEN` at runtime. The token is not present in the scripts, logged output or artifacts. The enrichment CSV should be inspected for exact/ambiguous/missing matches before use. Do not commit it to the repository.
