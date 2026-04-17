# Paperclip/Hermes parity spec for the Hollywood Studio

## Goal

Replace the Mission Control/OpenClaw control plane used for the 3090-based Hollywood Studio with a Paperclip/Hermes control plane, while preserving the studio's actual operating behavior.

This document is based on recovered Mission Control/OpenClaw history from April 14-17, 2026. It is intentionally behavior-first. It does not assume Paperclip or Hermes natively provide every required capability.

> **Note**
> Treat this as a parity target, not an implementation claim. Any Paperclip/Hermes primitive marked `verify` must be confirmed against the live system before coding against it.

## Recovered baseline

### Studio boards recovered from history

- `ComfyUI video pipeline`
- `character / identity assets`
- `ACE-Step music pipeline`

### Core board recovered from history

- **Board name**
  - `ComfyUI video pipeline`
- **Description**
  - Track visual generation workflows on the 3090, including Wan 2.2, LTX, triple-stage, iPhone-look experiments, proof runs, and output review.
- **Objective**
  - Build and optimize reusable ComfyUI video workflows on the 3090, including Wan 2.2, LTX, triple-stage, and iPhone-style aesthetic pipelines.
- **Success metric**
  - Reusable workflows completed and documented.
- **Board rules**
  - `require_review_before_done=true`
  - `comment_required_for_review=true`
  - `require_approval_for_done=false`
  - `max_agents=2`

### Recovered studio lanes

The recovered board history shows these lanes were built or proven:

- Wan 2.2 proof lane
- LTX proof lane
- production Wan baseline lane
- LUT / color grading lane
- lip-sync lane
- frame interpolation / FPS upscaling lane
- caption / subtitle burn-in lane
- reusable finishing recipe
- shot stitching / concat lane
- audio-safe finishing lane
- OmniVoice lane
- shot planning / storyboard / animatic system
- continuity supervisor
- editorial timeline / sequence manifest
- dialogue assembly pipeline
- audio post pipeline
- end-to-end scene pipeline
- cinematic harbor-night scene v1
- harbor-night first-frame / last-frame v2 experiment

### Recovered operating discipline

The old system was not just tasks and comments. It enforced a specific workflow:

- Lead and worker agents had separate workspaces.
- Each workspace had startup and role files:
  - `AGENTS.md`
  - `SOUL.md`
  - `USER.md`
  - `IDENTITY.md`
  - `TOOLS.md`
  - `HEARTBEAT.md`
- Each workspace kept two memory layers:
  - `memory/YYYY-MM-DD.md` for raw daily logs
  - `MEMORY.md` for durable operational memory
- Remote execution claims required machine evidence:
  - fresh prompt/job/build id
  - exact output path
- Media work used a reusable scene/run package:
  - workflow path
  - input/reference/keyframe paths
  - parameters
  - intermediate outputs
  - final output
  - QC verdict
- Task comments were for evidence and handoff.
- Board chat was for decisions and human questions.

## Parity target

The replacement target is not "project management." It is the full studio control plane around the 3090 executor stack.

### Out of scope

The following systems are not being replaced:

- ComfyUI
- the 3090 host
- SSH access to `192.168.1.143`
- SmartGallery
- Wan, LTX, FFmpeg, RIFE, LatentSync, OmniVoice, and related render tools

### In scope

- board/project model
- task workflow and review gates
- lead/worker runtime
- memory and heartbeat behavior
- task evidence and handoff structure
- operator chat and decision flow
- 3090 execution orchestration

## Entity mapping

| Original Mission Control/OpenClaw concept | Replacement target | Notes |
| --- | --- | --- |
| Organization | Paperclip company | Use one company for the studio org. |
| Board | Paperclip project | One project per recovered board. |
| Board group | Custom portfolio/program layer or Paperclip equivalent `verify` | Needed if multiple studio boards stay grouped. |
| Task | Paperclip issue/work item | Must support review-gated status transitions. |
| Task comment | Paperclip issue comment | Evidence-first updates only. |
| Board chat | Custom project ops thread | This is not just comments on a single issue. |
| Board memory (non-chat) | Custom project memory store | Durable project-level notes and operator memory. |
| Lead agent | Hermes lead runtime + Paperclip agent registry `verify` | Owns sequencing, staffing, gates, blocker escalation. |
| Worker agent | Hermes worker runtime + Paperclip agent registry `verify` | Owns execution quality and artifact production. |
| Workspace bootstrap files | Hermes workspace provisioner | Must materialize role files and memory files per agent. |
| Heartbeat | Hermes scheduled operator loop | Pre-flight, task poll, state update, blocker publish. |
| Gateway ask-user flow | Hermes gateway bridge | Preserve the "lead asks user through gateway" path. |
| Review gate | Custom workflow policy engine | Must enforce `comment_required_for_review` and similar rules. |
| Max agents per board | Custom staffing policy | Per-project staffing cap. |
| Task evidence schema | Shared studio execution schema | Required for reproducibility and QC. |
| Scene/run package | Shared studio artifact schema | Required for staged media tasks. |

