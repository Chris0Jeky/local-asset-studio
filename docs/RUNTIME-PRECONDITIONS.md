# Runtime preconditions

What has to be true on the configured PC before a large Qwen or FLUX.2 job is submitted, and why.
Everything below was read from the installed ComfyUI source or measured from `C:/AI/logs` on
12 September 2026; the two places that rest on someone else's reading are labelled.

Installed runtime: ComfyUI 0.35.0, PyTorch 2.9.1+rocm7.2.1, ROCm `(7, 2)`, AMD arch `gfx1201`,
`Total VRAM 16304 MB, total RAM 32487 MB` (`C:/AI/logs/20260912-173147-error.log`).
Source root for every line number: `C:/AI/ComfyUI_windows_portable/ComfyUI`.

## 1. How much VRAM a model is allowed to occupy

`comfy/model_management.py`:

```
863  EXTRA_RESERVED_VRAM = 400 * 1024 * 1024
864  if WINDOWS:
865      EXTRA_RESERVED_VRAM = 600 * 1024 * 1024 #Windows is higher because of the shared vram issue
866      if total_vram > (15 * 1024):  # more extra reserved vram on 16GB+ cards
867          EXTRA_RESERVED_VRAM += 100 * 1024 * 1024
869  if args.reserve_vram is not None:
870      EXTRA_RESERVED_VRAM = args.reserve_vram * 1024 * 1024 * 1024
876  def minimum_inference_memory():
877      return (1024 * 1024 * 1024) * 0.8 + extra_reserved_memory()
```

So ComfyUI's own default on this 16,304 MB Windows card is **700 MiB** reserved, and `--reserve-vram`
replaces that number outright rather than adding to it. `--reserve-vram 0.6` is 614 MiB, i.e. about
86 MiB *below* the default — close to it, not equal to it.

`load_models_gpu` then computes the budget (`comfy/model_management.py`):

```
929      inference_memory = minimum_inference_memory()
930      extra_mem = max(inference_memory, memory_required + extra_reserved_memory())
932          minimum_memory_required = extra_mem
1009         current_free_mem = get_free_memory(torch_dev) + loaded_memory
1011         lowvram_model_memory = max(0, (current_free_mem - minimum_memory_required), min(current_free_mem * MIN_WEIGHT_MEMORY_RATIO, current_free_mem - minimum_inference_memory()))
1012         lowvram_model_memory = lowvram_model_memory - loaded_memory
```

With nothing already loaded on the device that reduces to

```
usable = free_vram - reserve - max(0.8 GiB, memory_required)
```

where `memory_required` is the sampler's working set for this canvas and reference count.
`MIN_WEIGHT_MEMORY_RATIO` is `0.4` on AMD (`model_management.py:458`), so the third branch only
matters when the first two are smaller than 40 % of free VRAM.

`usable` is the `lowvram_model_memory` figure that `ModelPatcher.load` spends module by module
(`comfy/model_patcher.py`):

```
1001                 lowvram_fits = mem_counter + module_mem + potential_offload < lowvram_model_memory
1093                 logging.info("loaded partially; {} {:.2f} MB loaded, {:.2f} MB offloaded, ...")
1096                 logging.info("loaded completely; {} {:.2f} MB loaded, full load: {}")
```

The first module that does not fit flips the whole load to partial. `partially_load` sets
`full_load = True` only when `model_loaded_weight_memory + extra_memory > model_size()`
(`model_patcher.py:1273-1274`). **The exit test for any reserve change is therefore the log line**:
`Requested to load QwenImage` followed by `loaded completely; … full load: True`.

## 2. Fit table — `qwen-image-edit-2511-Q4_K_M`

`models/diffusion_models/qwen-image-edit-2511-Q4_K_M.gguf`, 13,244,758,624 B on disk.
Measured resident size, identical in every log that loads it: **12,738.98 MB** — read either from a
full load or by adding a partial load's two halves (`20260911-171055-error.log:282` =
11,353.72 loaded + 1,385.26 offloaded; `20260912-043327-error.log:246` = 12,556.31 + 182.67).

