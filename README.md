# Podcast Action Briefs

A public, read-only dashboard of evidence-checked podcast briefs. Each published brief keeps its original conclusion, action items, reasons, practical protocol, evidence assessment, safety notes, applicability, and source links.

The public snapshot intentionally includes the personal and family applicability recorded in each final brief. It does not include raw transcripts, SQLite data, processing history, capture files, Pocket Casts session data, archive tokens, local paths, or generated Word files.

## Run locally

```bash
npm test
npm run build
python3 -m http.server 8766 --directory dist
```

Open <http://127.0.0.1:8766/>.

## Refresh the published briefs

Start the private Podcast Action Dashboard locally, then run:

```bash
python3 scripts/export_snapshot.py \
  --base-url http://127.0.0.1:8765 \
  --output site/data/briefs.json
npm test
npm run build
```

The exporter accepts loopback HTTP URLs only. It copies each stored `brief` object unchanged and adds only the display metadata required by the static site.

## Publication boundary

`npm run build` runs the public-tree check before copying `site/` into `dist/`. The check blocks database artifacts, transcript/capture/work directories, local home paths, credential-shaped JSON keys, and unexpected episode fields.

The website is educational and does not replace medical, legal, or financial advice.
