#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

PAGES = [
    ("01", "Та-Ё", "http://gramota.org/alfavit01.html"),
    ("02", "Ёк-Ио", "http://gramota.org/alfavit02.html"),
    ("03", "Йо-Пи", "http://gramota.org/alfavit03.html"),
    ("04", "Па-Ер", "http://gramota.org/alfavit04.html"),
    ("05", "Еры-Исто", "http://gramota.org/alfavit05.html"),
    ("06", "Ису-Ятый", "http://gramota.org/alfavit06.html"),
]

USER_AGENT = "vseyasvetnaya-gramota-recovery/1.0"
TIMEOUT = 30


class ImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag.lower() == "img":
            for key in ("src", "data-src"):
                value = attrs.get(key)
                if value:
                    self.urls.append(value)
            srcset = attrs.get("srcset")
            if srcset:
                for item in srcset.split(","):
                    candidate = item.strip().split()[0]
                    if candidate:
                        self.urls.append(candidate)


def fetch(url):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read(), resp.headers.get_content_type()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def wayback_captures(url):
    api = (
        "https://web.archive.org/cdx/search/cdx?"
        f"url={quote(url, safe=':/')}&output=json"
        "&filter=statuscode:200&filter=mimetype:text/html"
        "&collapse=digest&fl=timestamp,original,statuscode,digest,mimetype"
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


def arquivo_captures(url):
    api = (
        "https://arquivo.pt/wayback/cdx?"
        f"url={quote(url, safe=':/')}&output=json&filter=statuscode:200"
    )
    raw, _ = fetch(api)
    try:
        rows = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(rows, dict):
        return rows.get("captures") or rows.get("results") or []
    if isinstance(rows, list):
        return rows[1:] if rows and isinstance(rows[0], list) else rows
    return []


def choose_wayback(rows):
    rows = [r for r in rows if r.get("timestamp") and r.get("original")]
    rows.sort(key=lambda r: r["timestamp"])
    return rows[-1] if rows else None


def safe_name(url, index):
    tail = url.rstrip("/").split("/")[-1] or f"image-{index:03d}"
    tail = re.sub(r"[^A-Za-z0-9._-]+", "_", tail)
    return f"{index:03d}-{tail}"


def main():
    ap = argparse.ArgumentParser(description="Harvest archived six-page Bukovnik visual sheets without modifying canonical data.")
    ap.add_argument("--output", default="recovery-output", help="Output directory.")
    ap.add_argument("--max-images", type=int, default=200, help="Maximum images per page.")
    ap.add_argument("--sleep", type=float, default=0.2, help="Delay between downloads.")
    ap.add_argument("--page", action="append", choices=[x[0] for x in PAGES], help="Only harvest selected page ids.")
    args = ap.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    selected = [p for p in PAGES if not args.page or p[0] in args.page]
    manifest = {"status": "research-only", "canonical_mutation": False, "pages": []}

    for page_id, label, original in selected:
        record = {"page_id": page_id, "label": label, "original_url": original, "status": "unresolved"}
        try:
            wb = wayback_captures(original)
            capture = choose_wayback(wb)
        except Exception as exc:
            record["wayback_error"] = f"{type(exc).__name__}: {exc}"
            capture = None

        if capture:
            timestamp = capture["timestamp"]
            archived = f"https://web.archive.org/web/{timestamp}id_/{capture['original']}"
            record["archive"] = "wayback"
            record["capture"] = capture
            record["archived_url"] = archived
            try:
                html, ctype = fetch(archived)
                page_dir = out / f"page-{page_id}-{re.sub(r'[^0-9A-Za-z_-]+', '_', label)}"
                page_dir.mkdir(parents=True, exist_ok=True)
                html_path = page_dir / "source.html"
                html_path.write_bytes(html)
                record["html"] = {"path": str(html_path.relative_to(out)), "sha256": sha256(html), "content_type": ctype}
                parser = ImageParser()
                parser.feed(html.decode("utf-8", errors="replace"))
                image_urls = []
                seen = set()
                for raw_url in parser.urls:
                    absolute = urljoin(archived, raw_url)
                    if absolute not in seen:
                        seen.add(absolute)
                        image_urls.append(absolute)
                image_urls = image_urls[: args.max_images]
                record["images"] = []
                for idx, image_url in enumerate(image_urls, 1):
                    try:
                        time.sleep(args.sleep)
                        blob, image_type = fetch(image_url)
                        filename = safe_name(image_url, idx)
                        image_path = page_dir / "images" / filename
                        image_path.parent.mkdir(parents=True, exist_ok=True)
                        image_path.write_bytes(blob)
                        record["images"].append({
                            "url": image_url,
                            "path": str(image_path.relative_to(out)),
                            "sha256": sha256(blob),
                            "content_type": image_type,
                            "bytes": len(blob),
                        })
                    except Exception as exc:
                        record["images"].append({"url": image_url, "error": f"{type(exc).__name__}: {exc}"})
                record["status"] = "harvested"
            except Exception as exc:
                record["status"] = "archive-found-fetch-failed"
                record["fetch_error"] = f"{type(exc).__name__}: {exc}"
        else:
            record["status"] = "no-wayback-capture"

        manifest["pages"].append(record)

    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(out),
        "pages": len(manifest["pages"]),
        "harvested": sum(p["status"] == "harvested" for p in manifest["pages"]),
        "canonical_mutation": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
