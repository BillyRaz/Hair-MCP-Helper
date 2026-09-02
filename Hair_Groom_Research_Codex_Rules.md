# Hair Groom Research & Codex Production Rules

**Purpose:** Research-backed working knowledge for building strand-based
hairstyles in Blender, with later Alembic Groom export to Unreal
Engine.\
**Scope:** This document defines *how hair should be constructed and
validated*. It does **not** define any particular hairstyle. A separate
style-specific `.md` should be created from reference images later.

------------------------------------------------------------------------

## 1. Core Production Principle

Treat a hairstyle as a hierarchy, not as thousands of individually
authored hairs.

**Recommended construction hierarchy:**

1.  Scalp and hairline
2.  Parting / crown / flow field
3.  Primary guide curves and overall silhouette
4.  Major hair regions and masses
5.  Secondary clumps and layering
6.  Dense interpolated hairs
7.  Curl / wave / roll deformation
8.  Controlled irregularity / frizz
9.  Flyaways and breakup
10. Collision, root, silhouette, and export validation

Blender's hair system is explicitly guide-oriented:
`Interpolate Hair Curves` creates dense curves from a smaller set of
guides on a surface, and requires a valid surface and UV map. This
supports a guide-first authoring strategy rather than attempting to
manually author the final strand density.

Source: -
https://docs.blender.org/manual/en/5.1/modeling/geometry_nodes/hair/generation/interpolate_hair_curves.html -
https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/hair/generation/generate_hair_curves.html

------------------------------------------------------------------------

## 2. Non-Negotiable Rules for Codex

### Rule 2.1 --- Never start with dense hair

Codex must establish the hairstyle with a deliberately sparse guide
groom first. Dense/interpolated hairs are a downstream operation.

### Rule 2.2 --- Silhouette before detail

Do not add flyaways, frizz, micro-clumping, or high density until front,
side, back, and 3/4 silhouettes are acceptable.

### Rule 2.3 --- Roots belong to the scalp

Hair roots must remain attached to the intended scalp surface. Never
solve a styling problem by allowing roots to float.

Blender provides `Attach Hair Curves to Surface`, including root
snapping, surface-normal alignment, UV attachment, and blending
deformation along a curve.

Source: -
https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/hair/utility/attach_hair_curves_to_surface.html

### Rule 2.4 --- Preserve partings

A part is a structural boundary. Guides and later clumps must not
casually cross it.

Houdini's grooming documentation explicitly describes parting barriers
that prevent interpolation and grooming operations from being influenced
by guides across the opposite side of a part. XGen workflows similarly
rely on region/parting maps.

Sources: - https://www.sidefx.com/docs/houdini/fur/groom.html -
https://www.classcentral.com/course/youtube-introduction-to-xgen-quick-start-guide-127595

### Rule 2.5 --- Use regions

At minimum, reason about: - hairline / fringe - top - crown - left
temple - right temple - left side - right side - back - nape

A style may add dedicated regions for ponytails, buns, braids,
sidelocks, face-framing strands, etc.

### Rule 2.6 --- Large forms before small forms

The automation should work in passes:

**Primary:** silhouette, part, major direction, length, volume.\
**Secondary:** layers, major clumps, face framing, overlap.\
**Tertiary:** breakup, small clumps, loose hairs, flyaways.

### Rule 2.7 --- Randomness must be controlled

Do not apply uniform random noise to the entire groom. Randomness should
be masked by region and usually become stronger away from roots.

### Rule 2.8 --- Preserve useful curve length

When smoothing, clumping, curling, blending, or adding frizz, prefer
operations that preserve strand length unless a deliberate
haircut/length change is intended.

Blender's Smooth, Clump, Blend, Straighten and Frizz hair operations
expose length-preservation controls.

Sources: -
https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/hair/deformation/smooth_hair_curves.html -
https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/hair/deformation/blend_hair_curves.html -
https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/hair/deformation/straighten_hair_curves.html -
https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/hair/deformation/frizz_hair_curves.html

### Rule 2.9 --- Never destroy editable guides unnecessarily

Keep a non-destructive/editable guide representation until the groom is
approved. Dense render hair is derived data.

