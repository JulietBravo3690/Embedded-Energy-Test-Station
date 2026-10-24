# Firmware interface reservation — not implemented

No C/C++ firmware, board support, pinout or flashing tool is implemented here.
Future firmware must implement docs/protocol.md and requirements REQ-001–007,
using physical samples rather than simulator injection. Specify board, ADC reference,
sensor conversion/uncertainty, sample period, startup sensor validity, timeout
framing/resynchronization and safe output behavior before integration.

Simulation reset values are fixture defaults, not a physical reset policy. Firmware
must reevaluate actual sensor inputs after reset. Keep simulation-only controls out
of production commands. Hardware evidence must be reported separately from examples/.
