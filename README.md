# CGIAR topical review: offline-first data contract

Minimal starter for `ILRI-CGIAR/topicalreview`. **Proposed schema v1.1**; not yet a frozen controlled-vocabulary ontology. The codebook/manual must be reconciled before production model extraction.

## Organisation

- `config/article.schema.json`: JSON Schema for one article per JSONL line, including Lens-style bibliographic metadata.
- `config/ontology_template.csv`: empty **template**, not an approved codebook. Never fabricate code-label pairs.
- `examples/example.jsonl`: fictional format example. Its category numbering/labels are **illustrative**, not approved ontology values.
- `R/build_tables.R`: offline reader, structural checks and dashboard table export.
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

## Future updates

Store raw model responses, PDFs and adjudications locally. Create **one current canonical record per stable article ID**; retain previous extraction versions in a separate local history, never append duplicate articles to a current snapshot. Validate and adjudicate before dashboard publication. Rebuild dashboard tables from a current-state JSONL snapshot on each update. Count distinct article IDs. Do not commit research data or generated tables. Do not add CI automation until a safe local workflow has been tested.

## Pending decisions before production

1. Transcribe and verify every Level 1–3 code, label and parent relationship from the coding manual and presentation, including revised Theme 5 methods.
2. Establish a reviewed crosswalk from the 47-column historical workbook to the approved hierarchical categories; **do not infer codes from labels**.
3. Add full schema, ontology, and genuine ISO-3 membership validation; add tests against representative real records.
4. Confirm allowed adaptation, mitigation, methods and hazards vocabulary, plus missing/not-applicable semantics.

The repository deliberately does **not** include the earlier legacy Excel importer: its flat code mapping would violate the approved hierarchical contract. Implement it after the crosswalk is signed off.
