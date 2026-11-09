import csv
import sys
from collections import deque
from datetime import datetime
 
import pyqtgraph as pg
from PySide6 import QtGui, QtWidgets
 
from sensorread import TISerialWorker, available_ports
 
STYLE_START = "background-color: #d4edda; font-weight: bold; padding: 6px; font-size: 13px;"
STYLE_STOP = "background-color: #f8d7da; font-weight: bold; padding: 6px; font-size: 13px;"
 
 
def make_plot(title, color_rgb, color_hex, unit):
    """Lager en graf med akseetikett og en digital verdi-boks pinnet øverst til venstre.
 
    Returnerer (plotwidget, kurve, verdiboks).
    """
    pw = pg.PlotWidget(title=title)
    pw.showGrid(x=True, y=True)
    pw.setLabel("left", unit)
    pw.setLabel("bottom", "Tid (s)")
    line = pw.plot([], [], pen=pg.mkPen(color=color_rgb, width=2))
 
    box = pg.TextItem(
        text=f"0.0 {unit}",
        color=color_hex,
        fill=pg.mkBrush("#0b0b0b"),
        border=pg.mkPen(color_hex, width=2),
        anchor=(0, 0),
    )
    box.setFont(QtGui.QFont("Consolas", 14, QtGui.QFont.Weight.Bold))
    pw.addItem(box, ignoreBounds=True)
 
    # Hold boksen i øvre venstre hjørne uansett zoom/skalering
    vb = pw.getPlotItem().getViewBox()
 
    def pin(*_):
        (x0, _x1), (_y0, y1) = vb.viewRange()
        box.setPos(x0, y1)
 
    vb.sigRangeChanged.connect(pin)
    pin()
 
    return pw, line, box
 
 
