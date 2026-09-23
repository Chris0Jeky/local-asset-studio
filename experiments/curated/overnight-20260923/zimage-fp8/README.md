# Z-Image Turbo: fp8 build and the text encoder on the CPU — 23 September 2026 (overnight lab)

**Question.** The speed census measured the shipped `zimage` preset (bf16 diffusion model 11.7 GB, `qwen_3_4b` text encoder
7.7 GB, 1024², 8 steps) at 28.7 s/step and 308 s per image with the process in WDDM shared memory. Is the installed fp8 build
faster without a visible quality loss, and does the Krea finding (`../krea-gguf/`: keep the big text encoder off the GPU) apply?

**Method.** `ab_zimage.py`, straight to the primary ComfyUI 0.35.0 (`--reserve-vram 0.6 --disable-pinned-memory`), 06:23-06:54
local. The shipped `zimage` graph (res_multistep/simple, cfg 1, shift 3, tiled VAE decode) on the showcase suite's prose prompts
with fixed seeds. Only the diffusion file changes (`z-image-turbo_fp8_scaled_e4m3fn_KJ.safetensors`, 6.2 GB, civitai 2169712
version 2445746, SHA-256 `59610861…b3cf`, which matches the listing) and the encoder device (`CLIPLoader` `device: cpu`, marked
`-cpute`).
- **Configurations:** `fp8-cpute` on all seven cases; `fp8` (GPU encoder) and `bf16-cpute` on portrait, action and hands.
- **Timing:** node and step times from the websocket; GPU memory from the process timeline; commit from `GlobalMemoryStatusEx`.
- **Blind A/B:** `seal` shuffled the three configurations of each shared case, and all nine judgements were written before the
  key was read (`judgements.jsonl`).

Pictures of famous characters stay local: ComfyUI `output/Research/overnight-20260923/zimage-fp8/index.html`. The Git sheet
shows the original-character cases only.

## Results: speed

| configuration | runs | text encode s | KSampler s (s/step) | VAE decode s | whole prompt s | peak shared MB |
| --- | --- | --- | --- | --- | --- | --- |
| shipped `zimage` (bf16, GPU encoder), census | 1 | – | 246 incl. load (28.7) | 21 | **308** | 715 while sampling |
| `fp8`, GPU encoder | 3 | 0.6-16 | 8.8 on the first run, then **470-476 (58.6-59.7)** | 44-46 | 71, **532, 533** | 1951-2593 |
| `bf16-cpute` | 3 | 29-61 | 6.1-15.4 (0.71-1.03) | **32-34** | 69-147 | 1807 during decode |
| **`fp8-cpute`** | 7 | 29-65 | **5.8-6.2 (0.72-0.77)**, 14.9 on the first | **1.2-1.4** | **37-76** | **79 (no spill)** |

- **The same mechanism as Krea.** With the encoder on the GPU, ComfyUI kept about 7 GB of the 7.7 GB Qwen3-4B encoder resident
  next to the diffusion model. The process spilled 2-2.6 GB into shared memory, and sampling fell to about 59 s/step: the fp8
  action and hands runs took 532-533 s. With `device: cpu` nothing spills.
- **fp8 against bf16, both with the CPU encoder.** Sampling is similar (0.72 against 0.71-1.03 s/step). The bf16 model stays
  resident during the VAE decode, though, and the decode spills 1.8 GB and takes 32-34 s instead of 1.2-1.4 s.
- **Where the time goes on `fp8-cpute`.** The CPU encode of the 4B encoder is most of it, at 29-65 s per new prompt. A seed audition
  with the same text reuses the cached conditioning; that was not timed separately here, since the Krea run already showed the
  pattern (`../krea-gguf/`: 38 s against 77-101 s).
- **Host commit.** It was 53-61 % before the fp8-cpute runs and peaked at 62.0-70.2 %. For the bf16-cpute runs it was 44-68 %
  before and peaked at 69.9-81.9 %. The encoder in RAM is visible, but it stayed below the commit ceiling.

## Results: quality (blind)

| case | configurations (unblinded) | verdicts |
| --- | --- | --- |
| portrait (Makima) | fp8-cpute / fp8 / bf16-cpute | keep ×3 |
| action (2B) | bf16-cpute / fp8 / fp8-cpute | keep ×3 |
| hands (original alchemist) | bf16-cpute / fp8-cpute / fp8 | keep ×3 |

**A tie on every case.** The three pictures of a case share composition, pose and palette, and differ only in small details: a
softer smile, the flask's reflection. Every hand checked at full resolution is five-fingered and clean. The worst defects are
shared: Makima's eyes lack her rings, and 2B's skirt-flare framing. The other four fp8-cpute suite cases (duo, environment,
pinup-swim, glamour) are in the local gallery; they were not A/B-compared.

## Proposal (this PR)

- **Pin** `z-image-turbo_fp8_scaled_e4m3fn_KJ.safetensors` in `models/library.json`: civitai 2169712 / 2445746, SHA-256 and
  bytes as installed, civitai flags Image/RentCivit/Rent/Sell/SellMerge, base model Apache-2.0.
- **Add a preset** `zimage-fast`: the shipped `zimage` graph with the fp8 file and `CLIPLoader` `device: cpu`. The bindings and
  variants are the same, and it is `verified: false` until a Studio proof. The shipped `zimage` is unchanged.

## Not verified

- Three blind cases. One observation per timing row.
- The cached-text timing was not measured for Z-Image.
- The fp8 build is a third-party quantization (SupernovaTech). Its hash matches the civitai listing, which proves the bytes,
  not the creator.
- No art acceptance or licence clearance.
