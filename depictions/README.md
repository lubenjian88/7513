# Depictions

Optional, one folder per package id: `index.html` (the web depiction),
`depiction.json` (the native depiction Irisin shows), `icon.jpg` and a
`screenshots/` folder. They are published at
`<source>/depictions/<package id>/…`, and the package's control file has to
link to them (`Depiction`, `SileoDepiction`, `Icon`) — a folder nothing points
at is never opened.

Every picture the two files reference has to exist in this folder. Deleting a
screenshot means deleting its entry from both `depiction.json` and
`index.html`; `scripts/validate.py` fails the build when one is left behind.

Both files also show the version, and it has to be the newest version in
`debs/`. The validator compares them, so a release is not done until the
depiction moves with it.
