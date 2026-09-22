"""Pure storage-role metadata shared by guidance and runtime model inventory.

No model discovery, imports from the installed ComfyUI app, or filesystem probes.
Unknown node classes still need an explicit resource declaration/reviewed adapter.
"""

SUFFIXES = {".safetensors", ".gguf", ".pth", ".pt", ".onnx"}

FOLDERS = {
    "checkpoints": "Complete image models", "diffusion_models": "Diffusion / video / 3D models",
    "text_encoders": "Prompt interpreters", "vae": "Image, video and audio decoders",
    "loras": "Style and capability adapters", "controlnet": "Pose and structure controls",
    "clip_vision": "Reference image encoders", "upscale_models": "Image upscalers",
    "embeddings": "Learned prompt tokens", "latent_upscale_models": "Latent video upscalers",
    "background_removal": "Foreground isolation models", "ipadapter": "Reference identity adapters",
    "ultralytics": "Face, hand and person detectors", "inpaint": "Inpaint heads and patches",
    "vae_approx": "Fast latent previewers",
}

# Annotator checkpoints that a preprocessor node fetches into its own custom-node folder
# (comfyui_controlnet_aux `ckpts/`) on first use. They never live in the models library,
# so readiness must not project them as missing model files; the node reports its own failure.
ANNOTATOR_SELECTIONS = {
    ("DepthAnythingV2Preprocessor", "ckpt_name"),
}

# Reviewed class/input storage roles used by this catalog. This is not a universal
# custom-node inference engine; new loaders need a declaration or reviewed adapter.
MODEL_INPUT_FOLDERS = {
    ('CheckpointLoaderSimple', 'ckpt_name'): 'checkpoints',
    ('ImageOnlyCheckpointLoader', 'ckpt_name'): 'checkpoints',
    ('UNETLoader', 'unet_name'): 'diffusion_models',
    ('UnetLoaderGGUF', 'unet_name'): 'diffusion_models',
    ('CLIPLoader', 'clip_name'): 'text_encoders',
    ('CLIPVisionLoader', 'clip_name'): 'clip_vision',
    ('IPAdapterModelLoader', 'ipadapter_file'): 'ipadapter',
    ('VAELoader', 'vae_name'): 'vae',
    ('LoraLoader', 'lora_name'): 'loras',
    ('LoraLoaderModelOnly', 'lora_name'): 'loras',
    ('ControlNetLoader', 'control_net_name'): 'controlnet',
    ('UpscaleModelLoader', 'model_name'): 'upscale_models',
    ('UltralyticsDetectorProvider', 'model_name'): 'ultralytics',
    ('LoadBackgroundRemovalModel', 'bg_removal_name'): 'background_removal',
    ('INPAINT_LoadFooocusInpaint', 'head'): 'inpaint',
    ('INPAINT_LoadFooocusInpaint', 'patch'): 'inpaint',
}