| `usable` reported in the log | outcome | log |
| --- | --- | --- |
| 11,379.72 MB | `loaded partially`, 1,385.26 MB offloaded | `20260911-171055-error.log:282` |
| 12,584.27 MB | `loaded partially`, 182.67 MB offloaded | `20260912-043327-error.log:246` |
| 12,633.22 MB | `loaded partially`, 131.93 MB offloaded | `20260912-043327-error.log:274` |
| 12,751.49 MB | `loaded completely`, full load: True | `20260911-053144-error.log:311` |
| 12,888.02 / 12,899.61 MB | `loaded completely`, full load: True | `20260912-173147-error.log:109,127` |

The threshold sits between 12,633 and 12,751 MB of usable, i.e. the 12,738.98 MB of weights plus a
small offload buffer (25.35 MB in the partial-load lines above).

Applying the §1 formula with the measured `free_vram` range 15,630–16,137 MiB and the strategy's
`memory_required` of 1,749 MiB for 832×1216 with two references:

| `--reserve-vram` | usable @832×1216, 2 refs | Q4_K_M (needs ~12,764 MiB) |
| --- | --- | --- |
| 2 (previous) | 11,833–12,340 MiB | **partial load** |
| 0.6 (current) | 13,267–13,774 MiB | **full load**, ~0.5–1.0 GiB margin |

Two caveats, both measured:

- Reserve 2 was not a *guaranteed* partial. At 17:31 on 12 September, with an otherwise quiet
  desktop and a one-reference 512×1128 canvas, the same model fully loaded at 12,888 MB usable and
  then had 32.78 MB and 250.98 MB *unloaded* again to make room for the VAE
  (`20260912-173147-error.log:130,137`). Reserve 2 put this box on the boundary; whether a given job
  crossed it depended on how much VRAM the desktop happened to be holding.
- The 13,019 MiB requirement quoted in the 12 September research strategy is that same 12,738.98 MB
  plus a 280 MiB buffer allowance. The buffer actually reserved in the logs is 25.35 MB, so 13,019
  MiB is a conservative figure, **derived from the strategy's reading**, not measured here.

Out of scope: `scripts/h3-launch.py` and `scripts/hidream-launch.py` still pass `--reserve-vram 2`.
They are isolated backends on ports 8194 and 8192 with different residency profiles and no Qwen
route; changing them needs its own measurement.

## 3. The host-commit gate

VRAM is not the constraint that killed #77 and #89 — Windows commit is.

Measured on this box (`Get-CimInstance Win32_OperatingSystem`, 12 September 2026):

```powershell
Get-CimInstance Win32_OperatingSystem |
  Select-Object TotalVisibleMemorySize, FreePhysicalMemory, TotalVirtualMemorySize, FreeVirtualMemory, SizeStoredInPagingFiles
```

All values are in KiB. `SizeStoredInPagingFiles` read 41,943,040 (the fixed 40 GiB page file),
`TotalVirtualMemorySize` 75,209,264 — that is the **commit limit**, 77,014,286,336 B / 71.7 GiB, the
same number recorded in #77. `TotalVirtualMemorySize - FreeVirtualMemory` is committed bytes;
`FreeVirtualMemory` is the headroom. Per-process detail comes from the same counters ComfyUI does
not read: ComfyUI's caches key on physical RAM only.

**Rule: require at least 32 GiB of commit headroom before submitting any Qwen or FLUX.2 job at
1 MP or above, and record the reading in the run's evidence.** Sample it during the run, not only
before it. The number is a measured lower bound plus margin, not a derivation: the 12 September
`qwen-2ref` job (§7) started with 29 GB of headroom and still failed on a host allocation, and its
87 % reading was taken after the run, so the peak was not captured. Treat 29 GB as the floor the
failure proved insufficient; the earlier 20 GiB figure was below it and is withdrawn.

Set `enforce_host_commit_headroom` to `true` in the local configuration to enforce this rule on a
Windows host. The Studio reads `GetPerformanceInfo` commit counters rather than physical RAM,
rechecks after waiting for the queue and immediately before each `/prompt`, and records each pass
in the run state. It fails closed when that Windows reading is unavailable for a qualifying graph.
The gate performs no restart, `/free`, paging change, or other automatic memory action. Qwen Plus
reference scalers at 1 MP qualify even where the output canvas is smaller; a Qwen text encoder by
itself does not. Qwen-Image 2.1 (the isolated `qwen21` backend) qualifies at **any** size: its 7B model and 9.35 GB int8
text encoder left only 2.1-6.5 GiB of commit at 832 × 1248, and its edit graph has no width or height
(`docs/QWEN-IMAGE-21.md`).

