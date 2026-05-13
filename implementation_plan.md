# Implementation Plan

## 1. Project Definition

This project is not a generic floor-plan converter.
It is a pipeline for converting Japanese incident-site floor plans into simple 3D explanatory models for leakage and defect communication.

Primary product goal:

- Ingest a floor plan or scanned drawing.
- Recover enough spatial structure to explain the incident.
- Attach leakage and damage semantics to the scene.
- Produce customer-facing 3D views and packaged outputs.

Non-goals for the current phase:

- Full BIM authoring
- Construction-grade geometric precision
- Fully automatic, no-human-review processing

## 2. Current State

The current codebase already covers part of the geometry pipeline:

- PDF/image floor-plan ingestion
- Wall extraction
- Room detection and refinement
- STEP export
- IFC export

Main gaps:

- No domain model for leakage incidents
- No manual correction workflow
- No presentation-oriented 3D annotation layer
- Weak handling for real-world Japanese field drawings
- No end-to-end product workflow for customer explanation

## 3. Delivery Strategy

The upgrade should be executed in three product stages:

1. Stabilize the geometry pipeline
2. Add incident semantics and correction workflow
3. Build presentation and delivery outputs

This plan assumes incremental delivery with verification at every step.

## 4. Phase Breakdown

### Phase 1. Domain and Data Contract Stabilization

Goal:
Define the system around incident explanation, not just geometry extraction.

Target outcomes:

- Standardized typed payloads between pipeline stages
- Incident-centered metadata model
- Clear separation between geometry, incident data, and exports

Implementation tasks:

1. Create a new `domain/` package.
2. Add models for:
   - `LeakCase`
   - `FloorPlanAsset`
   - `DamageZone`
   - `InspectionNote`
   - `SceneAnnotation`
3. Add a shared pipeline payload schema:
   - `IngestPayload`
   - `GeometryPayload`
   - `ScenePayload`
   - `ExportPayload`
4. Refactor `out/result.meta.json` generation to include incident metadata and processing metadata separately.
5. Normalize coordinates, units, and identifiers across parser/export steps.

Suggested file additions:

- `domain/models.py`
- `domain/schemas.py`
- `pipeline/contracts.py`

Suggested refactor targets:

- `parser/room_export.py`
- `parser/export_step.py`
- `parser/export_ifc.py`

Validation:

- Schema validation tests for 3 sample incident cases
- Stable JSON snapshots for intermediate payloads

Exit criteria:

- Every major step reads and writes a documented payload shape
- Incident metadata can flow from input to final export metadata

### Phase 2. Ingestion and Drawing-Type Routing

Goal:
Make the intake path robust for real Japanese field drawings.

Target outcomes:

- Better routing between vector PDF and image PDF
- Better preprocessing for noisy scans
- Deterministic intake diagnostics

Implementation tasks:

1. Upgrade PDF classification:
   - vector-first
   - image-first
   - hybrid
2. Add preprocessing for image plans:
   - deskew
   - denoise
   - contrast normalization
   - border cleanup
3. Add ingest diagnostics:
   - source type
   - page size
   - detected rotation
   - rasterization scale
   - confidence
4. Persist ingest debug artifacts under a structured naming rule.

Suggested refactor targets:

- `parser/pdf_type.py`
- `parser/pdf_vector.py`
- `parser/image_outline.py`

Validation:

- 10 representative Japanese plan samples
- Classification accuracy by document type
- Reduced wall extraction failure on skewed scans

Exit criteria:

- Intake stage produces a reliable routing decision and debug report

### Phase 3. Geometry Extraction Hardening

Goal:
Raise the stability of wall, room, and opening extraction.

Target outcomes:

- More reliable wall graph
- Reduced false room splits/merges
- Better door/opening inference

Implementation tasks:

1. Harden line extraction and merge rules.
2. Add confidence scoring to walls and openings.
3. Improve wall fill and boundary closure.
4. Reduce over-reliance on axis-aligned assumptions where possible.
5. Distinguish:
   - structural wall candidate
   - partition candidate
   - uncertain line
