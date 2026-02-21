---
name: nano-pdf
description: "Edit PDF slides and pages using natural language with Gemini AI. Supports editing existing pages, adding new slides, and style-matching. Requires GEMINI_API_KEY."
requires_env:
  - GEMINI_API_KEY
---

# Nano PDF

Edit PDF files using natural language instructions, powered by Google Gemini.

## When to Use

- "Update this slide to include 2025 data"
- "Change the title on page 3"
- "Add an agenda slide to this deck"
- "Edit this PDF to fix the chart"
- Any natural-language PDF editing request

## Edit a Page

```bash
nano-pdf edit document.pdf 2 "Change the title to 'Q4 Results'"
```
Arguments: `edit <file> <page_number> "<instruction>"`

## Add a New Slide

```bash
nano-pdf add presentation.pdf 0 "Agenda slide with: Overview, Financial Results, Outlook"
```
Inserts at position 0 (beginning). Use page count to append at end.

## Edit with Style Reference

```bash
nano-pdf edit document.pdf 5 "Add a summary section" --style-pages 1,2
```
Uses pages 1-2 as visual style reference for consistent design.

## Batch Edit Multiple Pages

```bash
nano-pdf edit report.pdf 1-5 "Update the footer to say 'Confidential 2026'"
```

## Notes

- Requires `GEMINI_API_KEY` with billing enabled (Gemini 3 Pro Image)
- Uses Poppler to convert PDF pages to images for processing
- Non-destructive: preserves searchable text layer via OCR re-hydration
- Output overwrites the original file — make a copy first if needed
- Works best with slide decks and visually structured PDFs
- For basic PDF operations (merge, split, rotate) without AI, use `python3` with pypdf
