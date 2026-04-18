# Scene Package v1

## Purpose

Define the first practical product-layer artifact for the Hollywood Studio:
a machine-runnable scene package that chains approved still anchors into
sequential first/last-frame video shots and records the exact outputs.

This is the layer above individual render lanes.

## Elements Contract

The studio should maintain versioned assets under a rigid `elements/` tree:

- `elements/characters/<id>/`
- `elements/locations/<id>/`
- `elements/props/<id>/`
- `elements/voices/<id>/`

Each element directory should contain:

- one or more approved master reference assets
- optional metadata describing prompt fragments, wardrobe, or usage notes
- any derived assets needed by the anchor pipeline

Example:

```text
elements/
  characters/
    maya_stone_01/
      master_neutral.png
      prompt.txt
      metadata.json
  locations/
    laundromat_dawn/
      hero_plate.png
      metadata.json
```

## Execution Stages

1. **Anchor stage**
   - generate or approve the first/last still anchors
   - store them as explicit file paths
2. **Shot stage**
   - run one FF/LF lane against the anchor pair
   - save the resulting clip
   - extract the terminal frame
3. **Scene stage**
   - hand the terminal frame from shot `N` into shot `N+1`
   - repeat until the ordered shot list is complete
   - stitch the final scene if needed

## Scene Package Schema

The first runnable schema is intentionally small:

```yaml
id: scene_001
title: Dawn Bus Arrival
output_dir: runs/scene_001
elements:
  - id: maya_stone_01
    kind: character
    root: elements/characters/maya_stone_01
shots:
  - id: shot_001
    workflow_api_json: {...}
    first_frame_path: /abs/path/to/shot_001_first.png
    last_frame_path: /abs/path/to/shot_001_last.png
    first_frame_target:
      node_id: "10"
      input_name: image
    last_frame_target:
      node_id: "11"
      input_name: image
    output_kind: video
  - id: shot_002
    workflow_api_json: {...}
    first_frame_target:
      node_id: "10"
      input_name: image
    chain_previous_terminal_frame: true
    output_kind: video
```

## Current Prototype

The first prototype lives in `DirectorsConsole/Orchestrator`:

- model: `orchestrator/core/models/scene_package.py`
- runner: `orchestrator/core/engine/scene_chain_runner.py`
- CLI: `scripts/run_scene_package.py`

Current behavior:

- upload still inputs to ComfyUI
- submit sequential shots
- download the resulting clip
- extract the last frame from the clip
- feed that frame into the next shot when `chain_previous_terminal_frame=true`

## Not In Scope Yet

- automated anchor generation
- automated location locking
- audio generation or lip sync
- scene-wide edit propagation
- timeline UI

Those stay separate until the basic scene-chain loop is stable.
