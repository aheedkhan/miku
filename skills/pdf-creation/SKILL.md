---
name: pdf-creation
description: >-
  Convert markdown reports and notes into PDF deliverables. Use when the user
  asks for a PDF, printable report, export to PDF, or after report-generation.
---

# PDF creation

## Goal
Turn a finished markdown report into a clean PDF under `workspace/reports/pdf/`.

## When to use
- "Make a PDF" / "export this report"
- After `report-generation` saves a `.md`
- Lab / pentest deliverables that need a shareable file

## Preferred toolchain (pick first available)
1. **pandoc** + engine (`pdflatex`, `xelatex`, or `wkhtmltopdf` / `weasyprint` if configured)
2. Fallback: `scripts/md_to_pdf.py` (HTML → PDF via weasyprint if installed, else writes HTML for browser print)

Check:
```bash
command -v pandoc
command -v pdflatex || command -v xelatex || command -v weasyprint
```

## Workflow
1. Confirm source `.md` path (prefer `workspace/reports/**/*.md`)
2. Ensure output dir: `workspace/reports/pdf/`
3. Convert with pandoc when possible:

```bash
SRC="workspace/reports/<type>/<file>.md"
OUT="workspace/reports/pdf/<same-slug>.pdf"
mkdir -p workspace/reports/pdf
pandoc "$SRC" -o "$OUT" --pdf-engine=xelatex -V geometry:margin=1in
# If xelatex missing, try:
# pandoc "$SRC" -o "$OUT" --pdf-engine=pdflatex -V geometry:margin=1in
# or:
# python3 skills/pdf-creation/scripts/md_to_pdf.py "$SRC" "$OUT"
```

4. Verify PDF exists and is non-empty (`ls -la`, `file`)
5. Tell the user the absolute path

## Style defaults
- Letter or A4, ~1in margins
- Keep monospace for code fences
- Title from first `#` heading
- Do not embed malware samples or secrets

## If tools missing
- Install hint (Fedora): `sudo dnf install pandoc texlive-scheme-basic` (user runs sudo)
- Or: `pip install weasyprint markdown` then use `md_to_pdf.py`
- Last resort: emit polished HTML next to the md and say "Print → Save as PDF"

## Never
- Silently drop findings to "fit" a page
- Put live binaries or credentials in the PDF
- Overwrite an existing PDF without asking (use `-v2` slug or confirm)