### Rule 2.10 --- Do not optimize for Unreal until the style works

First solve the groom artistically in Blender. Export grouping, guide
attributes, cards and LOD generation come after the hairstyle passes
visual validation.

------------------------------------------------------------------------

## 3. Scalp Preparation

A reliable scalp is foundational.

### Requirements

-   Scalp should cover every region where roots may exist.
-   It should conform closely to the character head.
-   Avoid roots on forehead, ears, neck, or exposed skin unless
    intentional.
-   Keep a stable UV map.
-   Keep transforms predictable and consistent.
-   Preserve the scalp object used by the hair system.
-   Define or derive masks for hairline and regional boundaries.

Blender interpolation and attachment operations rely on the surface and
Surface UV Map.

Sources: -
https://docs.blender.org/manual/en/5.1/modeling/geometry_nodes/hair/generation/interpolate_hair_curves.html -
https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/hair/utility/attach_hair_curves_to_surface.html

------------------------------------------------------------------------

## 4. Hairline, Parting, Crown, and Flow

These should be established before dense hair.

### Hairline

The hairline determines where visible roots begin and strongly affects
realism. It should be treated as a designed boundary rather than a
random density falloff.

### Parting

A part should control: - root direction - which guides may influence
which side - clump grouping - interpolation boundaries where necessary

Blender's interpolation system can separate influence by mesh islands,
and guide maps/group IDs can constrain which guides belong together.

Sources: -
https://docs.blender.org/manual/en/3.6/modeling/geometry_nodes/hair/generation/interpolate_hair_curves.html -
https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/hair/guides/create_guide_index_map.html

### Crown / whorl

Treat the crown as a directional source. Guides around it should
transition coherently rather than all pointing in a single global
direction.

### Flow rule

Adjacent guides should usually produce a readable flow field. Abrupt
direction changes should correspond to an intentional style feature,
part, curl, tie, braid, or clump.

------------------------------------------------------------------------

## 5. Guide Placement

Guide curves describe the hairstyle.

### Sparse first pass

Use only enough guides to communicate: - silhouette - major direction -
length - part - major clumps - major layers

### Add guides only where needed

Increase guide density around: - bangs/fringe - hairline - strong
curvature - ponytail/bun transitions - short layers - complex overlap -
asymmetric features - areas where interpolation fails to preserve the
desired shape

Houdini's Guide Groom workflow follows the same principle: new guides
can be planted by interpolating orientation and length from surrounding
guides.

Source: - https://www.sidefx.com/docs/houdini/fur/groom.html

------------------------------------------------------------------------

## 6. Guide Maps and Hair Groups

Blender's `Create Guide Index Map` stores the nearest guide relationship
in `guide_curve_index`. It can use `Group ID` so curves only choose
guides from the same group.

This is useful for preventing: - left/right part contamination - bangs
being clumped into crown hair - ponytail strands using unrelated
guides - nape hairs being influenced by long back guides

Source: -
https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/hair/guides/create_guide_index_map.html

**Codex rule:** Prefer explicit groups for structurally different hair
masses instead of relying entirely on nearest-distance behavior.

------------------------------------------------------------------------

## 7. Interpolation and Density

`Interpolate Hair Curves` generates dense hairs from guides and
supports: - guide count/influence - distance to guides - Poisson
distribution - density - density masks - texture masks - viewport
density - seed - surface-normal following

Source: -
https://docs.blender.org/manual/en/3.6/modeling/geometry_nodes/hair/generation/interpolate_hair_curves.html

### Production rule

Use low viewport density during styling. Increase density only for
validation/render/export stages.

### Density should not be uniform by default

Potentially lower density: - at exposed part lines - around
intentionally thin edges - in sparse flyaway groups

Potentially higher density: - inside major masses - where coverage is
needed - where card generation later requires sufficient source
information

------------------------------------------------------------------------

## 8. Clumping

Realistic hair should not read as independent uniformly distributed
lines.

Blender's `Clump Hair Curves` supports: - guide-driven clumps -
strength - root-to-tip shape - tip spread - random clump offset -
distance falloff - thresholds - length preservation

