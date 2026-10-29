#!/usr/bin/env bash
# Indexes debs/ into Packages, Packages.xz and Release and writes the site
# GitHub Pages serves to _site/. Run by the workflow on every push to
# main; on Debian or Ubuntu it runs the same by hand.
set -euo pipefail

repository_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_root"

for command_name in apt-ftparchive xz; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    exit 69
  fi
done

name="${REPOSITORY_NAME:-$(basename "$repository_root")}"
owner="${REPOSITORY_OWNER:-$name}"
work_dir="$(mktemp -d "$repository_root/.repo-build.XXXXXX")"
trap 'rm -rf -- "$work_dir"' EXIT
site_dir="$work_dir/site"
mkdir -p "$site_dir"

shopt -s nullglob
packages=(debs/*.deb)
shopt -u nullglob

# Running from the root keeps each Filename relative: debs/<file>.deb.
if ((${#packages[@]} > 0)); then
  apt-ftparchive packages debs > "$work_dir/Packages"
else
  : > "$work_dir/Packages"
fi

# A package with no Section is filed under nothing; refuse it here.
awk '
  BEGIN { RS = ""; FS = "\n" }
  {
    package = ""; section = ""
    for (field = 1; field <= NF; field++) {
      if ($field ~ /^Package: /) package = substr($field, 10)
      if ($field ~ /^Section: /) section = substr($field, 10)
    }
    if (package != "" && section == "") {
      printf "Package %s has no Section field, which package managers file it by.\n", package > "/dev/stderr"
      exit 1
    }
  }
' "$work_dir/Packages"

xz -9e -c "$work_dir/Packages" > "$work_dir/Packages.xz"
mkdir -p "$work_dir/indexes"
cp "$work_dir/Packages" "$work_dir/Packages.xz" "$work_dir/indexes/"

# Architectures come from the packages, so Release never advertises one the
# repository has nothing for. The fallback keeps an empty source valid.
architectures="$(awk '/^Architecture: /{print $2}' "$work_dir/Packages" | sort -u | tr '\n' ' ')"
architectures="${architectures% }"
if [[ -z "$architectures" ]]; then
  architectures="iphoneos-arm64 iphoneos-arm64e"
fi

# Release is written beside the indexes, never among them, so it does
# not hash itself.
apt-ftparchive \
  -o APT::FTPArchive::Release::Origin="$owner" \
  -o APT::FTPArchive::Release::Label="$name" \
  -o APT::FTPArchive::Release::Suite="stable" \
  -o APT::FTPArchive::Release::Version="1.0" \
  -o APT::FTPArchive::Release::Codename="$name" \
  -o APT::FTPArchive::Release::Architectures="$architectures" \
  -o APT::FTPArchive::Release::Components="main" \
  -o APT::FTPArchive::Release::Description="Packages from $owner" \
  release "$work_dir/indexes" > "$work_dir/Release"

# Signing is optional. Without RELEASE_SIGNING_KEY the source builds and works
# as before, but clients show it as unverified. Both signatures are written
# beside Release; clients accept either InRelease or Release + Release.gpg.
if [[ -n "${RELEASE_SIGNING_KEY:-}" ]]; then
  if ! command -v gpg >/dev/null 2>&1; then
    echo "RELEASE_SIGNING_KEY is set but gpg is not installed." >&2
    exit 69
  fi
  gpg_options=(--batch --yes --local-user "$RELEASE_SIGNING_KEY")
  if [[ -n "${RELEASE_SIGNING_PASSPHRASE:-}" ]]; then
    gpg_options+=(--pinentry-mode loopback --passphrase "$RELEASE_SIGNING_PASSPHRASE")
  fi
  gpg "${gpg_options[@]}" --armor --detach-sign \
    --output "$work_dir/Release.gpg" "$work_dir/Release"
  gpg "${gpg_options[@]}" --clearsign \
    --output "$work_dir/InRelease" "$work_dir/Release"
fi

if ((${#packages[@]} > 0)); then
  mkdir -p "$site_dir/debs"
  cp "${packages[@]}" "$site_dir/debs/"
fi
for file in index.html CydiaIcon.png SileoIcon.png sileo-featured.json; do
  if [[ -f "$file" ]]; then
    cp "$file" "$site_dir/"
  fi
done
# The home page's QR code: Irisin's add-source link for the address
# Pages serves, which the Camera opens in Irisin. Left out without
# qrencode or an address, and the page shows the card without it.
source_url="${SOURCE_URL:-}"
if [[ -n "$source_url" ]] && command -v qrencode >/dev/null 2>&1; then
  [[ "$source_url" == */ ]] || source_url="$source_url/"
  qrencode -t SVG --svg-path -m 0 --foreground=1F232B -o "$site_dir/qr.svg" \
    "irisin://repository/add?url=$source_url"
fi
if [[ -d depictions ]]; then
  cp -R depictions "$site_dir/depictions"
fi
cp "$work_dir/Packages" "$work_dir/Packages.xz" "$work_dir/Release" "$site_dir/"
for file in Release.gpg InRelease; do
  if [[ -f "$work_dir/$file" ]]; then
    cp "$work_dir/$file" "$site_dir/"
  fi
done
# Pages runs no Jekyll over the site.
touch "$site_dir/.nojekyll"

rm -rf -- "$repository_root/_site"
mv "$site_dir" "$repository_root/_site"
echo "Built the APT repository in _site/ (${#packages[@]} packages)"
