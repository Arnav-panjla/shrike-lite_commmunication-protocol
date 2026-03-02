// DEBUG BUILD — FSM state tracker for logic analyzer
// TESTER FOR WAVEFORM GENERATOR
//
// Architecture: "read first, recombine later"

// Logic Analyzer hookup (6 channels):
//   dac[0]  = state[0]     ──┐
//   dac[1]  = state[1]       │  5-bit state ID (0–14)
//   dac[2]  = state[2]       │  see table below
//   dac[3]  = state[3]       │
//   dac[4]  = state[4]     ──┘
//   dac[5]  = TRIGGER        ← HIGH from first ctrl↑ until back in IDLE
//   dac[6]  = ctrl (live echo of comm_line[0])
//   dac[7]  = ctrl_rise (one-clock pulse)
//   dac[8]  = ctrl_fall (one-clock pulse)
//   dac[9]  = raw_chunk[0][0]  ──┐
//   dac[10] = raw_chunk[0][1]    │  raw captured wave type
//   dac[11] = raw_chunk[0][2]  ──┘
//
//   0  = IDLE        5  = ST_D3       10 = ST_SIN
//   1  = ST_WAVE     6  = ST_D4       11 = ST_TRI
//   2  = ST_D0       7  = ST_D5       12 = ST_IMP
//   3  = ST_D1       8  = ST_D6       13 = ST_SQ
//   4  = ST_D2       9  = ST_D7       14 = ST_RAMP
//
// Raw chunk mapping:
//   raw_chunk[0] = wave type       (captured in ST_WAVE)
//   raw_chunk[1] = CLK_DIV[ 2: 0]  (captured in ST_D0)
//   raw_chunk[2] = CLK_DIV[ 5: 3]  (captured in ST_D1)
//   raw_chunk[3] = CLK_DIV[ 8: 6]  (captured in ST_D2)
//   raw_chunk[4] = CLK_DIV[11: 9]  (captured in ST_D3)
//   raw_chunk[5] = CLK_DIV[14:12]  (captured in ST_D4)
//   raw_chunk[6] = CLK_DIV[17:15]  (captured in ST_D5)
//   raw_chunk[7] = CLK_DIV[20:18]  (captured in ST_D6)
//   raw_chunk[8] = CLK_DIV[23:21]  (captured in ST_D7)
//
//   wave    <= raw_chunk[0]
//   CLK_DIV <= {raw_chunk[8], raw_chunk[7], ..., raw_chunk[1]}
// ==========================================================================

