# FPGA Communication Protocol v2

## Overview

The microcontroller pre-computes `CLK_DIV` and sends it directly to the FPGA — **no arithmetic on the FPGA side**. Data is sent 3 bits at a time via `comm_line[3:1]`, with `comm_line[0]` as the control bit.

**Key timing rule:** Data must be set **before** the ctrl edge. The FPGA captures data on the **first clock cycle after entering** each new state.

---

## Signal Description

| Signal | Width | Direction | Description |
|--------|-------|-----------|-------------|
| `comm_line[0]` | 1 bit | Input | Control bit (edge-triggered state transitions) |
| `comm_line[3:1]` | 3 bits | Input | Data payload |
| `dac[11:0]` | 12 bits | Output | DAC output value |

---

## State Machine

```
IDLE --(ctrl↑)--> ST_WAVE --(ctrl↓)--> ST_D0 --(ctrl↑)--> ST_D1
  --(ctrl↓)--> ST_D2 --(ctrl↑)--> ST_D3 --(ctrl↓)--> ST_D4
  --(ctrl↑)--> ST_D5 --(ctrl↓)--> ST_D6 --(ctrl↑)--> ST_D7
  --(ctrl↓)--> [wave state based on wave type]

Wave states: ST_SIN, ST_TRI, ST_IMP, ST_SQ, ST_RAMP
All wave states return to IDLE on ctrl rising edge.
```

---

## Timing Sequence

```
MCU:  set data=wave_type  -->  ctrl=1(↑)  -->  set data=d[2:0]  -->  ctrl=0(↓)  --> ...
FPGA:                     ST_WAVE(capture)                       ST_D0(capture)
```

Data is stable **before** the edge. FPGA latches on the first clock of the new state.

---

## Data Frame

### ST_WAVE: Wave Type (3 bits on comm_line[3:1])

| Value | Wave Type |
|-------|-----------|
| `000` | Sine |
| `001` | Triangle |
| `010` | Impulse |
| `011` | Square |
| `100` | Ramp |

### ST_D0 through ST_D7: CLK_DIV (24 bits, 3 bits per state)

| State | Captures | Entering Edge |
|-------|----------|---------------|
| ST_WAVE | `wave[2:0]` | Rising |
| ST_D0 | `CLK_DIV[2:0]` | Falling |
| ST_D1 | `CLK_DIV[5:3]` | Rising |
| ST_D2 | `CLK_DIV[8:6]` | Falling |
| ST_D3 | `CLK_DIV[11:9]` | Rising |
| ST_D4 | `CLK_DIV[14:12]` | Falling |
| ST_D5 | `CLK_DIV[17:15]` | Rising |
| ST_D6 | `CLK_DIV[20:18]` | Falling |
| ST_D7 | `CLK_DIV[23:21]` | Rising |

---

## CLK_DIV Calculation (done on microcontroller)

```
For sine:          CLK_DIV = FPGA_CLK / (desired_frequency * 128)
For square:        CLK_DIV = FPGA_CLK / desired_frequency  (half-period)
For triangle/ramp: CLK_DIV = FPGA_CLK / desired_frequency  (full period, /4096 steps)
For impulse:       CLK_DIV is unused (fixed IMPULSE_WIDTH)
```

Where `FPGA_CLK` = 50 MHz. Clamped to 24 bits (max 16,777,215).

## DAC Output

- **All non-waveform states**: `dac = 0` (explicitly)
- **ST_SIN**: 128-sample sine LUT, one sample every `CLK_DIV` clocks → `f = 50M / (CLK_DIV * 128)`
- **ST_SQ**: Toggles between 0 and 4095 every `CLK_DIV` clocks
- **ST_TRI**: Ramps 0→4095→0 with `CLK_DIV/4096` clocks per step
- **ST_IMP**: Outputs 4095 for `IMPULSE_WIDTH` clocks, then 0
- **ST_RAMP**: Ramps 0→4095 (sawtooth) with `CLK_DIV/4096` clocks per step

---

## Return to IDLE

From any waveform state, a **rising edge** on `ctrl` returns the FSM to IDLE.
