# Benji Task Guide — Sim Morphology, CAD, and Spatial Evaluation

This is a study guide for Benji's side of Prosthesis-RL SIM. Use it to answer technical questions about what you built, why it works, which files matter, and how the pieces connect.

## One-Sentence Summary

I built the design and morphology layer: it turns a perceived ADL problem into candidate simulated assistive-limb designs, validates those designs spatially and mechanically, exports per-link geometry/MJCF assets for MuJoCo, runs candidate comparison over verifier feedback, and produces a rationale for the winning design.

## Product Context

The project is now **simulation-first**. The final artifact is not a physical prosthesis. The final artifact is:

- a runnable simulation,
- a simulated assistive-limb morphology,
- a controller or policy rollout,
- metrics from evaluation,
- and replay/video evidence.

That matters because my CAD work is not about claiming a manufacturable medical device. It is about creating valid geometry and kinematic structure for simulation, viewer rendering, and evaluation.

## My Ownership

From `docs/WORK_SPLIT.md`, my responsibilities are:

- **Sim morphology generation:** create candidate limb structures with links, joints, limits, actuators, masses, and collision geometry.
- **AI design reasoning:** turn the problem/task plus sim feedback into better design parameters.
- **Spatial reasoning:** check reachability, workspace coverage, mount frame, joint limits, and collision-aware constraints.
- **Simulation geometry:** generate MJCF/URDF/mesh assets as simulation inputs.
- **Empirical evaluation analysis:** compare candidates using reward distributions and failure modes.
- **Validation gates:** reject impossible or unstable designs before they reach the sim.

## High-Level Architecture

```text
Perception / task input
        |
        v
ProblemSpec
        |
        v
RequirementsAgent
  action-specific engineering brief
        |
        v
DesignAgent
  DesignParams candidates
        |
        v
CadBridge / MJCF builder
  per-link STL + MuJoCo XML
        |
        v
Verifier
  SimFeedback / EvalResult
        |
        v
DesignAgent.compare()
  winning candidate + rationale report
```

The important idea: the design layer does not just output a mesh. It outputs a **structured kinematic design** that the sim, controller, CAD bridge, and evaluator can all understand.

## Core Data Contracts

### `ProblemSpec`

Defined in `prosthesis_rl/contracts/schemas.py`.

This is the input from perception. It contains:

- `tasks`: ADL task categories and pain points.
- `constraints`: ROM, residual strength, and grip capacity.
- `primary_action`: the specific action, such as opening a bottle cap.
- `affected_side`: which side needs the prosthesis.
- `residual_side`: the compensating side.
- `residual_anthropometrics`: intact-arm measurements used for sizing.

Technical answer:

> `ProblemSpec` is the bridge from perception into design. I use it to decide mount side, required reach, grip width, and whether the design should emphasize grasping, twisting, reaching, or another ADL behavior.

### `DesignParams`

This is the main output of my design agent.

`DesignParams` includes classic scalar fields:

- `upper_arm_len`
- `forearm_len`
- `joint_stiffness`
- `grip_width`
- `joint_limits`
- `mount_frame`

But the most important field is:

```python
links: tuple[LinkDef, ...]
```

That `links` chain is the actual morphology. Each `LinkDef` can contain one or more `JointDef`s.

### `LinkDef`

Represents one body/link in the simulated limb:

- `name`
- `length`
- `radius`
- `joints`
- optional mesh name
- display color

The convention is that a link starts at its proximal joint and extends along local `-Z`.

### `JointDef`

Represents one actuated degree of freedom:

- `name`
- `axis`
- `range_deg`
- `type`

Example:

```python
JointDef("elbow", (0, 1, 0), (0.0, 130.0))
```

Technical answer:

> We moved away from a hidden fixed arm. The morphology is explicit. The design agent declares the link chain, the joint axes, and the joint ranges. The simulator then builds exactly that tree.

## Important Design Decision: No Separate `MorphologySpec`

The technical plan originally described a conceptual `MorphologySpec`. In the current code, morphology is implemented as:

```python
DesignParams.links
```

So if someone asks, “Where is `MorphologySpec`?”:

> Conceptually, `MorphologySpec` is the simulated limb morphology. In implementation, we folded that into `DesignParams` because the design agent already needs to emit lengths, joint limits, stiffness, grip width, and an explicit link chain. `DesignParams.links` is the source of truth for morphology, so we avoid maintaining two overlapping contracts.

## Main Files I Worked On

### `prosthesis_rl/agents/design.py`

This is the core design agent.

It handles:

