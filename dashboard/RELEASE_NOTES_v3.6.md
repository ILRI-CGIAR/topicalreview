# v3.6 — frozen baseline

Approved dashboard design: **CGIAR Climate-related Journal Articles in Low- and Middle-Income Countries**.

Baseline input: `CGIAR_source_updated_v9_transformed.csv` from the latest v2.6 data update. Source workbook `A_FileFor_BerenguerJose1(7).xlsx`. Previous exact-DOI enrichments from Lens and OpenAlex and one manually verified bibliographic recovery are retained. No publication-ready research data are committed.

Baseline verification (13 November 2026):
- **2,652** article records; **476** without country ISO3 codes
- Thematic Level 1 article counts: **1,041 / 386 / 1,142 / 502 / 667** for Themes 1–5, overlapping
- **2,641** Lens exact-DOI matches, with OpenAlex and manual additions preserved
- **538** articles with usable cleaned named products; **274** distinct names; **190** singletons, all represented in the cloud and ranked table
- The approved combined adaptation code `Autonomous/unplanned adaptation` remains merged
- High-income countries excluded from map shading only, not the dataset

The committed code and template define the frozen build process; on each new CSV the corresponding generated HTML and manifest should be archived externally, with the CSV checksum. This release does not imply that an arbitrary new CSV is automatically valid: unmatched ontology labels or newly introduced ISO3 codes require review.