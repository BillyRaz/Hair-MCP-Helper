# Hair MCP Helper 0.3

A thin Blender semantic bridge for **Codex / MCP / CLI-assisted hair grooming**.

This is intentionally **not a hairstyle generator** and **not a full artist-facing grooming addon**. Its job is to translate between human grooming language and stable machine operations.

## Design contract

The extension follows the research rules in `Hair_Groom_Research_Codex_Rules.md`:

- sparse guides before density
- silhouette before detail
- roots belong to the scalp
- preserve part boundaries
- work in semantic regions
- checkpoint before destructive/large downstream passes
- keep editable guide data
- validate before Unreal export

## Stable semantic names

Default regions:

- FRINGE_L / FRINGE_R
- CROWN_L / CROWN_R
- TEMPLE_L / TEMPLE_R
- SIDE_L / SIDE_R
- MIDLENGTH_L / MIDLENGTH_R
- REAR_L / REAR_R
- BACK_LONG
- NAPE
- FLYAWAYS

Default checkpoints:

- A_SCALP_REGIONS
- B_PRIMARY_GUIDES
- C_SILHOUETTE_PART
- D_INTERPOLATED_GROOM
- E_CLUMPS_DEFORMATION
- F_TERTIARY_FLYAWAYS
- G_UNREAL_EXPORT

## Install

Blender 4.2+:

1. Zip the `hair_mcp_helper` directory.
2. Blender → Edit → Preferences → Get Extensions / Add-ons → Install from Disk.
3. Install the zip.
4. Enable **Hair MCP Helper**.
5. View3D → Sidebar → **Hair MCP**.

## MCP / Codex API

`mcp_exec.py` injects a resolved `hmh` module into every submitted script, so
callers do not need to know whether Blender installed the extension as
`hair_mcp_helper` or under a `bl_ext.*` namespace:

```python
result = hmh.execute({"action": "init"})
print(result)
```

For other Blender execution endpoints, load `resolver.py` and call
`resolve_hair_mcp_helper()`. Resolution uses the stable extension id and add-on
name rather than a hard-coded repository namespace.

Set a scalp:

```python
hmh.execute({
    "action": "set_scalp",
    "args": {"object_name": "Head_Scalp"}
})
```

Create a semantic region:

```python
hmh.execute({
    "action": "ensure_region",
    "args": {
        "name": "FRINGE_L",
        "side": "LEFT",
        "group_id": 10
    }
})
```

Create sparse primary guides from machine-readable points:

```python
hmh.execute({
    "action": "create_guides",
    "args": {
        "region": "FRINGE_L",
        "group_id": 10,
        "guides": [
            [[0,0,1.7], [-0.03,-0.02,1.66], [-0.08,-0.04,1.58]]
        ]
    }
})
```

Checkpoint:

```python
hmh.execute({
    "action": "checkpoint",
    "args": {
        "name": "B_PRIMARY_GUIDES",
        "note": "Ready for human silhouette review"
    }
})
```

Validate:

```python
report = hmh.validate()
```

Snapshot machine state:

```python
state = hmh.snapshot()
```

## Phase 1 query and guide operations

Scalp queries are read-only and use world coordinates by default:

```python
hmh.execute({"action": "nearest_scalp_point", "args": {"point": [0, 0, 1.7]}})
hmh.execute({"action": "nearest_scalp_normal", "args": {"point": [0, 0, 1.7]}})
hmh.execute({"action": "root_to_scalp_distance", "args": {"object_name": "HR_GUIDE_TEST_000"}})
```

Editable legacy `CURVE` guides support `read_guide_points`,
`set_guide_points`, `snap_guide_root`, `snap_guide_roots`, `resample_guide`,
`smooth_guide`, `duplicate_guide`, and `delete_guide`. These operations retain
the guide's role, region, group id, coordinate space, and primary-guide flag.
See `command_schema.json` and `example_commands.json` for argument shapes.

## Human → machine translation

A style document can say:

> Create left and right curtain fringe as separate regions. Keep the center part locked. Use sparse primary guides. Stop after silhouette review.

Codex translates that into calls such as:

```json
{"action":"ensure_region","args":{"name":"FRINGE_L","side":"LEFT","group_id":10}}
{"action":"ensure_region","args":{"name":"FRINGE_R","side":"RIGHT","group_id":11}}
{"action":"create_guides","args":{"region":"FRINGE_L","group_id":10,"guides":[...]}}
{"action":"create_guides","args":{"region":"FRINGE_R","group_id":11,"guides":[...]}}
{"action":"checkpoint","args":{"name":"C_SILHOUETTE_PART","note":"Awaiting human approval"}}
```

This is the core purpose of the extension.

## Machine → human translation

The extension writes:

- `HR_MACHINE_STATE.json` — current semantic scene state
- `HR_VALIDATION.json` — validation results when run from UI
- `HR_MACHINE_LOG.txt` — action log
- `HR_CHECKPOINT_<NAME>.json` — checkpoint snapshots

These live as Blender Text datablocks so MCP/Codex can inspect them without depending on UI state.

## Current validation

0.3 checks:

- scalp exists and is a mesh
- scalp UV availability
- unapplied scalp scale warning
- guide object types
- minimal guide point count
- floating roots and excessive root distance
- invalid, zero-length, and duplicate-point guide geometry
- duplicate semantic names
- semantic region counts
- late-checkpoint-without-guides error

## Native Hair Curves workflow

Legacy `CURVE` guides remain the stable semantic authoring source. Native
Blender Hair Curves are explicit derived objects:

