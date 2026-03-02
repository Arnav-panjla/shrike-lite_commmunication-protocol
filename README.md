# Function generator

## Communication protocol (summary)
- Uses a 4-bit `comm_line[3:0]` where:
  - `bit[0]` = control bit (state transition)
  - `bit[1]` = unused (reserved)
  - `bit[3:2]` = 2-bit data payload per state
- Transfer sequence:
  - STATE_1: wave type (`bit[3:2]`)
  - STATE_2: frequency unit (`bit[3:2]`)
  - STATE_3..STATE_10: four BCD digits (0-9), each digit sent as two 2-bit chunks (lower then upper)
  - After STATE_10 the FPGA enters the selected waveform state (sine/triangle/impulse/square)

See [COMMUNICATION_PROTOCOL.md](COMMUNICATION_PROTOCOL.md) for full details and diagrams.

Simple sequence diagram (overview):

```
IDLE --(ctrl=1)--> [STATE_1: wave(2b)] --(ctrl=0)--> [STATE_2: unit(2b)] --(ctrl=1)--> [STATE_3: f1_lo(2b)]
 --(ctrl=0)--> [STATE_4: f1_hi(2b)] --(ctrl=1)--> [STATE_5: f2_lo(2b)] ... --(ctrl=1)--> [STATE_10: f4_hi(2b)]
 --(ctrl=1)--> (WAVE_STATE)
```

Notes:
- Each 4-bit BCD digit is reconstructed from two 2-bit chunks (low then high).
- `controll_bit` toggles between 1 and 0 to step states reliably.

## FPGA pin mapping

12-bit DAC (MSB → LSB):

```
MSB -> LSB: 0, 1, 2, 7, 9, 11, 13, 15, 14, 12, 10, 8
```

Communication lines:

| Signal | FPGA pin | Raspberry Pi pin |
|--------|----------:|-----------------:|
| comm_line[3] | 6 | 3 |
| comm_line[2] | 5 | 2 |
| comm_line[1] | 4 | 1 |
| comm_line[0] | 3 | 0 |

