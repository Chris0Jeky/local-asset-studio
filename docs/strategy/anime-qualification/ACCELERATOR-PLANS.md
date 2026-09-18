# Keep acceleration separate from generic style experiments

Implementation slice under #552/#144. The supplied research distinguishes Anima Base, Aesthetic,
standalone Turbo and Base plus a turbo adapter (pp. 6, 9-11). This change fixes an existing planner
boundary; it does not qualify a new schedule or model.

## Behaviour

`app/settings_planner.py` uses the existing settings KB's exact filename-to-role entries. A selected
`role: accelerator` is not a style slider. Generic family grids withhold its strength axis, including when
it is off, so a sweep cannot turn it on without the corresponding schedule. When its effective strength
is anything other than finite zero, the generic steps, CFG, sampler, scheduler and denoise axes are
also withheld. Unknown or negative strength does not prove inactivity. Primary and companion aliases
that write those same inputs are withheld too. A primary default alone cannot prove a companion
strength is zero; an explicit zero control edit writes all its bindings and can establish inactivity.

The current control snapshot wins over authored defaults. `Production.plan` supplies that snapshot to
the same planner it uses to produce variants. This fixes the mismatch where displayed axes could differ
from the actual grid after a filename or strength change.

Remix varies only the remaining active non-accelerator slots. Selected accelerator filenames and
strengths are preserved, including single-binding defaults omitted from the caller's snapshot. A missing
strength spanning multiple inputs requires an explicit value before remixing, so the primary default
cannot silently overwrite a different companion default. Missing or nonfinite accelerator strengths
also refuse, including companion-only slots, rather than contributing a fabricated zero. Preserved strengths contribute
to the existing total-strength warning. The explanation states what was held. An accelerator-only
selection has no style remix and returns an actionable refusal, rather than reweighting it or inventing
an alternative schedule.

Anima's generic step axis is now 20/30, not 8/20/30. The eight-step Base-plus-turbo starting point remains
in the existing `anima-turbo-authored-schedule` resource-scoped claim with its exact Base/LoRA targets
and active-accelerator condition. That claim remains authored guidance, not a newly verified source
recommendation. Existing graph defaults, recipes, manual comparisons and generation settings are
unchanged. Disabling an accelerator explicitly does not itself repair the rest of a user's schedule.

## Limits

This is a conservative hold based on declared KB roles. It is not a complete compatibility engine,
loaded-file hash attestation or automatic schedule repair. Renamed/unknown files and baked-in
acceleration without a declared LoRA role cannot be classified by this slice. Manual controls remain
available through their existing validation and review path. Neither a plan nor its explanation grants
execution authority, artistic acceptance or a model-install permission.

## Verification

`tests/test_settings_accelerators.py` exercises effective overrides, zero versus unknown strength,
sixth/companion slots, alias writes, immutability, retained defaults, warning accounting and the real
Anima knowledge entry. `tests/test_production.py` drives the actual planner through the configured
Studio fixture and checks exact filesystem retention, empty jobs/queue and no comparison reservation.

Run:

```sh
python -m unittest discover -s tests -p 'test_settings_*.py' -v
python -m unittest discover -s tests -p 'test_production.py' -v
python scripts/validate-repo.py
```

The initial regressions fail on the old planner; the alias regression also failed before the physical
binding hold. Exact-head local and hosted evidence is recorded on the PR. No GPU, new image,
Windows-runtime performance or owner-art claim follows from these software checks.
