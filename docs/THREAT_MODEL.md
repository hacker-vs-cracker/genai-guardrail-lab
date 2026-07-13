# Threat model and safety boundaries

## Assets considered

- system and developer instructions;
- protected canary values;
- confidential RAG content;
- tool and agent permissions;
- application output integrity;
- API credentials used by test targets;
- test evidence stored in SQLite and reports.

## Threats covered by the built-in scenarios

- direct instruction hierarchy override;
- indirect instructions in retrieved text;
- later-turn attempts to reset policy;
- instructions embedded in simulated tool output;
- protected value disclosure;
- deterministic attack-marker compliance.

## Threats not adequately covered

- visual or audio prompt injection;
- poisoned embeddings or retrieval-index manipulation;
- model supply-chain compromise;
- training data poisoning;
- browser automation and UI-only targets;
- real tool invocation and side-effect verification;
- authorization bypass outside the model response;
- output handling vulnerabilities in downstream code;
- denial of service and cost exhaustion;
- privacy, fairness, and broad content-safety evaluation.

## Trust boundaries

Prompt cases and collected intelligence are untrusted. Remote source plugins may return hostile content. Only curated structured cases should be executable.

Target responses are also untrusted. Reports escape HTML, but users should still avoid opening reports in privileged environments if external plugins modify the reporting pipeline.

## Data handling

The SQLite database and reports can contain complete prompts, complete responses, endpoint metadata, and application errors. Store them as security test evidence and apply the same access controls used for penetration-test reports.

Use `reporting.redact_patterns`, but do not rely on regex redaction alone. Review exported files before publishing them.
