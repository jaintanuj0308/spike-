# gpio_output.py - Hardware GPIO controllers and display outputs (with mock support)
import asyncio
import logging
import sys
import threading
import time
import config

logger = logging.getLogger("gpio_output")

# Check for RPi.GPIO availability and configuration flag
HAS_GPIO = False
if config.ENABLE_GPIO:
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        HAS_GPIO = True
        logger.info("Physical RPi.GPIO library detected. Running in hardware mode.")
    except (ImportError, RuntimeError):
        logger.info("RPi.GPIO not available or not running on a Pi. Running in Mock Mode.")
else:
    logger.info("GPIO hardware disabled via configuration. Running in Mock Mode.")


# Segment mapping representing index corresponding to GPIO_7SEG_SEGMENTS
# [A, B, C, D, E, F, G, DP] where 1 is ON (HIGH anode) and 0 is OFF (LOW anode)
SEGMENT_MAP = {
    '0': [1, 1, 1, 1, 1, 1, 0, 0],
    '1': [0, 1, 1, 0, 0, 0, 0, 0],
    '2': [1, 1, 0, 1, 1, 0, 1, 0],
    '3': [1, 1, 1, 1, 0, 0, 1, 0],
    '4': [0, 1, 1, 0, 0, 1, 1, 0],
    '5': [1, 0, 1, 1, 0, 1, 1, 0],
    '6': [1, 0, 1, 1, 1, 1, 1, 0],
    '7': [1, 1, 1, 0, 0, 0, 0, 0],
    '8': [1, 1, 1, 1, 1, 1, 1, 0],
    '9': [1, 1, 1, 1, 0, 1, 1, 0],
    '-': [0, 0, 0, 0, 0, 0, 1, 0],
    ' ': [0, 0, 0, 0, 0, 0, 0, 0],
}


