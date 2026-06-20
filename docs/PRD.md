# Prosthesis-RL — Product Requirements Document

> **Status:** Draft
> **Last updated:** 2026-06-20
> **Companion doc:** [WORK_SPLIT.md](../WORK_SPLIT.md) is the single source of truth for ownership, tasks, milestones, and timeline.

## 1. Overview

**Prosthesis-RL** is an AI-driven system that designs and optimizes custom robotic prosthetic arms from a short patient video. It runs a closed **perceive -> design -> verify -> optimize -> manufacture** loop:

1. **Perceive** patient pain points, ADL goals, and physical constraints from video.
2. **Design** an arm specification tailored to the patient's body and tasks.
3. **Verify** the design in physics simulation against concrete ADL tasks.
4. **Optimize** future designs with reinforcement learning from verifier feedback.
5. **Manufacture** the winning design as a printable CAD/STL artifact.

The core idea is measurable iteration: AI reasoning proposes designs, a deterministic verifier scores them, empirical evaluation identifies what is working, and the loop improves toward a personalized prosthesis design.

## 2. Problem

Prosthetic design is often manual, expensive, and slow. It is hard to quickly translate a patient's real daily limitations into a validated, manufacturable arm design. Prosthesis-RL explores whether video-grounded perception, AI design reasoning, physics verification, and RL optimization can automate a first-pass personalized design loop.

## 3. Users

**Primary user:** people with upper-limb loss or impairment who need a prosthetic or assistive arm tuned to their body constraints and daily activities.

**Demo user:** a researcher or builder who provides an ADL clip and receives a simulated design, reward evidence, and CAD/STL output.

## 4. Goals

- Close a real end-to-end loop: video -> `ProblemSpec` -> `DesignParams` -> simulated grade -> reward -> improved design -> exported STL.
- Produce prosthesis designs that satisfy spatial, mechanical, and task-specific constraints.
- Make the verifier deterministic and cheap enough for repeated empirical evaluation.
- Use RL or repeated feedback to improve design proposals over time.
- Produce a compelling demo with a personalized design, evaluation summary, and STL output.

## 5. Non-Goals

- Clinical validation, regulatory approval, or real-patient deployment.
- Physical manufacturing beyond producing printable CAD/STL artifacts.
- Production-grade web UI.
- A learned low-level control policy as a hard requirement; scripted or IK control is acceptable for v1.

## 6. Success Metrics

| Metric | Target |
| --- | --- |
| End-to-end loop | Input can flow through perceive, design, verify, optimize, and manufacture stages |
| Eval run | `hud eval tasks.py claude` returns a real numeric score |
| Verifier determinism | Same inputs produce the same reward |
| Reward usefulness | Tasks produce meaningful variance rather than all-pass or all-fail scores |
| CAD output | Top design exports as STL |
| Demo evidence | Final design includes an evaluation summary and reasoning trace |

## 7. System Architecture

```text
patient video
    |
    v
+------------+   ProblemSpec    +------------+   DesignParams   +------------+
| Perceive   | ---------------> | Design     | ---------------> | Verify     |
| VLM/CV     |                  | AI reasoner|                  | MuJoCo     |
+------------+                  +------------+                  +------------+
                                      ^                                |
                                      | reward feedback                |
                                      v                                |
                                +------------+                        |
                                | Optimize   | <----------------------+
                                | RL/GRPO    |
                                +------------+
                                      |
                                      v
                                +------------+
                                | Manufacture|
                                | CAD -> STL |
                                +------------+
```

### Perceive

Extracts relevant patient context from video and structured intake. The output is a validated `ProblemSpec` containing target ADL tasks and physical constraints.

### Design

Uses AI reasoning to generate candidate prosthesis parameters. The output is `DesignParams`, which must satisfy schema and range constraints before reaching CAD or simulation.

### Verify

Builds a parametric simulation from `DesignParams`, runs ADL task scenes, and returns a deterministic reward. The verifier should capture reach, grasp, energy, ROM violations, and collision behavior.

### Optimize

Uses verifier feedback to improve future design proposals. The optimization layer should prioritize reward distributions with usable variance and avoid all-pass/all-fail tasks.

### Manufacture

Converts the selected `DesignParams` into CAD geometry and exports printable STL artifacts.

## 8. Data Contracts

The contracts are the coordination boundary between components.

### `ProblemSpec`

```jsonc
{
  "tasks": ["reach", "grasp", "feeding"],
  "constraints": {
    "rom": {
      "shoulder_flexion": [0.0, 120.0],
      "elbow_flexion": [0.0, 145.0],
      "wrist_rotation": [-80.0, 80.0]
    },
    "residual_strength": 30.0,
    "grip_capacity": 15.0
  }
}
```

- `tasks` must be non-empty and validated against the task registry.
- `rom` values are patient-facing degrees.
- Strength and grip fields are non-negative numeric constraints.

### `DesignParams`

```jsonc
{
  "upper_arm_len": 0.30,
  "forearm_len": 0.25,
  "joint_stiffness": 10.0,
  "grip_width": 0.08,
  "joint_limits": {
    "shoulder_flexion": [0.0, 2.094],
    "elbow_flexion": [0.0, 2.531],
    "wrist_rotation": [-1.396, 1.396]
  }
}
```

- Lengths are meters.
- Joint limits are radians for simulation compatibility.
- Invalid ranges should be rejected rather than silently clamped.
- Design joint limits must stay within patient ROM after unit conversion.

### `Reward`

- A single deterministic `float` per episode.
- Higher is better.
- Same `ProblemSpec`, `DesignParams`, task, and seed should produce the same value.

## 9. Reward and Grading

The verifier composes reward from task success and physically meaningful penalties:

```text
reward = clip(success - energy_penalty - rom_penalty - collision_penalty)
```

| Term | Meaning |
| --- | --- |
| `success` | Fraction of task goal achieved |
| `energy_penalty` | Normalized actuator energy used |
| `rom_penalty` | Amount of motion beyond patient limits |
| `collision_penalty` | Self-collision or unsafe contact measure |

Weights can be tuned per task so rewards have useful variance for empirical comparison and optimization.

## 10. Infrastructure

| Provider / Tool | Role |
| --- | --- |
| Anthropic / Claude | Vision and design reasoning |
| HUD | Eval API and training/eval platform |
| MuJoCo | Physics simulation |
| OpenSCAD / CadQuery | Parametric CAD generation |
| Daytona | CAD sandbox execution |
| Fireworks AI | GRPO or RL training |
| Modal | Optional heavier CV or inference serving |
| Antim Worldsim/Newton | Optional higher-fidelity task validation |

## 11. Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Loop does not close | Demo fails regardless of component quality | Stand up a stubbed loop first |
| Contracts churn | Components block each other | Keep schemas explicit and shared |
| Reward has no variance | Optimization cannot learn | Tune tasks and weights empirically |
| Sim is not faithful enough | In-sim winners may not transfer | Keep grading physically grounded and add fidelity checks |
| CAD output is invalid | Final design is not usable | Add validation gates before export |
| Perception guesses too much | `ProblemSpec` is unreliable | Pair video with structured intake when needed |

## 12. Open Questions

- Exact ADL task registry IDs and success criteria.
- Final numeric ranges for every `ProblemSpec` and `DesignParams` field.
- Per-task reward weights.
- Which task, if any, should receive higher-fidelity Worldsim/Newton validation.
- Whether learned low-level control is attempted after scripted/IK control works.

## 13. Scope Boundary

This produces simulation evidence and CAD concepts, not a medical device. Real prosthetic deployment would require biomechanical safety analysis, clinical validation, and regulatory review.
