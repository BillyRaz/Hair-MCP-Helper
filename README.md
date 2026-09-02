# Hair MCP Helper 0.1

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

From a Blender Python execution endpoint:

```python
import hair_mcp_helper as hmh

result = hmh.execute({"action": "init"})
print(result)
```

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

0.1 checks:

- scalp exists and is a mesh
- scalp UV availability
- unapplied scalp scale warning
- guide object types
- minimal guide point count
- approximate guide-root distance to scalp
- semantic region counts
- late-checkpoint-without-guides error

## Deliberate omissions in 0.1

Not implemented yet:

- Geometry Nodes hair interpolation
- automatic root snapping
- part-boundary curve generation
- clumping/curl/frizz graph construction
- collision correction
- direct Alembic groom attribute authoring
- Unreal export
- image/reference analysis

Those belong in later helper modules only after the semantic protocol is proven in your actual Blender + MCP setup.

## Why legacy CURVE guides in 0.1?

The helper uses lightweight Blender `CURVE` objects for machine-authored *primary guides*. This keeps point editing and MCP scripting stable across Blender versions. Later, an explicit conversion/interpolation stage can target Blender Hair Curves / Geometry Nodes once your installed Blender version and groom export path are locked.
