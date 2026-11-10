from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = "2.0.11"
COMMIT = "fa978b24e75fb03c137bf2cdae4fef0e711cf8a1"
EXPECTED_SHA256 = "d6fdc75f204e6bdefa99b69bf1e6d4ac69b8a364f77929f45c13476b4000f717"
URL = f"https://raw.githubusercontent.com/bigskysoftware/htmx/{COMMIT}/dist/htmx.min.js"
TARGET = ROOT / "src" / "studio_manager" / "static" / "vendor" / "htmx-2.0.11.min.js"
MANIFEST = ROOT / "src" / "studio_manager" / "static" / "vendor" / "htmx.manifest.json"


def main() -> int:
    request = urllib.request.Request(URL, headers={"User-Agent": "Universal-AI-Cartoon-Studio/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        data = response.read()
    actual = hashlib.sha256(data).hexdigest()
    if actual != EXPECTED_SHA256:
        raise RuntimeError(f"HTMX SHA-256 mismatch: {actual}")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_bytes(data)
    manifest = {
        "name": "htmx.org",
        "version": VERSION,
        "license": "0BSD",
        "source_commit": COMMIT,
        "source_url": URL,
        "sha256": actual,
        "bytes": len(data),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "target": str(TARGET), "sha256": actual, "bytes": len(data)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
