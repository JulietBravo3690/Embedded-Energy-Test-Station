# Engineering decisions and four-week plan

## Decision log

- D001: Python standard library runtime and a small package. This keeps installation
  and debugging understandable; pytest and Ruff are development-only tools.
- D002: JSON lines rather than binary framing. Human-readable logs simplify early
  serial diagnosis. A strict size limit bounds memory; throughput is not yet measured.
- D003: Explicit sample advancement instead of wall-clock sleeps. Deterministic tests
  expose exact boundaries without scheduling noise. Real firmware timing still needs validation.
- D004: Independent literal acceptance vectors. The test oracle never imports the
  simulator threshold predicate. The mutant's strict greater-than comparison is
  detected at exactly 15 V and 60 °C, where the required behavior is FAULT.
- D005: Two safe samples plus hysteresis. Separate assertion and recovery boundaries
  reduce state chatter conceptually; two samples demonstrate recovery qualification.
  Neither value is justified for physical hardware until sample period and noise are known.
- D006: Volatile config for milestone 1. Reset semantics are explicit without claiming
  flash endurance, power-loss safety or nonvolatile storage implementation.
- D007: FAIL means a completed observation violated an expectation; ERROR means an
  observation could not be completed. Expected rejection of malformed communications
  is PASS. Reports preserve observed evidence rather than only totals.
- D008: No serial driver or board-specific firmware yet. Selecting a toolchain before
  identifying hardware would create unsupported assumptions.

## Roadmap (goals, not completed work)

| Week | Deliverable | Exit evidence |
|---|---|---|
| 1 | Software-only simulator, protocol, acceptance runner and CI | Normal PASS; boundary mutant FAIL; traceable reports |
| 2 | Select low-voltage board/sensors; implement firmware and serial transport | Recorded board/toolchain, flashing steps, identity and telemetry on real device |
| 3 | Controlled measurement and fault stimuli | Instrument references, uncertainty budget, boundary and recovery results |
| 4 | Investigate faults, harden behavior, portfolio write-up | Reproduction logs, root causes, regression reports and honest limitations |

## Hardware-selection checklist

Ask before choosing: development OS/version; available board(s); programming/debug
adapter; voltage and temperature sensors; DMM/bench supply/oscilloscope availability;
budget and access to lab support. Record board revision and MCU part number.

Check documented ADC reference/range/resolution, input protection and conditioning,
sensor transfer function and accuracy, USB serial support, available debugger,
open toolchain support on the user's OS, logic voltage compatibility and low-voltage
bench safety. Choose physical limits only after reviewing component ratings.
No battery charging, mains/high-voltage work or custom PCB is in this milestone.

## First investigation: intentional boundary defect (simulation only)

Symptom: the mutant reports NORMAL at exactly 15 V and exactly 60 °C. Expected:
FAULT at equality. Root cause: `>` instead of `>=` in the assertion predicate.
Reproduce with the defective CLI scenario. Two named boundary checks fail while
above-threshold and recovery checks pass. This demonstrates sensitivity to this
specific defect; it is not proof that all controller bugs can be detected.

## Student exercise

Add one independent acceptance vector for a fault where **both channels** exceed
limits, followed by two safe samples. Expected states: FAULT, RECOVERY, NORMAL.
Add it in `runner.checks()` using literal sample/expected lists. Update any test
that asserts the suite count. Run pytest and both CLI scenarios: normal must still
pass and only the two intentional mutant boundary failures should remain.
