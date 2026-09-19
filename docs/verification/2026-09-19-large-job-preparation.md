# Verification: measured owned-resource cleanup

Date: 2026-09-19

Base: `chatgpt/178-stage-aware-admission` at
`f822fba06d34c901e9ed878d837875e99d9530b4`.

## Deterministic checks

The focused suite is intentionally inert: fake queue, process and counter adapters are
used; no ComfyUI request, process termination, generation or cloud action occurs.

```text
PYTHONPATH=/tmp/las306:/tmp/las306/app:/tmp/las306/tests python -m unittest discover -s /tmp/las306/tests -v
24 tests passed

python -m py_compile \
  app/large_job_prep_common.py \
  app/large_job_prep_flow.py \
  app/large_job_prep_actions.py \
  app/large_job_prep_journal.py \
  app/large_job_prep_runtime.py \
  app/large_job_prep_lifecycle.py \
  app/large_job_preparation.py \
  studio_prompt/resource_cleanup_http.py \
  studio_prompt/reference_job_http.py \
  tests/large_job_prep_test_support.py \
  tests/test_large_job_preparation_policy.py \
  tests/test_large_job_preparation_lifecycle.py \
  tests/test_large_job_preparation_http.py
passed
```

Covered failures include unknown counters, missing exact profiles, active/uncertain
work, queue changes before and after `/free`, PID reuse, process-inspection denial,
HTTP success with no measured relief, dropped `/free` response, interrupted durable
intent, restart startup failure, newly online unrelated listeners and dropped launch
return reconciliation without a second launch.

The HTTP seam is composed through the existing reference-job extension chain and is
separately exercised for same-origin JSON dispatch, cross-origin and media-type refusal,
and bounded validation errors. Two mutation checks also proved that
the dry-run branch and PID/creation-identity recheck tests fail when those gates are
removed, then return to green after restoration.

## Deliberately unclaimed

- no full-repository suite;
- no GitHub Actions or Codex review evidence;
- no live Windows `/free`, termination or restart;
- no GPU generation, throughput improvement or universal memory threshold;
- no owner-approved proof receipt.

Those environment-dependent claims remain part of issue #306's local acceptance, not
something deterministic fixtures can manufacture.
