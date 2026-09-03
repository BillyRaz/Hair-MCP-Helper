# Hair MCP Helper — Updated Development Plan
## Agent-Native Groom Control Architecture

**Status:** Research-aligned development plan  
**Target:** Hair MCP Helper after Guide Shaper V0.1  
**Primary goal:** Build the best practical control system for an AI agent to author and refine hair guides while Blender remains the geometry/grooming backend.

---

## 1. What HMH Is Becoming

Hair MCP Helper should **not** become another complete grooming engine.

Mature systems already solve large parts of the grooming problem well:

- Houdini uses guide-first grooming, layered guide processing, resampling, masking, mirroring, and generated hair.
- MetaHuman grooming is parameter/procedure driven.
- FollicleFX keeps manual guide edits as a non-destructive relative layer.
- Blender already provides native Hair Curves, guide interpolation, guide maps, clumping, curl, surface attachment, and density tools.

HMH's job is the layer **above** those mechanics:

```text
Human / Reference
      ↓
Agent interpretation
      ↓
Hair semantic representation
      ↓
Sparse guide design
      ↓
Guide shaping / correction layers
      ↓
Blender native interpolation + groom processing
      ↓
Visual validation
      ↓
Agent/human iteration
```

The project's advantage is **agent legibility and controllability**, not superior low-level grooming algorithms.

---

## 2. Core Architectural Rule

### HMH decides intent.
### Blender executes geometry.

Use custom HMH geometry processing only where Blender lacks a useful native operation.

Prefer Blender Hair Curves, Geometry Nodes, Blender hair assets, native surface attachment, native guide maps, native interpolation, and native clumping/curl/smoothing where appropriate.

Avoid Python point-by-point production deformation, destructive baking as the default, rebuilding mature grooming algorithms inside HMH, and giant one-shot hairstyle generation.

---

## 3. Revised Grooming Hierarchy

HMH should use three clearly separated artistic scales.

### A. MACRO — Guide Authoring

This is the hairstyle.

Controlled by root placement, parting, hairline, crown direction, guide length, silhouette, C/S shape, lift, fall, face framing, depth, tip direction, guide spacing, and symmetry/asymmetry.

Primary subsystem: **Guide Shaper / Guide Authoring**.

### B. MESO — Hair Family Structure

This turns good guides into coherent locks.

Controlled by interpolation locality, guide ownership, guide maps, strand distribution, clump size, clump strength, broad secondary flow, and controlled blending between neighboring guides.

Primary systems: Interpolate Hair Curves, Guide Index / guide maps, Clump, and FLOW as a secondary modifier.

### C. MICRO — Surface Detail

This adds realism after the design works.

Controlled by curl character, breakup, frizz, flyaways, small randomness, and final polish.

**Rule:** MICRO must never be used to rescue a bad MACRO guide.

---

## 4. Immediate Priority — Prove Guide Shaper

Do not expand the system until Guide Shaper passes visual tests.

Test one solo guide only. No generated hair, interpolation, FLOW, clump, curl, or frizz.

### Required visual tests

#### Test A — C Lock

Calm root → gentle outward departure → broad continuous bend → soft released tip.

#### Test B — S Lock

Root calm → upper moves outward → mid reaches main silhouette → lower returns → tip releases.

#### Test C — Root Lift + Fall

Stable scalp attachment, controlled upper lift, progressive downward fall, and no hinge at lift/fall boundaries.

#### Test D — Face Frame

Guide exits scalp cleanly, passes around the face, returns inward through the lower section, and finishes with deliberate tip direction.

### Acceptance

Guide Shaper passes when these shapes can be made intentionally and repeatably without visible segment kinks, root movement, frame flipping, arbitrary world-space behavior, uncontrolled stretching, or dependence on downstream styling.

---

## 5. Guide Authoring V0.2 — After Visual Proof

If V0.1 passes, improve the **artist/agent experience**, not the number of algorithms.

### 5.1 Semantic Guide Anchors

Keep normalized ROOT, UPPER, MID, LOWER, TIP controls. Do not expose raw control-point indices as the main API.

The agent should say **“move MID outward”**, not **“move point 7 by 0.04 m.”**

### 5.2 Stable Local Frame

