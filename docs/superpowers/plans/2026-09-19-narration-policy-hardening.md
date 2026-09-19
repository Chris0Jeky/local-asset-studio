# Narration Qualification Policy Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make narration-profile qualification evidence unambiguous, canonically policy-bound, producer-aware, and capable of proving calm-versus-spark delivery control without weakening the existing Spoken Brief contracts.

**Architecture:** Introduce one standard-library strict JSON decoder shared by profile and qualification inputs. Move candidate roles, producer-family expectations, measurement fields, long-form bounds, and contrast-pair identity into a checked-in qualification-policy document with its own revision and SHA-256; generated plans copy that policy but validators independently reload and compare the canonical source. Extend candidate reports with exact producer/runtime/reference provenance and a separate paired-delivery judgement, then enforce an independent producer-family comparison before acceptance.

**Tech Stack:** Python 3.12 standard library, JSON, existing Spoken Brief profile and qualification modules, unittest, GitHub Actions on Ubuntu and Windows.

**Spec:** GitHub issue #659, building on PR #653 and issue #637.

## Global Constraints

- Keep PR #653's profile catalogue, catalogue-bound local overlay, profile/delivery manifest binding, and pre-side-effect execution admission unchanged.
- Use no new runtime dependency and no model installation, download, synthesis, or network call.
- Reject duplicate JSON object keys and `NaN`, `Infinity`, and `-Infinity` before schema validation.
- Validate a qualification plan against the checked-in policy and evaluation set, not merely against its own recomputed hash.
- A local profile registry may overlay only the profile binding from the checked-in catalogue; it cannot redefine candidates, measurements, evaluation text, contrast pairing, or long-form requirements, and it is not treated as durable mutable CAS state.
- Require the measured Kokoro control, at least two measured non-control candidates, and at least one measured non-control producer family different from the selected candidate's family.
- Require exact candidate producer family, adapter, model revision, runtime SHA-256, configuration SHA-256, and reference evidence when the canonical policy says a reference is required.
- Represent delivery contrast as two stable line IDs with identical text and distinct `calm-brief` and `spark-recap` deliveries.
- Keep machine transcript evidence separate from owner identity-consistency and delivery-control findings.
- Preserve Python 3.12 compatibility and the repository's standard-library-first runtime.
- Do not commit model files, reference recordings, generated audio, local reports, or machine-specific absolute paths.

## Review Focus

- Duplicate nested keys must be rejected at decode time, not collapsed by `json.loads` before schema checks.
- A locally rehashed plan with one candidate removed, a bound relaxed, or an evaluation line changed must fail canonical-policy validation.
- Two Qwen variants plus the Kokoro control must not satisfy the independent producer-family gate when a Qwen route is selected.
- A candidate marked reference-required must fail when any reference audio hash, transcript hash, or permission scope is absent or malformed.
- Contrast evidence must name the canonical calm/spark line pair and remain separate from ASR substitutions, insertions, and deletions.

---

### Task 1: Add a shared strict bounded JSON decoder

**Files:**
- Create: `scripts/strict_json.py`
- Modify: `scripts/voice_profile.py`
- Modify: `scripts/voice_profile_qualification.py`
- Create: `tests/test_voice_profile_json.py`

**Interfaces:**
- Produces: `load_bounded_json(path: Path, *, label: str, maximum_bytes: int) -> object`
- Produces: `loads_strict(raw: bytes, *, label: str) -> object`
- Consumed by: profile catalogues, local registries, evaluation sets, qualification plans, and qualification reports.

- [ ] **Step 1: Write failing integration tests**

Add tests that write duplicate top-level and nested keys plus `NaN`, `Infinity`, and `-Infinity` into temporary catalogue, registry, plan, and report files. Assert `VoiceProfileError` or `QualificationError` contains `duplicate key` or `non-standard numeric constant` before any schema-specific error.

```python
def test_catalog_rejects_duplicate_nested_key_before_schema_validation(self):
    path.write_text('{"schema_version":1,"profiles":[{"id":"a","id":"b"}]}')
    with self.assertRaisesRegex(voice_profile.VoiceProfileError, 'duplicate key.*id'):
        voice_profile.load_catalog(path)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m unittest tests.test_voice_profile_json -v
```

Expected: duplicate-key cases reach later schema validation or parse successfully, and non-standard constants are accepted by the default decoder.

- [ ] **Step 3: Implement `strict_json.py`**

