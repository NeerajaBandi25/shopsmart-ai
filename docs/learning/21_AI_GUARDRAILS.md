# 21. AI guardrails

## What and why

Guardrails define where untrusted text may influence a response. They prevent prompt injection from changing tool policy and preserve the backend as the commerce authority.

## Flow and files

Input checks reject direct secret extraction, policy override, arbitrary SQL and cross-shopper requests. Every provider tool must be allowlisted, parsed by a strict schema and executed against current-user services. Retrieved policy is treated as data and screened before synthesis. Final commerce claims refer to current tool results. Prompt, guardrail and tool schema versions are recorded with the assistant trace.

## Security and failure modes

Unauthenticated identity is never taken from model arguments. Invalid tool input fails safely, mutations are bounded and duplicate mutation attempts are rejected. Public providers receive only reviewed bounded shopping intent and approved policy IDs; private cart/order calls stay on the deterministic path unless an explicit deployment policy allows them. Provider failure returns a safe fallback.

## How to test and debug

Run AI security, provider-tool, commerce assistant, adversarial evaluation and browser tests. Confirm that malformed IDs, unapproved tools, cross-user order IDs and malicious retrieved instructions cannot execute actions. Review the normalized decision trace; do not store secrets or private prompt bodies.

## Interview explanation

“We put a typed authorization boundary between model proposals and every action. Retrieval evidence never grants permissions, and final commerce facts are validated by services.”
