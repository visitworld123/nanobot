#!/usr/bin/env python3
"""Download academic papers from arXiv or direct PDF URLs."""

import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_OUTPUT_DIR = "/tmp/papers"


def extract_arxiv_id(input_str: str) -> str | None:
    """Extract arXiv ID from a URL or raw ID string."""
    # Match arXiv ID patterns: 2301.07041, 2301.07041v2, hep-th/9901001
    patterns = [
        r"arxiv\.org/abs/(\d{4}\.\d{4,5}(?:v\d+)?)",
        r"arxiv\.org/pdf/(\d{4}\.\d{4,5}(?:v\d+)?)",
        r"^(\d{4}\.\d{4,5}(?:v\d+)?)$",
        r"arxiv\.org/abs/([a-z-]+/\d{7}(?:v\d+)?)",
        r"^([a-z-]+/\d{7}(?:v\d+)?)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, input_str.strip())
        if match:
            return match.group(1)
    return None


def fetch_arxiv_metadata(arxiv_id: str) -> dict:
    """Fetch paper metadata from arXiv API."""
    api_url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
    try:
        result = subprocess.run(
            ["curl", "-sL", api_url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return {}

        root = ET.fromstring(result.stdout)
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }

        entry = root.find("atom:entry", ns)
        if entry is None:
            return {}

        title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
        summary = entry.findtext("atom:summary", "", ns).strip()
        authors = [
            a.findtext("atom:name", "", ns)
            for a in entry.findall("atom:author", ns)
        ]
        published = entry.findtext("atom:published", "", ns)
        categories = [
            c.get("term", "")
            for c in entry.findall("atom:category", ns)
        ]

        return {
            "arxiv_id": arxiv_id,
            "title": title,
            "authors": authors,
            "abstract": summary,
            "published": published,
            "categories": [c for c in categories if c],
        }
    except Exception as e:
        print(f"Warning: Could not fetch arXiv metadata: {e}", file=sys.stderr)
        return {}


def download_pdf(url: str, output_path: str) -> bool:
    """Download a PDF file using curl."""
    try:
        result = subprocess.run(
            ["curl", "-sL", "-o", output_path, "-w", "%{http_code}", url],
            capture_output=True, text=True, timeout=120
        )
        http_code = result.stdout.strip()
        if result.returncode != 0 or not http_code.startswith("2"):
            print(f"Error: Download failed (HTTP {http_code})", file=sys.stderr)
            return False

        # Verify it's a PDF
        with open(output_path, "rb") as f:
            header = f.read(5)
        if header != b"%PDF-":
            print("Error: Downloaded file is not a valid PDF", file=sys.stderr)
            os.remove(output_path)
            return False

        return True
    except Exception as e:
        print(f"Error downloading PDF: {e}", file=sys.stderr)
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: download_paper.py <arxiv_id_or_url> [output_dir]")
        print()
        print("Examples:")
        print("  download_paper.py 2301.07041")
        print("  download_paper.py https://arxiv.org/abs/2301.07041")
        print("  download_paper.py https://example.com/paper.pdf")
        sys.exit(1)

    input_str = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUTPUT_DIR

    os.makedirs(output_dir, exist_ok=True)

    # Try to extract arXiv ID
    arxiv_id = extract_arxiv_id(input_str)

    if arxiv_id:
        # Fetch metadata
        print(f"Fetching metadata for arXiv:{arxiv_id}...")
        metadata = fetch_arxiv_metadata(arxiv_id)
        if metadata:
            print(f"Title: {metadata.get('title', 'Unknown')}")
            print(f"Authors: {', '.join(metadata.get('authors', []))}")
            print(f"Published: {metadata.get('published', 'Unknown')}")

            # Save metadata
            meta_path = os.path.join(output_dir, f"{arxiv_id.replace('/', '_')}_metadata.json")
            with open(meta_path, "w") as f:
                json.dump(metadata, f, indent=2)
            print(f"Metadata saved to: {meta_path}")

        # Download PDF
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        pdf_filename = f"{arxiv_id.replace('/', '_')}.pdf"
        pdf_path = os.path.join(output_dir, pdf_filename)

        print(f"Downloading PDF from {pdf_url}...")
        if download_pdf(pdf_url, pdf_path):
            file_size = os.path.getsize(pdf_path)
            print(f"PDF saved to: {pdf_path} ({file_size / 1024:.1f} KB)")
        else:
            sys.exit(1)

    else:
        # Treat as direct URL
        parsed = urlparse(input_str)
        if not parsed.scheme:
            print(f"Error: '{input_str}' is not a valid arXiv ID or URL", file=sys.stderr)
            sys.exit(1)

        # Generate filename from URL
        url_path = parsed.path.rstrip("/")
        filename = os.path.basename(url_path)
        if not filename.endswith(".pdf"):
            filename = filename + ".pdf" if filename else "paper.pdf"
        pdf_path = os.path.join(output_dir, filename)

        print(f"Downloading PDF from {input_str}...")
        if download_pdf(input_str, pdf_path):
            file_size = os.path.getsize(pdf_path)
            print(f"PDF saved to: {pdf_path} ({file_size / 1024:.1f} KB)")
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()
