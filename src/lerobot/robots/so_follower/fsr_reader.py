"""Background reader for the two gripper FSRs on the ESP32.

Expects the ESP32 to print one line per reading with the two finger values,
small finger first, e.g.  "123.4,456.7"  (any separator works; the first two
numbers on the line are used). Values are passed through as-is, so if the
ESP32 already sends grams you get grams.

Reading runs in a background thread so it never slows down the control loop;
get_observation() just grabs the latest values.
"""

import logging
import re
import threading
import time

import serial

logger = logging.getLogger(__name__)

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


class FSRReader:
    def __init__(self, port: str, baudrate: int = 115200, timeout_s: float = 1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout_s = timeout_s
        self._serial: serial.Serial | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._small = 0.0
        self._large = 0.0
        self._last_update = 0.0

    @property
    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def connect(self, wait_for_first_reading_s: float = 3.0) -> None:
        self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout_s)
        self._serial.reset_input_buffer()
        self._stop.clear()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

        # Wait for the first valid line so the first observations aren't zeros.
        deadline = time.time() + wait_for_first_reading_s
        while time.time() < deadline:
            if self._last_update > 0:
                logger.info(f"FSRReader connected on {self.port}")
                return
            time.sleep(0.05)
        logger.warning(
            f"FSRReader on {self.port}: no valid reading after {wait_for_first_reading_s}s. "
            "Check the port, baud rate and what the ESP32 is printing."
        )

    def _read_loop(self) -> None:
        while not self._stop.is_set():
            try:
                line = self._serial.readline().decode(errors="ignore").strip()
            except (serial.SerialException, OSError) as e:
                logger.error(f"FSRReader serial error: {e}")
                time.sleep(0.5)
                continue
            if not line:
                continue
            numbers = _NUMBER.findall(line)
            if len(numbers) != 3:
                continue  # expect "millis,small,large"; ignore anything else
            with self._lock:
                self._small = float(numbers[1])
                self._large = float(numbers[2])
                self._last_update = time.time()

    def read(self) -> dict[str, float]:
        with self._lock:
            return {"fsr_small": self._small, "fsr_large": self._large}

    def seconds_since_update(self) -> float:
        return time.time() - self._last_update if self._last_update else float("inf")

    def disconnect(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._serial is not None and self._serial.is_open:
            self._serial.close()
        self._serial = None
        self._thread = None