Use `json.loads` with an `object_pairs_hook` that raises on the second occurrence of a key and a `parse_constant` callback that rejects all non-standard constants. Decode UTF-8 strictly, reject empty/oversized/changing files, and return plain dictionaries/lists without executing imported data.

```python
def loads_strict(raw: bytes, *, label: str):
    def pairs_hook(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise StrictJsonError(f'{label} contains duplicate key {key!r}')
            result[key] = value
        return result
    def reject_constant(value):
        raise StrictJsonError(f'{label} contains non-standard numeric constant {value}')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs_hook,
                      parse_constant=reject_constant)
```

- [ ] **Step 4: Route both existing readers through the shared decoder**

Keep `voice_profile` and `voice_profile_qualification` exception types and user-facing labels by catching `StrictJsonError` and re-raising their domain errors. Remove duplicate byte-reading logic only where the shared function fully preserves existing bounds.

- [ ] **Step 5: Run focused suites and verify GREEN**

Run:

```bash
python -m unittest tests.test_voice_profile_json -v
python -m unittest discover -s tests -p "test_voice_profile*.py" -v
```

Expected: all strict-decoding and existing profile/qualification tests pass.

### Task 2: Add canonical qualification-policy identity

**Files:**
- Create: `research/voice-profiles/qualification-policy.json`
- Modify: `scripts/voice_profile_qualification.py`
- Modify: `tests/test_voice_profile_qualification.py`

**Interfaces:**
- Produces: `load_policy(path: Path | None = None) -> dict`
- Produces: `policy_digest(policy: dict) -> str`
- Extends plan: `policy: {id, revision, sha256}` plus exact canonical `candidates`, `measurement_fields`, `long_form`, and `delivery_contrast` projections.
- Extends `_validate_plan(plan)` to reload canonical policy/evaluation data and compare exact projections.

- [ ] **Step 1: Write failing canonical-policy tests**

Build a valid plan, mutate one candidate role, remove one measurement, alter one long-form bound, or change one evaluation line, then recompute `plan_sha256`. Each mutation must still fail with `canonical policy` or `canonical evaluation`.

```python
mutated = copy.deepcopy(plan)
mutated['long_form']['minimum_seconds'] = 1
mutated['plan_sha256'] = qualification.canonical_digest(
    {k: v for k, v in mutated.items() if k != 'plan_sha256'}
)
with self.assertRaisesRegex(qualification.QualificationError, 'canonical policy'):
    qualification.validate_report(mutated, accepted_report(plan))
```

Also prove a local profile registry changes the plan's profile binding while policy ID, revision, hash, candidates, and evaluation identity remain unchanged.

- [ ] **Step 2: Run focused test and verify RED**

Run:

```bash
python -m unittest tests.test_voice_profile_qualification.VoiceProfileQualificationTests.test_rehashed_plan_cannot_weaken_canonical_policy -v
```

Expected: the recomputed weakened plan is accepted by `_validate_plan` or fails only because the report references the old plan hash.

- [ ] **Step 3: Add the checked-in policy document**

The policy schema must contain exact fields:

```json
{
  "schema_version": 1,
  "id": "spoken-brief-qualification-policy-v1",
  "revision": 1,
  "candidates": [],
  "measurement_fields": [],
  "long_form": {},
  "delivery_contrast": {
    "calm_line_id": "contrast-calm",
    "spark_line_id": "contrast-spark"
  }
}
```

Populate candidates with stable IDs, roles, producer family, adapter, control/selectable flags, required status, and `reference_requirement` (`none` or `required`).

- [ ] **Step 4: Implement strict policy loading and exact plan comparison**

Validate the policy's exact schema, stable IDs, one control, at least one selectable custom route, unique candidates/measurements, valid long-form bounds, and distinct contrast IDs. `build_plan()` copies canonical projections and embeds only `{id, revision, sha256}` as policy identity. `_validate_plan()` independently reloads policy and evaluation files, verifies their hashes, and compares every projected field exactly.

- [ ] **Step 5: Run focused suites and verify GREEN**

Run:

```bash
python -m unittest tests.test_voice_profile_qualification -v
```

Expected: all deterministic-plan, canonical-policy, local-registry, and existing report tests pass.

### Task 3: Enforce producer provenance, independence, and paired delivery evidence

**Files:**
- Modify: `research/voice-profiles/evaluation-set.json`
- Modify: `research/voice-profiles/qualification-policy.json`
- Modify: `scripts/voice_profile_qualification.py`
- Modify: `tests/test_voice_profile_qualification.py`

