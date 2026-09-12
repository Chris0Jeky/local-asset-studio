# Reference atelier

Choose **Edit image** on a Workspace asset, or select a **Qwen Atelier** recipe.
The reference board supports one, two or three images. Assign each image a role,
describe what to carry over, and state which details to avoid copying. Typical
roles are identity, pose and style. Changing the number of references preserves
the brief, shared controls and existing images. Reordering changes the model's
image numbering as well as the displayed instructions.

The canvas is independent of the references. Width and height are both editable,
default to 832x1248 and must be multiples of 16 within roughly one megapixel.
Every reference — not only the first — is scaled to 1.0 MP with its aspect
preserved before either encoder branch sees it, so no reference sets the output
size and none is silently shrunk. The catalog's `max_reference_pixels` caps that
authored per-slot target, which is the number the compiler checks; the resized and
VAE sizes it records are the node's and the encoder's own rounded results and can
land a fraction of a percent either side of it. The prompt says **Picture 1/2/3** because
`TextEncodeQwenImageEditPlus` injects exactly those tokens. **Preview resolved
recipe** shows these choices and the complete graph without submitting work.
Guidance expresses intent; it does not lock pixels, guarantee anatomical accuracy
or turn a sketch into a pose-control network.

Each run and saved setup retains reference roles, guidance, filenames, SHA-256
hashes, dimensions and per-slot resize metadata. Original uploaded bytes live in
the local workspace. Missing or changed references must be reattached; Studio
keeps the rest of the recipe. Exported recipes can be checked against the current
template before loading. The current three graphs derive from the reference
factory merged in PR #20 and use the existing Qwen Edit 2511 Q4, matching encoder,
VAE and four-step Lightning adapter. Their geometry was rebuilt for issue #21;
`scripts/build-reference-recipes.py` holds the transform and is the only thing
that should regenerate them.

Run small comparisons first. Keep identity and pose fixed while changing only
the style reference or seed. Saved execution evidence is separate from your
decision to accept an image.