- generating a single candidate with `propose()`,
- generating multiple variations with `propose_candidates()`,
- validating morphology with `validate()`,
- evaluating candidates with `evaluate_candidates()`,
- choosing the winner with `compare()`,
- writing a readable explanation with `rationale_report()`.

Key class:

```python
class DesignAgent:
```

This is the heart of my task.

### `prosthesis_rl/cad/bridge.py`

This is the geometry bridge.

It handles:

- `export_arm()`: writes one STL per simulated link.
- `export_mjcf()`: writes a lightweight MJCF XML file for inspection/handoff.
- `export_stl()`: legacy single-STL export path.

Even though it says CAD, its current role is simulation geometry. It makes assets MuJoCo and the viewer can consume.

### `prosthesis_rl/sim/mjcf_builder.py`

This converts `DesignParams.links` into a complete MuJoCo environment.

Important details:

- It builds nested `<body>` tags from the link chain.
- It emits one `<joint>` per `JointDef`.
- It uses each joint's declared axis.
- It uses capsule geometry by default.
- If per-link STL files exist, it skins each body with mesh geometry.
- It adds target sites, mount body, optional floor, and visual human mannequin.

### `prosthesis_rl/agents/requirements.py`

This turns `ProblemSpec` into an engineering brief.

It can use Gemini if available, but also has deterministic fallback profiles for actions like:

- twist,
- cap,
- lid,
- tear,
- fold,
- zip,
- plug,
- pour.

The brief gives design-specific guidance such as:

- wrist rotation range,
- grip width,
- grip force target,
- arm lengths,
- actuator torque guesses,
- task rationale.

### `prosthesis_rl/agents/cad_spec.py`

This converts requirements + design output into a precise instruction JSON for the CAD/CadGPT layer.

It serializes:

- link dimensions,
- joint order,
- ROM metrics,
- end-effector spec,
- actuator torques,
- reach envelope,
- anthropometric sizing basis,
- natural-language CAD instructions.

### `prosthesis_rl/agents/cad_agent.py`

This is the CadGPT-style layer. It takes structured design instructions and produces a build sheet.

It includes:

- material choice,
- wall thickness calculation,
- print orientation,
- FDM settings,
- per-link output specs,
- STL/MJCF paths,
- build sheet JSON.

Important caveat:

> In the sim-only pivot, this is best described as simulation geometry plus engineering-style analysis. We should not claim this creates a ready-to-use physical prosthesis.

## What `DesignAgent.propose()` Does

`propose()` creates one validated candidate design.

Inputs:

- `ProblemSpec`
- optional `SimFeedback`
- optional requirements `brief`

Outputs:

- `DesignParams`
- control hints such as `ik_weight` and `grip_force_target`

How it works:

1. If a requirements brief exists, it uses action-specific values from the brief:
   - upper arm length,
   - forearm length,
   - grip width,
   - joint stiffness,
   - elbow ROM,
   - wrist ROM.
2. If no brief exists, it uses safe defaults.
3. It adapts based on previous sim feedback:
   - high ROM penalty widens elbow/wrist ranges,
   - high collision penalty shortens links,
   - low reward lengthens the forearm,
   - high energy penalty reduces stiffness.
4. It chooses the mount frame from `ProblemSpec.affected_side`.
5. It builds a `DesignParams` object with an explicit 4-DoF chain.
6. It runs validation gates.

The canonical 4-DoF design is:

- shoulder flexion,
- shoulder abduction,
- elbow flexion,
- wrist rotation.

## What `DesignAgent.propose_candidates()` Does

This generates multiple candidate morphologies around the base design.

The current strategy:

- Candidate 0: base design.
- Candidate 1: longer reach and wider ROM.
- Candidate 2: shorter, stiffer, more compact design.

This is simple but explainable. It creates meaningful variations for the verifier to score.

Technical answer:

> I do not randomly generate designs. I generate structured variations around a task-specific base design: one biased toward reach and range of motion, and one biased toward compactness, energy efficiency, and precision.

## Validation Gates

`DesignAgent.validate()` rejects designs before they enter simulation.

It checks:

- link length is positive,
- link radius is positive,
- joint ranges are valid,
- joint types are known,
- joint axes are nonzero,
- joint names are unique,
- total reach is enough for the task.

Why this matters:

> The sim should not waste time on invalid morphology. Validation catches broken geometry, impossible reach envelopes, and bad kinematics before MuJoCo or the controller sees them.

## Geometry and MJCF Export

### Per-Link STL Export

`CadBridge.export_arm(params)` creates one STL file per link.

These are saved under:

```text
assets/stl/<name>/
```

Each link is represented with simple procedural geometry:

- cylinders,
- spheres,
- capsules.

This is enough for:

- viewer rendering,
- MuJoCo mesh skinning,
- visual inspection,
- sim asset handoff.

