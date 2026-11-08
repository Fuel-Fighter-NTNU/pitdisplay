import time
import random
import math
import serial
from PySide6 import QtCore

class TISerialWorker(QtCore.QThread):
    # Sender tre verdier: akselerasjon, fart, temperatur
    values_received = QtCore.Signal(float, float, float)

    def __init__(self, port="COM9", baudrate=115200, simulate=False):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.simulate = simulate  # True = generer fake data, False = bruk ekte serielport
        self.is_running = True

    def run(self):
        if self.simulate:
            print("Kjører i SIMULERINGSMODUS (genererer testdata)...")
            counter = 0
            while self.is_running:
                counter += 1
                # Generer litt livlige og realistiske testdata
                acc = round(math.sin(counter * 0.1) * 3.0 + random.uniform(-0.2, 0.2), 2)
                fart = round(max(0, math.cos(counter * 0.05) * 15 + 30), 2)
                temp = round(21.5 + math.sin(counter * 0.02) * 1.5, 2)

                # Send dataene til GUI-en
                self.values_received.emit(acc, fart, temp)
                
                # Vent i 50 millisekunder (gir ca. 20 oppdateringer i sekundet)
                time.sleep(0.05)
            return

        # --- Ekte serielesing (hvis simulate=False) ---
        try:
            ser = serial.Serial(self.port, self.baudrate, timeout=1)
            print(f"Koblet til {self.port} med {self.baudrate} baud.")

            while self.is_running:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    try:
                        parts = line.split()
                        if len(parts) >= 3:
                            acc = float(parts[0])
                            fart = float(parts[1])
                            temp = float(parts[2])
                            self.values_received.emit(acc, fart, temp)
                    except ValueError:
                        pass
            ser.close()
        except Exception as e:
            print(f"Seriell kommunikasjonsfeil: {e}")

    def stop(self):
        self.is_running = False
        self.wait()