(* top *) module main(
  (* iopad_external_pin, clkbuf_inhibit *) input clk,
  (* iopad_external_pin *) output clk_en,
  (* iopad_external_pin *) output reg [11:0] dac,
  (* iopad_external_pin *) output [11:0] dac_en,
  (* iopad_external_pin *) input [3:0] comm_line,
  (* iopad_external_pin *) output [3:0] comm_line_en
);

    assign clk_en       = 1'b1;
    assign dac_en       = 12'hFFF;
    assign comm_line_en = 4'b0000;

    wire ctrl  = comm_line[0];
    wire [2:0] data = comm_line[3:1]; // 3-bit payload

    // FSM STATES
    localparam [4:0] IDLE      = 5'd0,
                     ST_WAVE   = 5'd1,
                     ST_D0     = 5'd2,
                     ST_D1     = 5'd3,
                     ST_D2     = 5'd4,
                     ST_D3     = 5'd5,
                     ST_D4     = 5'd6,
                     ST_D5     = 5'd7,
                     ST_D6     = 5'd8,
                     ST_D7     = 5'd9,
                     ST_SIN    = 5'd10,
                     ST_TRI    = 5'd11,
                     ST_IMP    = 5'd12,
                     ST_SQ     = 5'd13,
                     ST_RAMP   = 5'd14;

    reg [4:0] state, next_state;

    // EDGE DETECTION
    reg ctrl_d;
    always @(posedge clk)
        ctrl_d <= ctrl;

    wire ctrl_rise =  ctrl & ~ctrl_d;
    wire ctrl_fall = ~ctrl &  ctrl_d;

    reg [2:0] raw_chunk [0:8]; 

    reg [2:0]  wave;
    reg [23:0] CLK_DIV;

    reg [4:0] state_prev;
    reg trigger;

    always @(posedge clk) begin
        state <= next_state;
        state_prev <= state;
    end

    // FSM COMBINATIONAL
    always @(*) begin
        next_state = state;
        case (state)
            IDLE:    if (ctrl_rise) next_state = ST_WAVE;
            ST_WAVE: if (ctrl_fall) next_state = ST_D0;
            ST_D0:   if (ctrl_rise) next_state = ST_D1;
            ST_D1:   if (ctrl_fall) next_state = ST_D2;
            ST_D2:   if (ctrl_rise) next_state = ST_D3;
            ST_D3:   if (ctrl_fall) next_state = ST_D4;
            ST_D4:   if (ctrl_rise) next_state = ST_D5;
            ST_D5:   if (ctrl_fall) next_state = ST_D6;
            ST_D6:   if (ctrl_rise) next_state = ST_D7;
            ST_D7:   if (ctrl_fall) begin
                case (raw_chunk[0])          
                    3'd0:    next_state = ST_SIN;
                    3'd1:    next_state = ST_TRI;
                    3'd2:    next_state = ST_IMP;
                    3'd3:    next_state = ST_SQ;
                    3'd4:    next_state = ST_RAMP;
                    default: next_state = IDLE;
                endcase
            end

            ST_SIN:  if (ctrl_rise) next_state = IDLE;
            ST_TRI:  if (ctrl_rise) next_state = IDLE;
            ST_IMP:  if (ctrl_rise) next_state = IDLE;
            ST_SQ:   if (ctrl_rise) next_state = IDLE;
            ST_RAMP: if (ctrl_rise) next_state = IDLE;

            default: next_state = IDLE;
        endcase
    end

    wire state_entered = (state != state_prev);

    always @(posedge clk) begin
        case (state)
            IDLE: begin
                trigger <= 1'b0;
                // clear all raw slots
                raw_chunk[0] <= 3'd0;
                raw_chunk[1] <= 3'd0;
                raw_chunk[2] <= 3'd0;
                raw_chunk[3] <= 3'd0;
                raw_chunk[4] <= 3'd0;
                raw_chunk[5] <= 3'd0;
                raw_chunk[6] <= 3'd0;
                raw_chunk[7] <= 3'd0;
                raw_chunk[8] <= 3'd0;
            end

            ST_WAVE: begin
                trigger <= 1'b1;
                if (state_entered) raw_chunk[0] <= data;
            end

            ST_D0: if (state_entered) raw_chunk[1] <= data;
            ST_D1: if (state_entered) raw_chunk[2] <= data;
            ST_D2: if (state_entered) raw_chunk[3] <= data;
            ST_D3: if (state_entered) raw_chunk[4] <= data;
            ST_D4: if (state_entered) raw_chunk[5] <= data;
            ST_D5: if (state_entered) raw_chunk[6] <= data;
            ST_D6: if (state_entered) raw_chunk[7] <= data;
            ST_D7: if (state_entered) raw_chunk[8] <= data;

            default: ;
        endcase
    end

    always @(posedge clk) begin
        if (state == IDLE) begin
            wave    <= 3'd0;
            CLK_DIV <= 24'd0;
        end
        else if (state_entered && (state == ST_SIN  || state == ST_TRI ||
                                   state == ST_IMP  || state == ST_SQ  ||
                                   state == ST_RAMP)) begin
            wave    <= raw_chunk[0];
            CLK_DIV <= { raw_chunk[8], raw_chunk[7], raw_chunk[6],
                         raw_chunk[5], raw_chunk[4], raw_chunk[3],
                         raw_chunk[2], raw_chunk[1] };
        end
    end

    always @(posedge clk) begin
        dac[4:0]  <= state;            // 5-bit state ID
        dac[5]    <= trigger;          // HIGH while active
        dac[6]    <= ctrl;             // live ctrl echo
        dac[7]    <= ctrl_rise;        // one-clk pulse
        dac[8]    <= ctrl_fall;        // one-clk pulse
        dac[11:9] <= raw_chunk[0];     // raw wave type (visible immediately after ST_WAVE)
    end

endmodule