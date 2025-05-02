# -------------------------------------------------------------
# 4-Digit Countdown Timer using Raspberry Pi, 74HC595, and GPIOZero
# - Set minutes/seconds with buttons
# - Start/stop with short press
# - Reset with long press (2 sec)
# - Display via 7-segment and shift register
# -------------------------------------------------------------

from gpiozero import DigitalOutputDevice, Button
from time import sleep, time

# Button Inputs
sw_1 = Button(2)      # Increase seconds
sw_2 = Button(23)     # Increase minutes
sw_3 = Button(24)     # Start/stop timer

# Timing delays
delay = 0.005                   # Delay for display refresh
delay_for_setting = 0.1         # Debounce delay for setting buttons
last_countdown_time = time()
reset_hold_duration = 2         # Delay for reset

# Digits: [D1, D2, D3, D4] = [S1, S2, M1, M2]
current_digit_d_1 = 0   # Seconds (ones)
current_digit_d_2 = 0   # Seconds (tens)
current_digit_d_3 = 0   # Minutes (ones)
current_digit_d_4 = 0   # Minutes (tens)

# Decimal points setup: [D1, D2, D3, D4]
decimal_points = [False, False, False, False]

# State tracking for button edges
last_sw_1_state = False
last_sw_2_state = False
last_sw_3_state = False
timer_running = False
reset_hold_start_time = None

# Shift Register Pins (SN74HC595)
SER = DigitalOutputDevice(17)    # DS - Serial data
SRCLK = DigitalOutputDevice(27)  # SHCP - Shift clock
RCLK = DigitalOutputDevice(22)   # STCP - Latch clock

# Digit control pins (Common Cathode, active LOW)
DIGIT_PINS = [
    DigitalOutputDevice(5, active_high=False, initial_value=True),   # D1 (rightmost)
    DigitalOutputDevice(6, active_high=False, initial_value=True),   # D2
    DigitalOutputDevice(13, active_high=False, initial_value=True),  # D3
    DigitalOutputDevice(19, active_high=False, initial_value=True)   # D4 (leftmost)
]

# Segment encodings (common cathode (0-9), no DP by default)
SEGMENTS = {
    '0': 0b00111111,
    '1': 0b00000110,
    '2': 0b01011011,
    '3': 0b01001111,
    '4': 0b01100110,
    '5': 0b01101101,
    '6': 0b01111101,
    '7': 0b00000111,
    '8': 0b01111111,
    '9': 0b01101111
}

def shift_out(data):
    """Send 8-bit data to SN74HC595."""
    RCLK.off()        # Disable latch while shifting
    for i in range(8):
        SRCLK.off()
        bit = (data >> (7 - i)) & 0x01
        SER.value = bit
        SRCLK.on()
    RCLK.on()        # Latch the output

def display_number(d_1, d_2, d_3, d_4, delay, decimal_points=None):
    """Display 4 digits using multiplexing and optional decimal points."""
    if decimal_points is None:
        decimal_points = [False, False, False, False]

    digits = [d_1, d_2, d_3, d_4]

    for digit in range(len(digits)):
        # Turn all digits off to avoid ghosting
        for pin in DIGIT_PINS:
            pin.off()

        segment_data = SEGMENTS.get(digits[digit])
        if decimal_points[digit]:
            segment_data |= 0b10000000   # Set DP bit

        shift_out(segment_data)

        # Turn on current digit only
        DIGIT_PINS[digit].on()
        sleep(delay)
        DIGIT_PINS[digit].off()

def setting_timer():
    """Handle setting the timer using sw_1 and sw_2 (minutes and seconds)."""
    global current_digit_d_1, current_digit_d_2, current_digit_d_3, current_digit_d_4
    global last_sw_1_state, last_sw_2_state, delay_for_setting

    # sw_1: Increase seconds
    if sw_1.is_pressed and not last_sw_1_state:
        if current_digit_d_2 == 5 and current_digit_d_1 == 9:
            current_digit_d_1 = 0
            current_digit_d_2 = 0
        else:
            current_digit_d_1 += 1

        if current_digit_d_1 > 9:
            current_digit_d_1 = 0
            current_digit_d_2 += 1
        sleep(delay_for_setting)

    # sw_2: Increase minutes
    if sw_2.is_pressed and not last_sw_2_state:
        if current_digit_d_4 == 5 and current_digit_d_3 == 9:
            current_digit_d_3 = 0
            current_digit_d_4 = 0
        else:
            current_digit_d_3 += 1

        if current_digit_d_3 > 9:
            current_digit_d_3 = 0
            current_digit_d_4 += 1
        sleep(delay_for_setting)

    last_sw_1_state = sw_1.is_pressed
    last_sw_2_state = sw_2.is_pressed

def start_stop_timer():
    """Toggle timer start/stop with sw_3."""
    global last_sw_3_state, timer_running
    global reset_hold_start_time, reset_hold_duration
    global current_digit_d_1, current_digit_d_2, current_digit_d_3, current_digit_d_4

    if sw_3.is_pressed:
        if reset_hold_start_time is None:
            reset_hold_start_time = time()

        # Check if held long enough for reset
        if time() - reset_hold_start_time >= reset_hold_duration:

            # Reset the timer
            current_digit_d_1 = 0
            current_digit_d_2 = 0
            current_digit_d_3 = 0
            current_digit_d_4 = 0
            timer_running = False
            reset_hold_start_time = None    # Prevent repeat resets while still held
            sleep(0.5)                      # Prevent immediate re-trigger

    else:
        # If button was just released
        if last_sw_3_state and reset_hold_start_time is not None:
            press_duration = time() - reset_hold_start_time

            if press_duration < reset_hold_duration:

                # Short press = toggle timer
                timer_running = not timer_running

        reset_hold_start_time = None

    last_sw_3_state = sw_3.is_pressed

def countdown():
    """Count down every second if timer is running."""
    global current_digit_d_1, current_digit_d_2, current_digit_d_3, current_digit_d_4
    global last_countdown_time, timer_running

    if time() - last_countdown_time >= 1:
        last_countdown_time = time()

        # Stop at 00:00
        if current_digit_d_1 == 0 and current_digit_d_2 == 0 and current_digit_d_3 == 0 and current_digit_d_4 == 0:
            timer_running = False
            return

        # Decrement digits in correct order
        if current_digit_d_1 > 0:
            current_digit_d_1 -= 1
        else:
            current_digit_d_1 = 9
            if current_digit_d_2 > 0:
                current_digit_d_2 -= 1
            else:
                current_digit_d_2 = 5
                if current_digit_d_3 > 0:
                    current_digit_d_3 -= 1
                else:
                    current_digit_d_3 = 9
                    if current_digit_d_4 > 0:
                        current_digit_d_4 -= 1

# --------- Main Loop ---------
while True:
    setting_timer()
    start_stop_timer()

    if timer_running:
        countdown()

    # Display the correct timer value, with DP lit on digit D3 (MM:SS)
    display_number(
        str(current_digit_d_1),
        str(current_digit_d_2),
        str(current_digit_d_3),
        str(current_digit_d_4),
        delay,
        decimal_points=[False, False, True, False]
    )
