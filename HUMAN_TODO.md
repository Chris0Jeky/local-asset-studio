# Creative choices

No human setup action is required on the configured PC once launcher validation is complete. These are optional choices, not inferred approvals:

- [ ] Choose your preferred pixel-art result after the first LoRA comparison.
- [ ] Pick one real game or product brief for a focused production pack.
- [ ] Decide which results are good enough to curate; successful execution alone is not art approval.

The repository defaults to private. Public visibility has not been requested.

## Anime & fantasy atelier — open items

**q-1 — install the koukouya Krea 2 style LoRA (human-only; needs your civitai account).**
`krea2_koukouya_sytle_c1-st3000.safetensors` is the one adapter the owner's target recipe names that is
not installed. Civitai's metadata API is reachable without credentials, but the download requires a
personal API key tied to your account, so an agent cannot fetch it for you.

1. Sign in at civitai.com and mint a key under **Account settings → API Keys** (`civitai.com/user/account`).
2. Set it in your own shell only, as the environment variable `CIVITAI_API_TOKEN`. Do not put it in
   `config/local.json`, in a committed file, or on a command line — `scripts/civitai-fetch.py` reads
   the env var and never accepts, prints or stores the token.
3. Run `python scripts/civitai-fetch.py --version-id <version id of the koukouya file>`. It resolves the
   filename and sha256 from the API, writes into the configured ComfyUI `models/loras/`, appends a
   receipt to `.runtime/downloads/receipts.json` and prints a `models/library.json` entry stub.
4. Paste the stub into `models/library.json` (or ask an agent to), then restart the Studio so the
   installed-LoRA list refreshes.
5. Alternative: download it in the browser and run `python scripts/intake-downloads.py`, which sorts it
   into the right folder by safetensors header and writes the same receipt.

Until then the atelier guide lists koukouya as **not installed**, and any recipe that names it is
reported as unavailable rather than failing at submission. Its author documents 1280×1856 or
1536×1536, weight 1.0, `er_sde`/`simple`, 8–10 steps.

**q-2 — creative review of the atelier results (human-only; subjective).**
The new Krea 2 and SDXL anime presets were each executed once on 12 September 2026 (six presets are now
`verified: true`; images and prompt IDs in `experiments/curated/anime-fantasy-atelier/`). Execution is not art
approval. Decide, after looking at the actual outputs:

- which of the LoRA stacks (Niji Sweet Spot + TextFusion, NIJISIS painterly, the oil/watercolour fal
  styles) matches the look you want, and at which strengths;
- whether the 15-step target recipe is worth roughly sixteen minutes per image (measured 941 s), or whether
  the 4-step distill LoRA (271 s, comparable quality in the probes) is the everyday path;
- which recipes deserve to be curated into `experiments/curated/`, and which presets may have
  `verified` flipped to `true` on the strength of a run you inspected.

Successful execution is not art approval, and it is not licence clearance either. Third-party LoRA
terms are recorded in `models/library.json`, not cleared.

## Recorded owner decisions

Recorded owner decisions, 11 September 2026: use free alternatives to NIJISIS
instead of spending Buzz; MiniMax H3 is being used from an eligible territory.
These decisions do not approve the generated art. The Workflow Lab expansion
requires no additional disk space at the current installed footprint.

**Superseded, 12 September 2026:** the owner downloaded the NIJISIS Krea 2 LoRA
(`NIJISIS_KREA_2_krea2_3274861_epoch_8.safetensors`, civitai model 2863875 version 3302337) and spent
the Buzz for it. The 11 September "use free alternatives instead of spending Buzz" note no longer
applies to this file; the free Comfy-Org and fal style adapters remain installed and in use alongside
it. Recorded from the owner's statement, not inferred from a download receipt. The other decisions
above stand.
