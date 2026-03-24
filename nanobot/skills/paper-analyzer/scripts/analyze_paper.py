#!/usr/bin/env python3
"""Extract and analyze text content from PDF papers."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path


def extract_text_with_python(pdf_path: str) -> str | None:
    """Try to extract text using Python libraries."""
    # Try pypdf first
    try:
        from pypdf import PdfReader

        reader = PdfReader(pdf_path)
        text_parts = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(f"--- Page {i + 1} ---\n{page_text}")
        if text_parts:
            return "\n\n".join(text_parts)
    except ImportError:
        pass
    except Exception as e:
        print(f"Warning: pypdf extraction failed: {e}", file=sys.stderr)

    # Try pdfplumber
    try:
        import pdfplumber

        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"--- Page {i + 1} ---\n{page_text}")
        if text_parts:
            return "\n\n".join(text_parts)
    except ImportError:
        pass
    except Exception as e:
        print(f"Warning: pdfplumber extraction failed: {e}", file=sys.stderr)

    return None


def extract_text_with_pdftotext(pdf_path: str) -> str | None:
    """Extract text using pdftotext command-line tool."""
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", pdf_path, "-"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Warning: pdftotext extraction failed: {e}", file=sys.stderr)
    return None


def extract_sections(text: str) -> dict:
    """Try to identify common paper sections from extracted text."""
    sections = {}
    # Common section headers in academic papers
    section_patterns = [
        r"(?:^|\n)\s*(Abstract)\s*\n",
        r"(?:^|\n)\s*(\d+\.?\s*Introduction)\s*\n",
        r"(?:^|\n)\s*(\d+\.?\s*Related\s+Work)\s*\n",
        r"(?:^|\n)\s*(\d+\.?\s*(?:Method(?:ology)?|Approach|Model))\s*\n",
        r"(?:^|\n)\s*(\d+\.?\s*(?:Experiment(?:s|al)?(?:\s+(?:Setup|Results))?))\s*\n",
        r"(?:^|\n)\s*(\d+\.?\s*Results?(?:\s+and\s+Discussion)?)\s*\n",
        r"(?:^|\n)\s*(\d+\.?\s*Discussion)\s*\n",
        r"(?:^|\n)\s*(\d+\.?\s*Conclusion(?:s)?)\s*\n",
        r"(?:^|\n)\s*(References|Bibliography)\s*\n",
    ]

    positions = []
    for pattern in section_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            positions.append((match.start(), match.group(1).strip()))

    positions.sort(key=lambda x: x[0])

    for i, (pos, name) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        content = text[pos:end].strip()
        # Remove the section header from content
        content = re.sub(r"^\s*" + re.escape(name) + r"\s*\n?", "", content, count=1)
        sections[name] = content.strip()

    return sections


def analyze_paper(pdf_path: str) -> dict:
    """Extract and analyze paper content."""
    result = {
        "file": pdf_path,
        "file_size_kb": round(os.path.getsize(pdf_path) / 1024, 1),
        "text_extracted": False,
        "extraction_method": None,
        "total_characters": 0,
        "sections": {},
        "text": "",
    }

    # Try extraction methods in order
    text = extract_text_with_python(pdf_path)
    if text:
        result["extraction_method"] = "python"
    else:
        text = extract_text_with_pdftotext(pdf_path)
        if text:
            result["extraction_method"] = "pdftotext"

    if not text:
        result["error"] = (
            "Could not extract text from PDF. "
            "Install pypdf (`pip install pypdf`) or pdftotext for text extraction."
        )
        return result

    result["text_extracted"] = True
    result["total_characters"] = len(text)
    result["text"] = text

    # Try to identify sections
    sections = extract_sections(text)
    if sections:
        result["sections"] = {k: v[:500] + "..." if len(v) > 500 else v for k, v in sections.items()}

    # Check for metadata JSON file
    meta_path = pdf_path.replace(".pdf", "_metadata.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path) as f:
                result["arxiv_metadata"] = json.load(f)
        except Exception:
            pass

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_paper.py <pdf_path> [--text-only] [--sections-only]")
        print()
        print("Options:")
        print("  --text-only      Output only the extracted text")
        print("  --sections-only  Output only identified sections")
        print("  --save           Save extracted text to a .txt file")
        sys.exit(1)

    pdf_path = sys.argv[1]
    flags = set(sys.argv[2:])

    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    result = analyze_paper(pdf_path)

    if not result["text_extracted"]:
        print(f"Error: {result.get('error', 'Unknown extraction error')}", file=sys.stderr)
        sys.exit(1)

    if "--text-only" in flags:
        print(result["text"])
    elif "--sections-only" in flags:
        for name, content in result["sections"].items():
            print(f"\n## {name}\n")
            print(content)
    else:
        # Print summary
        print(f"File: {result['file']}")
        print(f"Size: {result['file_size_kb']} KB")
        print(f"Extraction method: {result['extraction_method']}")
        print(f"Total characters: {result['total_characters']}")

        if "arxiv_metadata" in result:
            meta = result["arxiv_metadata"]
            print(f"\nTitle: {meta.get('title', 'N/A')}")
            print(f"Authors: {', '.join(meta.get('authors', []))}")
            print(f"Abstract: {meta.get('abstract', 'N/A')[:300]}...")

        if result["sections"]:
            print(f"\nIdentified sections: {', '.join(result['sections'].keys())}")

        print(f"\n--- Extracted Text (first 2000 chars) ---\n")
        print(result["text"][:2000])
        if len(result["text"]) > 2000:
            print(f"\n... ({result['total_characters'] - 2000} more characters)")

    if "--save" in flags:
        txt_path = pdf_path.replace(".pdf", ".txt")
        with open(txt_path, "w") as f:
            f.write(result["text"])
        print(f"\nText saved to: {txt_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
