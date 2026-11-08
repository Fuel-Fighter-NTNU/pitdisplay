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

        # --- MODERNE RETRO-STIL (Med font som støtter ° og ² ) ---
        retro_style = """
            color: {color}; 
            background-color: #0b0b0b; 
            font-family: 'Consolas', 'Courier New', sans-serif; 
            font-size: 18px; 
            font-weight: bold; 
            padding: 4px 8px; 
            border-radius: 2px;
            border: 2px solid {color};
        """

        # --- GRAF-LAYOUT (Akselerasjon, Fart, Temperatur) ---
        self.max_points = 200

        # Graf 1: Akselerasjon
        self.pw1 = pg.PlotWidget(title="Akselerasjon")
        self.pw1.showGrid(x=True, y=True)
        self.pen1 = pg.mkPen(color=(255, 255, 0), width=2)  # Gul
        self.line1 = self.pw1.plot([], [], pen=self.pen1)
        main_layout.addWidget(self.pw1)
        
        # Digital verdi-boks for Graf 1 (Akselerasjon: m/s²)
        self.lbl_val1 = QtWidgets.QLabel(" 0.0 m/s² ", self.pw1)
        self.lbl_val1.setStyleSheet(retro_style.format(color="#ffff00"))
        self.lbl_val1.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl_val1.setMinimumWidth(150)

        # Graf 2: Fart
        self.pw2 = pg.PlotWidget(title="Fart")
        self.pw2.showGrid(x=True, y=True)
        self.pen2 = pg.mkPen(color=(0, 255, 255), width=2)  # Cyan
        self.line2 = self.pw2.plot([], [], pen=self.pen2)
        main_layout.addWidget(self.pw2)
        
        # Digital verdi-boks for Graf 2 (Fart: m/s)
        self.lbl_val2 = QtWidgets.QLabel(" 0.0 m/s ", self.pw2)
        self.lbl_val2.setStyleSheet(retro_style.format(color="#00ffff"))
        self.lbl_val2.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl_val2.setMinimumWidth(150)

        # Graf 3: Temperatur
        self.pw3 = pg.PlotWidget(title="Temperatur")
        self.pw3.showGrid(x=True, y=True)
        self.pen3 = pg.mkPen(color=(255, 0, 128), width=2)  # Rosa
        self.line3 = self.pw3.plot([], [], pen=self.pen3)
        main_layout.addWidget(self.pw3)
        
        # Digital verdi-boks for Graf 3 (Temperatur: °C)
        self.lbl_val3 = QtWidgets.QLabel(" 0.0 °C ", self.pw3)
        self.lbl_val3.setStyleSheet(retro_style.format(color="#ff0080"))
        self.lbl_val3.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl_val3.setMinimumWidth(150)

        # Plasser boksene riktig første gang
        QtCore.QTimer.singleShot(50, self.update_label_positions)

        # --- Data-buffere for det rullende vinduet ---
        self.x_data = []
        self.y_acc = []
        self.y_fart = [] 
        self.y_temp = [] 
        self.counter = 0

        self.worker = None

    def update_label_positions(self):
        """Plasserer de digitale verdi-boksene øverst til venstre."""
        margin_left = 65  
        margin_top = 32
        self.lbl_val1.move(margin_left, margin_top)
        self.lbl_val2.move(margin_left, margin_top)
        self.lbl_val3.move(margin_left, margin_top)

    def resizeEvent(self, event):
        """Sørger for at boksene holder seg på venstre side hvis vinduet endres."""
        super().resizeEvent(event)
        self.update_label_positions()

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

        # Oppdater boksene med tall 
        self.lbl_val1.setText(f"{acc:4.1f} m/s²")
        self.lbl_val2.setText(f"{fart:4.1f} m/s")
        self.lbl_val3.setText(f"{temp:4.1f} °C")

        # Vis siste verdier i statusfeltet nederst også
        self.status_label.setText(f"Mottar fra COM6 | Aks: {acc:.1f} | Fart: {fart:.1f} | Temp: {temp:.1f}")

    def closeEvent(self, event):
        if self.worker:
            self.worker.stop()
        event.accept()