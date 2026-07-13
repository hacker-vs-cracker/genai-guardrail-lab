# Portfolio notes

## One-line description

Built a plugin-based defensive test harness for evaluating prompt-injection resilience across local LLMs, hosted model APIs, RAG services, and Python-based GenAI applications.

## Longer project summary

I built GenAI Guardrail Lab to turn manual prompt-injection experiments into a repeatable regression workflow. The project collects curated test cases, de-duplicates them in SQLite, renders the same case across direct, RAG, multi-turn, and tool-output scenarios, executes those scenarios against pluggable targets, and generates reviewable HTML, JSON, CSV, and JUnit evidence.

The framework currently supports Ollama, OpenAI-compatible APIs, generic JSON endpoints, and Python callables. This allows it to test either a foundation model or the complete application around it.

## Engineering and security areas demonstrated

- Python package design and command-line tooling;
- plugin registries and adapter patterns;
- REST API integration;
- SQLite schema design and evidence retention;
- concurrency and provider error handling;
- prompt-injection and indirect-injection testing;
- RAG and agent security boundaries;
- deterministic evaluation and false-positive awareness;
- static HTML, CSV, JSON, and JUnit reporting;
- CI, tests, documentation, responsible-use controls, and release packaging.

## Evidence to add after a real run

- exact Ollama and model versions;
- machine specification and test date;
- number and categories of cases tested;
- direct versus indirect scenario comparison;
- manually validated examples;
- changes made after findings and the regression result;
- known limitations and cases excluded from the conclusion.

## Claims to avoid

Do not claim that the project proves a model is secure, detects every jailbreak, or confirms business impact from automated output alone. Describe it as a regression harness and evidence-collection tool.

## AI assistance disclosure

AI assistance was used for design exploration, code drafting, refactoring suggestions, documentation editing, and test-case brainstorming. I reviewed, modified, organised, and tested the implementation and remain responsible for its design and limitations.
