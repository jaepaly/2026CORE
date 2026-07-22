# 2026CORE live demo

Interactive, dependency-free demo for the 학술제 presentation.

## Run

From the repository root:

```bash
python -m http.server 8080
```

Open:

```text
http://localhost:8080/demo/
```

The demo is static HTML/CSS/JS. It fetches committed summary JSON files from
`output/` when served over HTTP and falls back to embedded values if unavailable.

## Design basis

The visual language follows the Notion-style `DESIGN.md` installed with:

```bash
npx getdesign@latest add notion
```

Key choices: warm paper canvas, white document-like cards, Notion blue as the
single structural accent, a deep indigo hero band, pill CTAs, hairline borders,
and small decorative sticker colors.
