# Representative examples, not decorative thumbnails

Implementation owner: #143, building on #10/#14/#36. This is an experiment
protocol, not an executed benchmark or authorization to spend a new budget.

## Initial evidence

The first index references two existing local files: `witch-nijisis-baseline.jpg`
and `krea-target-stack-koukouya.jpg` under `examples/anime-fantasy-atelier/`.
Their prompt IDs and receipt paths are retained in `bundle-showcase.json`.
They are historical selected trials; the first has a recorded original hash and
an owner "potential but imperfect" judgment. Neither is advertised as a new
controlled study, a guaranteed result or a finished asset. Existing owner
choices in HUMAN_TODO.md are unchanged.

The superficially similar `witch-target-stack-4step` is deliberately not used as
an exact illustration of the current `krea-4step-audition` recipe: the recorded
trial used a different resolution. A shared family/adapter name is
not enough to attach an exact-result badge.

## First bounded portfolio

Freeze one appropriate original-character bundle and three briefs before
rendering: a portrait showing facial/cloth detail; a full-body pose with visible
hands and a held prop; an environment testing illumination, depth and texture.
Use two seeds and two valid conditions per brief: baseline versus the selected
adapter stack. That is **12 image-producing attempts**, not twelve successful
outputs plus free retries. Required accelerators cannot simply be removed while
keeping an invalid schedule; choose and document a supported comparator.

Use the same native model/runtime, canvas and brief across a paired comparison
except the declared intervention. When an adapter also requires trigger words,
label the experiment as a compound trigger-plus-adapter change. Do not claim
it isolates weights alone. Record failures, response uncertainty, cancellations
and image-producing warmups under the same budget accounting. Repairs need an
explicit additional allowance and remain distinguishable from primary results.

For a specialist style, replace a generic brief with a task exposing its claimed
strength: a material close-up for brush texture, an architectural scene for line
work, a held object for anatomical/contact behavior, or a final-scale icon for
pixel readability. Keep at least one difficult/held-out case. Multi-adapter
attribution requires separate one-change studies; a whole-stack comparison does
not explain which adapter contributed which effect.

## Each example's record

Retain the original artifact, thumbnail/crop derivative hashes, recipe revision,
full positive/negative text, resolved wildcards, seed, settings, references and
transforms, native graph fingerprint, model/encoder/VAE/adapter identifiers and
hashes where known, node/runtime identities, prompt/job IDs, and actual timings.
Record cleanup and selection separately. Unknown measurements are null, not
zero. Similar integer seeds across unrelated families do not establish equal
noise or an equal-compute comparison.

Execution, visual review, owner acceptance, usage terms and export acceptance
are separate dimensions. Record the reviewer and reviewed version rather than
inferring approval from a successful run. A hash identifies bytes; it does not
authenticate a reviewer or establish artistic correctness.

## Card and comparison policy

Show one labelled representative selection, a small range of outcomes and at
least one revealing failure. Explain what to inspect: line edges, texture,
identity, small hands, prop contact or final-scale detail. Offer original/full
frame alongside crops; do not hide problems by cropping. Show selection policy
and attempted/usable/accepted counts. A pretty sample alone has no success rate.

Labels should distinguish a historical local trial, source-author example,
controlled comparison and illustrative UI material. A source example needs
attribution and its own available recipe, not a promise of local reproduction.
An image generated using another service must never become evidence for a local
bundle. No extra images are fetched, generated or hotlinked by this PR.

Only a complete effective-input identity match can earn an exact-current-recipe
label. Missing model/runtime pins mean unknown. Any effective edit invalidates
that match immediately while preserving the old image as historical evidence.
The first implementation conservatively uses only the historical label.

## Handoff and acceptance

Store runs and reviews in the existing Production/Workspace system. Generate
the showcase index from those records later; do not establish another evidence
database. Acceptance requires an owner-run portfolio, retained rejects, verified
preview links and browser tests for stale recipe changes and missing artifacts.
The current two preview links and synthetic browser fixture do not satisfy that
inference/representativeness milestone.
