import math
import random
import time
 
import serial
from serial.tools import list_ports
from PySide6 import QtCore
 
 
def available_ports():
    """Returnerer en liste med navn på tilgjengelige serieporter (f.eks. COM6)."""
    return [p.device for p in list_ports.comports()]
 
 
class TISerialWorker(QtCore.QThread):
    # Sender: tid (s), akselerasjon, fart, temperatur
    values_received = QtCore.Signal(float, float, float, float)
    # Sender feilmelding til GUI-et (port finnes ikke, kabel trukket, osv.)
    error = QtCore.Signal(str)
 
    def __init__(self, port="COM6", baudrate=115200, simulate=False):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.simulate = simulate  # True = fake data, False = ekte serielport
 
    def run(self):
        t0 = time.monotonic()
 
        if self.simulate:
            self._run_simulation(t0)
        else:
            self._run_serial(t0)
 
    # ------------------------------------------------------------------
    def _run_simulation(self, t0):
        counter = 0
        while not self.isInterruptionRequested():
            counter += 1
            acc = round(math.sin(counter * 0.1) * 3.0 + random.uniform(-0.2, 0.2), 2)
            fart = round(max(0, math.cos(counter * 0.05) * 15 + 30), 2)
            temp = round(21.5 + math.sin(counter * 0.02) * 1.5, 2)
 
            self.values_received.emit(time.monotonic() - t0, acc, fart, temp)
            self.msleep(50)  # ca. 20 oppdateringer i sekundet
 
    # ------------------------------------------------------------------
    def _run_serial(self, t0):
        try:
            # Kort timeout slik at stop() reagerer raskt.
            # "with" sørger for at porten alltid lukkes, også ved feil.
            with serial.Serial(self.port, self.baudrate, timeout=0.1) as ser:
                ser.reset_input_buffer()
 
                while not self.isInterruptionRequested():
                    raw = ser.readline()
                    if not raw:
                        continue  # timeout, ingen data ennå
 
                    line = raw.decode("utf-8", errors="ignore").strip()
                    parts = line.split()
                    if len(parts) < 3:
                        continue
 
                    try:
                        acc = float(parts[0])
                        fart = float(parts[1])
                        temp = float(parts[2])
                    except ValueError:
                        continue  # ødelagt/delvis linje, hopp over
 
                    self.values_received.emit(time.monotonic() - t0, acc, fart, temp)
 
        except serial.SerialException as e:
            self.error.emit(f"Seriefeil på {self.port}: {e}")
        except Exception as e:
            self.error.emit(f"Uventet feil: {e}")
 
    # ------------------------------------------------------------------
    def stop(self):
        """Ber tråden avslutte og venter på den (går raskt pga. kort timeout)."""
        self.requestInterruption()
        self.wait()
 