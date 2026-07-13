# Screenshot guide

Screenshots make the project easier to understand, but they should show reproducible evidence rather than decorative mock-ups.

Recommended screenshots:

1. `dashboard.png` — total results and target comparison.
2. `findings.png` — one manually reviewed finding with the response and signals visible.
3. `prompts.png` — date-sorted prompt and intelligence library.
4. `terminal.png` — a complete command and generated report path.
5. `architecture.png` — an optional diagram based on `docs/ARCHITECTURE.md`.

## Generate safe example pages

```bash
guardrail-lab --config config.demo.yaml all --archive
open demo-output/reports/index.html
```

Capture the browser at a readable desktop width. Label demo screenshots as **mock data**.

For portfolio screenshots from real models:

- show the exact run date and model name;
- state that results are experimental;
- distinguish automated findings from manually validated findings;
- redact API keys, internal hostnames, usernames, file paths, private prompts, customer data, and confidential retrieved content;
- do not claim that a `BYPASS` result affects every deployment of the same model.