class MultiLiveDataWindow(QtWidgets.QMainWindow):
    MAX_POINTS = 200
 
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TI Radio Sensor Dashboard - LIS3DH")
        self.resize(900, 780)
 
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QVBoxLayout(central)
 
        # --- Kontrollpanel, rad 1: port, simulering, logging ---
        row1 = QtWidgets.QHBoxLayout()
 
        row1.addWidget(QtWidgets.QLabel("Port:"))
        self.port_combo = QtWidgets.QComboBox()
        self.port_combo.setMinimumWidth(100)
        row1.addWidget(self.port_combo)
 
        self.btn_refresh = QtWidgets.QPushButton("Oppdater")
        self.btn_refresh.clicked.connect(self.refresh_ports)
        row1.addWidget(self.btn_refresh)
 
        self.chk_sim = QtWidgets.QCheckBox("Simuler data")
        self.chk_sim.setChecked(True)
        self.chk_sim.toggled.connect(self._update_port_enabled)
        row1.addWidget(self.chk_sim)
 
        self.chk_log = QtWidgets.QCheckBox("Logg til CSV")
        row1.addWidget(self.chk_log)
 
        row1.addStretch()
        main_layout.addLayout(row1)
 
        # --- Kontrollpanel, rad 2: knapper og status ---
        row2 = QtWidgets.QHBoxLayout()
 
        self.btn_toggle = QtWidgets.QPushButton("Start Måling")
        self.btn_toggle.setCheckable(True)
        self.btn_toggle.setStyleSheet(STYLE_START)
        self.btn_toggle.clicked.connect(self.toggle_measurement)
        row2.addWidget(self.btn_toggle)
 
        self.btn_pause = QtWidgets.QPushButton("Pause")
        self.btn_pause.setCheckable(True)
        self.btn_pause.setEnabled(False)
        self.btn_pause.toggled.connect(self._on_pause_toggled)
        row2.addWidget(self.btn_pause)
 
        self.btn_reset = QtWidgets.QPushButton("Nullstill")
        self.btn_reset.clicked.connect(self.clear_buffers)
        row2.addWidget(self.btn_reset)
 
        self.status_label = QtWidgets.QLabel("Status: Klar")
        self.status_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        row2.addWidget(self.status_label, stretch=1)
 
        main_layout.addLayout(row2)
 
        # --- Grafer ---
        self.pw1, self.line1, self.box1 = make_plot("Akselerasjon", (255, 255, 0), "#ffff00", "m/s²")
        self.pw2, self.line2, self.box2 = make_plot("Fart", (0, 255, 255), "#00ffff", "m/s")
        self.pw3, self.line3, self.box3 = make_plot("Temperatur", (255, 0, 128), "#ff0080", "°C")
        for pw in (self.pw1, self.pw2, self.pw3):
            main_layout.addWidget(pw)
 
        # --- Rullende buffere ---
        n = self.MAX_POINTS
        self.x_data = deque(maxlen=n)
        self.y_acc = deque(maxlen=n)
        self.y_fart = deque(maxlen=n)
        self.y_temp = deque(maxlen=n)
 
        self.worker = None
        self.log_file = None
        self.log_writer = None
 
        self.refresh_ports()
 
    # ------------------------------------------------------------------
    # Portvalg
    # ------------------------------------------------------------------
    def refresh_ports(self):
        current = self.port_combo.currentText()
        self.port_combo.clear()
        ports = available_ports()
        self.port_combo.addItems(ports)
        if current in ports:
            self.port_combo.setCurrentText(current)
        self._update_port_enabled()
 
    def _update_port_enabled(self):
        """Port-valget er bare aktivt når vi ikke simulerer og ikke måler."""
        enabled = not self.chk_sim.isChecked() and self.worker is None
        self.port_combo.setEnabled(enabled)
        self.btn_refresh.setEnabled(enabled)
 
    # ------------------------------------------------------------------
    # Start / stopp
    # ------------------------------------------------------------------
    def toggle_measurement(self, checked):
        if checked:
            self.start_measurement()
        else:
            self.stop_measurement("Status: Måling stoppet.")
 
    def start_measurement(self):
        simulate = self.chk_sim.isChecked()
        port = self.port_combo.currentText()
 
        if not simulate and not port:
            self.btn_toggle.setChecked(False)
            self.status_label.setText("Status: Ingen serieport valgt/funnet.")
            return
 
        self.clear_buffers()
        if self.chk_log.isChecked():
            self._open_log()
 
        self.worker = TISerialWorker(port=port, baudrate=115200, simulate=simulate)
        self.worker.values_received.connect(self.handle_new_data)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()
 
        self.btn_toggle.setText("Stopp Måling")
        self.btn_toggle.setStyleSheet(STYLE_STOP)
        self.btn_pause.setEnabled(True)
        self.chk_sim.setEnabled(False)
        self.chk_log.setEnabled(False)
        self.status_label.setText("Status: Simulerer data..." if simulate else f"Status: Kobler til {port}...")
        self._update_port_enabled()
 
    def stop_measurement(self, status_text):
        if self.worker:
            # Koble fra slik at forsinkede signaler ikke havner i GUI-et
            for sig, slot in (
                (self.worker.values_received, self.handle_new_data),
                (self.worker.error, self.on_worker_error),
            ):
                try:
                    sig.disconnect(slot)
                except (RuntimeError, TypeError):
                    pass
            self.worker.stop()
            self.worker = None
 
        self._close_log()
 
        self.btn_toggle.setChecked(False)
        self.btn_toggle.setText("Start Måling")
        self.btn_toggle.setStyleSheet(STYLE_START)
        self.btn_pause.setChecked(False)
        self.btn_pause.setEnabled(False)
        self.chk_sim.setEnabled(True)
        self.chk_log.setEnabled(True)
        self.status_label.setText(status_text)
        self._update_port_enabled()
 
    def on_worker_error(self, message):
        self.stop_measurement(f"Status: {message}")
 
    # ------------------------------------------------------------------
    # Pause / nullstill
    # ------------------------------------------------------------------
    def _on_pause_toggled(self, paused):
        self.btn_pause.setText("Fortsett" if paused else "Pause")
 
    def clear_buffers(self):
        for buf in (self.x_data, self.y_acc, self.y_fart, self.y_temp):
            buf.clear()
        for line in (self.line1, self.line2, self.line3):
            line.setData([], [])
 
    # ------------------------------------------------------------------
    # CSV-logging
    # ------------------------------------------------------------------
    def _open_log(self):
        name = f"telemetri_{datetime.now():%Y%m%d_%H%M%S}.csv"
        try:
            self.log_file = open(name, "w", newline="", encoding="utf-8")
            self.log_writer = csv.writer(self.log_file)
            self.log_writer.writerow(["tid_s", "akselerasjon_m_s2", "fart_m_s", "temperatur_C"])
        except OSError as e:
            self.log_file = None
            self.log_writer = None
            self.status_label.setText(f"Status: Kunne ikke åpne loggfil: {e}")
 
    def _close_log(self):
        if self.log_file:
            self.log_file.close()
        self.log_file = None
        self.log_writer = None
 
    # ------------------------------------------------------------------
    # Ny data
    # ------------------------------------------------------------------
    def handle_new_data(self, t, acc, fart, temp):
        # Logging skjer alltid, også når visningen er pauset
        if self.log_writer:
            self.log_writer.writerow([f"{t:.3f}", acc, fart, temp])
            self.log_file.flush()
 
        if self.btn_pause.isChecked():
            return
 
        self.x_data.append(t)
        self.y_acc.append(acc)
        self.y_fart.append(fart)
        self.y_temp.append(temp)
 
        x = list(self.x_data)
        self.line1.setData(x, list(self.y_acc))
        self.line2.setData(x, list(self.y_fart))
        self.line3.setData(x, list(self.y_temp))
 
        self.box1.setText(f"{acc:6.1f} m/s²")
        self.box2.setText(f"{fart:6.1f} m/s")
        self.box3.setText(f"{temp:6.1f} °C")
 
        self.status_label.setText(
            f"Mottar | t={t:.1f} s | Aks: {acc:.1f} | Fart: {fart:.1f} | Temp: {temp:.1f}"
        )
 
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        self.stop_measurement("Status: Avsluttet.")
        event.accept()
 
 
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MultiLiveDataWindow()
    window.show()
    sys.exit(app.exec())
 