Continue using a scalp-aware frame with semantics such as `along`, `outward/lateral`, `depth`, and `up/down`.

Future improvement should make frame derivation per-guide for multi-guide native objects, preserve directional consistency around the full scalp, and avoid sudden side/depth sign changes.

### 5.3 True Artist Falloff

Make `smooth`, `soft`, and `sharp` produce genuinely different response curves. Also make `smoothness` and `tension` affect the envelope rather than remaining semantic metadata only.

### 5.4 Mirror + Controlled Asymmetry

Add only after the solo-guide shaping model is proven.

Workflow:

```text
design left macro guide
      ↓
mirror
      ↓
apply small deterministic semantic offsets
      ↓
right-side variation
```

Do not use noisy random mirroring.

---

## 6. Non-Destructive Guide Layers

One of the most valuable lessons from mature groomers is to treat manual/semantic adjustments as layers rather than destructive bakes.

HMH should evolve toward:

```text
BASE GUIDE
    ↓
SEMANTIC SHAPE LAYER
    ↓
STYLE LAYER
    ↓
ARTIST / AGENT CORRECTION LAYER
    ↓
FINAL GUIDE
```

A correction should ideally be stored as a **relative change**, not a destructive replacement.

Benefits include preserving upstream length changes, root revisions, style changes, correction blending, and the ability for an agent to say **“reduce this correction by 30%.”**

Each layer should eventually have a stable id, strength, enabled state, semantic description, deterministic rebuild, and inspectable source.

Do not implement the full layer stack until Guide Shaper visual quality is proven.

---

## 7. Guide Graph — Future Agent Representation

The agent should eventually understand a hairstyle as a graph of meaningful guide relationships.

```text
PART_L
 ├─ FACEFRAME_L_01
 ├─ FACEFRAME_L_02
 └─ TOP_L_01

CROWN
 ├─ BACK_UPPER_01
 └─ BACK_UPPER_02

SIDE_L
 ├─ SIDE_L_01
 ├─ SIDE_L_02
 └─ SIDE_L_03
```

Relationships may describe parent semantic region, neighboring guides, mirror partner, dominant direction, length class, influence radius, blend eligibility, and lock/family identity.

This should help an agent reason about a hairstyle structurally instead of object-by-object.

---

## 8. Guide Ownership and Guide Maps

Keep the current ownership system. Per-curve ownership remains authoritative.

Continue preserving `hair_mcp_group_id`, `guide_curve_index`, region metadata, and source guide metadata.

Use Blender's guide-map model rather than inventing a second unrelated grouping system.

Future semantic controls should include strict guide ownership, blended guide influence, clump guide ownership, family radius, and cross-region blocking.

The system must distinguish **root distribution** from **directional ownership**. Root spread is expected; guide-following direction must remain coherent.

---

## 9. Interpolation Plan

Current known-good default for strict guide-shape following:

```text
interpolation_guides = 1
follow_surface_normal = False
```

Keep explicit controls for `distance_to_guides`, `density`, `viewport_amount`, `seed`, `distribution_method`, `follow_surface_normal`, `interpolation_guides`, and `part_by_mesh_islands`.

### Future research/test

Test **Random vs Poisson Disk** for polished character hair.

Goal: stable local root spacing, fewer accidental density clusters, and no loss of semantic guide ownership.

Do not change the default without visual evidence.

---

## 10. Clump System Upgrade

Current clump support is only the beginning.

Blender already exposes factor, shape, tip spread, clump offset, distance falloff, distance threshold, seed, preserve length, and guide-map controls.

HMH should eventually expose artist semantics such as:

```text
clump_strength
clump_size
root_hold
tip_spread
clump_variation
distance_falloff
preserve_length
```

The agent should not need to understand every Blender socket name.

**Rule:** Clumping organizes locks. It does not define the hairstyle silhouette.

---

## 11. Reposition FLOW

FLOW remains useful, but it is no longer the primary hairstyle designer.

```text
Guide Shaper = macro silhouette
FLOW         = secondary broad variation
Curl         = repeated wave/curl character
Frizz        = micro breakup
```

FLOW should subtly break mechanical duplication, add broad secondary motion, and preserve the authored guide design.

