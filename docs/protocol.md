# Protocol v1 — provisional serial interface

UTF-8 JSON objects, one per line, LF terminator. Maximum frame length is 1024 bytes
**including LF**. No binary payload, batching, unsolicited telemetry or injection command.
The synchronous client allows one outstanding request. IDs are positive integers
1–2147483647, not booleans. A long-lived caller must reconnect before ID exhaustion.

Request: `{"v":1,"id":1,"cmd":"identity","params":{}}`

Success: `{"v":1,"id":1,"ok":true,"result":{"device_id":"SIM-001","firmware_version":"sim-0.1.0","protocol_version":1,"simulated":true,"model":"reference"}}`

Error: `{"v":1,"id":1,"ok":false,"error":{"code":"UNKNOWN_COMMAND","message":"Unsupported command"}}`

All examples above require a trailing LF. Unknown envelope fields are ignored for
forward compatibility. Every request must include all four envelope fields. Invalid
or unavailable request IDs produce `id:null` errors; clients reject uncorrelated
responses rather than associating them with an outstanding operation.

| Command | params | result |
|---|---|---|
| identity | empty object | device_id, firmware_version, protocol_version, simulated, model |
| telemetry | empty object | voltage_v, temperature_c, state, safe_samples, simulated |
| config.get | empty object | all four configuration values |
| config.set | nonempty partial object of known config keys | complete accepted configuration |
| reset | empty object | reset:true, config_persisted:false |

`MALFORMED`: invalid UTF-8, JSON, incomplete frame, non-object or oversized frame.
`BAD_REQUEST`: invalid ID, command field or params structure, unexpected parameters.
`VERSION`: unsupported envelope version. `UNKNOWN_COMMAND`: unknown command name.
`INVALID_CONFIG`: unknown config key, empty update, invalid value or inconsistent bounds.
Invalid requests must not mutate controller configuration.

The client defaults to a 1 second transaction deadline. `Transport.exchange` must
return exactly one complete frame within the deadline or raise `TimeoutError`.
Malformed frames, response versions, envelopes and mismatched IDs raise
`ProtocolError`; well-formed device rejection raises `DeviceError`.
The simulator returns immediately and timeout tests use a deterministic fault
transport; these do not measure elapsed serial timeout performance.

Future serial implementation: buffer up to 1024 bytes; discard an oversized frame
through LF; return MALFORMED; on deadline discard incomplete transaction data and
resynchronize before another request. Do not blindly retry writes or reset after a
timeout: execution may have occurred. This serial buffering and resynchronization
is an **interface requirement**, not implemented serial functionality.

Simulator-only `Controller.inject` is an in-process fixture API. It is deliberately
absent from the device protocol. Test-runner access to this API must be replaced by
controlled physical stimulus for hardware acceptance tests.