## Must-have replacement components

### 1. Studio company model

Create one Paperclip company for the studio.

Suggested initial shape:

- `OpenClaw Hollywood Studio`
- projects:
  - `ComfyUI video pipeline`
  - `character / identity assets`
  - `ACE-Step music pipeline`

Required fields:

- project description
- project objective
- project success metric
- project rules
- staffing cap

### 2. Project rule engine

Mission Control board rules were first-class. Paperclip/Hermes parity needs a rule engine with at least:

- `require_review_before_done`
- `comment_required_for_review`
- `require_approval_for_done`
- `block_status_changes_with_pending_approval`
- `only_lead_can_change_status`
- `max_agents`

Minimum behavior:

1. A task cannot move to `review` without at least one evidence comment when `comment_required_for_review=true`.
2. A task cannot move to `done` without passing `review` when `require_review_before_done=true`.
3. Staffing assignment must refuse or queue beyond `max_agents`.

### 3. Lead/worker runtime

Hermes must provide two explicit runtime roles:

- **Lead**
  - plans
  - sequences
  - reassigns
  - enforces gates
  - escalates blockers
- **Worker**
  - executes assigned tasks
  - records proof
  - hands off cleanly

Each runtime needs:

- identity
- role
- project membership
- online/offline state
- current assignment
- last heartbeat

### 4. Workspace provisioner

The old system relied on file-backed runtime context. Preserve that as generated workspace state.

Required generated files per agent workspace:

- `AGENTS.md`
- `SOUL.md`
- `USER.md`
- `IDENTITY.md`
- `TOOLS.md`
- `HEARTBEAT.md`
- `MEMORY.md`
- `memory/YYYY-MM-DD.md`

Minimum generated values:

- agent id
- project id
- base URL / auth context
- role contract
- communication rules
- heartbeat rules
- memory template

### 5. Memory system

Parity requires two layers:

- **Daily log**
  - raw events
  - check-ins
  - blockers
  - execution notes
- **Durable memory**
  - current delivery status
  - decisions
  - standards
  - known constraints
  - reusable playbooks

Required durable sections:

- current delivery status
- decisions / assumptions
- evidence (short)
- package / artifact set
- quality gate
- success criteria

### 6. Heartbeat engine

Hermes must schedule and run a project-aware heartbeat loop.

Minimum loop:

1. load workspace files
2. verify auth and control-plane health
3. pull project tasks and project memory
4. update local delivery state
5. take one next action
6. publish either:
   - evidence
   - blocker
   - handoff

Required rules:

- no status-only spam
- one blocker publish per repeated failure path
- remote execution claims require fresh execution id and output path

### 7. Project ops thread

Mission Control board chat was a distinct surface. Recreate it as a project-level ops thread, separate from issue comments.

Use cases:

- human decisions
- `@lead` questions
- assignment direction
- cross-task guidance
- gateway-to-human relays

Required behavior:

- mention support
- notify lead by default
- route agent-targeted mentions
- keep task evidence out of the ops thread unless task comments fail

### 8. Issue evidence schema

Every studio task needs a structured reporting contract.

Minimum fields:

```json
{
  "workflow_paths": [],
  "input_paths": [],
  "reference_paths": [],
  "keyframe_paths": [],
  "parameters": {},
  "execution_id": "",
  "output_paths": [],
  "qc_verdict": "",
  "next_step": "",
  "blocker": ""
}
```

### 9. Scene/run package schema

For staged media work, issue comments are not enough. Recreate the reusable scene/run package.

Minimum package contents:

- target look or acceptance criteria
- workflow/template path
- input/reference/keyframe paths
- key parameters
- intermediate outputs
- final output
- benchmark output if relevant
- QC checklist
- QC verdict

### 10. 3090 executor bridge

This is the most important external integration.

Hermes must drive:

- SSH to `straughter@192.168.1.143`
- ComfyUI API at `http://192.168.1.143:8188`
- SmartGallery awareness at `http://192.168.1.143:8291`
- local shell tools on the 3090:
  - `ffmpeg`
  - render scripts
  - file inspection

Minimum executor capabilities:

- submit ComfyUI prompt JSON
- poll queue/history
- verify output existence
- inspect workflow files on disk
- run shell post-processing
- capture exact output paths for evidence

### 11. Review and approval flow

Needed behaviors:

- explicit `review` stage
- optional approval stage per task or project
- evidence-required review submissions
- lead-driven closeout

Minimum review checklist for media tasks:

- proof of execution
- proof of quality
- exact output path
- exact workflow path
- acceptance criteria comparison

### 12. Gateway ask-user bridge