FLOW should not replace C/S guide shaping, create the main face-frame trajectory, or rescue bad guides.

---

## 12. Agent Workflow

### Step 1 — Interpret Reference

Agent identifies part, length, main masses, silhouette, fringe, crown, side locks, back layers, and special structures.

### Step 2 — Build Semantic Regions

Create only the regions needed.

### Step 3 — Sparse Primary Guides

Create a small number of important guides.

### Step 4 — Guide Shape Pass

Use Guide Shaper to establish root direction, silhouette, length, lift, fall, and tip.

### Step 5 — Human/Visual Checkpoint

Stop. Review only the sparse guide silhouette.

### Step 6 — Guide Family / Interpolation

Generate local children using guide ownership.

### Step 7 — Meso Grooming

Apply clump, optional FLOW, and controlled guide blending.

### Step 8 — Micro Grooming

Apply curl, smooth, breakup, frizz, and flyaways.

### Step 9 — Final Validation

Check scalp penetration, silhouette, part integrity, density, region ownership, and export readiness.

---

## 13. Machine-Readable Agent State

HMH should continue investing in structured state.

The agent should be able to ask:

```text
What regions exist?
Which guides control SIDE_L?
Which guides are shaped?
Which guide is mirrored from which?
Which guide has a correction layer?
What is the current checkpoint?
Which regions passed silhouette review?
Which generated hair object belongs to which guide family?
```

Do not make the agent infer this from Blender names or viewport appearance alone.

---

## 14. Visual Feedback Loop — Important Future Step

The long-term system should not be:

```text
agent writes commands
      ↓
done
```

It should be:

```text
agent plans
      ↓
HMH applies
      ↓
Blender evaluates
      ↓
viewport/render inspection
      ↓
agent compares result with intent/reference
      ↓
localized correction
      ↓
human checkpoint
```

The agent should make **localized revisions**, not regenerate the entire groom after every mismatch.

This is where HMH can become genuinely AI-native.

---

## 15. What NOT to Build Yet

Until guide authoring is proven visually, do not spend major effort on simulation, braids, cornrows, loc systems, physics, advanced collision, automatic full-hairstyle generation, large material systems, Unreal export automation, complex flyaway generation, giant UI panels, custom replacement interpolation, or custom replacement clumping.

Those may become useful later, but they do not solve today's main problem.

---

## 16. Development Order

### Phase 1 — Current
**Guide Shaper V0.1 visual validation**

C / S / lift-fall / face-frame.

### Phase 2
**Guide Shaper V0.2**

- real smoothness/tension
- real falloff modes
- multi-guide stable frames
- mirror/asymmetry
- improved inspection

### Phase 3
**Non-destructive Guide Layers**

- semantic shape layer
- correction/delta layer
- strength blending
- stable guide ids

### Phase 4
**Guide Graph**

- neighbor relations
- family identity
- mirror relations
- influence semantics

### Phase 5
**Interpolation + Distribution Refinement**

- Poisson vs Random
- density masks
- local spacing
- guide blending rules

### Phase 6
**Clump / Lock System**

Expose mature clump concepts semantically.

### Phase 7
**Styler Refinement**

FLOW becomes secondary. Curl/frizz remain tertiary.

### Phase 8
**Reference → Semantic Plan**

Use multimodal analysis to create the region/guide plan, but keep human checkpoints.

### Phase 9
**Visual Iteration Agent**

Agent detects silhouette/local problems and applies targeted corrections.

---

## 17. Success Definition

HMH succeeds when an agent can reliably perform this sequence:

> Understand a hairstyle reference → identify semantic regions → create sparse guides → intentionally shape those guides → stop for silhouette review → generate coherent hair families → add secondary grooming → inspect → make localized corrections.

The final quality should come from **good guide decisions + Blender's mature native hair operations**, not from one giant custom HMH hair-generation algorithm.

---

## 18. Production Independence

HMH should remain its own long-term project.

It may help a current production when practical, but its architecture and development should not be limited to one game or one hairstyle.

If a production deadline requires mesh hair or another fallback, that does not invalidate HMH.

The correct measure is whether HMH becomes a reusable **agent-native grooming control layer** that gets better over time.
