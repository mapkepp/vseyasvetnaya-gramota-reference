#!/usr/bin/env python3
import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ORIGINAL = "http://washbrain.narod.ru/Image61.gif"
UA = "vseyasvetnaya-gramota-fita-recovery/1.0"
TIMEOUT = 30


def fetch(url):
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read(), resp.headers.get_content_type()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def captures(url):
    api = (
        "https://web.archive.org/cdx/search/cdx?"
        f"url={quote(url, safe=':/')}&output=json"
        "&filter=statuscode:200&collapse=digest"
        "&fl=timestamp,original,statuscode,digest,mimetype"
        "&limit=50"
    )
    raw, _ = fetch(api)
    rows = json.loads(raw.decode("utf-8"))
    if not rows:
        return []
    if isinstance(rows[0], list):
        header = rows[0]
        return [dict(zip(header, row)) for row in rows[1:]]
    return rows


def main():
    ap = argparse.ArgumentParser(description="Recover the original Fita Image61.gif from an archive without touching canonical data.")
    ap.add_argument("--output", default="fita-recovery-output", help="Output directory.")
    args = ap.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "status": "research-only",
        "canonical_mutation": False,
        "original_url": ORIGINAL,
        "status_detail": "unresolved",
    }

    try:
        rows = captures(ORIGINAL)
        rows = [r for r in rows if r.get("timestamp") and r.get("original")]
        rows.sort(key=lambda r: r["timestamp"])
    except Exception as exc:
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        rows = []

    if rows:
        cap = rows[-1]
        archived = f"https://web.archive.org/web/{cap['timestamp']}id_/{cap['original']}"
        manifest["capture"] = cap
        manifest["archived_url"] = archived
        try:
            blob, content_type = fetch(archived)
            path = out / "Image61.gif"
            path.write_bytes(blob)
            manifest["status_detail"] = "recovered"
            manifest["file"] = {
                "path": str(path.relative_to(out)),
                "sha256": sha256(blob),
                "bytes": len(blob),
                "content_type": content_type,
            }
        except Exception as exc:
            manifest["status_detail"] = "capture-found-fetch-failed"
            manifest["fetch_error"] = f"{type(exc).__name__}: {exc}"
    else:
        manifest["status_detail"] = "no-wayback-capture"

    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