class Direct7SegmentDriver:
    """
    Multiplexing driver for standard 2-digit 7-segment display wired directly.
    Runs on a background daemon thread to satisfy Persistence of Vision (POV).
    Digit Pin pulled LOW turns that digit ON (Active Low Common Cathode).
    Segment Pin pulled HIGH turns that segment ON.
    """
    def __init__(self):
        self.char_tens = ' '
        self.char_ones = ' '
        self.running = False
        self.thread = None

        if HAS_GPIO:
            # Initialize segment pins as OUTPUT, starting LOW (OFF)
            for pin in config.GPIO_7SEG_SEGMENTS:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)
            
            # Initialize digit select pins as OUTPUT, starting HIGH (OFF)
            for pin in config.GPIO_7SEG_DIGITS:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.HIGH)
                
            logger.info("Initialized direct segment GPIO pins.")

    def set_value(self, val):
        """Prepares characters to display. Accepts integers or 2-char strings."""
        s = str(val).strip()
        if not s:
            self.char_tens = ' '
            self.char_ones = ' '
        elif len(s) == 1:
            self.char_tens = '0'
            self.char_ones = s[0]
        else:
            self.char_tens = s[0]
            self.char_ones = s[1]

    def start(self):
        """Starts display multiplexing thread."""
        if not HAS_GPIO:
            return
        self.running = True
        self.thread = threading.Thread(target=self._multiplex_loop, daemon=True)
        self.thread.start()
        logger.info("Started 7-segment multiplexing daemon thread.")

    def stop(self):
        """Gracefully stops background multiplexing thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        self._clear_pins()

    def _clear_pins(self):
        if HAS_GPIO:
            # Turn digits OFF (HIGH) and segments OFF (LOW)
            for pin in config.GPIO_7SEG_DIGITS:
                GPIO.output(pin, GPIO.HIGH)
            for pin in config.GPIO_7SEG_SEGMENTS:
                GPIO.output(pin, GPIO.LOW)

    def _multiplex_loop(self):
        try:
            while self.running:
                # 1. Display Tens Digit (Digit Index 0)
                pat_tens = SEGMENT_MAP.get(self.char_tens, SEGMENT_MAP[' '])
                self._display_digit(0, pat_tens)
                time.sleep(0.005) # Display for 5ms
                
                # 2. Display Ones Digit (Digit Index 1)
                pat_ones = SEGMENT_MAP.get(self.char_ones, SEGMENT_MAP[' '])
                self._display_digit(1, pat_ones)
                time.sleep(0.005) # Display for 5ms
        except Exception as e:
            logger.error(f"Error in multiplexing loop: {e}", exc_info=True)

    def _display_digit(self, digit_idx: int, pattern: list):
        # 1. Turn off all digits to prevent ghosting
        for pin in config.GPIO_7SEG_DIGITS:
            GPIO.output(pin, GPIO.HIGH)
            
        # 2. Set segment signals
        for pin, state in zip(config.GPIO_7SEG_SEGMENTS, pattern):
            GPIO.output(pin, GPIO.HIGH if state else GPIO.LOW)
            
        # 3. Pull target digit cathode LOW to enable it
        target_pin = config.GPIO_7SEG_DIGITS[digit_idx]
        GPIO.output(target_pin, GPIO.LOW)


class GPIOHandler:
    def __init__(self):
        self._current_state = "idle"
        self._indicator_task = None
        self.display = None
        
        if HAS_GPIO:
            if config.GPIO_BUZZER:
                GPIO.setup(config.GPIO_BUZZER, GPIO.OUT)
                GPIO.output(config.GPIO_BUZZER, GPIO.LOW)
            if config.GPIO_LED_RED:
                GPIO.setup(config.GPIO_LED_RED, GPIO.OUT)
                GPIO.output(config.GPIO_LED_RED, GPIO.LOW)
            if config.GPIO_LED_GREEN:
                GPIO.setup(config.GPIO_LED_GREEN, GPIO.OUT)
                GPIO.output(config.GPIO_LED_GREEN, GPIO.LOW)

        self.display = Direct7SegmentDriver()
        self.display.start()
        self._update_display("--")

    def _set_pin(self, pin, state: bool):
        if HAS_GPIO and pin is not None:
            GPIO.output(pin, GPIO.HIGH if state else GPIO.LOW)

    def _update_display(self, val):
        if self.display:
            self.display.set_value(val)
        if not HAS_GPIO:
            logger.debug(f"[MOCK DISPLAY] Display shows: {val}")

    def on_state_change(self, new_state: str):
        """Called immediately when the game state machine transitions."""
        self._current_state = new_state
        
        # Stop any active indicator flashing/rapid beeping tasks
        if self._indicator_task:
            self._indicator_task.cancel()
            self._indicator_task = None

        # Reset simple status pins to baseline
        self._set_pin(config.GPIO_BUZZER, False)
        
        if new_state == "idle":
            self._set_pin(config.GPIO_LED_RED, False)
            self._set_pin(config.GPIO_LED_GREEN, False)
            self._update_display("--")
            
        elif new_state == "planting":
            self._set_pin(config.GPIO_LED_RED, False)
            self._set_pin(config.GPIO_LED_GREEN, False)
            self._update_display("--")
            
        elif new_state == "planted":
            self._set_pin(config.GPIO_LED_RED, True)
            self._set_pin(config.GPIO_LED_GREEN, False)
            self._update_display(config.SPIKE_TIME)
            
        elif new_state == "defusing":
            # Rapid alarms flashing
            self._indicator_task = asyncio.create_task(self._defusing_loop())
            
        elif new_state == "exploded":
            self._set_pin(config.GPIO_LED_RED, True)
            self._set_pin(config.GPIO_LED_GREEN, False)
            self._update_display("EE") # E E representing Exploded / Error
            
        elif new_state == "defused":
            self._set_pin(config.GPIO_LED_RED, False)
            self._set_pin(config.GPIO_LED_GREEN, True)
            self._update_display("00")

    def tick(self, data):
        """Called every 1 second by the system tick loop."""
        if data.state in ("planted", "defusing"):
            self._update_display(data.spike_remaining)
        
        if data.state == "planting":
            # Pulse buzzer every second
            asyncio.create_task(self._pulse_buzzer(0.1))

    async def _pulse_buzzer(self, duration: float):
        """Pulses the buzzer once asynchronously."""
        if not HAS_GPIO:
            logger.info(f"[MOCK GPIO] Buzzer: SHORT BEEP ({duration * 1000:.0f}ms)")
            return
        
        try:
            self._set_pin(config.GPIO_BUZZER, True)
            await asyncio.sleep(duration)
            self._set_pin(config.GPIO_BUZZER, False)
        except Exception as e:
            logger.error(f"Error pulsing buzzer: {e}")

    async def _defusing_loop(self):
        """Background loop flashing Red LED and rapid beeping buzzer during defusal."""
        try:
            logger.info("Started rapid defuse indicator loop.")
            while True:
                self._set_pin(config.GPIO_LED_RED, True)
                self._set_pin(config.GPIO_BUZZER, True)
                if not HAS_GPIO:
                    logger.info("[MOCK GPIO] Red LED: FLASH ON | Buzzer: RAPID BEEP")
                await asyncio.sleep(0.1)
                
                self._set_pin(config.GPIO_LED_RED, False)
                self._set_pin(config.GPIO_BUZZER, False)
                await asyncio.sleep(0.15)
        except asyncio.CancelledError:
            self._set_pin(config.GPIO_LED_RED, False)
            self._set_pin(config.GPIO_BUZZER, False)
            logger.info("Stopped rapid defuse indicator loop.")

    def trigger_explosion(self):
        """Fires detonation outputs: solid Red LED + long buzzer blast."""
        self.on_state_change("exploded")
        asyncio.create_task(self._detonation_sequence())

    async def _detonation_sequence(self):
        if not HAS_GPIO:
            logger.info("[MOCK GPIO] Detonated! Buzzer: LONG BLAST (5.0s) | Red LED: SOLID ON")
            return
            
        try:
            self._set_pin(config.GPIO_BUZZER, True)
            await asyncio.sleep(5.0)
            self._set_pin(config.GPIO_BUZZER, False)
        except Exception as e:
            logger.error(f"Error in detonation sequence: {e}")

    def trigger_defused(self):
        """Fires victory outputs: solid Green LED + victory scale melody."""
        self.on_state_change("defused")
        asyncio.create_task(self._victory_sequence())

    async def _victory_sequence(self):
        if not HAS_GPIO:
            logger.info("[MOCK GPIO] Spike Defused! Buzzer: VICTORY MELODY (♪ ♩ ♫ ♬) | Green LED: SOLID ON")
            return
            
        try:
            # Play rising scale
            for pulse_len in [0.08, 0.08, 0.08, 0.25]:
                self._set_pin(config.GPIO_BUZZER, True)
                await asyncio.sleep(pulse_len)
                self._set_pin(config.GPIO_BUZZER, False)
                await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"Error in victory sequence: {e}")

    def cleanup(self):
        """Cleans up GPIO settings and stops display thread on application exit."""
        if self.display:
            self.display.stop()
            
        if HAS_GPIO:
            try:
                GPIO.cleanup()
                logger.info("Successfully cleaned up GPIO pins.")
            except Exception as e:
                logger.error(f"Failed to cleanup GPIO: {e}")


# Global instance of GPIOHandler
gpio_handler = GPIOHandler()
