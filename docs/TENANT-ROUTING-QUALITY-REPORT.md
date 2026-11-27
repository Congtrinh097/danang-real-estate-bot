# Tenant Routing and Security Evidence

## Scope

This evidence uses the production deterministic tenant classifier offline. It
does not call an LLM, external embedding service, database, or ticket provider.
The reproducible command is:

```bash
PYTHONPATH=backend TENANT_STORAGE_MODE=memory \
  backend/.venv/bin/python scripts/tenant_quality_report.py
```

Selected routing cases are regression-tested by
`tests/test_tenant_quality_and_security.py`; the command above scores all 10.

Latest baseline: 10/10 intent classifications correct (accuracy 1.0000) and
10/10 urgency classifications correct (accuracy 1.0000). Per-label precision
and recall are also 1.0000 for this curated set.

## Acceptance baseline

The report emits accuracy, precision, recall, per-label support, and every
prediction for the labeled set. A change to keywords or urgency rules should
regenerate this document's evidence and review false positives/negatives.

The security regression cases verify that prompt-injection wording remains
ordinary untrusted tenant text, does not become an instruction to the system,
and that PII is removed from trace-safe input. Pydantic length validation also
rejects oversized payloads before ticket processing.

## Known limitation

This is a curated regression set, not a production prevalence estimate. The
next evidence upgrade is to add anonymized labeled examples from real support
traffic and compare the report by channel and property type.
