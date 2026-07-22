# Experiment artifacts

Each v3 experiment is isolated in `experiments/<experiment_id>/`.

## Required layout

```text
experiments/<experiment_id>/
  manifest.json       # protocol, code/scenario/model hashes, planned tuples
  validation.json     # valid/technical-failure/invalid-protocol accounting
  summary.json        # aggregate metrics derived only from valid runs
  stats.json          # paired analysis derived from summary/run validation
  figures/            # generated, reviewable figures
  replay/             # reviewed synthetic demo replay only
  runs.jsonl          # raw run log — ignored
  traces/             # raw model responses/diagnostics — ignored
```

## Privacy and reproducibility rules

- `runs.jsonl`, raw model content, raw tool values, and tracebacks are local-only and ignored by Git.
- A standard delivery event records field names, record IDs, sensitivity labels/counts, hashes, policy decision, and latency; it does not duplicate raw sensitive values.
- Only reviewed synthetic manifests, aggregate summaries, statistics, figures, and demo replay examples may be committed.
- Do not overwrite `output/multi_model_results_v2.json` or v2 JSONL files. V2 remains an exploratory baseline.
- Before any push, inspect generated artifacts and obtain explicit user approval.
