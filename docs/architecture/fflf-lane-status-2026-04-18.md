# First/Last-Frame Lane Status - 2026-04-18

## Goal

Record which first/last-frame (FF/LF) video lanes are actually usable for the Hollywood Studio on the 24 GB 3090, and which ones should not be treated as production defaults.

## Current recommendation

For Paperclip/Hermes production use on this box:

- Default local FF/LF lane: Wan 2.2 local
- Default LTX FF/LF lane: `linoyts/LTX-2-3-First-Last-Frame` via Hugging Face
- Optional experimental lane: official local ComfyUI LTX 2.3 FF/LF template
- Deprioritized on this hardware: heavier WhatDreamsCost multi-stage LTX variants

The distinction matters. "Can be made to run once" is not the same thing as "should be a production lane on a 24 GB 3090."

## Proven lanes

### 1. Hugging Face LTX lane: proven and practical

- Space: `linoyts/LTX-2-3-First-Last-Frame`
- Inputs:
  - `/home/straughter/ComfyUI/output/harbor_v2_kf_/s01_first_00001_.png`
  - `/home/straughter/ComfyUI/output/harbor_v2_kf_/s01_last_00001_.png`
- Output:
  - `/home/straughter/ComfyUI/output/hf_ltx23_flf2v/harbor_v2_linoyts_flf2v_seed424242.mp4`
- Proof:
  - success
  - duration `3.041667`
  - size `1133721` bytes

This is the cleanest LTX FF/LF lane available right now for studio use.

### 2. Official Wan local FF/LF lane: proven and preferred on-box

- Workflow family: official local Wan FF/LF
- Output:
  - `/home/straughter/ComfyUI/output/wan_flf2v/harbor_v2_wan22_14b_official_00001_.mp4`
- Proof:
  - success
  - duration `5.062500`
  - size `602591` bytes

This is the practical local production lane for the 3090.

### 3. Official local LTX FF/LF lane: proven, but not the default

- Workflow family: official local `video_ltx2_3_flf2v`
- Required checkpoint:
  - `/home/straughter/ComfyUI/models/checkpoints/ltx-2.3-22b-distilled-fp8.safetensors`
- Output:
  - `/home/straughter/ComfyUI/output/video/ltx2.3_flf2v_harbor_retry_00001_.mp4`
- Proof:
  - success
  - duration `3.041667`
  - size `752566` bytes
- Execution evidence:
  - `journalctl -u comfyui.service` recorded `Prompt executed in 565.06 seconds`

This lane is not impossible on the 3090. It was proven locally once the intended distilled FP8 checkpoint was installed.

That said, it is slow enough that it should be treated as an optional experimental or fallback lane, not the main production default.

## Important correction

The earlier local LTX failure was not caused by the `model_type FLUX` log line.

In this ComfyUI build, local `LTXV` / `LTXAV` models use `ModelType.FLUX`, so that log line is normal. The real failure mode was memory pressure when the workflow fell back to a heavier local LTX checkpoint before the intended distilled FP8 checkpoint was installed.

## Deprioritized lanes

### WhatDreamsCost 2-stage and 3-stage local LTX

The WhatDreamsCost FF/LF workflows were investigated and partially adapted, but they should not be treated as active production targets on this hardware.

Reasons:

- they are heavier than the practical studio defaults
- they require workflow adaptation to the actual installed model names on the box
- they are a worse compute trade than Wan local or the Hugging Face LTX lane
- the studio already has two better FF/LF options for production work

If these variants matter later, they should be revisited only when:

- a stronger GPU is available, or
- there is a clear quality reason to prefer them over Wan local or Hugging Face LTX

## Production guidance for Paperclip

Paperclip should treat FF/LF lane selection like this on the 3090:

1. Prefer Wan local for the default machine-resident path.
2. Prefer Hugging Face LTX for the default LTX path.
3. Allow official local LTX only as an explicit experimental or fallback option.
4. Do not spend operator cycles trying to "repair every local LTX variant" unless there is a concrete quality or cost reason.
