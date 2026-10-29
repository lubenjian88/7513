# lubenjian88/7513

An APT source for jailbroken iOS, published with Apelin.

Add `https://lubenjian88.github.io/7513/` in Irisin.

## How it works

- Packages are the `.deb` files in `debs/`, named
  `<Package>_<Version>_<Architecture>.deb`. Apelin's Distribute… page
  publishes a release build here; a `.deb` pushed by hand works the same.
- On every push to `main`, `.github/workflows/update-repository.yml` runs
  `scripts/validate.py` and then `scripts/update-repository.sh`, which indexes
  `debs/` into `Packages`, `Packages.xz` and `Release`, and publishes the site
  to GitHub Pages. Never commit those indexes or `_site/`.
- `depictions/<package id>/` holds a package's depiction, icon and
  screenshots; `sileo-featured.json` the banners Irisin shows at the top of the
  source; `CydiaIcon.png` and `SileoIcon.png`, when present, the source's icon.
- Signing is optional. With the `GPG_PRIVATE_KEY` and `GPG_KEY_ID` secrets set,
  the build also publishes `InRelease` and `Release.gpg` beside `Release`;
  without them the source works the same but clients call it unverified.

Pages may serve the previous index for up to ten minutes after a push.

## Publishing a version

1. Put the new build in `debs/`, named after its own control file. A file whose
   name disagrees with `Package`, `Version` or `Architecture` still indexes, but
   `scripts/validate.py` reports it.
2. At build time, have the control file point at the package's web page, native
   depiction and icon, using absolute URLs on the address Pages serves:

   ```debcontrol
   Depiction: https://lubenjian88.github.io/7513/depictions/com.cracklock.7513/
   SileoDepiction: https://lubenjian88.github.io/7513/depictions/com.cracklock.7513/depiction.json
   Icon: https://lubenjian88.github.io/7513/depictions/com.cracklock.7513/icon.jpg
   Homepage: https://lubenjian88.github.io/7513/
   ```

   Without these fields the package still installs, but clients show its
   description as plain text and `depictions/<id>/` is never opened. The
   packages currently in `debs/` were built before these fields existed, so
   they carry none of them; the next build is where they belong. Rebuilding a
   published version to add metadata changes its hash without changing its
   version, which is why it is cheaper to wait for the next one.
3. Bump the version shown in `depictions/<package id>/depiction.json` and
   `index.html`. A depiction that lags the newest package is a build error, not
   a cosmetic one.
4. Run `python3 scripts/validate.py` before pushing; the same check runs in CI.
   It fails on a missing screenshot, a stale version, a duplicate
   `Package`+`Version`+`Architecture`, or a depiction URL outside `SOURCE_URL`.

## Renaming a package

To take over an older id, version-gate the takeover so an installed copy is
replaced rather than left behind with its files. Use the version being
published where `X.Y.Z` is:

```debcontrol
Breaks: com.cracklock.shatter (<< X.Y.Z)
Replaces: com.cracklock.shatter (<< X.Y.Z)
Provides: com.cracklock.shatter
```

Keep the version on `Breaks` and `Replaces`. An unversioned `Breaks` also
matches the package's own unversioned `Provides`, which reads as a conflict.
