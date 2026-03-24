---
name: paper-analyzer
description: Download and analyze academic papers from arXiv or PDF URLs. Use when user provides an arXiv ID/URL, a PDF link, or asks to analyze/summarize a research paper.
homepage: https://arxiv.org
metadata: {"nanobot":{"emoji":"📄","requires":{"bins":["python3","curl"]}}}
---

# Paper Analyzer

Download academic papers and extract key information for analysis.

## When to use (trigger phrases)

Use this skill when the user asks any of:
- "download this paper"
- "analyze this paper"
- "summarize this research paper"
- "what is this paper about?"
- Provides an arXiv ID (e.g., `2301.07041`) or arXiv URL
- Provides a direct PDF URL

## Quick start

### Download a paper from arXiv

```bash
python3 ~/.nanobot/workspace/skills/paper-analyzer/scripts/download_paper.py "2301.07041"
python3 ~/.nanobot/workspace/skills/paper-analyzer/scripts/download_paper.py "https://arxiv.org/abs/2301.07041"
```

### Download a paper from a direct PDF URL

```bash
python3 ~/.nanobot/workspace/skills/paper-analyzer/scripts/download_paper.py "https://example.com/paper.pdf"
```

### Analyze a downloaded paper

```bash
python3 ~/.nanobot/workspace/skills/paper-analyzer/scripts/analyze_paper.py "/tmp/papers/2301.07041.pdf"
```

## Workflow

1. **Download**: Use `download_paper.py` to fetch the PDF. It saves to `/tmp/papers/` by default.
2. **Extract text**: Use `analyze_paper.py` to extract text content and metadata from the PDF.
3. **Analyze**: Read the extracted text and provide insights based on the user's request:
   - Paper summary (abstract, key contributions, methodology, results)
   - Specific section analysis
   - Citation extraction
   - Comparison with other papers

## Supported sources

- **arXiv**: Provide an arXiv ID (`2301.07041`) or URL (`https://arxiv.org/abs/2301.07041`)
- **Direct PDF URLs**: Any URL ending in `.pdf` or serving a PDF content type
- **Semantic Scholar**: URLs from `semanticscholar.org`

## Output format

The analyzer extracts:
- **Title** and **Authors**
- **Abstract**
- **Full text** (section by section)
- **References** (when parseable)

## Tips

- For arXiv papers, metadata (title, authors, abstract) is fetched from the arXiv API first
- Large papers are split into sections for easier analysis
- If PDF text extraction fails (scanned PDFs), inform the user that OCR is not supported
