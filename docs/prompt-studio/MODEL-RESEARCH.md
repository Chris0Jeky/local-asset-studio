# Model dialects and local helper research

Reviewed 11 September 2026. The [source directory](../../research/prompt-studio/sources.json) links primary documentation. Recommendations are proposed experiments on the recorded RX9070XT16GB/32GB Windows workstation, not locally measured quality or speed rankings.

## Model-specific prompting is a real interface problem

[Animagine XL4](https://huggingface.co/cagliostrolab/animagine-xl-4.0) documents ordered tag-style prompting. Its conventions must not be indiscriminately mixed with Pony score tags or arbitrary SDXL derivatives. The shipped compiler emits only approved tags and explicitly asks for semantic coverage review; it does not invent artist names or quality tokens.

[FLUX2 documentation](https://help.bfl.ai/articles/7734566352-does-flux-2-support-negative-prompting) says negative prompting is unsupported. Exclusions should become reviewed affirmative alternatives, not be silently dropped or mechanically negated. The delivered profile blocks an unresolved avoidance list. A backend input named `negative` is not sufficient evidence of effective negative conditioning; CFG-one/distilled paths also need graph-specific review.

[Wan2.2](https://github.com/Wan-Video/Wan2.2) already includes prompt extension with Qwen options. Reuse a pinned implementation when appropriate rather than assuming prompt expansion is unexplored. For an accepted first frame, concentrate on action, camera movement and invariants; duration and frame-grid rules belong to the selected graph.

[Qwen Edit2511](https://huggingface.co/Qwen/Qwen-Image-Edit-2511) and the [native Comfy node](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_qwen.py) motivate explicit reference-slot roles. The included profile is scoped to the three-image `TextEncodeQwenImageEditPlus` graph, not every hosted Qwen interface. A prompt description does not guarantee disentangled identity/style/pose transfer.

[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) exposes literal speech separately from voice-design instruction and language. The compiler preserves exact words; it does not put acting directions into the spoken text. [ACE-Step1.5](https://ace-step.github.io/ACE-Step-1.5/en/INFERENCE) has caption, lyrics and musical metadata fields with documented limits. Keep those separate and map meter explicitly. TRELLIS2's image-input route is a useful counterexample: no invented text prompt can replace its approved image input.

## Recommended local helper portfolio

| Candidate | Proposed role | Decision boundary |
|---|---|---|
| [Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B) | First text/vision analyst for brief clarification and reference facets | Trial a supported quantized bundle and bounded non-thinking structured output. No local performance claim. |
| [Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B) | Quality comparison for ambiguous composition/reference work | Promote only when it improves accepted suggestions enough to justify memory and latency. |
| [Qwen3-VL-4B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct) | Independent mature vision-instruction baseline | Useful when its exact runner support is better than the newer family. |
| [Gemma4 E4B](https://huggingface.co/google/gemma-4-E4B) | Independent compact multimodal comparison | Effective parameter labels are not full resident-memory measurements; inspect the actual files and model terms. |
| [JoyCaption beta-one](https://huggingface.co/fancyfeast/llama-joycaption-beta-one-hf-llava) | Specialist image-description candidate | Descriptions are proposals, not exact original prompts, camera metadata or author identity. |
| [WD SwinV2 tagger v3](https://huggingface.co/SmilingWolf/wd-swinv2-tagger-v3) | Anime vocabulary suggestions, potentially in a separate CPU ONNX worker | Pair its exact model and tag CSV. Scores are not calibrated certainty; tags need review. |
| [SmolVLM2 2.2B](https://huggingface.co/HuggingFaceTB/SmolVLM2-2.2B-Instruct) | Smaller resource-conscious alternative | Benchmark fine-detail omissions and instruction fidelity, not only speed. |
| [Qwen3-VL-Embedding2B](https://huggingface.co/Qwen/Qwen3-VL-Embedding-2B) | Later retrieval of accepted example/recipe pairs | Retrieval and reranking do not replace generation or judge artistic acceptance. |

My first choice is a single Qwen3.5-4B trial plus a no-helper baseline; add the anime tagger only when approved tag suggestions are a real bottleneck. Avoid installing an entire portfolio at once. Active parameter count in a mixture-of-experts model does not equal total weight residency. Include vision projector, KV cache, image tokens and runtime buffers in memory estimates.

## Runner and hardware constraints

[Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs) provide the concrete schema-constrained API used by the included bridge. [Its hardware page](https://docs.ollama.com/gpu) distinguishes platform-specific ROCm support and experimental Vulkan. A working Comfy Torch/HIP runtime is not proof that Ollama's Windows GPU path supports the same card. Read its current exact platform list and measure the selected model. [llama.cpp](https://github.com/ggml-org/llama.cpp) offers another local route, but model, multimodal projector, build/backend and operation support must be checked together.

The delivered helper requests 8192 context tokens, 1800 output tokens, non-thinking mode and temperature zero as a **small structured-analysis baseline**, not an author-endorsed optimum. Qwen3.5's default thinking behaviour and native context recommendations differ. Confirm that the chosen runner honors `think:false`; do not rely on a magic `/nothink` phrase. Compare schema completion, semantic fidelity and latency before changing defaults.

The adapter is implemented for Ollama only. It does not install taggers, embeddings, llama.cpp or every candidate above. Text-only and image-preparation tests use simulated model replies; network tests exercise a real loopback HTTP server, not neural inference. No local model result is labelled benchmarked.

## How to tell whether assistance actually helps

Use fixed short briefs across image, edit, video, speech and music. Include an unchanged baseline, a concise clarified version and a profile-specific candidate. Measure preserved constraints, invented details, schema errors, useful-output rate, time-to-accepted-asset and cleanup minutes. Store rejections. Equal seeds across unrelated model families do not correspond to the same noise.

[GEPA](https://github.com/gepa-ai/gepa) is a later evaluation-driven optimization lead, not an excuse to optimize against an unreliable single aesthetic score. Start with user preferences and hard acceptance checks, hold out briefs, bound the trials and preserve provenance. A VLM's enthusiastic description of its own prompt is not evidence of improved generations.
