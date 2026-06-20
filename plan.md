# Egocentric-to-Assistive-Limb Pipeline (working name)

## Pitch

From a 5s Meta-glasses clip, auto-generate a custom assistive limb (CAD + articulation) fitted to a disabled user's body, drop it into a SLAM reconstruction of their environment, and train a control policy in sim. Agents find the painpoints from the clip and spec a limb designed for that specific user. Output is a `.pt` policy that drives the limb to assist them.

## Concrete I/O

- **Input:** 5s monocular egocentric RGB + IMU from Meta Ray-Ban glasses.
- **Output:** trained `.pt` policy checkpoint (sim-only) for the generated limb.

## Pipeline

1. **Capture.** 5s clip + IMU stream.
2. **Perception / SLAM.** Visual-inertial SLAM (IMU recovers metric scale, which monocular RGB alone can't) gives camera trajectory + a 3D reconstruction of the scene. Body-landmark detection (where the user looks + head pose) locates the attachment site (shoulder, residual limb) in metric coords.
3. **Painpoint reasoning (multi-agent).** Agents infer the functional limitation and the assist task from the clip + a short structured intake. Output: task spec, attachment site, required workspace/reach.
4. **Generative design.** Agent emits a _parametric_ kinematic description of the limb: link graph, joint types/axes/limits, per-link inertia, attachment frame. Geometry as per-link meshes or procedural primitives, dimensions driven by the user's measured body params.
5. **Validation gate.** Before sim: closed kinematic tree, mass > 0 and valid inertia per link, no self-collision at rest pose, target reachable within joint limits, attachment pose feasible. Reject and regenerate on fail.
6. **Sim assembly.** Compile to MJCF (MuJoCo). Load the SLAM reconstruction as collision + visual geometry. Place the limb at the fitted attachment pose.
7. **Policy training.** RL (or imitation if demos exist) for the assist task. Export `.pt`.

## The medium (the STL fix)

- STL is geometry only: no joints, no axes, no inertia, no link graph. It cannot carry the articulation you design, so it is wrong as the _handoff_ medium. It is fine only as per-link geometry.
- Better medium: a kinematic description format as the spine, meshes as leaves.
  - **Spine:** URDF or MJCF. URDF has the best LLM-generation coverage and is trivially parseable/validatable. MJCF is the better physics target (native MuJoCo, better contacts/actuators/defaults) and matches the stack.
  - **Recommended path:** agent emits parametric URDF (or directly MJCF), per-link meshes as OBJ/STL, then compile to MJCF for MuJoCo training. MuJoCo ingests URDF directly or via its compiler.
  - If targeting Isaac Lab instead, the spine is USD.
- **Why parametric, not a frozen mesh:** the point is fitting to _this_ user. Link lengths, joint placements, and attachment frame should be parameters bound to body measurements from the glasses, so you instantiate per-person without regenerating geometry.

## Personalization

- Metric scale from visual-inertial SLAM (IMU resolves the monocular scale ambiguity).
- Body landmarks located via gaze + head pose + SLAM scene geometry, giving an attachment frame in metric coords.
- Limb params (link lengths, mount offset) solved so the workspace covers the assist task without colliding with the body.

## Open questions / weak points

- **5s is thin for painpoint inference.** One clip shows one moment. Add a structured intake (condition + target task) plus a clip of the _specific_ task, or multiple clips. Otherwise the agent is guessing the disability.
- **Morphology class is undefined.** Pick one to start: augmentation (supernumerary / "third arm", where +1 DoF is natural), substitution (prosthesis for a missing limb), or support (orthosis/exo assisting an existing limb). Mechanics, attachment, and reward differ a lot across these.
- **"+1 DoF over what?"** Define the baseline morphology so the extra DoF has a purpose (e.g. base arm = N DoF for the task, +1 for redundancy / obstacle avoidance / wrist roll).
- **Reward / task spec for the `.pt` is undefined.** "Help the person" needs a concrete task, an observation space (does the policy see user intent? gaze? scene state? EMG?), and a reward.
- **SLAM reconstruction quality as collision geometry.** A 5s monocular+IMU reconstruction is sparse. Decide whether it is true collision geometry or a visual backdrop with hand-placed collision primitives.

## MVP slice (what to actually demo)

- Fix one morphology: supernumerary arm (easiest place to justify +1 DoF).
- Abstract painpoint reasoning to one task (e.g. "stabilize an object near the chest" or "reach a shelf").
- Parametric MJCF generator + the validation gate.
- SLAM as visual backdrop + a few placed collision primitives, attachment pose from gaze + IMU.
- Train one RL policy in MuJoCo, export `.pt`.
- That is a believable end-to-end vertical slice. Everything else is depth added later.

## Scope boundary

This produces a simulation policy and a CAD concept, not a medical device. A real assistive limb for a disabled person needs biomechanical safety, clinical validation, and regulatory review before it touches anyone. Keep the demo framed as sim/research.