Source: -
https://docs.blender.org/manual/en/5.1/modeling/geometry_nodes/hair/guides/clump_hair_curves.html

### Clump hierarchy

Use clumping in levels:

1.  **Primary clumps** --- large readable masses.
2.  **Secondary clumps** --- breakup within primary masses.
3.  **Tertiary breakup** --- subtle variation and separation.

### Critical parting rule

Never let automatic clump assignment pull hair across a deliberate part.
Use group IDs, masks, separate guide maps, or separate regions.

------------------------------------------------------------------------

## 9. Smoothing and Blending

### Smooth

Use smoothing to remove accidental kinks while retaining the designed
path.

Blender supports iteration count, shape influence, locked tips, and
preserved length.

Source: -
https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/hair/deformation/smooth_hair_curves.html

### Blend

`Blend Hair Curves` averages neighboring curve shapes and can help
harmonize transitions between neighboring masses.

Source: -
https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/hair/deformation/blend_hair_curves.html

**Rule:** Do not over-smooth. A technically smooth groom can become
lifeless if all intentional separation is erased.

------------------------------------------------------------------------

## 10. Straight Hair

For straight hairstyles: - establish clean flow with guides - maintain
subtle curvature around the skull - avoid perfectly parallel strands
everywhere - preserve layer differences - add small controlled breakup
after the main shape is correct

Blender's `Straighten Hair Curves` can move curves toward the root-tip
line while preserving length.

Source: -
https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/hair/deformation/straighten_hair_curves.html

------------------------------------------------------------------------

## 11. Wavy and Curly Hair

Blender's `Curl Hair Curves` provides: - curl start - radius - start/end
radius factors - frequency - per-curve random offset - subdivision -
guide grouping - length preservation

Source: -
https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/hair/guides/curl_hair_curves.html

### Rules

-   Curl should normally be layered on top of a correct large-scale
    guide shape.
-   Do not use curl deformation to solve a bad silhouette.
-   Vary curl phase and strength subtly.
-   Root areas often need less curl deformation than lengths/tips
    depending on the reference.
-   Different regions may require different curl settings.

------------------------------------------------------------------------

## 12. Rolls, Buns, and Rolled Forms

Blender's `Roll Hair Curves` can roll curves from the tips and exposes
roll length, radius, depth, taper, direction, orientation randomness,
and shape retention.

Source: -
https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/hair/deformation/roll_hair_curves.html

For buns or rolled sections: - first define the trajectory and
attachment of the mass - then create the rolled form - preserve readable
overlap - avoid making the entire bun a mathematically perfect spiral -
reserve loose strands for a later pass

------------------------------------------------------------------------

## 13. Frizz and Flyaways

Blender's `Frizz Hair Curves` offsets curve points using randomized
vectors and can preserve length.

Source: -
https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/hair/deformation/frizz_hair_curves.html

Houdini similarly treats frizz as point offsets along guides with noise
varying along the strand.

Source: -
https://www.sidefx.com/docs/houdini/shelf/sop_groom_guideprocess_frizz.html

### Rule

Frizz is a finishing layer, not the hairstyle.

### Flyaways

Prefer a dedicated sparse flyaway group rather than heavily disturbing
the main groom. Flyaways should reinforce natural breakup without
destroying the designed silhouette.

------------------------------------------------------------------------

## 14. Bangs / Fringe / Face-Framing Hair

These areas need more direct artistic control than bulk back hair.

Rules: - isolate them as their own guide/group region when practical -
preserve the intended forehead opening - use extra guides around strong
direction changes - evaluate against eyebrows, eyes, cheekbones, jaw,
and ears - prevent interpolation from pulling them backward into
crown/side groups - treat asymmetrical strands intentionally rather than
as random noise

A style-specific document should specify exact fringe shape and
reference landmarks.

------------------------------------------------------------------------

## 15. Ponytails

Treat a ponytail as multiple connected systems:

1.  scalp hair flowing toward tie
2.  tie/constraint region
3.  ponytail body
4.  secondary clumps
5.  loose/escaped hairs

