# Packages

Put one `.deb` per package version here, named
`<Package>_<Version>_<Architecture>.deb`, and push.

Each package's control file needs these fields:

```debcontrol
Package: com.example.tweak
Name: Example Tweak
Version: 1.0.0
Architecture: iphoneos-arm64
Description: A short description.
Maintainer: Your Name <you@example.com>
Author: Your Name <you@example.com>
Section: Tweaks
```

`Section` is the package's category (Tweaks, Applications, Utilities,
Themes…); the index refuses a package without it. Rootless packages are
`iphoneos-arm64`, roothide ones `iphoneos-arm64e`.

These optional fields make the package show its page in a client instead of a
plain description block. They want absolute URLs, not paths:

```debcontrol
Depiction: https://lubenjian88.github.io/7513/depictions/com.example.tweak/
SileoDepiction: https://lubenjian88.github.io/7513/depictions/com.example.tweak/depiction.json
Icon: https://lubenjian88.github.io/7513/depictions/com.example.tweak/icon.jpg
Homepage: https://lubenjian88.github.io/7513/
```

`scripts/validate.py` warns when a package with a `depictions/<package id>/`
folder declares none of them, fails when the URLs sit outside the address Pages
serves, and fails when the depiction does not show the newest version.

## Publishing a version

1. Put the new build here, named after its own control file.
2. Bump the version shown in `depictions/<package id>/depiction.json` and
   `index.html`. A depiction that lags the newest package is a build error, not
   a cosmetic one.
3. Run `python3 scripts/validate.py` before pushing; the same check runs in CI.
   It fails on a missing screenshot, a stale version, a duplicate
   `Package`+`Version`+`Architecture`, or a depiction URL outside `SOURCE_URL`.
4. Do not rebuild a version that is already published just to add metadata: its
   hash changes while its version does not, so clients that already installed it
   are never offered the new build. Put the fields in the next version instead.

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
