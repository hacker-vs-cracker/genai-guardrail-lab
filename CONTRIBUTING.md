# Contributing

Thank you for considering a contribution.

## Good first contributions

- new safe test cases with clear provenance;
- target adapters for common application interfaces;
- deterministic evaluators with calibration tests;
- documentation and reproducible examples;
- report accessibility improvements;
- bug fixes with regression tests.

## Development setup

```bash
python3.11 -m venv glab_dev_venv
source glab_dev_venv/bin/activate
pip install -e '.[dev]'
pytest
ruff check .
```

## Pull requests

A pull request should:

- explain the problem and design decision;
- include tests for behavioural changes;
- avoid committing credentials, reports containing private data, model files, or large datasets;
- document source, date, and licence for contributed prompt cases;
- keep test cases defensive and limited to authorised evaluation;
- update the changelog for user-visible behaviour.

## AI-assisted contributions

AI-assisted code or documentation is welcome when the contributor reviews and tests it. Disclose substantial AI assistance in the pull request description. The contributor remains responsible for correctness, licensing, security, and maintenance.
