import math
import random
import time
 
import serial
from serial.tools import list_ports
from PySide6 import QtCore
 
# Juster etter sensorinnstillingen (se tabell for LIS3DH):
# ±2 g i high-resolution (12 bit) = 1 mg per digit
MG_PER_DIGIT = 1.0
G = 9.81
 
# --- Innstillinger for fartsberegning ---
GRAVITY_TAU = 1.0     # s. Tyngdeestimat tilpasser seg raskt når sensoren er i ro
GRAVITY_TAU_MOVING = 15.0  # s. ...og veldig tregt i bevegelse (ellers regnes akselerasjon som tyngde)
LEAK_TAU = 10.0       # s. Fart "lekker" mot 0 for å begrense drift (stor = svakere effekt)
STILL_THRESHOLD = 0.3 # m/s². Under dette regnes sensoren som i ro
STILL_SAMPLES = 10    # Antall sammenhengende "i ro"-samples før farten nullstilles
 
 
class SpeedEstimator:
    """Anslår fart ved å integrere akselerasjon (x, y, z i m/s²) over tid.
 
    Ikke nøyaktig: små feil summeres opp og gir drift. Mottiltak:
    lekkasje mot 0 og nullstilling når sensoren ligger i ro.
    """
 
    def __init__(self):
        self.reset()
 
    def reset(self):
        self.g = None          # estimert tyngdevektor
        self.v = [0.0, 0.0, 0.0]
        self.t_prev = None
        self.still_count = 0
 
    def update(self, t, ax, ay, az):
        """Returnerer estimert fart (m/s) for ny måling ved tid t (s)."""
        a = [ax, ay, az]
 
        if self.g is None:
            # Antar at vi starter i ro, så første måling = tyngdekraft
            self.g = a[:]
            self.t_prev = t
            return 0.0
 
        dt = t - self.t_prev
        self.t_prev = t
        if dt <= 0 or dt > 1.0:   # hopp over rare tidssteg (f.eks. etter pause)
            return math.sqrt(sum(v * v for v in self.v))
 
        # Lineær akselerasjon = målt minus estimert tyngde
        lin = [ai - g for ai, g in zip(a, self.g)]
        lin_mag = math.sqrt(sum(c * c for c in lin))
 
        # Oppdater tyngdeestimat: raskt i ro, tregt i bevegelse
        tau = GRAVITY_TAU if lin_mag < STILL_THRESHOLD else GRAVITY_TAU_MOVING
        alpha = dt / (tau + dt)
        self.g = [g + alpha * (ai - g) for g, ai in zip(self.g, a)]
 
        # Stillstandsdeteksjon
        if lin_mag < STILL_THRESHOLD:
            self.still_count += 1
        else:
            self.still_count = 0
 
        if self.still_count >= STILL_SAMPLES:
            self.v = [0.0, 0.0, 0.0]
        else:
            leak = math.exp(-dt / LEAK_TAU)
            self.v = [(v + c * dt) * leak for v, c in zip(self.v, lin)]
 
        return math.sqrt(sum(v * v for v in self.v))
 
 
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
        speed = SpeedEstimator()
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
                        x = float(parts[0])
                        y = float(parts[1])
                        z = float(parts[2])
                    except ValueError:
                        continue  # ødelagt/delvis linje, hopp over
 
                    # Konverter fra digits til m/s²
                    scale = MG_PER_DIGIT / 1000 * G
                    ax, ay, az = x * scale, y * scale, z * scale
 
                    t = time.monotonic() - t0
 
                    # Absoluttverdi av akselerasjonsvektoren, i m/s²
                    acc = math.sqrt(ax * ax + ay * ay + az * az)
 
                    # Estimert fart i m/s (temperatur er 0 inntil vi har data)
                    fart = speed.update(t, ax, ay, az)
 
                    self.values_received.emit(t, acc, fart, 0.0)
 
        except serial.SerialException as e:
            self.error.emit(f"Seriefeil på {self.port}: {e}")
        except Exception as e:
            self.error.emit(f"Uventet feil: {e}")
 
    # ------------------------------------------------------------------
    def stop(self):
        """Ber tråden avslutte og venter på den (går raskt pga. kort timeout)."""
        self.requestInterruption()
        self.wait()
 