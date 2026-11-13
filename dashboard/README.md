# CGIAR Evidence Dashboard — locked v3.6

**Status:** v3.6 is the frozen visual/design and coding baseline. This directory contains all reproducible *code*, a data-free HTML template, the approved source-to-theme crosswalk, deterministic word-cloud settings, and offline regression tests. The original research CSV, provider-enriched metadata and generated dashboard are **not committed** (see the root repository's access and provenance policy).

## What this builds

`build.py` rebuilds the complete standalone HTML (interactive choropleth, region-only geography bar chart, publication-year plot, top-15 journal plot, adaptation/mitigation characteristics, full word cloud plus ranked table, thematic explorer, and searchable article database) from the current CSV. Counts, figure data, dropdown filters, theme-explorer node counts and word frequencies are regenerated. No external databases or tokens are queried during a build. Plotly and the geographical base map require their existing CDN dependency when viewing the HTML online.

## Input contract

The source must be a UTF-8 CSV exported from the revised `data` worksheet with these *exact* existing headers (including trailing spaces): `Filenames`, `Title`, `DOI`, `Citation`, `Year`, `Country`, `Region`, `Crop/livestock/tree/fish`, `Crop/livestock/tree/fish name (CLEAN)`, all existing theme and adaptation/mitigation columns. Either include the `lens_*` and `openalex_*` enrichment columns directly (63 columns in the v3.6 baseline) **or** pass the previous enriched CSV with `--bibliography` to carry forward only provider metadata by exact `Filenames`.

**The latest source CSV is authoritative for all coding and descriptive fields**. An enrichment carry-forward never changes `Filenames`, `DOI`, title, year, theme fields, countries, regions, or product codes. Do not attempt to reuse old provider data for a renamed filename without a reviewed crosswalk. New records are allowed, although their unrecognised theme values and country codes must be reviewed before publication.

### Run from a fresh terminal

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
python -m pip install -r dashboard/requirements.txt

# Fully enriched CSV
python dashboard/build.py --csv '/path/current_enriched.csv' --out ./local_output/dashboard

# Updated data CSV without bibliographic enrichment columns
python dashboard/build.py --csv '/path/new_data.csv' \\
  --bibliography '/path/previous_enriched.csv' --out ./local_output/dashboard

# Offline regression tests
python -m unittest discover -s dashboard/tests -v

# Extended frozen-dataset checks, if you have the private baseline CSV locally
CGIAR_BASELINE_CSV='/path/CGIAR_source_updated_v9_transformed.csv' \\
  python -m unittest discover -s dashboard/tests -v
```

Outputs are `CGIAR_evidence_dashboard.html`, `CGIAR_evidence_dashboard.zip`, `product_frequencies.csv`, and `build_manifest.json`, which includes SHA-256 hashes of the input and resulting HTML and counts for auditing. All should be inspected before publication.

For the closest visual reproduction of the original word cloud, select a locally installed **DejaVu Sans** font using `CGIAR_WORDCLOUD_FONT=/path/to/DejaVuSans.ttf`. The renderer uses fixed size, packing, minimum font size, seed `17`, and a fail-closed check that **all** distinct names are placed. No fonts are bundled with or distributed from the repository. Without that font, the installed wordcloud default font may result in slightly different packing.

## Frozen source-to-dashboard rules

- **Article key:** `Filenames`; duplicate or blank identifiers abort the build. `Year` must be a four-digit year if present. One record per CSV row.
- **Country:** source ISO-3 field, potentially with multiple comma/semicolon-delimited codes; map applies the *frozen FY2027 high-income-country exclusion only to the plotted map*. Records and country metadata remain intact in the database and filters. An unknown ISO-3 code fails rather than being assigned a guessed name.
- **Product dropdowns:** broad `Crop/livestock/tree/fish` source field. The `CLEAN` product-name field drives the word cloud and the database's fine-grained product display. Product values inside parentheses are preserved in the database display. For the word cloud and frequency table, the established v3.6 comma/semicolon tokenisation is retained so counts are compatible with the approved display.
- **Word cloud:** each distinct cleaned name counts at most once per article; all names, including singletons, are included; the ranked complete frequency table is regenerated with the same counts.
- **Thematic coding:** the exact source-column + exact cell-string crosswalk in `config/approved_dashboard_contract.json` defines all approved Level 3 nodes and display paths. Multiple codes on one article count as overlapping, not mutually exclusive. The builder *rejects any unrecognised source coding* instead of inventing an ontology mapping. Level 1 master-field coding is retained even where no Level 3 category was entered.
- **Adaptation nature:** former unplanned and autonomous classes were merged upstream to code **2**, now “Autonomous/unplanned adaptation”. The builder rejects a legacy standalone code 3 and never reintroduces that category. Code `90` is not relevant and never counted as a nature category.
- **Adaptation/mitigation nature denominators:** articles with relevant nonblank nature coding within overarching Themes 3 and 4, respectively. The separate Yes/No bars sum **only coded Yes and No responses**, not blanks.
- **Bibliography:** retain exact Lens matches, then exact OpenAlex matches and explicitly verified publisher recoveries. Abstracts are cleaned of HTML/JATS markup and whitespace for display; unresolved DOIs stay unresolved rather than being guessed. Provider metadata is carried forward by exact filename only.
- **Filters:** globally synchronized High-level theme, Year, Product and Boolean query (with Country in the database), and a unified **Clear filters** action. The thematic explorer is intentionally independent of the high-level theme dropdown. Regional/mapped plots retain their distinct country-coverage definitions.
- **Display:** do not alter headings, CSS, chart axes, placement or visual hierarchy as part of a data update. Any UI modification requires a new release contract/version and comparison to the locked baseline.

## Validation before publishing

1. Run the regression tests. A new thematic value, unknown country, malformed binary variable or duplicate article ID must fail; do **not** remove the validation.
2. Compare manifest article counts, five Level 1 counts, country-code coverage and product-name totals with the previous build and explain material differences.
3. Open the HTML and inspect the map, regional plot, year bars (including click-through), journal plot, both nature panels, theme tree, searchable word-frequency table and database Boolean search.
4. Confirm *Clear filters* works and chart titles are inside their boxes.
5. Save the new CSV checksum, manifest, dashboard HTML and any approved change log with the release. Never commit the private input dataset or API credentials.

## Release policy

The currently approved dashboard is **v3.6**. The HTML/CSS/JS template and approved codebook are frozen for routine data-only updates. A new design revision requires a new release version and documented review; do not silently change previous thematic mappings. Repository branches are not protected by this script: branch protection/tagging requires repository maintainers to configure GitHub's rulesets.

For a ChatGPT-assisted update, upload the new CSV in the chat and ask for a dashboard rebuild using this repository's `dashboard/build.py` and the retained enriched CSV; this is the same script used locally. The output HTML is delivered as a file, not committed to Git history.