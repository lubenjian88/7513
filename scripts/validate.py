#!/usr/bin/env python3
"""Validate the repository before it is published.

Catches the three ways this source has actually gone wrong: a depiction
pointing at a screenshot that was deleted, a depiction showing a version the
packages no longer have, and package metadata that disagrees with its own
file name or with the address the site is served from.

Run by the workflow on every push; runs the same by hand:

    SOURCE_URL=https://lubenjian88.github.io/7513/ python3 scripts/validate.py

Exit status is non-zero when anything must be fixed before publishing.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import gzip
import io
import lzma
from glob import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEBS_DIR = os.path.join(ROOT, "debs")
DEPICTIONS_DIR = os.path.join(ROOT, "depictions")
SOURCE_URL = os.environ.get("SOURCE_URL", "").rstrip("/") + "/" if os.environ.get("SOURCE_URL") else ""

ALLOWED_ARCH = {"iphoneos-arm", "iphoneos-arm64", "iphoneos-arm64e", "all"}
REQUIRED_FIELDS = ("Package", "Version", "Architecture", "Section", "Maintainer", "Description")

errors = []
warnings = []


def fail(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


# --- version handling --------------------------------------------------------

def version_key(v):
    """Sort key approximating dpkg's ordering (~ sorts before empty)."""
    epoch, _, rest = v.partition(":")
    if not _:
        rest, epoch = epoch, "0"
    parts = re.split(r"[-+]", rest)
    upstream = parts[0]
    revision = parts[1] if len(parts) > 1 else ""

    def split(s):
        out = []
        for tok in re.findall(r"\d+|[A-Za-z]+|~|[^0-9A-Za-z~]", s):
            out.append((1, int(tok)) if tok.isdigit() else (-1, tok) if tok == "~" else (0, tok))
        return out

    return (int(epoch), split(upstream), split(revision))


def newest(versions):
    return max(versions, key=version_key)


# --- reading .deb control ----------------------------------------------------

def parse_ar(path):
    data = open(path, "rb").read()
    if data[:8] != b"!<arch>\n":
        raise ValueError("not a Debian archive")
    off, members = 8, {}
    while off + 60 <= len(data):
        hdr = data[off:off + 60]
        name = hdr[0:16].decode("ascii", "replace").strip().rstrip("/")
        size = int(hdr[48:58].decode("ascii").strip())
        off += 60
        members[name] = data[off:off + size]
        off += size + (size % 2)
    return members


def control_from_ar(path):
    members = parse_ar(path)
    for name, blob in members.items():
        if not name.startswith("control.tar"):
            continue
        if name.endswith(".gz"):
            raw = gzip.decompress(blob)
        elif name.endswith(".xz"):
            raw = lzma.decompress(blob)
        else:
            raise ValueError(f"unsupported control compression: {name}")
        tf = tarfile.open(fileobj=io.BytesIO(raw))
        for member in tf.getmembers():
            if member.name.rstrip("/").lstrip("./") == "control":
                return tf.extractfile(member).read().decode("utf-8", "replace")
    raise ValueError("no control file in archive")


def parse_control(text):
    fields, current = {}, None
    for line in text.splitlines():
        if line[:1] in (" ", "\t") and current:
            fields[current] += "\n" + line.strip()
            continue
        match = re.match(r"^([A-Za-z0-9-]+):\s*(.*)$", line)
        if match:
            current = match.group(1)
            fields[current] = match.group(2).strip()
    return fields


def read_control(deb):
    if shutil.which("dpkg-deb"):
        result = subprocess.run(["dpkg-deb", "-f", deb], capture_output=True, text=True)
        if result.returncode == 0:
            return parse_control(result.stdout)
        warn(f"{os.path.basename(deb)}: dpkg-deb could not read it, falling back to the built-in reader")
    return parse_control(control_from_ar(deb))


# --- checks ------------------------------------------------------------------

def check_packages():
    debs = sorted(glob(os.path.join(DEBS_DIR, "*.deb")))
    if not debs:
        warn("debs/ has no packages; the source would publish an empty index")
        return {}

    versions_by_package, seen, unlinked = {}, {}, {}
    for deb in debs:
        base = os.path.basename(deb)
        try:
            fields = read_control(deb)
        except Exception as exc:  # noqa: BLE001 - report any parse failure as a build error
            fail(f"{base}: cannot read the control file ({exc})")
            continue

        for field in REQUIRED_FIELDS:
            if not fields.get(field):
                fail(f"{base}: control is missing the {field} field")

        package = fields.get("Package", "")
        version = fields.get("Version", "")
        arch = fields.get("Architecture", "")
        if not package or not version or not arch:
            continue

        if arch not in ALLOWED_ARCH:
            fail(f"{base}: Architecture '{arch}' is not one this source publishes")

        key = (package, version, arch)
        if key in seen:
            fail(f"{base}: duplicates {seen[key]} as {package} {version} {arch}")
        seen[key] = base
        versions_by_package.setdefault(package, []).append(version)

        if SOURCE_URL:
            for field in ("Depiction", "SileoDepiction", "Icon", "Homepage"):
                value = fields.get(field, "")
                if value and not value.startswith(SOURCE_URL):
                    fail(f"{base}: {field} '{value}' does not point at {SOURCE_URL}")

        depiction_dir = os.path.join(DEPICTIONS_DIR, package)
        if os.path.isdir(depiction_dir) and not fields.get("Depiction"):
            unlinked.setdefault(package, []).append(f"{version} {arch}")

    # One line per package rather than one per build; a rebuilt version is where
    # these fields belong, so this is a note, not a failure.
    for package, builds in sorted(unlinked.items()):
        warn(
            f"{len(builds)} build(s) of {package} declare no Depiction/SileoDepiction/Icon, "
            f"so depictions/{package}/ is published but nothing opens it "
            f"({', '.join(builds)})"
        )

    return {pkg: newest(v) for pkg, v in versions_by_package.items()}