What #77 measured (`C:/AI/character-lab/pilot-20260912/cache-release-{before,after}.json`):

| | committed | of limit | physical available |
| --- | --- | --- | --- |
| before `/free` | 74,920,812,544 B | **97 %** | 4,427 MB |
| after `/free` | 39,821,107,200 B | 51 % | 15,480 MB |

`/free` released 35,099,705,344 B — about 32.7 GiB — of host commit. `POST /free` with
`{"unload_models": true, "free_memory": true}` only sets two queue flags (`server.py:1192-1201`)
that the queue acts on between prompts; it never interrupts a running job. Caveat recorded in #77
and preserved here: the ComfyUI process also exited around that release, so the two are confounded
and the causal link is unproven. **`/free` is not reliable on its own** — after the 21:05 failure in
§7 it moved commit 87 % → 87 %, and only a process restart returned it. Prefer a restart when the
backend's idle commit is already large.

Why a partial load makes commit worse rather than better: ComfyUI-GGUF is reported to round-trip
each offloaded module in a way that breaks its file-backed mmap and turns it into private committed
host RAM. That chain is **reported by the 12 September strategy, not re-verified here** — but the
observable consequence (partial loads precede the commit spikes) is in the logs.

Raising the fixed 40 GiB page file would raise the limit directly. That is a system setting, it is
an owner decision (`HUMAN_TODO.md` q-4), and #77 explicitly says not to treat paging as a default
fix.

## 4. Flags

Verified against the installed source or this box's own logs:

| Flag / env | Verdict | Evidence |
| --- | --- | --- |
| `--use-pytorch-cross-attention` | **no-op** — already on | `model_management.py:531-537` enables it for `gfx1200/gfx1201` at ROCm ≥ 7.0 once `aotriton_supported()` passes; 23 of 23 startups in `C:/AI/logs` log `Using pytorch attention` |
| `--use-split-cross-attention`, `--use-quad-cross-attention` | **harmful** | both are the guard on that same `if` at `model_management.py:531`, so either one *disables* the AOTriton path |
| `--use-sage-attention`, `--use-flash-attention`, `torch.compile` | **unreachable** | 23 of 23 startups log `Found comfy_kitchen backend triton: {'available': False, … "ImportError: No module named 'triton'"}` |
| `--disable-smart-memory` | **wrong direction** | its own help text is "Force ComfyUI to agressively offload to regular ram" (`comfy/cli_args.py:191`) — that is more host commit, not less |
| `--vram-headroom`, DynamicVRAM | **inert** | `main.py:264-270` `dynamic_vram_supported()` needs `rocm_version >= (7, 14)` on AMD; this box logs `ROCm version: (7, 2)`, and `--vram-headroom` is only consumed inside that gated block |
| `--fast-disk` | **inert, and the surviving half is unhelpful** | DynamicVRAM is off (above); its one remaining effect makes `ensure_pin_budget` compare against the pinned cap instead of available RAM (`model_management.py:730-736`), i.e. pins *more* under low RAM |
| `COMFYUI_ENABLE_MIOPEN=1` | untested here, but the gate is real | `model_management.py:483-486` disables cuDNN unless the env var is `'1'`; every log line reads `Set: torch.backends.cudnn.enabled = False for better AMD performance.` |

