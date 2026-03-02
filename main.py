import shrike
from machine import Pin
import time

PIN_CTRL = 0   # comm_line[0] -> control bit
PIN_D1   = 1   # comm_line[1] -> data 0
PIN_D2   = 2   # comm_line[2] -> data 1
PIN_D3   = 3   # comm_line[3] -> data  2
PIN_TRIG = 29   # Trigger pin for logic analyzer 

BIT_DELAY = 40_000  # delay after each individual bit change
DELAY = 80_000     # delay after ctrl edge / before next phase

FPGA_CLK = 50_000_000  # 50 MHz

# Wave types (3-bit)
TYPE_SINE     = 0b000
TYPE_TRAINGLE = 0b001
TYPE_IMPULSE  = 0b010
TYPE_SQUARE   = 0b011
TYPE_RAMP     = 0b100


class FPGA_Bridge:
    def __init__(self):
        self.ctrl = Pin(PIN_CTRL, Pin.OUT)
        self.ctrl.value(0)

        self.d1 = Pin(PIN_D1, Pin.OUT)
        self.d2 = Pin(PIN_D2, Pin.OUT)
        self.d3 = Pin(PIN_D3, Pin.OUT)

        self.d1.value(0)
        self.d2.value(0)
        self.d3.value(0)

        self.trig = Pin(PIN_TRIG, Pin.OUT)
        self.trig.value(0)

        print("FPGA Bridge Initialized.")

    def _print_bus_4bit(self, label):
        """Debug helper: print full 4-bit comm_line[3:0] = [d3 d2 d1 ctrl]"""
        ctrl = self.ctrl.value()
        d1 = self.d1.value()
        d2 = self.d2.value()
        d3 = self.d3.value()
        bus = (d3 << 3) | (d2 << 2) | (d1 << 1) | ctrl
        print(f"  {label}: comm_line[3:0]={bus:04b} (d3 d2 d1 ctrl = {d3}{d2}{d1}{ctrl})")
        
    def _print_bits(self, label, val):
        """Debug helper: print 3-bit value being sent"""
        print(f"  {label}: {val:03b} (dec={val})")

    def set_data_3bit(self, val):
        """Put a 3-bit value onto comm_line[3:1] with per-bit settling delay"""
        self.d1.value((val >> 0) & 1)
        #time.sleep_us(BIT_DELAY)
        self.d2.value((val >> 1) & 1)
        #time.sleep_us(BIT_DELAY)
        self.d3.value((val >> 2) & 1)
        #time.sleep_us(BIT_DELAY)

    def compute_clk_div(self, freq_hz, wave_type=None):
        """Compute CLK_DIV clamped to 24-bit.
        For sine: f = f_clk / (CLK_DIV * 128), so CLK_DIV = f_clk / (f * 128)
        For others: CLK_DIV = f_clk / f
        """
        if freq_hz <= 0:
            return (1 << 24) - 1
        if wave_type == TYPE_SINE:
            div = FPGA_CLK // (freq_hz * 128)
        else:
            div = FPGA_CLK // freq_hz
        if div < 1:
            div = 1
        if div > (1 << 24) - 1:
            div = (1 << 24) - 1
        return div

    def send_wave_config(self, wave_type, freq_hz):
        clk_div = self.compute_clk_div(freq_hz, wave_type)
        print(f"--- Sending Config: Wave={wave_type}, Freq={freq_hz} Hz, CLK_DIV={clk_div} ---")

        # Precompute all 3-bit chunks for visibility
        print("Bit sequence (3 bits per state):")
        self._print_bits("WAVE    [wave[2:0]]       ", wave_type & 0b111)
        self._print_bits("D0     [CLK_DIV[2:0]]    ", clk_div & 0b111)
        self._print_bits("D1     [CLK_DIV[5:3]]    ", (clk_div >> 3) & 0b111)
        self._print_bits("D2     [CLK_DIV[8:6]]    ", (clk_div >> 6) & 0b111)
        self._print_bits("D3    [CLK_DIV[11:9]]   ", (clk_div >> 9) & 0b111)
        self._print_bits("D4   [CLK_DIV[14:12]]   ", (clk_div >> 12) & 0b111)
        self._print_bits("D5   [CLK_DIV[17:15]]   ", (clk_div >> 15) & 0b111)
        self._print_bits("D6   [CLK_DIV[20:18]]   ", (clk_div >> 18) & 0b111)
        self._print_bits("D7   [CLK_DIV[23:21]]   ", (clk_div >> 21) & 0b111)
        self._print_bits("FINAL  [0 (don't care)] ", 0)

        # Trigger HIGH — use as logic analyzer trigger (pos edge)
        self.trig.value(1)
        time.sleep_us(BIT_DELAY)

        self.set_data_3bit(wave_type)
        time.sleep_us(DELAY)
        self.ctrl.value(1)           # IDLE -> ST_WAVE, FPGA captures wave_type
        time.sleep_us(DELAY)

        # Set CLK_DIV[2:0], then falling edge -> enters ST_D0 (captures bits [2:0])
        self.set_data_3bit(clk_div & 0b111)
        time.sleep_us(DELAY)
        self.ctrl.value(0)           # ST_WAVE -> ST_D0
        time.sleep_us(DELAY)

        # Set CLK_DIV[5:3], then rising edge -> enters ST_D1 (captures bits [5:3])
        self.set_data_3bit((clk_div >> 3) & 0b111)
        time.sleep_us(DELAY)
        self.ctrl.value(1)           # ST_D0 -> ST_D1
        time.sleep_us(DELAY)

        # Set CLK_DIV[8:6], then falling edge -> enters ST_D2
        self.set_data_3bit((clk_div >> 6) & 0b111)
        time.sleep_us(DELAY)
        self.ctrl.value(0)           # ST_D1 -> ST_D2
        time.sleep_us(DELAY)

        # Set CLK_DIV[11:9], then rising edge -> enters ST_D3
        self.set_data_3bit((clk_div >> 9) & 0b111)
        time.sleep_us(DELAY)
        self.ctrl.value(1)           # ST_D2 -> ST_D3
        time.sleep_us(DELAY)

        # Set CLK_DIV[14:12], then falling edge -> enters ST_D4
        self.set_data_3bit((clk_div >> 12) & 0b111)
        time.sleep_us(DELAY)
        self.ctrl.value(0)           # ST_D3 -> ST_D4
        time.sleep_us(DELAY)

        # Set CLK_DIV[17:15], then rising edge -> enters ST_D5
        self.set_data_3bit((clk_div >> 15) & 0b111)
        time.sleep_us(DELAY)
        self.ctrl.value(1)           # ST_D4 -> ST_D5
        time.sleep_us(DELAY)

        # Set CLK_DIV[20:18], then falling edge -> enters ST_D6
        self.set_data_3bit((clk_div >> 18) & 0b111)
        time.sleep_us(DELAY)
        self.ctrl.value(0)           # ST_D5 -> ST_D6
        time.sleep_us(DELAY)

        # Set CLK_DIV[23:21], then rising edge -> enters ST_D7
        self.set_data_3bit((clk_div >> 21) & 0b111)
        time.sleep_us(DELAY)
        self.ctrl.value(1)           # ST_D6 -> ST_D7
        time.sleep_us(DELAY)

        # Falling edge -> enters wave state (no data needed)
        self.set_data_3bit(0)
        time.sleep_us(DELAY)
        self.ctrl.value(0)           # ST_D7 -> wave state
        time.sleep_us(DELAY)

        # Trigger LOW — bitstream transfer complete
        self.trig.value(0)

        print("Config sent. Waveform generating.\n")

    def return_to_idle(self):
        print("Returning to IDLE...")
        self.set_data_3bit(0)
        self.ctrl.value(1)
        time.sleep_us(DELAY)
        self.ctrl.value(0)
        time.sleep_us(DELAY)
        print("Returned to IDLE.\n")


def main():
    shrike.reset()
    shrike.flash("main_dg.bin")

    bridge = FPGA_Bridge()
    time.sleep(2)

    print("FPGA Communication Protocol v2")

    bridge.send_wave_config(TYPE_SINE, 20)
    time.sleep(1000)

    bridge.return_to_idle()

    print("Program running. Press Ctrl+C to exit.")
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()



