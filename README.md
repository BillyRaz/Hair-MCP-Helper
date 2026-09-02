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
bundled clump/curl/straighten/frizz/smooth/blend node assets are exposed as
separate actions. Interpolation is low-density by default and rebuildable.
No action automatically creates a final production groom.

Snapshots distinguish `NATIVE_GUIDE` from `GENERATED_HAIR` and report original
and evaluated curve/point counts, root attachment, ownership, guide-index
attributes, interpolation settings, and deformation stages.
Validation additionally detects unattached native roots, invalid required UVs,
missing ownership, part/group conflicts, missing interpolation guides, and
lost source guides when preservation was requested. Generated objects with an
empty evaluated result report `INTERPOLATION_EMPTY_OUTPUT`.

## Deliberate omissions

Not implemented yet:

- collision correction
- direct Alembic groom attribute authoring
- Unreal export
- image/reference analysis

Those belong in later helper modules only after the semantic protocol is proven in your actual Blender + MCP setup.

## Why legacy CURVE guides in 0.1?

The helper uses lightweight Blender `CURVE` objects for machine-authored *primary guides*. This keeps point editing and MCP scripting stable across Blender versions. Later, an explicit conversion/interpolation stage can target Blender Hair Curves / Geometry Nodes once your installed Blender version and groom export path are locked.
