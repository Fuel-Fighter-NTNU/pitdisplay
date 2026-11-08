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

        # Graf 1: Akselerasjon
        self.pw1 = pg.PlotWidget(title="Akselerasjon (Absolutt)")
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
        self.x_data = []
        self.y_acc = []
        self.y_fart = [] 
        self.y_temp = [] 
        self.counter = 0

        self.worker = None

    def toggle_measurement(self, checked):
        """Starter eller stoppes målingen fra COM6."""
        if checked:
            self.btn_toggle.setText("Stopp Måling")
            self.btn_toggle.setStyleSheet("background-color: #f8d7da; font-weight: bold; padding: 6px; font-size: 13px;")
            self.status_label.setText("Status: Kobler til COM6...")
            
            # Starter tråden på COM6 fra sensor_leser.py
            self.worker = TISerialWorker(port="COM6", baudrate=115200, simulate=True)
            self.worker.values_received.connect(self.handle_new_data)
            self.worker.start()
        else:
            self.btn_toggle.setText("Start Måling")
            self.btn_toggle.setStyleSheet("background-color: #d4edda; font-weight: bold; padding: 6px; font-size: 13px;")
            self.status_label.setText("Status: Måling stoppet.")
            
            if self.worker:
                self.worker.stop()
                self.worker = None

    def handle_new_data(self, acc, fart, temp):
        """Tar imot de tre verdiene og oppdaterer hver sin graf i det rullende vinduet."""
        self.counter += 1
        
        # Legg til nye verdier bakerst i listene
        self.x_data.append(self.counter)
        self.y_acc.append(acc)
        self.y_fart.append(fart)
        self.y_temp.append(temp)

        # Fjern det eldste elementet hvis vi har flere enn max_points (rullende vindu)
        if len(self.x_data) > self.max_points:
            self.x_data.pop(0)
            self.y_acc.pop(0)
            self.y_fart.pop(0)
            self.y_temp.pop(0)

        # Oppdater grafene
        self.line1.setData(self.x_data, self.y_acc)
        self.line2.setData(self.x_data, self.y_fart)
        self.line3.setData(self.x_data, self.y_temp)

        # Vis siste verdier i statusfeltet
        self.status_label.setText(f"Mottar fra COM6 | Aks: {acc:.2f} | Fart: {fart:.2f} | Temp: {temp:.2f}")

    def closeEvent(self, event):
        if self.worker:
            self.worker.stop()
        event.accept()