**Interfaces:**
- Extends candidate report with:
  - `producer: {family, adapter, model_id, model_revision, runtime_sha256}`
  - `configuration_sha256`
  - `reference: null | {audio_sha256, transcript_sha256, permission_scope}`
  - `delivery_contrast: {calm_line_id, spark_line_id, identity_consistency, delivery_control, accepted, notes}`
- Produces acceptance summary fields: `selected_producer_family`, `independent_producer_families`, and retained reference hashes when applicable.

- [ ] **Step 1: Write failing provenance and independence tests**

Update the accepted fixture to measure Qwen reusable, IndexTTS, and Kokoro. Add tests proving:

```python
# Same-family Qwen design + Qwen reusable + Kokoro is insufficient.
report['candidates'] = [qwen_design, qwen_reusable, kokoro]
with self.assertRaisesRegex(qualification.QualificationError, 'independent producer family'):
    qualification.validate_report(plan, report)
```

Also reject policy/report family or adapter mismatches, malformed 40/64-character model revisions, malformed runtime hashes, missing required references, selected non-selectable candidates, and selected candidates whose contrast evidence is not accepted.

- [ ] **Step 2: Write failing contrast-pair tests**

Revise the evaluation set to include `contrast-calm` and `contrast-spark` with identical text and distinct delivery IDs. Assert plan construction rejects mismatched text, reversed/missing IDs, or equal delivery IDs. Assert each candidate report names exactly the canonical pair and retains separate identity-consistency and delivery-control ratings.

- [ ] **Step 3: Run focused tests and verify RED**

Run:

```bash
python -m unittest tests.test_voice_profile_qualification -v
```

Expected: new report fields are rejected as unexpected or the independence/contrast rules are not enforced.

- [ ] **Step 4: Implement exact producer/reference validation**

Require producer family and adapter to equal the canonical candidate definition. Require model revisions to be lowercase hexadecimal with exactly 40 or 64 characters, runtime/configuration hashes to be SHA-256, and reference evidence exactly when policy says `required`. Permission scope remains a stable non-path identifier.

- [ ] **Step 5: Implement independent-family and contrast acceptance gates**

For an accepted decision, require the selected candidate to be canonical, measured, non-control, selectable, long-form reviewed, and contrast-accepted. Require another measured non-control candidate whose producer family differs from the selected family. Keep ASR word-difference fields unchanged and independent from contrast owner judgements.

- [ ] **Step 6: Run all focused contracts and verify GREEN**

Run:

```bash
python -m unittest discover -s tests -p "test_voice_profile*.py" -v
python -m unittest discover -s tests -p "test_spoken_brief*.py" -v
python scripts/voice_profile_qualification.py --help
```

Expected: zero failures and no Spoken Brief recovery regression.

### Task 4: Document, audit, and verify the stacked PR

**Files:**
- Modify: `docs/spoken-briefs/VOICE-PROFILE.md`
- Modify: `research/voice-profiles/README.md`
- Modify: `.github/workflows/spoken-brief.yml` only if new paths are not already covered.

**Interfaces:**
- Documents: strict JSON boundary, canonical policy identity, producer-family independence, reference evidence, paired delivery contrast, and remaining human/workstation evidence.

- [ ] **Step 1: Update operator and evidence documentation**

Document that a plan hash is necessary but not sufficient, policy/evaluation sources are reloaded during validation, local registries cannot rewrite qualification policy, and accepted reports require an independent producer family plus exact reference provenance where applicable.

- [ ] **Step 2: Update CI path coverage if required**

Ensure `research/voice-profiles/**`, `scripts/strict_json.py`, qualification scripts, and all `test_voice_profile*.py` tests trigger the Ubuntu/Windows Spoken Brief matrix.

- [ ] **Step 3: Run exact-head focused verification**

Require on the final stacked-branch head:

```bash
python -m unittest discover -s tests -p "test_voice_profile*.py" -v
python -m unittest discover -s tests -p "test_spoken_brief*.py" -v
python scripts/voice_profile_qualification.py --help
python scripts/validate-repo.py
```

Expected: zero failures on Ubuntu and Windows for the focused workflow, plus a green repository-wide `Check studio` run.

- [ ] **Step 4: Perform final review and PR audit**

Confirm the PR targets `codex/narration-profile-contract`, contains only the #659 delta, has no model/audio/private evidence, has no unresolved review thread, and explicitly states that subjective voice quality remains unproven.
