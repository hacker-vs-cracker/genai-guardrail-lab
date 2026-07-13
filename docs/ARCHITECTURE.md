# Architecture

GenAI Guardrail Lab uses four small plugin boundaries so that collection, execution, and assessment are not tied to a single model provider.

## 1. Sources

A source yields `PromptCase` objects. Cases include provenance, a publication date, a category, content, and an `executable` flag.

Structured case sources may be executable after review. Research and release sources are always created as non-executable intelligence by the built-in plugins.

## 2. Scenarios

A scenario turns a case into a concrete message sequence. It also creates a unique attack marker, protected canary, and safe token. The same source case can therefore be tested through multiple attack surfaces without duplicating it in the database.

Built-in surfaces:

- direct user input;
- retrieved/RAG document;
- later conversation turn;
- tool output.

## 3. Targets

A target sends rendered messages to the system under test and returns a normalized response.

Built-in targets:

- Ollama `/api/chat`;
- OpenAI-compatible chat completions;
- configurable JSON HTTP application;
- Python callable;
- deterministic mock target.

The HTTP and Python adapters are intended for complete applications. They provide better evidence than testing a foundation model alone because application prompts, retrieval, filters, and orchestration remain in the execution path.

## 4. Evaluators

An evaluator receives the rendered scenario and normalized target response. The built-in deterministic evaluator looks for the unique marker, canary, safe token, refusal phrases, and limited compliance indicators.

A plugin can add semantic scoring, an LLM judge, a policy engine, or application-specific assertions. Multiple evaluators may run for each result; the highest risk score determines the aggregate verdict while individual evaluator output is retained.

## Persistence

SQLite stores:

- prompt cases;
- collection history;
- test runs;
- normalized results and evaluator details.

Exact content de-duplication uses a normalized SHA-256 hash.

## Reporting

Reports are static and portable:

- HTML dashboard;
- full findings page;
- date-sorted prompt/intelligence page;
- JSON summary;
- CSV results;
- JUnit XML.

The report renderer supports configurable regular-expression redaction. It does not guarantee that every secret is removed, so manual inspection is still required.