6. Separate door inference from export logic and move it into geometry refinement.

Suggested refactor targets:

- `parser/line_refine.py`
- `parser/wall_fill.py`
- `parser/room_detect.py`
- `parser/rooms_pipeline.py`
- `parser/export_step.py`

Validation:

- Regression set with expected walls/rooms JSON
- Per-sample review of false positives and false negatives

Exit criteria:

- Door and room inference no longer depend on exporter-side fallback logic

### Phase 4. Space Semantics and Japanese Layout Heuristics

Goal:
Turn extracted polygons into meaningful explanatory spaces.

Target outcomes:

- Better room-type classification
- Adjacency graph useful for leakage explanation
- Explicit handling of wet-area spaces

Implementation tasks:

1. Expand room categories:
   - `ldk`
   - `bedroom`
   - `corridor`
   - `bathroom`
   - `toilet`
   - `kitchen`
   - `balcony`
   - `shaft`
   - `closet`
   - `unknown`
2. Add adjacency graph outputs:
   - room-to-room
   - room-to-opening
   - wet-area proximity
3. Add uncertainty labels for ambiguous room types.
4. Preserve a distinction between inferred semantics and verified semantics.

Suggested refactor targets:

- `parser/room_detect.py`
- `parser/rooms_pipeline.py`

Validation:

- Manual review on labeled samples
- Confusion matrix for room-type inference

Exit criteria:

- Output scene has interpretable spaces relevant to leakage communication

### Phase 5. Incident Semantics Layer

Goal:
Represent leakage incidents directly in the model.

Target outcomes:

- Leakage source markers
- Damage areas by surface type
- Explanation-ready incident overlays

Implementation tasks:

1. Add incident entities to scene payload:
   - source point
   - suspected path
   - damaged surfaces
   - severity
   - note anchors
2. Add support for:
   - ceiling damage
   - wall damage
   - floor damage
   - multi-room spread
3. Link site photos and notes to scene coordinates or room ids.
4. Keep all incident annotations editable and versioned.

Suggested file additions:

- `scene/incident_mapper.py`
- `scene/annotations.py`

Validation:

- Synthetic incident cases mapped onto sample plans
- JSON round-trip with annotations preserved

Exit criteria:

- A leakage case can be described inside the scene model, not just next to it

### Phase 6. Manual Correction Workflow

Goal:
Accept that auto-detection will fail and design for efficient correction.

Target outcomes:

- Human-correctable extraction
- Faster operational turnaround
- Trustworthy customer outputs

Implementation tasks:

1. Add a correction editor MVP:
   - edit wall segments
   - merge/split rooms
   - move openings
   - place leak source
   - paint damage zones
2. Save corrections as delta data, not destructive overwrite.
3. Re-run downstream scene build after correction.
4. Track auto vs human-corrected state.

Suggested architecture:

- `review/` or `editor/` package for correction logic
- correction JSON patch layer

Validation:

- Operator can correct a failed sample within 3 minutes
- Rebuild after correction is deterministic

Exit criteria:

- The product is usable even when automation is imperfect

### Phase 7. Explanation-Oriented 3D Scene Builder

Goal:
Produce scenes optimized for explanation, not CAD fidelity alone.

Target outcomes:

- Structured 3D scene payload
- Colored damage overlays
- Camera presets for customer explanation

Implementation tasks:

1. Introduce a scene builder layer separate from STEP/IFC export.
2. Build room, wall, opening, and damage meshes as logical scene objects.
3. Add presentation metadata:
   - labels
   - annotation anchors
   - recommended camera views
   - section/isolation presets
4. Keep STEP/IFC exporters as secondary outputs, not the primary scene model.

Suggested file additions:

- `scene/builder.py`
- `scene/view_presets.py`
- `scene/types.py`

Validation:

- Open the same case in a viewer and confirm explanation flow is human-readable

Exit criteria:

- The canonical output becomes an explanation scene, not just CAD exports

