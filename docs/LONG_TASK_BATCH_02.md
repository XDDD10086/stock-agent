# LONG TASK BATCH 02

- Start: 2026-04-17
- Status: In Progress

## Objective

Advance non-CDP milestones while dedicated browser setup is pending.

## Work Items

- [x] W1 Add live LLM integration tests with mocked provider SDK clients.
- [x] W2 Expand ValueCell parser to extract markdown-style result tables.
- [x] W3 Polish Streamlit console layout and readability for operator usage.

## Success Criteria

- New tests cover OpenAI/Gemini live-client JSON parsing paths without network calls.
- Parser returns structured `table` rows when raw response contains markdown tables.
- Streamlit UI remains API-compatible while improving usability and visual hierarchy.

## Verification Gate

- Run `pytest -q` and keep full suite green.
- Update `docs/MILESTONES.md` and `docs/LONG_RUN_EXECUTION.md` with evidence.

## Evidence

- `pytest -q` => `24 passed, 1 warning`
- `python -m py_compile app/frontend/streamlit_app.py app/providers/openai_client.py app/providers/gemini_client.py app/parsers/valuecell_parser.py` => `pass`