Reported by the 12 September strategy, **unverified here**: `--fast cublas_ops` is dead
(NVIDIA-only package absent); bare `--fast` enables `autotune` at a ~135 s first-run cost;
`--cache-ram 2 6` loosens rather than tightens; `--disable-pinned-memory` cannot be #77's root cause
because `MAX_PINNED_MEMORY` is a cap and `hipHostRegister` does not raise commit;
`PYTORCH_TUNABLEOP_ENABLED=1` (~60 % claimed, no it/s published);
`TORCH_ROCM_FA_PREFER_CK=1` (AMD's +20 % figure is Linux, and CK SDPA is not supported on RDNA).

## 5. The crash class, and what to do about it

Issue #89 recorded four ComfyUI deaths on 12 September, all `0xC0000005` native access violations
during a **host-side tensor move**, in two shapes:

- mmap page-in on reload after the RAM-pressure cache evicted a checkpoint
  (`torch/storage.py:470 __getitem__` ← `comfy/utils.py:172 load_torch_file`), logs
  `20260912-173147-error.log` and `20260912-201600-error.log`;
- device→host `.to()` while partially unloading SDXL to make room for the VAE
  (`model_patcher.py:1216 partially_unload` ← `model_management.free_memory`), logs
  `20260912-202719-error.log` and `20260912-203031-error.log`.

Both shapes need a *partial* load or unload to exist in the first place, which is the same lever as
§1. `--disable-mmap` and `--cache-classic` were each tried once and each crashed.

**Rules.** Restore ComfyUI with `C:/AI/Start-ComfyUI.ps1` — never by hand-assembling flags, and
never by leaving an experimental flag in place. Never resubmit a job whose outcome is uncertain:
keep the prompt ID and the exact submitted graph, and record the crash. A lost prompt ID is evidence
lost, not a reason to run again.

## 6. The launcher is outside Git

`C:/AI/Start-ComfyUI.ps1` is the owner's file; the repository cannot version it. On 12 September
2026 its `--reserve-vram` token was changed from `2` to `0.6` to match `app/backends.py`, because a
change to only one of the two produces two different runtimes on the same port.

| file | SHA-256 |
| --- | --- |
| `C:/AI/Start-ComfyUI.ps1` (`-ArgumentsFile`; standalone reserve 0.6, pinned memory off; current, §8) | `aef83687601d517f9e61a62efdfb77a463467fc307fd4f0ad5d2c03d761aa54e` |
| `C:/AI/Start-ComfyUI.ps1.bak-20260923-reserve4` (`-ArgumentsFile`; standalone reserve 4, a few hours on 23 September) | `ac8b40b650cb58838fcb9c8c10095880f09dad12112b30f74c984ecec3566d36` |
| `C:/AI/Start-ComfyUI.ps1.bak-20260923-reserve06` (reserve 0.6, 12-22 September) | `0c3fbc95bcb27444797eeffe08bb4047029a55f1ad352a9f979ed26bf8ea969e` |
| `C:/AI/Start-ComfyUI.ps1.bak-20260912-reserve2` (reserve 2, original) | `526fcda531f6d7aded268e9f69ad3fa1bc643d05f7e74e65f5b32f902ddc604c` |

**Rollback (since 23 September 2026).** The current launcher already defaults to reserve 0.6, like the Studio.
To return to the pre-`-ArgumentsFile` launcher (pinned memory on again; the Krea 2 load that crashed in §8 ran with it on, though §5 records the same
`load_torch_file` access violation without pinned memory, so the two were seen together, not proven cause and effect), with
the ComfyUI queue empty and its process stopped:

```powershell
Copy-Item "C:/AI/Start-ComfyUI.ps1.bak-20260923-reserve06" "C:/AI/Start-ComfyUI.ps1" -Force
Get-FileHash "C:/AI/Start-ComfyUI.ps1" -Algorithm SHA256   # expect 0c3fbc95...
```

`config/local.json` needs no change (the Studio's default reserve is 0.6). *Historical:* the
reserve-2 original (`bak-20260912-reserve2`) predates the measured reserve and would need
`"primary_reserve_vram": 2`. The changes are also logged in [`runtime-patches/README.md`](../runtime-patches/README.md).

`--enable-manager` (ComfyUI-Manager) is on the desktop path only: the launcher's standalone default and
`scripts/primary-comfy-args.py` pass it, while the Studio's switch and recovery launches do not. The ownership
checks read only `--listen`/`--port`, so either kind of launch is adopted.

## 7. What the reserve change did and did not do

The narrow exit test is one line in a Qwen job's log:

```
Requested to load QwenImage
loaded completely; <usable> MB usable, 12738.98 MB loaded, full load: True
```

at 832×1216 or larger with two bound references. **That line has not been observed.** Until it is,
the reserve-0.6 row of the fit table in §2 is a prediction from the formula.

One Qwen job has run since the change, and it failed before reaching that line
(`C:/AI/logs/20260912-205922-error.log`, ComfyUI PID 4916 started 20:59:22 through the launcher with
`--reserve-vram 0.6`; Studio job `f29937b7-478f-4598-b756-661305d18ed9`, preset `qwen-2ref`,
512-wide, two canon references, prompt `0603c5be-0321-4325-ae5f-9a268b94d605`):

- The flag was demonstrably in effect. The loader reported `13870.19 MB usable` for the VAE and
  `14250.91 MB usable` for the text encoder (lines 100 and 105) against `12,436 / 12,817 MB` at
  reserve 2 in the earlier logs. Those figures are unreachable at reserve 2.
- `Requested to load QwenImage` (line 111) was followed immediately by
  `DefaultCPUAllocator: not enough memory: you tried to allocate 4377600 bytes`. **No
  `loaded completely` or `loaded partially` line for QwenImage was printed at all.** The traceback
  runs `load_models_gpu` → `free_memory` → `model_unload` → `detach` → `unpatch_model` →
  `self.model.to(device_to)` — the same device→host move as §5, failing on a *host* allocation of
  4.2 MB rather than on VRAM. `Prompt executed in 44.93 seconds`.
- The prompt worker thread then died with `TypeError: 'NoneType' object is not callable` in
  `cleanup_models_gc` → `LoadedModel.is_dead` (`model_management.py:844`, lines 196-212), and
  ComfyUI was cycled (next log `20260912-210954`).

**The measured conclusion: the reserve does not move the host-commit ceiling.** Host commit went
from 60 % (≈29 GB headroom) before submission to 87 % (≈9.2 GB headroom, 5.3 GB physical free) at
failure and stayed at 87 % with an empty queue. `POST /free` did **not** release it this time
(87 % → 87 %); a ComfyUI restart did, to ≈67 %. That is the opposite of the pilot's earlier
release in §3 — where the ComfyUI process also exited — and it is why §3's caveat matters.

Per-process attribution at that 87 %, recorded in #77's newest comments: idle ComfyUI PID 4916 held
**16.8 GB** of commit *after* `/free` (torch CPU allocations and the GGUF loader's staged buffers
survive an unload; only a restart returns them), 158 `node.exe` MCP processes held **10.7 GB**, all
process private commit summed to 47.4 GB, and roughly **15 GB** was non-process (kernel, GPU driver,
pinned host registrations). A Qwen 2511 edit adds ≈20 GB on top of a 45–50 GB desktop-plus-agents
baseline, against the ~73 GB limit of §3.

So the three levers that actually move this, in order: the page file (owner decision, `HUMAN_TODO.md`
q-4), fewer resident agent sessions and MCP stacks during Qwen or FLUX.2 work, and a ComfyUI restart
— not `/free` — before a heavy job whose backend already holds more than ~6 GB of idle commit.
Runtime flags do not move the ceiling; §4's verdicts stand, but none of them is a remedy for #77.

## 8. The WDDM spill and the measured reserve — 23 September 2026

**What was wrong.** ComfyUI sizes its loads from the free VRAM PyTorch reports, and on this Windows/ROCm
box that figure does not subtract what *other* processes hold (§2's measured `free_vram` of
15,630-16,137 MiB on a 16,304 MiB card already showed it). On 23 September the Windows
`GPU Process Memory` counters put dwm at 2,282-2,306 MB of dedicated VRAM and the other desktop apps
(ProtonVPN, ChatGPT, Explorer, WebView2, Radeon Software, Razer, Claude, csrss) at about 1 GB more.
A model ComfyUI logs as `loaded completely` can therefore exceed the physical card, and Windows
silently backs the overflow with shared system memory that every sampling step pages across PCIe.

**Measured on Qwen-Image 2.1** (isolated backend, same graph, 8 steps at 832x1248;
`experiments/curated/vram-spill-20260923/qwen21-bench.json`): 17.7 s/step at the default reserve with
fast-disk loading, 12.5 s/step without fast-disk, with the ComfyUI process at 15,881 MB dedicated plus
1,537 MB **shared**; one step in eight completed in under a second, the rest waited on paging.
With `--reserve-vram 3` ComfyUI unloaded more of the text encoder, the process sat at 10,658 MB
dedicated / 78 MB shared, and the same steps ran at **0.68 s/step** (1.47 it/s) — 18-26x faster.
The primary's Krea 2 fp8 route (13.1 GB of diffusion weights) was recorded at 941-986 s for 15 steps
(`docs/ANIME-FANTASY-ATELIER.md`), the same shape.

**What changed** (PR #845, then corrected the same night; see *Measured on the primary* below):

- `app/gpu_memory.py` reads the per-process counters through PDH (no subprocess) and can size a launch
  reserve as *everything other processes hold on the discrete adapter + ComfyUI's own 0.7 GiB Windows
  margin*, rounded up to 0.1 GiB, clamped to 0.6-6.0 GiB (4.0 GiB if the counters cannot be read).
  For the primary this is **opt-in** (`"primary_reserve_vram": "auto"`); the default stays a fixed 0.6.
  `BackendManager.primary_argv` records every launch decision (`last_launch_reserve` in the backend
  snapshot, `launch_reserve` on the switch operation).
- `scripts/Start-Studio.ps1` no longer starts a different runtime from the Studio's own launcher: it
  writes `scripts/primary-comfy-args.py`'s output (`BackendManager.primary_argv`, so the configured
  reserve, 0.6 by default, and `--disable-pinned-memory` from config) to `.runtime/primary-comfy-args.json` and passes it
  to `C:/AI/Start-ComfyUI.ps1 -ArgumentsFile`. Before this, the startup script omitted
  `--disable-pinned-memory`, so a Studio started from the desktop shortcut pinned about 13 GB of host
  RAM (`Enabled pinned memory 12994.0` in `C:/AI/logs/20260922-231528-error.log`) although config asks
  for it off. The desktop path keeps `--enable-manager` (ComfyUI-Manager), which the Studio's switch and
  recovery launches still do not pass; the ownership checks only read `--listen`/`--port`. Run without
  `-ArgumentsFile`, the launcher defaults to `--reserve-vram 0.6 --disable-pinned-memory --enable-manager`.
- Pinned host memory is not counted as a spill: the primary started with about 13 GB pinned read
  9,755 MB dedicated and 79 MB shared through the same counters.
- Each job records the peak dedicated and shared memory of the ComfyUI process while it runs
  (`submissions[].gpu_memory`; sampled every 0.5 s on its own thread since §10, every 10 s before, which missed most
  decode overflows), the largest other GPU holders at the worst moment (`top_holders`) and, after a spill, whether the
  shared memory drained within 3 s (`settled_shared_bytes`, `lingering`). A spill that drained completes with *Complete. GPU
  memory overflowed … while it ran*; only a lingering one says *Complete, but slowly* and suggests a restart. Both name the
  largest other holder. `/api/health` carries the live `gpu_memory` reading and `vram_guard` (§10).

**Measured on the primary: the measured reserve is the wrong default there.** Krea 2 fp8 (`krea-portrait`
graph unchanged, 768x1152, 8 steps, seed 2026091103; `experiments/curated/vram-spill-20260923/krea_bench.json`):

| primary launch | outcome | s/step | peak dedicated / shared |
| --- | --- | --- | --- |
| reserve 0.6, pinned memory **on** (desktop launcher before #845) | **access violation** in `load_torch_file` while loading the 13.1 GB model; no image | — | — |
| reserve 0.6, pinned memory off (Studio recovery launch) | `loaded completely`, 12,533 MB; prompt `e3cec74f`, 423.5 s | **35.4** | 14,119 / 474 MB |
| reserve 2.9 measured, pinned memory off (#845 default) | `loaded partially`, 410 MB offloaded, **53 lowvram LoRA patches**; prompt `b53ee807`, 836 s | 95.0 | 14,165 / 4,480 MB |

A reserve that forces a model with a LoRA into a partial load makes ComfyUI apply the LoRA per step to the
offloaded modules and still spill during decode: 2.7x slower. A 13.1 GB model cannot fit this card with the
desktop's VRAM in use either way; the real fix for Krea 2 is a smaller quantization, not a reserve. The
measured reserve remains the right tool where evicting a text encoder is enough to make the diffusion
model fit (Qwen-Image 2.1 above, measured with the benchmark's `--reserve-vram 3`); no shipped backend applies
it automatically yet (the isolated qwen21 backend is #739's pending branch). The per-job spill message still
reports every run that spills. HiDream (8192) and H3 (8194) keep their fixed `--reserve-vram 2`.

**Checkpoint switches spill even when every model fits (23 September 2026, evening).** SDXL jobs of about 30 s spilled
0, 3.7 and 6.0 GB (CSTati, WAI, CSTati) and 0, 3.7 and 5.6 GB (WAI, AniFox, YumeFlux) in one ComfyUI process each. Every
load logged `loaded completely` with 12.6-13.0 GB "usable", and `/system_stats` read 16,136 MB free on the 16,304 MB card
with the desktop holding ~3.3 GB: ComfyUI's figure ignores other processes, so when the next checkpoint loads it unloads only
part of the previous one (`Unloaded partially: 1469.43 MB freed, 2093.49 MB remains loaded`) and the residue plus the new
model overflows into shared memory. Runs that reuse one checkpoint stayed flat. Since then the Studio posts
`/free {"unload_models": true}` before a graph that drops a model the previous Studio graph loaded on the same process, or
when that idle process already spills, and waits for `torch_vram_total` to fall (`docs/OPERATIONS.md`). The same
three-checkpoint sequence in a fresh process then peaked at 0.16, 0.09 and 0.08 GB shared in 30.4, 29.3 and 31.8 s; each
unload took PyTorch's reservation from 3.9-4.2 GB to 0.08 GB in 1.0-1.6 s
(`experiments/curated/vram-spill-20260923/checkpoint-switch.json`). A reserve increase would also have forced the unload
but costs every large model a partial load (Krea above); the unload costs a switch nothing, because the new checkpoint loads
from disk either way. Not measured: Anima/Klein/Qwen switches and graphs whose own working set spills without a switch.

To opt the primary into the measured reserve anyway, set `"primary_reserve_vram": "auto"` in `config/local.json`
and restart through `Start Studio.cmd` (the desktop path reads the same setting through `scripts/primary-comfy-args.py`).


## 9. Studio and ComfyUI vanishing together with empty logs — 23 September 2026

**Not a crash.** On 23 September the Studio and ComfyUI disappeared together several times, sometimes before any job, with
a 0-byte Studio error log and a ComfyUI log that stops mid-stream with no shutdown line. Windows recorded no Application
Error 1000 and no WER report for `python.exe` in those windows, which a native access violation (§5) would have left.

**Cause: the job object of the agent shell that launched them.** Grok Build runs every command inside a Windows job object.
The three job objects `grok.exe` held after 20:30 read `LimitFlags 0x2000` — `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, with neither
`BREAKAWAY_OK` nor `SILENT_BREAKAWAY_OK` (read by duplicating its job handles and calling `QueryInformationJobObject`).
`Start-Process` children stay in their parent's job, so `Start-Studio.ps1` run from a Grok command put the Studio and
ComfyUI in that command's job (`IsProcessInJob` was true for both, and both parents had already exited). When Grok later closes
the handle, Windows terminates every member at once. Tonight's two unplanned deaths each followed the launching command by a
few minutes: task `…-19` ended 20:04:10 and the pair was alive at 20:07:47 and gone by 20:09:14; task `…-91` ended 20:24:51
and its pair (PIDs 2180 and 31676) was alive at 20:25:01 and gone by 20:31:36, with no stop command from any agent in between.
Earlier deaths blamed on the spill or on loading Anima fit the same shape and are not separately proven either way.

**Fix.** `scripts/Start-Studio.ps1` checks `IsProcessInJob` on itself. Inside a job it starts itself again through
WMI `Win32_Process.Create` (hidden window, `-Detached`), which creates the process in the same interactive session but
outside any job, waits for it, relays any error it threw (`.runtime/start-studio-detached-*.log`), and succeeds only when
`/api/identity` answers for this workspace. The copy's output is deliberately not redirected: capturing it pipes the nested
ComfyUI launcher, whose `Start-Process` child inherits the pipe and keeps it open, and the first version of this fix hung that
way from a Grok command. Verified afterwards from a headless `grok` call running `Start-Studio.ps1`: exit 0 in under a minute,
and after the `grok` process exited both ComfyUI and the Studio were still serving, with `IsProcessInJob` false for each. Outside a job nothing changes. Reproduced with a harness job carrying Grok's flags:
closing the handle killed the `Start-Process` child and left the `Win32_Process.Create` child running, and the in-job check
read true inside that job and false in a Claude Code shell.

**Which launch paths are in a job (read 23 September 2026, 22:30).** `explorer.exe` is in no job, so `Start Studio.cmd`
opened from Explorer never needs the relaunch. A PowerShell tab in Windows Terminal 1.18 reported `IsProcessInJob` false
(chain `python.exe` → `powershell.exe` → `WindowsTerminal.exe`). WebStorm's terminal (`OpenConsole.exe` under
`webstorm64.exe`) and Claude Code's own `claude.exe` processes are in jobs, so a launch from them takes the WMI path.

**What an agent should still do.** Start or restart the Studio only through `Start-Studio.ps1` (or `Start Studio.cmd`),
never by launching `app/server.py` or ComfyUI's `main.py` directly from an agent command: a direct launch stays in the job.
Deaths remain possible for other reasons; when one happens, check whether the launching command's task has ended before
reading it as a runtime failure.


## 10. The decode overflow and the VRAM guard — 23 September 2026, late evening

**What was left after §8's unload fix.** With the desktop holding more VRAM as the evening went on (dwm 2.3 GB, then
3.3, 5.6, 6.0 and 6.3 GB; all other processes together 8.0-8.5 GB), SDXL jobs still spilled. A probe that sampled the
ComfyUI process and every other GPU user every 0.25 s and lined the samples up with ComfyUI's log
(`experiments/curated/vram-spill-20260923/phase_probe.py`, results in `vram-guard-sdxl.json`) showed where: sampling ran at
8.6 GB dedicated with no spill and 4.3 it/s. At `Requested to load AutoencoderKL` ComfyUI unloaded only part of the
UNet (`Unloaded partially: 1341 MB freed, 3556 MB remains loaded`), because its free-VRAM figure ignores other processes.
The VAE decode (bf16, 832x1216) then overflowed **3.7-3.8 GB** into shared memory for about 3 s. The overflow drained
when the prompt finished, so this was not §8's residue that slows every later job. It did add seconds to every job. The
Studio's 10 s sampling saw 0.08 GB of it, which is why the receipts looked clean.

**The guard.** `runtime-patches/comfy-extensions/studio_vram_guard` is loaded into the Studio's primary launch through
`--extra-model-paths-config`. No file of the ComfyUI installation changes (`runtime-patches/README.md`). While
`comfy.model_management.free_memory` decides what to unload, `get_free_memory` subtracts the dedicated VRAM other
processes hold, read from the same Windows counters as `app/gpu_memory.py`. Evictions therefore make room that exists.
Whether a model loads completely or partially is decided exactly as before. That keeps §8's lesson: a truthful *load*
decision forced Krea 2 into a partial load with per-step LoRA patches (2.7x slower). The guard pins the two functions'
source hashes, stays off on any other ComfyUI version, and reports its state in the ComfyUI log, at `GET /studio/vram-guard`
and in `/api/health` (`vram_guard`). `"primary_vram_guard": false` launches without it.

**Measured, same desktop load (other processes 8.0-8.5 GB):**

| run | peak shared | time |
| --- | --- | --- |
| SDXL WAI → CSTati, no guard | 3.70 / 3.83 GB | 31.9 / 32.6 s |
| SDXL WAI → CSTati → WAI, guard | 0.16 / 0.15 / 0.08 GB | 34.4 (after the restart, from disk) / 26.2 / 28.3 s |
| Krea 2 fp8 `krea-portrait`, 8 steps, no guard (control, prompt `383c3ae9`) | 6,019 MB | 52.9 s/step, 557.7 s |
| Krea 2 fp8 `krea-portrait`, 8 steps, guard (prompt `a95ade87`) | 2,353 MB | 52.4 s/step, 528.1 s |

Both Krea runs logged `loaded completely … 12532.86 MB loaded, full load: True`: the guard did not bring back the partial
load. Before its decode, the control ran a partial unload with 128 lowvram patches (`10404.14 MB remains loaded`) and then
decoded with 2 GB "usable". With the guard, the decode had 11.4 GB and no patches. Krea's 52 s/step against §8's 35 s/step
is the desktop: 8.5 GB held elsewhere against about 3.3 GB then, with the same 12.5 GB model. It is not the guard. The
control shows the same rate. The Krea records are in `krea_bench.json`.

**Not measured:** Anima, Klein, Qwen and video graphs under the guard; a desktop that holds even more (the guard cannot
make a model that does not fit fit, it only stops evictions from being too small). **Residual:** dwm's VRAM grew all
evening and was not given back while the session ran. Signing out and back in (or a restart) resets it; the Studio now
names it in the spill message when it is the largest other holder.