### Phase 8. Customer Delivery Outputs

Goal:
Package outputs for actual customer communication.

Target outcomes:

- Customer-ready still images
- Overlay floor-plan visuals
- Incident summary report
- Scene export package

Implementation tasks:

1. Generate:
   - incident summary JSON
   - floor-plan overlay PNG
   - labeled 3D snapshots
   - report-ready asset bundle
2. Add view presets:
   - overall layout
   - incident room focus
   - damage spread view
3. Define an export bundle structure for each case.

Suggested file additions:

- `reporting/package_case.py`
- `reporting/render_summary.py`

Validation:

- One-click generation for a sample incident package

Exit criteria:

- A non-technical customer can understand the issue from the generated outputs

### Phase 9. Observability and Quality Control

Goal:
Make failures visible and improve the system with evidence.

Target outcomes:

- Structured logs
- Stage timing
- Confidence and error reports
- Regression-friendly artifacts

Implementation tasks:

1. Add per-stage logs with consistent IDs.
2. Record:
   - runtime
   - input type
   - confidence
   - failure reason
   - correction count
3. Separate debug artifacts from final outputs.
4. Add a case manifest per run.

Suggested file additions:

- `pipeline/logging.py`
- `pipeline/run_manifest.py`

Validation:

- Failed runs are diagnosable without manual guesswork

Exit criteria:

- The team can see where and why the pipeline fails

### Phase 10. Test and Release Discipline

Goal:
Move from experimentation to controlled delivery.

Target outcomes:

- Regression protection
- Stable sample corpus
- Release confidence

Implementation tasks:

1. Add tests for:
   - schema validation
   - PDF routing
   - wall extraction
   - room extraction
   - scene payload generation
   - STEP/IFC smoke export
2. Create a small benchmark corpus under `samples/`.
3. Add snapshot-based result checks for key JSON outputs.
4. Define release criteria for MVP and v1.

Suggested structure:

- `tests/test_contracts.py`
- `tests/test_ingest.py`
- `tests/test_geometry.py`
- `tests/test_scene.py`
- `tests/test_exports.py`

Validation:

- All critical flows pass on the benchmark corpus before release

Exit criteria:

- The pipeline is measurable and regression-resistant

## 5. Recommended 4-Week Execution Plan

### Week 1

Focus:

- Phase 1
- Phase 2 foundation

Deliverables:

- domain models
- pipeline contracts
- input classification cleanup
- structured metadata output

Verification:

- schema tests
- 3 sample-case contract snapshots

### Week 2

Focus:

- Phase 3
- Phase 4 foundation

Deliverables:

- stronger geometry refinement
- door inference moved out of exporter fallback
- adjacency graph
- first room semantic pass

Verification:

- regression comparison on sample plans
- manual review for 10 drawings

### Week 3

Focus:

- Phase 5
- Phase 6 MVP

Deliverables:

- leakage incident scene model
- manual correction data format
- correction workflow prototype

Verification:

- operator correction time trial
- annotation persistence tests

### Week 4

Focus:

- Phase 7
- Phase 8
- Phase 9 and 10 baseline

Deliverables:

- explanation scene builder
- customer package generator
- structured logs
- initial automated test suite

Verification:

- end-to-end run from plan input to customer package
- smoke export of STEP and IFC

## 6. Immediate Coding Priority

Start here first:

1. `domain/models.py`
2. `pipeline/contracts.py`
3. refactor `parser/room_export.py`
4. refactor `parser/export_step.py`
5. refactor `parser/export_ifc.py`

Reason:
Without a proper data contract, every later improvement will stay brittle.

## 7. Boundaries

Do not do these early:

- building a polished frontend first
- chasing IFC perfection before scene semantics
- forcing full automation without correction tools
- expanding into full BIM scope

## 8. Success Definition

The MVP is successful when:

- a Japanese floor plan can be ingested reliably,
- the operator can correct extraction quickly,
- leakage/damage semantics can be attached to the scene,
- a customer-facing explanatory 3D package can be produced consistently.