def check_asset_exists(package, reference, where):
    if re.match(r"^[a-z]+://", reference):
        return  # absolute URLs are checked against SOURCE_URL at the package level
    target = os.path.normpath(os.path.join(DEPICTIONS_DIR, package, reference))
    if not target.startswith(os.path.join(DEPICTIONS_DIR, package)):
        fail(f"depictions/{package}: {where} points outside the package folder ('{reference}')")
    elif not os.path.isfile(target):
        fail(f"depictions/{package}: {where} references '{reference}', which does not exist")


def walk_depiction_strings(node, package, where):
    """Check every asset-ish string anywhere in a native depiction."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("url", "icon", "banner", "fullsize") and isinstance(value, str):
                check_asset_exists(package, value, f"{where}.{key}" if where else key)
            else:
                walk_depiction_strings(value, package, f"{where}.{key}" if where else key)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            walk_depiction_strings(value, package, f"{where}[{index}]")


def declared_version(node):
    """Find the version shown by a DepictionTableTextView titled 版本."""
    if isinstance(node, dict):
        if node.get("class") == "DepictionTableTextView" and node.get("title") == "版本":
            return node.get("text")
        for value in node.values():
            found = declared_version(value)
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = declared_version(value)
            if found:
                return found
    return None


def check_depictions(latest_versions):
    if not os.path.isdir(DEPICTIONS_DIR):
        return
    for package in sorted(os.listdir(DEPICTIONS_DIR)):
        folder = os.path.join(DEPICTIONS_DIR, package)
        if not os.path.isdir(folder):
            continue
        expected_version = latest_versions.get(package)

        native = os.path.join(folder, "depiction.json")
        if os.path.isfile(native):
            try:
                data = json.load(open(native, encoding="utf-8"))
            except json.JSONDecodeError as exc:
                fail(f"depictions/{package}/depiction.json: invalid JSON ({exc})")
                data = None
            if data is not None:
                walk_depiction_strings(data, package, "")
                shown = declared_version(data)
                if expected_version and shown and shown != expected_version:
                    fail(
                        f"depictions/{package}/depiction.json: shows version {shown} "
                        f"but the newest package is {expected_version}"
                    )

        web = os.path.join(folder, "index.html")
        if os.path.isfile(web):
            html = open(web, encoding="utf-8").read()
            for reference in re.findall(r'<img[^>]+src="([^"]+)"', html):
                check_asset_exists(package, reference, "index.html")
            match = re.search(r"<dt>版本</dt><dd>([^<]+)</dd>", html)
            if expected_version and match and match.group(1).strip() != expected_version:
                fail(
                    f"depictions/{package}/index.html: shows version {match.group(1).strip()} "
                    f"but the newest package is {expected_version}"
                )


def check_featured():
    path = os.path.join(ROOT, "sileo-featured.json")
    if not os.path.isfile(path):
        return
    try:
        data = json.load(open(path, encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"sileo-featured.json: invalid JSON ({exc})")
        return
    for index, banner in enumerate(data.get("banners", [])):
        url = banner.get("url", "")
        if not url:
            fail(f"sileo-featured.json: banner {index} has no url")
            continue
        if SOURCE_URL and url.startswith(SOURCE_URL):
            # A banner on the published address must exist in the tree that
            # gets published.
            local = os.path.join(ROOT, url[len(SOURCE_URL):].lstrip("/"))
            if not os.path.isfile(local):
                fail(f"sileo-featured.json: banner {index} references '{url}', which does not exist")
        elif not re.match(r"^[a-z]+://", url) and not os.path.isfile(os.path.join(ROOT, url.lstrip("./"))):
            fail(f"sileo-featured.json: banner {index} references '{url}', which does not exist")


def main():
    latest = check_packages()
    check_depictions(latest)
    check_featured()

    for message in warnings:
        print(f"warning: {message}")
    for message in errors:
        print(f"error: {message}")

    if errors:
        print(f"\n{len(errors)} problem(s) must be fixed before publishing.")
        return 1
    print(f"Repository contents look consistent ({len(latest)} package(s) checked).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