Do not simply point all scalp hairs at one point and call the result
finished. The scalp section still needs believable surface flow and
volume.

------------------------------------------------------------------------

## 16. Collision and Penetration

Codex must validate for: - guide roots outside the scalp - strands
entering the skull - strands penetrating ears - unwanted face
penetration - neck/shoulder penetration - extreme self-crossing -
floating clumps

Use deterministic correction where possible. Do not hide structural
penetration by increasing density.

------------------------------------------------------------------------

## 17. Automation Strategy for Codex

Codex should operate through **Blender Python and/or MCP**, but use
scripts for repeatable geometry operations.

Preferred architecture:

``` text
Reference Style Specification
        ↓
Codex reads research rules
        ↓
Create/validate scalp
        ↓
Create named hair regions
        ↓
Create primary guides
        ↓
Shape guides
        ↓
Create guide maps/groups
        ↓
Interpolate
        ↓
Clump
        ↓
Curl/wave/straighten as required
        ↓
Secondary breakup
        ↓
Flyaways
        ↓
Validation
        ↓
Human review
        ↓
Alembic export
```

### Automation rule

Codex must stop at logical checkpoints rather than making hundreds of
destructive changes without inspection.

Recommended checkpoints:

-   **CHECKPOINT A:** scalp + regions
-   **CHECKPOINT B:** primary guides only
-   **CHECKPOINT C:** silhouette and part
-   **CHECKPOINT D:** interpolated groom
-   **CHECKPOINT E:** clumps/deformation
-   **CHECKPOINT F:** tertiary/flyaway pass
-   **CHECKPOINT G:** Unreal export validation

------------------------------------------------------------------------

## 18. Suggested Procedural Functions

The future Blender helper layer should expose small composable
operations rather than one `make_hair()` function.

Examples:

``` python
validate_scalp()
create_hair_region()
create_part_boundary()
create_guide()
resample_guides()
smooth_guides()
attach_roots_to_scalp()
create_guide_map()
interpolate_guides()
apply_clumping()
apply_curl()
apply_frizz()
apply_straightening()
create_flyaway_group()
validate_root_attachment()
validate_head_intersections()
validate_curve_lengths()
prepare_unreal_groups()
export_groom_alembic()
```

Codex should compose these according to the style specification.

------------------------------------------------------------------------

## 19. Naming Rules

Use predictable semantic names.

Example:

``` text
HR_SCALP
HR_GUIDES_TOP
HR_GUIDES_FRINGE
HR_GUIDES_SIDE_L
HR_GUIDES_SIDE_R
HR_GUIDES_BACK
HR_GUIDES_NAPE
HR_GUIDES_PONYTAIL
HR_RENDER_MAIN
HR_FLYAWAYS
```

Every curves object intended for Epic's Send to Unreal workflow should
have a unique name. Epic warns that duplicate curves/particle-system
names can cause Unreal assets to be overwritten.

Source: -
https://github.com/EpicGames/BlenderTools/blob/main/docs/send2ue/asset-types/groom.md

------------------------------------------------------------------------

## 20. Unreal Alembic Groom Requirements

Unreal's Groom system consumes strand data through Alembic using Epic's
naming/schema conventions.

Useful supported attributes include: - `groom_guide` -
`groom_group_id` - `groom_root_uv` - `groom_id` - `groom_color` -
`groom_closest_guides` - `groom_guide_weights`

Unreal can generate guides automatically when explicit guide data is not
supplied. Root UV is optional and can also be generated by Unreal.

Source: -
https://dev.epicgames.com/documentation/unreal-engine/using-alembic-for-grooms-in-unreal-engine?lang=en-US

### Unreal project prerequisites

Enable: - **Alembic Groom Importer** - **Groom**

For appropriate bound groom rendering, Epic also documents **Support
Compute Skin Cache**.

Sources: -
https://dev.epicgames.com/documentation/unreal-engine/setting-up-a-project-for-grooms-in-unreal-engine?lang=en-US -
https://dev.epicgames.com/documentation/unreal-engine/hair-simulation-and-rendering-quick-start-guide-in-unreal-engine

------------------------------------------------------------------------

