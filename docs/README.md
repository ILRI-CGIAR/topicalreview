# GitHub Pages website

This folder is the publication root for the CGIAR Evidence Dashboard.

## Publish the approved dashboard

Upload the complete, approved standalone HTML for v4.2 as **`docs/index.html`** on the `main` branch.

The release file is named `CGIAR_evidence_atlas_v42.html` in the ChatGPT deliverables. Rename it locally to `index.html` before uploading; do not use the data-free `dashboard/template.html` as the published file.

Settings → Pages:
- Source: Deploy from a branch
- Branch: `main`
- Folder: `/docs`

Expected URL: https://ilri-cgiar.github.io/topicalreview/

## Updating the site

Rebuild and validate the HTML from the approved `dashboard/` pipeline with the latest CSV, review the output, and replace `docs/index.html` in a new commit. Keep the underlying research data and API keys out of the public repository. The HTML itself contains embedded article data and is intentionally public once published.

Do not edit `dashboard-v3.6` (frozen reference branch).