### MJCF Export

There are two MJCF paths:

1. `CadBridge.export_mjcf()`
   - lightweight standalone MJCF for inspection/handoff.
2. `sim/mjcf_builder.py`
   - full MuJoCo environment builder used by the verifier.

The full MJCF builder:

- compiles the link chain into nested MuJoCo bodies,
- creates joints using `JointDef.axis`,
- creates position actuators,
- adds a target site,
- optionally skins bodies with STL meshes,
- excludes parent/child self contacts.

## Joint Axis Convention

In the full sim path, axes come from `JointDef.axis`.

Examples:

- shoulder flexion uses `(0, 1, 0)`,
- shoulder abduction uses `(1, 0, 0)`,
- elbow uses `(0, 1, 0)`,
- wrist uses `(1, 0, 0)`.

The axis string in MJCF is generated directly from these tuples.

Technical answer:

> The axis is not hardcoded globally anymore. The design contract declares the axis per joint, and the MJCF builder emits that into the joint tag. That means a wrist rotation can use `axis="1 0 0"` while elbow flexion can use `axis="0 1 0"`.

## Candidate Evaluation

`DesignAgent.evaluate_candidates()` runs every candidate through the verifier over multiple seeds.

Inputs:

- candidates,
- `ProblemSpec`,
- verifier,
- CAD bridge,
- number of seeds,
- number of targets,
- rollout seconds.

For each candidate:

1. export per-link STLs with `cad.export_arm()`;
2. run the verifier for multiple seeds;
3. collect reward and metrics;
4. aggregate into `_FullEval`.

Metrics include:

- success rate,
- mean reward,
- reward variance,
- mean energy,
- final distance to target,
- collision rate,
- ROM violation,
- peak stress,
- predicted service life.

Why multi-seed matters:

> A single rollout can be lucky. Multi-seed evaluation gives us a distribution, so we can compare robustness and not just one score.

## Candidate Comparison

`DesignAgent.compare()` chooses the best candidate by:

```text
mean_reward, then success_rate, then lower collision_rate
```

So the ranking prioritizes:

1. overall reward,
2. actually completing the task,
3. avoiding unsafe/self-collision behavior.

## Rationale Report

`DesignAgent.rationale_report()` turns metrics into a human-readable table.

It reports:

- upper arm length,
- forearm length,
- elbow ROM,
- wrist ROM,
- reward,
- reward variance,
- success rate,
- distance,
- energy,
- collision,
- predicted life,
- winning candidate.

It also flags failure modes:

- low success rate,
- high energy,
- self-collision,
- ROM violations,
- short predicted service life.

Technical answer:

> The point of the rationale report is explainability. We do not just pick the best reward. We show why the selected morphology won and what failure modes remain.

## Fatigue / Service-Life Estimate

`prosthesis_rl/fatigue/estimate.py` estimates service life from a torque trace.

Pipeline:

```text
joint torque over rollout
    -> nominal bending stress
    -> local stress with stress concentration factor
    -> Basquin S-N fatigue estimate
    -> predicted years
```

Important caveat:

> This is a rough sim estimate, not a real durability guarantee. It uses simplified material constants and a placeholder stress concentration factor.

## Software and Tools Used

### Python

The backend and simulation pipeline are Python.

Used for:

- dataclasses/contracts,
- design reasoning,
- CAD bridge,
- tests,
- rollout evaluation,
- MuJoCo integration.

### MuJoCo

Used for physics simulation.

Relevant files:

- `prosthesis_rl/sim/mjcf_builder.py`
- `prosthesis_rl/sim/verifier.py`
- `prosthesis_rl/sim/control.py`

### MJCF

MuJoCo XML format used to describe:

- bodies,
- joints,
- geoms,
- sites,
- actuators,
- contact exclusions.

### STL

Used as geometry assets for sim/viewer rendering.

Important framing:

> STL here is a simulation asset, not a physical manufacturing claim.

### Gemini / Google GenAI

Used optionally in `RequirementsAgent` for LLM-backed requirements derivation.

If no key is available, deterministic fallback profiles keep the system runnable.

### Pytest

Used for validation and regression tests.

Important tests:

- `tests/test_design_agent.py`
- `tests/test_cad_agent.py`
- `tests/test_cad_spec.py`

### React / Three.js Viewer

Used for local visualization.

Relevant folder:

```text
viewer/
```

## How to Run My Slice

From repo root:

```bash
source .venv/bin/activate
PYTHONPATH=. python scripts/cad_agent_test.py
```

Candidate comparison:

```bash
PYTHONPATH=. python scripts/compare_candidates.py
```

