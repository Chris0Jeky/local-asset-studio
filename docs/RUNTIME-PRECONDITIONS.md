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
itself does not.

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
| `C:/AI/Start-ComfyUI.ps1` (`-ArgumentsFile`, measured reserve; current since 23 September 2026, §8) | `ac8b40b650cb58838fcb9c8c10095880f09dad12112b30f74c984ecec3566d36` |
| `C:/AI/Start-ComfyUI.ps1.bak-20260923-reserve06` (reserve 0.6, 12-22 September) | `0c3fbc95bcb27444797eeffe08bb4047029a55f1ad352a9f979ed26bf8ea969e` |
| `C:/AI/Start-ComfyUI.ps1.bak-20260912-reserve2` (reserve 2, original) | `526fcda531f6d7aded268e9f69ad3fa1bc643d05f7e74e65f5b32f902ddc604c` |

To revert, with the ComfyUI queue empty and its process stopped, copy the backup back over the
launcher and re-check the hash:

```powershell
Copy-Item "C:/AI/Start-ComfyUI.ps1.bak-20260912-reserve2" "C:/AI/Start-ComfyUI.ps1" -Force
Get-FileHash "C:/AI/Start-ComfyUI.ps1" -Algorithm SHA256
```

Reverting the launcher alone leaves `app/backends.py` at 0.6; revert both or neither. The change is
also logged in [`runtime-patches/README.md`](../runtime-patches/README.md).

The two argument lists are **not** otherwise identical, and this predates the reserve change: the
launcher (and its backup) end with `--enable-manager`, while `BackendManager.primary_argv` does not
pass it. A Studio-started primary backend therefore runs without ComfyUI-Manager; a launcher-started
one runs with it. Reconciling that is a separate decision, not part of this change.

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
`experiments/curated/qwen-image-21-20260922/bench.json`): 17.7 s/step at the default reserve with
fast-disk loading, 12.5 s/step without fast-disk, with the ComfyUI process at 15,881 MB dedicated plus
1,537 MB **shared**; one step in eight completed in under a second, the rest waited on paging.
With `--reserve-vram 3` ComfyUI unloaded more of the text encoder, the process sat at 10,658 MB
dedicated / 78 MB shared, and the same steps ran at **0.68 s/step** (1.47 it/s) — 18-26x faster.
The primary's Krea 2 fp8 route (13.1 GB of diffusion weights) was recorded at 941-986 s for 15 steps
(`docs/ANIME-FANTASY-ATELIER.md`), the same shape.

**What changed** (PR for this section):

- `app/gpu_memory.py` reads the per-process counters through PDH (no subprocess) and sizes a launch
  reserve as *everything other processes hold on the discrete adapter + ComfyUI's own 0.7 GiB Windows
  margin*, rounded up to 0.1 GiB, clamped to 0.6-6.0 GiB; if the counters cannot be read it uses
  4.0 GiB. `BackendManager.primary_argv` uses it for every Studio launch of the primary backend
  (switch and recovery) and records the decision (`last_launch_reserve` in the backend snapshot,
  `launch_reserve` on the switch operation). Config `primary_reserve_vram` pins a number instead.
- `scripts/Start-Studio.ps1` no longer starts a different runtime from the Studio's own launcher: it
  writes `scripts/primary-comfy-args.py`'s output (`BackendManager.primary_argv`, so the measured
  reserve and `--disable-pinned-memory` from config) to `.runtime/primary-comfy-args.json` and passes it
  to `C:/AI/Start-ComfyUI.ps1 -ArgumentsFile`. Before this, the startup script omitted
  `--disable-pinned-memory`, so a Studio started from the desktop shortcut pinned about 13 GB of host
  RAM (`Enabled pinned memory 12994.0` in `C:/AI/logs/20260922-231528-error.log`) although config asks
  for it off. Run without `-ArgumentsFile`, the launcher now defaults to `--reserve-vram 4
  --disable-pinned-memory` (and still `--enable-manager`, which the Studio's own path does not pass).
- Each job records the peak dedicated and shared memory of the ComfyUI process while it runs
  (`submissions[].gpu_memory`, sampled every 10 s); a job that spilled more than 512 MB completes with
  the message *Complete, but slowly: GPU memory spilled … into system RAM*. `/api/health` carries the
  live `gpu_memory` reading.

**What it trades.** A larger reserve makes big models load partially (ComfyUI streams the remainder
from RAM each step) instead of spilling. That is what §2 set out to avoid at reserve 2, but a managed
partial load moves a known slice per step while a WDDM spill pages unpredictably; the Krea 2 before /
after measurement below is the exit test. The reserve is measured at launch; apps opened afterwards
(a browser with video, a game) can still push the card over, and the per-job spill message is how
that shows up. HiDream (8192) and H3 (8194) keep their fixed `--reserve-vram 2`.

To revert: copy `C:/AI/Start-ComfyUI.ps1.bak-20260923-reserve06` over the launcher (hash in §6) and set
`"primary_reserve_vram": 0.6` in `config/local.json`; revert both or neither.