## 21. Blender → Unreal Tooling

Epic's Send to Unreal tooling supports Blender Curves objects surfaced
to meshes. It converts the curves internally as needed for Alembic groom
export and can create post-import groom assets such as bindings.

Source: -
https://github.com/EpicGames/BlenderTools/blob/main/docs/send2ue/asset-types/groom.md

A separate community Groom Exporter also targets modern Blender Curves →
Unreal Groom schema and exposes attributes such as root UV, widths,
guides, IDs, closest guides, and guide weights. Treat this as optional
tooling rather than a core dependency.

Source: - https://turbocheke.gumroad.com/l/Groomexporter

------------------------------------------------------------------------

## 22. Unreal Import Validation

On import Unreal exposes per-group: - curve count - guide count - curve
decimation - vertex decimation - guide type - interpolation settings

Source: -
https://dev.epicgames.com/documentation/en-us/unreal-engine/importing-grooms-into-unreal-engine

Validate: - correct scale - correct orientation - correct position -
correct group separation - reasonable curve/guide count - expected
width - correct binding - animation deformation - no root drift

------------------------------------------------------------------------

## 23. Cards and Platform Strategy

Unreal supports strand, card, and mesh groom representations. Cards and
groom meshes are supported across platforms, while strand rendering is
more restricted and expensive.

Sources: -
https://dev.epicgames.com/documentation/unreal-engine/groom-platform-support-in-unreal-engine?lang=en-US -
https://dev.epicgames.com/documentation/unreal-engine/groom-scalability-and-performance-with-unreal-engine?lang=en-US

The Hair Card Generator can create card representations/LODs from a
groom.

Source: -
https://dev.epicgames.com/documentation/unreal-engine/creating-hair-cards-and-lods-using-hair-card-generator

**Production rule:** Build a clean source groom first. Treat cards as an
optimized downstream representation, not as a reason to compromise the
source hairstyle.

------------------------------------------------------------------------

## 24. Hair Card Generator Preparation

Epic's current Hair Card Generator workflow supports card groups and
Dataflow-driven card generation.

Potential groom grouping should therefore be planned semantically, for
example: - core/main mass - front/fringe - sides - back - short hairs -
flyaways

Exact grouping should be chosen per hairstyle and validated against the
current Unreal Hair Card Generator workflow.

Source: -
https://dev.epicgames.com/documentation/unreal-engine/creating-hair-cards-and-lods-using-hair-card-generator

------------------------------------------------------------------------

## 25. Performance Rules

Do not judge a groom only at maximum strand density.

Test: - reduced viewport density - Unreal curve decimation - Unreal
vertex decimation - strand LOD - card LOD - target platform

Epic explicitly recommends cards/meshes where strands are unavailable or
too expensive.

Source: -
https://dev.epicgames.com/documentation/unreal-engine/groom-scalability-and-performance-with-unreal-engine?lang=en-US

------------------------------------------------------------------------

## 26. Human Review Rules

Automation should never automatically mark a hairstyle complete.

Human review should inspect at minimum:

### Front

-   hairline
-   part
-   fringe
-   facial framing
-   symmetry/asymmetry

### 3/4

-   temple volume
-   crown volume
-   layer transitions
-   silhouette

### Side

-   forehead projection
-   skull clearance
-   ear relationship
-   back-of-head volume
-   length

### Back

-   crown flow
-   center/side part continuation
-   layer structure
-   nape
-   overall width

### Top

-   parting
-   crown/whorl
-   root flow
-   unwanted bald gaps

------------------------------------------------------------------------

## 27. Failure Modes Codex Must Detect

### Technical

-   floating roots
-   missing surface attachment
-   missing scalp UV
-   invalid or duplicated object names
-   wrong transforms
-   excessive control points
-   insufficient curve resolution
-   cross-part interpolation
-   broken guide maps
-   accidental destructive conversion

### Artistic

-   helmet hair
-   uniform spaghetti strands
-   perfectly identical curls
-   over-clumping
-   over-frizzing
-   excessive symmetry
-   flat crown
-   missing skull clearance
-   random flyaways before primary shape is solved
-   bangs merged into unrelated hair regions
-   silhouette changing drastically after interpolation

