# PROMPTS

Prompt version: `v2` (rule-based + risk grading + few-shot examples)

## Planner Prompt

File: `app/prompts/planner_system.md`

Requirements:

- Output valid JSON object.
- Include keys:
  - `objective`
  - `constraints`
  - `required_outputs`
  - `steps`
  - `risk_flags`
  - `needs_review`
- Include investment research guardrails (research only, no trade execution claims).
- Include risk categories and downstream Green/Yellow/Red framing guidance.
- Include few-shot examples for stable structured output.

## Reviewer Prompt

File: `app/prompts/reviewer_system.md`

Requirements:

- Review planner output only.
- Output valid JSON object with:
  - `approved`
  - `missing_items`
  - `ambiguities`
  - `risk_flags`
  - `suggested_changes`
- Apply approval gating for ambiguity/completeness/risk coverage.
- Include actionable suggested changes (imperative wording).
- Include few-shot examples for pass/fail review cases.

## Finalizer Prompt

File: `app/prompts/finalizer_system.md`

Requirements:

- Combine planner/reviewer outputs.
- Output valid JSON object with:
  - `target`
  - `valuecell_prompt`
  - `expected_sections`
  - `browser_steps`
  - `timeout_seconds`
- Force `target=valuecell_web` and minimal browser step sequence.
- Force `expected_sections` to include `summary`, `table`, `risk_rating`.
- Encode risk-rating instruction (Green/Yellow/Red) inside `valuecell_prompt`.

## Committee Prompts

Files:

- `app/prompts/committee_draft_system.md`
- `app/prompts/committee_review_system.md`
- `app/prompts/committee_finalize_system.md`

Requirements:

- Committee chain order:
  - GPT-5.4 draft
  - Gemini 3.1 Pro review
  - GPT-5.4 finalize
- Finalizer output must include:
  - `committee_summary`
  - `committee_actions`
  - `detailed_report` (portfolio risk diagnosis execution report JSON)
- Finalizer must preserve key numbers from source material when available.
- If evidence is missing, finalizer must explicitly state:
  - `材料未提供，暂无法确认`
- Finalizer report must provide 5-trading-day action framework and trigger logic.
