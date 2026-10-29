# Scripts

`update-repository.sh` indexes `debs/` into `Packages`, `Packages.xz` and
`Release` and writes the site to `_site/`. `validate.py` checks the repository
before that happens. Both run on every push to `main` from
`.github/workflows/update-repository.yml`:

```
validate.py  →  update-repository.sh  →  upload _site/  →  deploy to Pages
```

Never commit `Packages`, `Packages.xz`, `Release` or `_site/`; they are built
from `debs/` on every run. Pages may serve the previous index for up to ten
minutes after a push.

`Release`'s `Architectures` is read from the packages, and a package without a
`Section` fails the build rather than being filed under nothing.

## Signing

Off by default. To turn it on, add these repository secrets:

| Secret | Value |
| --- | --- |
| `GPG_PRIVATE_KEY` | the ASCII-armored secret key (`gpg --export-secret-keys --armor <id>`) |
| `GPG_KEY_ID` | the key's fingerprint or uid, passed to `--local-user` |
| `GPG_PASSPHRASE` | optional, only if the key has one |

The build then publishes `InRelease` and `Release.gpg` beside `Release`; a key
that is configured but cannot sign fails the build instead of publishing an
unsigned index quietly. Users import the public half with
`gpg --export --armor <id>` and trust it in their package manager.