This existed in the old system and should be preserved.

Flow:

1. lead decides user input is required
2. gateway asks user through the configured channel
3. user reply is written back into project memory
4. lead resumes using that reply

This should not be implemented as ad hoc chat scraping.

## Recovered studio scope to preserve

### Project 1: ComfyUI video pipeline

Must preserve:

- base generation lanes
- finishing lanes
- audio/dialogue lanes
- planning/editorial lanes
- continuity/QC lanes
- end-to-end scene assembly

Recovered task inventory:

- prove Wan 2.2 + LTX path
- convert Wan 2.2 workflow to API format
- production Wan 2.2 pass
- reusable asset baseline promotion
- LUT lane
- lip-sync lane
- frame interpolation lane
- caption burn-in lane
- finishing recipe
- stitching / concat lane
- audio-safe finishing
- OmniVoice lane
- live OmniVoice proof
- shot planning / storyboard / animatic
- continuity supervisor
- editorial timeline / sequence manifest
- dialogue assembly
- audio post
- end-to-end scene
- harbor-night cinematic scene
- harbor-night v2 first/last-frame experiment
- harbor-night v1 workflow template documentation

### Project 2: character / identity assets

Must preserve:

- feeder-selection methodology
- identity pack metadata schema
- reusable identity asset library
- Klein workflows
- iPhone-look anchors
- ref packs
- identity-safe edit path
- character consistency benchmarking

### Project 3: ACE-Step music pipeline

Recovered scope was lighter, but parity still needs:

- dedicated music project
- reusable music workflow tracking
- proof runs and outputs
- same lead/worker and memory model

## Build plan

### Phase 1: Control-plane minimum viable parity

Build first:

1. Paperclip company
2. Paperclip projects for the three recovered boards
3. Hermes lead/worker runtime registry
4. project rule engine
5. project ops thread
6. issue comments with evidence schema
7. memory system
8. heartbeat engine

Acceptance:

- A lead and one worker can operate the `ComfyUI video pipeline` project.
- A task can move `inbox -> in_progress -> review -> done` with rule enforcement.
- Evidence comments and project ops thread are separate.

### Phase 2: 3090 execution parity

Build next:

1. SSH executor bridge
2. ComfyUI API submission and polling
3. output path verification
4. ffmpeg/post-processing execution
5. reusable execution result schema

Acceptance:

- Hermes can submit a real ComfyUI run on the 3090.
- The system records prompt id and exact output path.
- The result can be posted back to the issue in structured form.

### Phase 3: Studio workflow parity

Build next:

1. scene/run package support
2. QC checklist and review gate helpers
3. cross-lane workflow templates
4. issue templates for recovered lanes

Acceptance:

- One real Wan 2.2 proof task can be executed end to end.
- One finishing-lane task can be executed end to end.
- One multi-step scene task can be run with a reusable scene/run package.

### Phase 4: Migration and archive

Build last:

1. import historical board/task metadata
2. attach recovered outputs and workflow paths where useful
3. archive Mission Control/OpenClaw state as read-only provenance

Acceptance:

- The recovered Hollywood Studio work is discoverable from the new system.
- New work happens in Paperclip/Hermes only.

## Acceptance checklist for true parity

The replacement is not complete until all items below are true:

- A Paperclip project exists for each recovered studio board.
- Hermes can run lead and worker roles with separate state.
- Project rules enforce review gates and staffing caps.
- Agents keep daily logs and durable memory.
- Project ops chat exists and supports lead-targeted decisions.
- Issue comments carry structured execution evidence.
- The 3090 executor bridge can run ComfyUI and post-processing tasks.
- A real Wan 2.2 proof task can be run from the new control plane.
- A real finishing-lane task can be run from the new control plane.
- A real multi-step scene task can be run with a reusable scene/run package.

## Known custom-build items

These should be assumed custom until proven native:

- project ops thread with mentions
- project-level durable memory
- heartbeat daemon and status discipline
- workspace provisioner
- rule engine for review/status/staffing
- gateway ask-user bridge
- scene/run package helpers
- exact evidence schema enforcement

## Open questions to verify before implementation

- Does Paperclip already expose a project-level chat/thread primitive?
- Does Paperclip already expose customizable workflow/status rules?
- Does Paperclip already expose agent presence and assignment state?
- Does Hermes already provide scheduled heartbeats or only agent runtime?
- Should historical Mission Control task ids be preserved as foreign keys in the new system?
- Should SmartGallery links be stored directly on issues, on artifact records, or both?

## Immediate next step

Implement Phase 1 against the `ComfyUI video pipeline` project only. Do not start with all three boards at once.

The first successful milestone should be:

1. create the studio company and `ComfyUI video pipeline` project
2. stand up one lead and one worker in Hermes
3. enforce review-gated issue flow
4. run one real Wan 2.2 proof task through the new path