```python
hmh.execute({"action": "convert_guide_to_native", "args": {
    "object_name": "HR_GUIDE_TEST_REGION_000",
    "keep_source": True
}})
hmh.execute({"action": "attach_native_to_scalp", "args": {
    "object_name": "HR_GUIDE_TEST_REGION_000_NATIVE",
    "require_uv": True
}})
hmh.execute({"action": "configure_interpolation", "args": {
    "object_name": "HR_GUIDE_TEST_REGION_000_NATIVE",
    "generated_name": "HR_GENERATED_TEST_REGION",
    "density": 2.0,
    "viewport_amount": 0.05
}})
```

Interpolation creates a separate `GENERATED_HAIR` Curves object; the input
object remains a `NATIVE_GUIDE`. Region conversion, guide grouping, generic part boundaries, and Blender's
native clump/flow/curl/straighten/frizz/smooth/blend node processing are exposed as
separate actions. Interpolation is low-density by default and rebuildable.
No action automatically creates a final production groom.

`configure_interpolation` exposes `follow_surface_normal` explicitly. Keep it
`false` for strict, coherent guide following: roots remain distributed on the
surface while each child preserves the owning guide's direction and shape.
Enable it only when deliberate surface-normal reorientation is wanted.

Snapshots distinguish `NATIVE_GUIDE` from `GENERATED_HAIR` and report original
and evaluated curve/point counts, root attachment, ownership, guide-index
attributes, interpolation settings, and deformation stages.
Validation additionally detects unattached native roots, invalid required UVs,
missing ownership, part/group conflicts, missing interpolation guides, and
lost source guides when preservation was requested. Generated objects with an
empty evaluated result report `INTERPOLATION_EMPTY_OUTPUT`.

## Guide Shaper V0.1

`shape_guide` creates a separate native Hair Curves guide and leaves the artist-authored
source untouched. A rebuild replaces that derived stage, so repeated calls do not stack
modifiers. Blender's native Resample Curve and Set Position nodes execute the macro shape;
the same node graph invokes the native Restore Curve Segment Length asset when
`preserve_length=True`.
Directional values use a fixed frame derived from the source root tangent and nearest scalp
normal (`lateral`, `depth`, and optional world-vertical), not curve tilt or point normals.

```python
hmh.shape_guide(
    object_name="HR_SIDE_L_GUIDE", point_count=16,
    root_lock=1.0, root_zone=0.12,
    lift=0.025, lift_zone=0.20,
    upper={"lateral": -0.025, "depth": 0.005},
    mid={"lateral": -0.070, "depth": 0.020},
    lower={"lateral": -0.035, "depth": 0.035},
    tip={"lateral": 0.010, "depth": 0.050},
    fall=0.10, fall_start=0.25,
    tip_release=0.35, smoothness=0.8, tension=0.45,
    preserve_length=True, rebuild=True,
)
```

V0.1 uses one fixed root frame per shaped object. This is flip-free and predictable for a
single primary guide; multi-curve native inputs share the first curve's frame. Mirroring is
deferred. Falloff modes (`smooth`, `soft`, and `sharp`) adjust the lift/fall response while
retaining smootherstep boundaries. `tension` localizes semantic turns by shaping those
transitions, and `smoothness` pulls that response toward the neutral smooth curve without
moving or averaging authored control points.

## Styler V0.3 FLOW resolution

`styler.py` adds a semantic profile/planning layer without replacing Blender's
Hair Curves algorithms. The built-in `RAZ_ARII_HAIR_V1` profile declares only
the native interpolation, clump, flow, curl, straighten, smooth, blend, and frizz
stages needed by each region. V0.3 adds a native, length-aware `resample_flow`
stage immediately before FLOW. Its `points_per_meter` control supplies enough
longitudinal samples for broad deformation without editing coordinates in
Python. Defaults fill parameters for a declared stage;
an omitted stage is never invented.

FLOW is a rebuildable Geometry Nodes modifier that applies a broad sinusoidal
offset in the native curve-normal direction through a smooth five-control
root-to-tip envelope. Deterministic variation keys from `guide_curve_index`,
keeping strands generated from the same guide coherent. `preserve_length` is
currently advisory: Blender's native Set Position node does not provide an
exact curve-length constraint, and strong FLOW values can therefore stretch
the evaluated curve. Curve-normal/tilt quality also determines side-direction
stability.

```python
hmh.style_capabilities()
hmh.plan_style("RAZ_ARII_HAIR_V1", regions=["FACEFRAME_L", "BACK_MID"])
hmh.apply_style("RAZ_ARII_HAIR_V1", regions=["FACEFRAME_L"], rebuild=True)
```

The same entry points are available through `hmh.execute` as
`style_capabilities`, `style_plan`, and `style_apply`. Planning and discovery
are read-only, return JSON-serializable resolution details, and report missing
regions instead of creating or guessing targets. Profile values are initial
working presets, not final artist-approved ARII values.

## Deliberate omissions

Not implemented yet:

- collision correction
- direct Alembic groom attribute authoring
- Unreal export
- image/reference analysis

Those belong in later helper modules only after the semantic protocol is proven in your actual Blender + MCP setup.

## Why legacy CURVE guides in 0.1?

The helper uses lightweight Blender `CURVE` objects for machine-authored *primary guides*. This keeps point editing and MCP scripting stable across Blender versions. Later, an explicit conversion/interpolation stage can target Blender Hair Curves / Geometry Nodes once your installed Blender version and groom export path are locked.
