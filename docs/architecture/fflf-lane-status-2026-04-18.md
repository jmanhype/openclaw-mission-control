# First/Last-Frame Lane Status

## Purpose

Promote the actually proven first/last-frame lanes into the Paperclip Hollywood Studio as production-capable options, and separate the blocked local LTX lane into an explicit repair track instead of treating it as already ready.

## Production-Capable Lanes

### 1. Wan 2.2 local FF/LF on the 3090

- **Status:** proven
- **Execution class:** local ComfyUI on the 3090
- **Workflow source:** `/home/straughter/ComfyUI/venv/lib/python3.12/site-packages/comfyui_workflow_templates_media_video/templates/video_wan2_2_14B_flf2v.json`
- **First frame:** `/home/straughter/ComfyUI/input/harbor_v2_first.png`
- **Last frame:** `/home/straughter/ComfyUI/input/harbor_v2_last.png`
- **Output:** `/home/straughter/ComfyUI/output/wan_flf2v/harbor_v2_wan22_14b_official_00001_.mp4`
- **Proof result:** success
- **Output proof:** `5.062500s`, `602591` bytes
- **Recommendation:** use as the default local first/last-frame lane in Paperclip until local LTX is repaired

### 2. LTX 2.3 external FF/LF via linoyts Space

- **Status:** proven
- **Execution class:** external Hugging Face Space via `gradio_client`
- **Space:** `linoyts/LTX-2-3-First-Last-Frame`
- **Instruction source:** `https://huggingface.co/spaces/linoyts/LTX-2-3-First-Last-Frame/agents.md`
- **First frame:** `/home/straughter/ComfyUI/output/harbor_v2_kf_/s01_first_00001_.png`
- **Last frame:** `/home/straughter/ComfyUI/output/harbor_v2_kf_/s01_last_00001_.png`
- **Output:** `/home/straughter/ComfyUI/output/hf_ltx23_flf2v/harbor_v2_linoyts_flf2v_seed424242.mp4`
- **Proof result:** success
- **Output proof:** `3.041667s`, `1133721` bytes
- **Recommendation:** use as the default external LTX first/last-frame lane in Paperclip

### 3. Official local LTX 2.3 FF/LF on the 3090

- **Status:** proven
- **Execution class:** local ComfyUI on the 3090
- **Workflow source:** `/home/straughter/ComfyUI/venv/lib/python3.12/site-packages/comfyui_workflow_templates_media_video/templates/video_ltx2_3_flf2v.json`
- **First frame:** `/home/straughter/ComfyUI/input/harbor_v2_first.png`
- **Last frame:** `/home/straughter/ComfyUI/input/harbor_v2_last.png`
- **Proof prompt id:** `f84300cb-2c22-4f01-9067-50fb026917fe`
- **Output:** `/home/straughter/ComfyUI/output/video/ltx2.3_flf2v_harbor_retry_00001_.mp4`
- **Proof result:** success
- **Output proof:** ComfyUI history reported `status.success` and `Prompt executed in 565.06 seconds`
- **Repair notes that mattered:** the official template wanted `ltx-2.3-22b-distilled-fp8.safetensors`; once that checkpoint was installed on the 3090, the local lane stopped falling back to the heavier dev stack and ran cleanly
- **Important log correction:** `model_type FLUX` is normal in this ComfyUI build for local `LTXV` / `LTXAV`; it was not the failure
- **Recommendation:** promote as the default local LTX first/last-frame lane in Paperclip

## Validation Lanes

### 4. WhatDreamsCost local LTX FF/LF 2-stage

- **Status:** in validation
- **Execution class:** local ComfyUI on the 3090
- **Workflow source:** `/home/straughter/ComfyUI/custom_nodes/WhatDreamsCost-ComfyUI/example_workflows/LTX I2V First Last Frame 2 Stage Workflow v6.json`
- **Current input pair:** `/home/straughter/ComfyUI/input/harbor_v2_first.png` and `/home/straughter/ComfyUI/input/harbor_v2_last.png`
- **What was repaired before runtime:** missing `easy mathInt` nodes were removed by inlining the computed frame count, model names were remapped to installed 3090 assets, and the guide resize was stepped down for proof mode
- **First proof outcome:** the original proof-size run OOM-killed `comfyui.service` at `2026-04-18 15:27:51`
- **Second proof outcome:** the reduced-memory run cleared the memory wall but failed inside `ComfyUI-KJNodes` preview generation with `AttributeError: 'NoneType' object has no attribute 'encode'` on `SamplerCustomAdvanced` prompt `aa77724c-276a-471d-8cc5-a50dcb63a21b`
- **Current state:** a no-preview rerun was submitted as prompt `33c4b152-ab02-440c-9af4-2cd94392e863`
- **Current blocker:** after the no-preview rerun entered compute, the 3090 stopped answering ComfyUI status probes and SSH banner exchange even with `60s` timeouts, so the exact terminal outcome is not yet recoverable from the box
- **Recommendation:** do not promote yet; wait for a full no-preview proof artifact

### 5. WhatDreamsCost local LTX FF/LF 3-stage

- **Status:** prepared for validation
- **Execution class:** local ComfyUI on the 3090
- **Workflow source:** `/home/straughter/ComfyUI/custom_nodes/WhatDreamsCost-ComfyUI/example_workflows/LTX I2V First Last Frame 3 Stage Workflow v6.json`
- **Current input pair:** `/home/straughter/ComfyUI/input/harbor_v2_first.png` and `/home/straughter/ComfyUI/input/harbor_v2_last.png`
- **Prepared proof profile:** `25` frames, `0.25` guide resize, stage-3 switched from `2x` to `1.5x`, preview wrapper bypassed
- **Prepared prompt file:** `/tmp/wdc_ltx_3stage_nopreview_submit.json`
- **Recommendation:** submit only after the 2-stage no-preview rerun resolves cleanly

## Paperclip Promotion Decision

- **Promote now:** Wan local FF/LF, linoyts external LTX FF/LF, official local LTX FF/LF
- **Do not promote yet:** WhatDreamsCost 2-stage local LTX FF/LF, WhatDreamsCost 3-stage local LTX FF/LF

This keeps the Hollywood Studio truthful: three usable FF/LF lanes are available now, and the WhatDreamsCost variants remain explicit validation work instead of silent partial failures.