### Unreal

-   scale mismatch
-   orientation mismatch
-   group mismatch
-   excessive strand count
-   binding failure
-   width mismatch
-   poor card conversion
-   unsuitable strand-only target-platform strategy

------------------------------------------------------------------------

## 28. Codex Decision Rules

When uncertain:

1.  Preserve the existing groom.
2.  Make a duplicate/version before destructive changes.
3.  Prefer fewer, better guides over more uncontrolled guides.
4.  Prefer region masks/groups over global modifiers.
5.  Prefer deterministic operations before randomness.
6.  Do not add detail to hide a bad silhouette.
7.  Do not change a reference-defined style feature without approval.
8.  Ask for human visual review at checkpoints.
9.  Keep style-specific values outside this research document.
10. Record successful parameters into the style-specific `.md`, not into
    universal rules unless they generalize.

------------------------------------------------------------------------

## 29. Style-Specific MD --- Future Step

For each actual reference hairstyle, create a separate file such as:

``` text
styles/
  STYLE_LongLayered_CurtainBangs.md
```

It should contain:

-   reference image IDs/paths
-   front/side/back observations
-   part type and position
-   hairline observations
-   crown flow
-   length landmarks
-   volume landmarks
-   fringe/bangs construction
-   side construction
-   back construction
-   layer structure
-   curl/wave profile
-   primary clumps
-   secondary breakup
-   flyaway character
-   asymmetry
-   guide-region plan
-   suggested guide count by region
-   Blender operation plan
-   expected checkpoints
-   uncertainties hidden by the reference
-   manual decisions required

**Do not invent hidden geometry from a single reference.** Mark
uncertain back/side information explicitly and ask for another reference
or human direction where it materially changes the style.

------------------------------------------------------------------------

## 30. Research-Derived Workflow Summary

``` text
REFERENCE / STYLE SPEC
          ↓
       SCALP
          ↓
HAIRLINE + PART + CROWN
          ↓
    REGIONAL GROUPS
          ↓
   PRIMARY GUIDES
          ↓
  SILHOUETTE REVIEW
          ↓
 ADD NECESSARY GUIDES
          ↓
 GUIDE MAPS / BOUNDARIES
          ↓
     INTERPOLATION
          ↓
   PRIMARY CLUMPING
          ↓
SECONDARY CLUMPING/LAYERS
          ↓
 CURL/WAVE/STRAIGHTEN
          ↓
 SMOOTH + CONTROLLED BREAKUP
          ↓
   FLYAWAY GROUP
          ↓
 COLLISION/ROOT VALIDATION
          ↓
      HUMAN REVIEW
          ↓
   ALEMBIC GROOM EXPORT
          ↓
      UNREAL IMPORT
          ↓
 BINDING / LOD / VALIDATION
          ↓
  HAIR CARD GENERATION
```

------------------------------------------------------------------------

## 31. Source Priority

When Codex or a human needs to resolve a technical conflict, use this
order:

1.  Current Blender official manual
2.  Current Unreal Engine official documentation
3.  Epic BlenderTools / Send to Unreal documentation
4.  SideFX / Autodesk professional grooming documentation for
    transferable grooming principles
5.  Reputable production tutorials
6.  Community/forum workarounds only when official workflows do not
    solve the issue

Do not treat an old tutorial's exact UI sequence or exporter workaround
as a universal rule when current official documentation differs.

------------------------------------------------------------------------

## 32. Current Research Conclusion

The most practical automation target is **AI-assisted procedural
grooming**, not AI hair generation.

Codex can reasonably automate: - scalp/region setup - guide creation
from explicit specifications - curve placement and resampling -
smoothing - interpolation - guide maps - clumping - curl/wave/frizz
modifiers - grouping - validation - export preparation

Human visual judgment remains responsible for: - likeness to reference -
silhouette quality - appealing flow - intentional asymmetry - face
framing - final clump placement - resolving ambiguous hidden portions of
a hairstyle

The system should therefore be designed as a **Codex → Blender → human
review loop**, not a one-shot generator.
