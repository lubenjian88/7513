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
