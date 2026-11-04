import serial
from PySide6 import QtCore

class TISerialWorker(QtCore.QThread):
    # Sender flyttallsverdier videre til resten av programmet
    value_received = QtCore.Signal(float)

    def __init__(self, port="COM6", baudrate=115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.is_running = True

    def run(self):
        try:
            ser = serial.Serial(self.port, self.baudrate, timeout=1)
            print(f"Koblet til {self.port} med {self.baudrate} baud.")

            while self.is_running:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    try:
                        val = float(line)
                        self.value_received.emit(val)
                    except ValueError:
                        # Ignorer linjer som ikke er rene tall
                        pass
            ser.close()
        except Exception as e:
            print(f"Seriell kommunikasjonsfeil: {e}")

    def stop(self):
        self.is_running = False
        self.wait()