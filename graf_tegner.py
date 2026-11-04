from PySide6 import QtCore, QtWidgets
import pyqtgraph as pg

# Importerer tråden fra vår egen serieleser-fil
from sensor_leser import TISerialWorker

class MultiLiveDataWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        # Vindusoppsett
        self.setWindowTitle("TI Radio Sensor Dashboard - LIS3DH")
        self.resize(800, 700)

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QVBoxLayout(central_widget)

        # --- KONTROLLPANEL (START/STOPP & STATUS) ---
        control_layout = QtWidgets.QHBoxLayout()
        
        self.btn_toggle = QtWidgets.QPushButton("Start Måling")
        self.btn_toggle.setCheckable(True)
        self.btn_toggle.setStyleSheet("background-color: #d4edda; font-weight: bold; padding: 6px; font-size: 13px;")
        self.btn_toggle.clicked.connect(self.toggle_measurement)
        control_layout.addWidget(self.btn_toggle)

        self.status_label = QtWidgets.QLabel("Status: Klar (Venter på start på COM6)")
        self.status_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        control_layout.addWidget(self.status_label)
        
        main_layout.addLayout(control_layout)

        # --- GRAF-LAYOUT (Akselerasjon, Fart, Temperatur) ---
        self.max_points = 100

        # Graf 1: Absolutt Akselerasjon
        self.pw1 = pg.PlotWidget(title="Akselerasjon")
        self.pw1.showGrid(x=True, y=True)
        self.pen1 = pg.mkPen(color=(255, 255, 0), width=2)  # Gul
        self.line1 = self.pw1.plot([], [], pen=self.pen1)
        main_layout.addWidget(self.pw1)

        # Graf 2: Fart
        self.pw2 = pg.PlotWidget(title="Fart")
        self.pw2.showGrid(x=True, y=True)
        self.pen2 = pg.mkPen(color=(0, 255, 255), width=2)  # Cyan
        self.line2 = self.pw2.plot([], [], pen=self.pen2)
        main_layout.addWidget(self.pw2)

        # Graf 3: Temperatur
        self.pw3 = pg.PlotWidget(title="Temperatur")
        self.pw3.showGrid(x=True, y=True)
        self.pen3 = pg.mkPen(color=(255, 0, 128), width=2)  # Rosa
        self.line3 = self.pw3.plot([], [], pen=self.pen3)
        main_layout.addWidget(self.pw3)

        # --- Data-buffere for det rullende vinduet ---
        self.x_data = list(range(self.max_points))
        self.y_acc = [0.0] * self.max_points
        self.y_fart = [0.0] * self.max_points
        self.y_temp = [0.0] * self.max_points
        self.counter = 0

        self.worker = None

    def toggle_measurement(self, checked):
        """Starter eller stoppes målingen fra COM6."""
        if checked:
            self.btn_toggle.setText("Stopp Måling")
            self.btn_toggle.setStyleSheet("background-color: #f8d7da; font-weight: bold; padding: 6px; font-size: 13px;")
            self.status_label.setText("Status: Kobler til COM6...")
            
            # Starter tråden fra sensor_leser.py
            self.worker = TISerialWorker(port="COM6", baudrate=115200)
            self.worker.value_received.connect(self.handle_new_data)
            self.worker.start()
        else:
            self.btn_toggle.setText("Start Måling")
            self.btn_toggle.setStyleSheet("background-color: #d4edda; font-weight: bold; padding: 6px; font-size: 13px;")
            self.status_label.setText("Status: Måling stoppet.")
            
            if self.worker:
                self.worker.stop()
                self.worker = None

    def handle_new_data(self, value):
        """Tar imot data fra tråden og oppdaterer grafene."""
        self.counter += 1
        
        self.x_data.pop(0)
        self.x_data.append(self.counter)

        # Foreløpig sender vi verdien inn på akselerasjonsgrafen
        self.y_acc.pop(0)
        self.y_acc.append(value)

        self.line1.setData(self.x_data, self.y_acc)
        # Her kan du senere oppdatere self.line2 og self.line3 når du henter fart og temperatur!
        
        self.status_label.setText(f"Mottar fra COM6 | Akselerasjon: {value}")

    def closeEvent(self, event):
        if self.worker:
            self.worker.stop()
        event.accept()