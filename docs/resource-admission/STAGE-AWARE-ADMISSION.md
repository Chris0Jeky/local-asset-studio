# Stage-aware resource admission

Studio can optionally refuse a generation after the backend queue becomes idle and immediately before it records submission intent. The gate is deliberately conservative and local.

A reservation is a **Studio concurrency contract**, not an operating-system or GPU allocation. External applications, allocator fragmentation, backend caches, and driver state can still change after a safe observation.

## What is identified

Every admission profile is bound to one SHA-256 identity containing:

- the exact submitted graph digest and resource-shaping inputs;
- model, VAE, text-encoder, LoRA, and ControlNet filename bindings;
- the selected backend profile digest;
- the observed ComfyUI and PyTorch versions;
- the preset identifier and the existing Wan decode projection, when applicable.

A graph, model, backend path/profile, runtime version, or relevant shape change produces a different identity. Profiles never fall back by family name.

## Decision states

`observed_safe`, `estimated_safe`, `unknown`, and `observed_unsafe` remain different facts. `unknown` is never converted into zero use or implicit safety. A profile with estimated requirements can only produce `estimated_safe`, even when current counters are observed.

Each stage declares independent headroom requirements for physical RAM, Windows commit, and VRAM. Studio evaluates every stage and reserves the maximum requirement in each dimension so two concurrent local preparers cannot both spend the same observed capacity.

## Configuration

The feature is off until exact local profiles have been recorded:

```json
{
  "enforce_stage_resource_admission": true,
  "resource_admission_device_index": 0,
  "resource_admission_profiles": {
    "<identity_sha256>": {
      "schema": "studio.resource-admission-profile/v1",
      "identity_sha256": "<identity_sha256>",
      "basis": "observed",
      "source": {
        "receipt_sha256": "<sha256 of the bounded source observation>",
        "kind": "job-resource-observation"
      },
      "stages": [
        {
          "name": "load_models",
          "physical_ram_bytes": 6442450944,
          "windows_commit_bytes": 19327352832,
          "vram_bytes": 12884901888
        },
        {
          "name": "sample",
          "physical_ram_bytes": 7516192768,
          "windows_commit_bytes": 24696061952,
          "vram_bytes": 16106127360
        },
        {
          "name": "decode",
          "physical_ram_bytes": 21474836480,
          "windows_commit_bytes": 37580963840,
          "vram_bytes": 8589934592
        }
      ]
    }
  }
}
```

The numbers above only illustrate the schema. They are not defaults or guarantees. First enable the gate with an empty profile map on a controlled test job. The refusal receipt records the exact identity. Build the profile only from bounded local observations for that identity and keep the source receipt hash.

## Lifecycle and recovery

The coordinator checks capacity only after the existing queue wait. Check and reservation are atomic inside Studio. A second batch member rechecks fresh counters without double-reserving its own job.

Definitively terminal jobs are released before the next admission and receive a release receipt. Jobs with a pending submission, an uncertain outcome, or unresolved prompt receipts retain their reservation. On restart, retained reservation receipts are reconstructed before new capacity is offered. Studio never replays a prompt merely to resolve capacity state.

Receipts are bounded and stored with the job. They include the exact identity, profile provenance, raw projected counters, other Studio reservations, every stage verdict, the selected decision, and the explicit non-guarantee.

## Relationship to existing guards

This does not replace `wan_capacity.enforce`, the Qwen/FLUX Windows-commit preflight, queue-idle proof, or submission-recovery rules. The Wan projection is included in the exact identity rather than copied into a second limit registry. Existing static guards still run and can be stricter.
