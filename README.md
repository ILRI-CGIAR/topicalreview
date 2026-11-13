# CGIAR topical review: offline-first data contract

Minimal starter for `ILRI-CGIAR/topicalreview`. **Proposed schema v1.1**; not yet a frozen controlled-vocabulary ontology. The codebook/manual must be reconciled before production model extraction.


## Frozen interactive evidence dashboard (v3.6)

The approved CGIAR Evidence Dashboard is reproducible from an updated, source-faithful CSV using the locked code and visual template in [`dashboard/`](dashboard/README.md). This includes the approved ontology crosswalk, Lens/OpenAlex enrichment precedence, high-income country exclusion *for the map only*, the merged adaptation category, all-product word cloud, interactive charts, theme explorer, and database. The current visual design is frozen for data-only updates.

Run `python dashboard/build.py --csv /path/updated.csv --bibliography /path/previous_enriched.csv --out ./local_output/dashboard` after installing `dashboard/requirements.txt`. Use `--bibliography` only if the uploaded CSV does not already contain its enrichment fields. Run `python -m unittest discover -s dashboard/tests -v` and review the manifest before releasing. See [the locked release notes](dashboard/RELEASE_NOTES_v3.6.md).

The research CSV, provider-enriched metadata, and generated 8 MB HTML are **not stored in Git**; keep them as local/restricted release artifacts. The deterministic build pipeline and data-free template are version controlled.

## Organisation

- `config/article.schema.json`: JSON Schema for one article per JSONL line, including Lens-style bibliographic metadata.
- `config/ontology_template.csv`: empty **template**, not an approved codebook. Never fabricate code-label pairs.
- `examples/example.jsonl`: fictional format example. Its category numbering/labels are **illustrative**, not approved ontology values.
- `R/build_tables.R`: offline reader of already-approved canonical JSONL, structural checks and dashboard table export.
- `R/legacy_preflight.R`: offline, **source-first** review of the `data` sheet. Emits a row-level conflict report and a lossless raw-row JSONL archive. **Does not produce canonical thematic codes**.
- `tests/smoke_test.R`: basic self-test.
- `.gitignore`: keeps original workbooks, licensed metadata, full texts, raw extracts and generated outputs out of Git.

## Canonical record

One article per line. Stable `article_id` is assigned upstream and must survive deduplication and later updates. `file_name` is just the primary full-text file basename. The `bibliographic` object contains ordered `authors` with affiliations and IDs; `year_published`, `title`, `source`, volume, issue, pages, DOI, abstract and `external_ids` as `{type,value}`. A DOI may appear both in `doi` and in `external_ids`. Bibliographic provenance is separate from identifier namespaces. Affiliation country is **not** study geography.

Thematic assignments are an array under `thematic_codes`, **each containing both `code` and `label` at every assigned level**:

```json
{"level_1":{"code":"3","label":"Adaptation options in agri-food systems"},"level_2":{"code":"3.2","label":"Water-related adaptation"},"level_3":{"code":"3.2.1","label":"Irrigation and management (all scales)"},"evidence":{"quote":null,"page":null}}
```

This example is for format illustration only. For broad assignments, `level_2` or `level_3` can be `null`, but a Level 3 assignment requires a Level 2 parent. The canonical record repeats labels intentionally for transparency. **Once an ontology is approved, verify every code–label pair and its parent relationships against it.** The current script checks only structural and numeric-prefix consistency; it does not imply semantic approval.

Other facets (country ISO3 array, regions, climate hazards, crops/species, method descriptors) are stored separately; adaptation/mitigation outcomes are true/false/null (null = unassessed or unavailable). These are article-level observations, not cases or interventions. Multiple country and theme assignments represent article-level co-occurrence and do not imply that every theme applies separately to every country.

## Run locally from a fresh R session

Install `jsonlite` once: `install.packages("jsonlite")`.

```bash
Rscript R/build_tables.R --input examples/example.jsonl --out local_output/example
Rscript tests/smoke_test.R
```

Generated outputs include `canonical.jsonl` (unchanged records), `articles.csv`, `article_countries.csv`, `article_thematic_codes.csv`, `article_facets.csv`, `article_flags.csv`. All generated outputs are ignored by Git. The script rejects duplicate IDs, missing structural fields, incorrect types, blank codes/labels and broken numeric parent prefixes. It makes no automatic corrections or silent mappings. The JSON schema can be checked separately with any Draft 2020-12 validator; it is **not** fully enforced by the R script yet.

## Legacy data: source-of-truth and conflict policy

The latest `data` tab of the workbook is authoritative over the coding manual **where they disagree**. A column heading is never a coded cell value. Do not turn an option number or label into a fabricated hierarchical ID. Keep every exact source label and its column/Excel row; preserve the original value even when it cannot be mapped.

In particular, the worksheet has `3.5 Climate Information System` with `CIEW` in 68 cells. The manual's option `(5) Other adaptations which do not fit above categories? (Specify)` is not automatically `3.5 Other`, and neither `3.5.1 CIEW` nor `3.99 Other` is approved. The worksheet's `5.2 Method time scale` uses option `5` for two different labels. A legacy crosswalk must be explicitly approved, with exact source column + value, three levels of complete code/label pairs, and human sign-off. Unknown values are unresolved, **not auto-normalised or discarded**. Where there is any unresolved conflict, canonical export is blocked.

Run the preliminary local audit (install `readxl` and `jsonlite` once):

```bash
Rscript R/legacy_preflight.R --input /absolute/path/workbook.xlsx --out local_audit/preflight_01
```

The output directory must be empty. This creates review flags and an archive of unmodified source cell values, but no canonical dataset. The preflight is not a replacement for full ontology/ISO3 validation and the initial full audit must be reviewed before conversion. The original workbook stays offline and unchanged.

## Future updates

Store raw model responses, PDFs and adjudications locally. Create **one current canonical record per stable article ID**; retain previous extraction versions in a separate local history, never append duplicate articles to a current snapshot. Validate and adjudicate before dashboard publication. Rebuild dashboard tables from a current-state JSONL snapshot on each update. Count distinct article IDs. Do not commit research data or generated tables. Do not add CI automation until a safe local workflow has been tested.

## Pending decisions before production

1. Transcribe and verify every Level 1–3 code, label and parent relationship from the coding manual and presentation, including revised Theme 5 methods.
2. Establish a reviewed crosswalk from the 47-column historical workbook to the approved hierarchical categories; **do not infer codes from labels**.
3. Add full schema, ontology, and genuine ISO-3 membership validation; add tests against representative real records.
4. Confirm allowed adaptation, mitigation, methods and hazards vocabulary, plus missing/not-applicable semantics.

The repository deliberately does **not** include a permissive legacy Excel-to-canonical converter: its prior flat code mapping violated the hierarchical contract. Implement an exact, fail-closed converter only after the crosswalk is signed off.
