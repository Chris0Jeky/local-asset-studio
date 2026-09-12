# Reference atelier

Choose **Edit image** on a Workspace asset, or select a **Qwen Atelier** recipe.
The reference board supports one, two or three images. Assign each image a role,
describe what to carry over, and state which details to avoid copying. Typical
roles are identity, pose and style. Changing the number of references preserves
the brief, shared controls and existing images. Reordering changes the model's
image numbering as well as the displayed instructions.

Image 1 sets the output aspect ratio. Width is editable; height is computed by
ComfyUI. The VAE trims to its eight-pixel grid. Other images use Qwen's native
encoder preprocessing. **Preview resolved recipe** shows these choices and the
complete graph without submitting work. Guidance expresses intent; it does not
lock pixels, guarantee anatomical accuracy or turn a sketch into a pose-control
network.

Each run and saved setup retains reference roles, guidance, filenames, SHA-256
hashes, dimensions and primary resize metadata. Original uploaded bytes live in
the local workspace. Missing or changed references must be reattached; Studio
keeps the rest of the recipe. Exported recipes can be checked against the current
template before loading. The current three graphs derive from the reference
factory merged in PR #20 and use the existing Qwen Edit 2511 Q4, matching encoder,
VAE and four-step Lightning adapter.

Run small comparisons first. Keep identity and pose fixed while changing only
the style reference or seed. Saved execution evidence is separate from your
decision to accept an image.
