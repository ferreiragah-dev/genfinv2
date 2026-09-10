"""Download pinned, self-hosted UI dependencies. Run once during setup.

Only explicitly selected package assets are extracted; no package code runs.
Upstream license files are retained alongside the assets.
"""

import io
import json
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "assets" / "vendor"


def package(name, version):
    request = urllib.request.Request(
        f"https://registry.npmjs.org/{name}/{version}", headers={"User-Agent": "GenFin-asset-setup"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        metadata = json.load(response)
    with urllib.request.urlopen(metadata["dist"]["tarball"], timeout=60) as response:
        return tarfile.open(fileobj=io.BytesIO(response.read()), mode="r:gz")


def write_asset(archive, member, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(archive.extractfile(member).read())


def main():
    with package("chart.js", "4.5.1") as archive:
        write_asset(archive, "package/dist/chart.umd.js", ROOT / "chart.umd.js")
        write_asset(archive, "package/LICENSE.md", ROOT / "CHART-LICENSE.md")
    with package("@fortawesome/fontawesome-free", "6.7.2") as archive:
        write_asset(archive, "package/css/all.min.css", ROOT / "fontawesome/css/all.min.css")
        for member in archive.getmembers():
            if member.name.startswith("package/webfonts/") and member.name.endswith(".woff2"):
                write_asset(archive, member, ROOT / "fontawesome/webfonts" / Path(member.name).name)
        write_asset(archive, "package/LICENSE.txt", ROOT / "fontawesome/LICENSE.txt")
    with package("@fontsource-variable/inter", "5.2.5") as archive:
        write_asset(
            archive, "package/files/inter-latin-wght-normal.woff2", ROOT / "inter/inter-latin.woff2"
        )
        write_asset(archive, "package/LICENSE", ROOT / "inter/LICENSE")
    (ROOT / "inter/inter.css").write_text(
        "@font-face{font-family:'Inter';font-style:normal;font-weight:100 900;font-display:swap;src:url('./inter-latin.woff2') format('woff2')}\n",
        encoding="utf-8",
    )
    print("Chart.js 4.5.1, Font Awesome 6.7.2 and Inter 5.2.5 vendored.")


if __name__ == "__main__":
    main()
