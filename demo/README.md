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

The visual language is inspired by the MIT-licensed VoltAgent design guide from
[`VoltAgent/awesome-design-md`](https://github.com/VoltAgent/awesome-design-md):
near-black canvas, emerald accent, terminal-native cards, tight grids, and
developer-tool style interaction.