Focused tests:

```bash
PYTHONPATH=. python -m pytest -q tests/test_design_agent.py
PYTHONPATH=. python -m pytest -q tests/test_cad_spec.py tests/test_cad_agent.py
```

Full smoke:

```bash
PYTHONPATH=. python scripts/smoke.py
```

Viewer:

```bash
cd viewer
npm run dev
```

## What I Should Be Able To Say in a Demo

Here is a clean explanation:

> My part starts once perception produces a `ProblemSpec`. I take that problem and derive a task-specific engineering brief: what action we are optimizing for, what ROM the arm needs, what side it mounts on, what grip width and force are useful, and how long the segments should be. Then the design agent turns that brief into explicit `DesignParams`, including a `links` chain where every link and joint is declared. I validate that the morphology is physically meaningful before simulation. Then I export per-link STL assets and MJCF so MuJoCo can load the exact same kinematic chain. Finally, I evaluate multiple candidate designs across fixed seeds, compare them by reward, success rate, and collision rate, and generate a rationale report explaining why the best candidate won.

## Likely Technical Questions and Answers

### What exactly did you build?

I built the morphology/design layer. It generates simulated assistive-limb candidates, validates their kinematics, exports geometry and MJCF assets, compares candidates using sim feedback, and explains the winning design.

### What is the input to your module?

The main input is `ProblemSpec`, which comes from perception. Optionally, I also use a requirements brief and previous `SimFeedback`.

### What is the output?

The main output is `DesignParams`, plus control hints. `DesignParams.links` contains the full morphology.

### Why use `DesignParams.links` instead of a separate `MorphologySpec`?

Because morphology and design parameters are tightly coupled. The link chain, joint axes, joint ranges, grip width, stiffness, and segment lengths all belong to the design output. Keeping morphology inside `DesignParams` avoids duplicated contracts.

### How do you know a generated design is valid?

I run validation gates: positive link dimensions, valid joint ranges, valid joint types, nonzero axes, unique joint names, and enough reach for the task.

### What does spatial reasoning mean here?

It means checking whether the limb can physically cover the workspace required by the task: reach envelope, segment lengths, mount side, joint ranges, and collision-aware compactness.

### How does feedback improve the design?

If sim feedback reports ROM penalty, the design widens joint ranges. If collisions are high, it shortens links. If reward is low, it increases forearm reach. If energy penalty is high, it reduces stiffness.

### What does the CAD bridge do?

It converts structured design parameters into geometry assets: per-link STL meshes and lightweight MJCF XML. Those assets are used for sim and viewer rendering.

### How does MuJoCo know the joints?

The MJCF builder reads every `JointDef` from `DesignParams.links` and emits MJCF `<joint>` tags with the correct name, type, axis, and range.

### What is `axis="1 0 0"`?

That is a MuJoCo joint axis. In this repo, axes are declared per joint. A wrist or shoulder-abduction joint can rotate around X with `(1, 0, 0)`, while elbow flexion can rotate around Y with `(0, 1, 0)`.

### What metrics do you use to compare candidates?

Mean reward, success rate, collision rate, energy, distance-to-goal, ROM violations, and service-life estimate.

### How do you select the winner?

The current comparison chooses the candidate with the best tuple: mean reward, success rate, and lower collision rate.

### What is the role of the fatigue estimate?

It gives a rough simulated stress/life signal from torque traces. It helps flag designs that are dynamically expensive or mechanically suspicious, but it is not a real-world durability guarantee.

### What happens if no API key is available?

The requirements layer falls back to deterministic action profiles, so the loop still runs offline.

### What is the biggest limitation?

The CAD and fatigue parts are simplified. The system is good for sim iteration and evidence, but not for physical prosthesis claims.

## Known Caveats

- Some code still uses CAD/manufacturing vocabulary from the earlier product direction. In the current pitch, treat those as simulation geometry/build-sheet artifacts.
- The fatigue estimate is a simplified model, not FEA.
- The fallback requirements profiles are deterministic and useful for demos, but a live LLM can produce more task-specific briefs.
- Candidate generation is systematic rather than fully learned. It explores explainable variations around a base design.
- Sim performance does not imply real-world safety.

## Short Version To Memorize

I owned the simulated morphology and CAD reasoning layer. My system takes the task/problem spec, turns it into explicit design parameters with a link-and-joint chain, validates that the design is spatially and mechanically plausible, exports per-link geometry and MJCF for MuJoCo, evaluates multiple candidates across seeds, and produces a rationale for the best design. The main architecture choice was making `DesignParams.links` the source of truth for morphology, so the design agent, CAD bridge, sim builder, and evaluator all operate on the same structure.
