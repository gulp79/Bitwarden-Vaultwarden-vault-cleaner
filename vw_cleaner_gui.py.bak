
# vw_cleaner_gui.py
import os
import datetime
from PySide6 import QtCore, QtGui, QtWidgets
from vw_cleaner_core import clean_vault, DEFAULT_OUTPUT, DEFAULT_DELETED

MATRIX_QSS = """
QWidget {
  background-color: #050806;
  color: #00ff66;
  font-family: Consolas, "Courier New", monospace;
  font-size: 12px;
}
QLineEdit, QTextEdit {
  background-color: #07110b;
  border: 1px solid #00aa44;
  padding: 6px;
  selection-background-color: #00ff66;
  selection-color: #000000;
}
QPushButton {
  background-color: #061a10;
  border: 1px solid #00ff66;
  padding: 8px 12px;
}
QPushButton:hover { background-color: #0a2a18; }
QPushButton:pressed { background-color: #00aa44; color: #000; }
QProgressBar {
  border: 1px solid #00aa44;
  text-align: center;
  background-color: #07110b;
}
QProgressBar::chunk {
  background-color: #00ff66;
}
QGroupBox {
  border: 1px solid #00aa44;
  margin-top: 10px;
}
QGroupBox::title {
  subcontrol-origin: margin;
  left: 10px;
  padding: 0 3px 0 3px;
}
"""

class Worker(QtCore.QObject):
    log = QtCore.Signal(str)
    progress = QtCore.Signal(int, int)
    finished = QtCore.Signal(dict)
    failed = QtCore.Signal(str)

    def __init__(self, input_file, output_file, deleted_file):
        super().__init__()
        self.input_file = input_file
        self.output_file = output_file
        self.deleted_file = deleted_file

    @QtCore.Slot()
    def run(self):
        try:
            stats = clean_vault(
                input_file=self.input_file,
                output_file=self.output_file,
                deleted_file=self.deleted_file,
                log_cb=self.log.emit,
                progress_cb=lambda d, t: self.progress.emit(d, t),
            )
            self.finished.emit(stats)
        except Exception as e:
            self.failed.emit(str(e))

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bitwarden/Vaultwarden Cleaner — Matrix GUI")
        self.resize(900, 650)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        layout = QtWidgets.QVBoxLayout(central)

        warn = QtWidgets.QLabel(
            "⚠ ATTENZIONE: il file contiene password in chiaro durante l'elaborazione.\n"
            "Lavora sempre su una COPIA e cancella subito il file 'deleted' dopo verifica."
        )
        warn.setStyleSheet("color: #9dffb8; border: 1px solid #00aa44; padding: 10px;")
        layout.addWidget(warn)

        box = QtWidgets.QGroupBox("File")
        form = QtWidgets.QFormLayout(box)

        self.inp = QtWidgets.QLineEdit()
        self.out = QtWidgets.QLineEdit(DEFAULT_OUTPUT)
        self.del_ = QtWidgets.QLineEdit(DEFAULT_DELETED)

        btn_in = QtWidgets.QPushButton("Sfoglia…")
        btn_out = QtWidgets.QPushButton("Scegli…")
        btn_del = QtWidgets.QPushButton("Scegli…")

        h1 = QtWidgets.QHBoxLayout()
        h1.addWidget(self.inp); h1.addWidget(btn_in)

        h2 = QtWidgets.QHBoxLayout()
        h2.addWidget(self.out); h2.addWidget(btn_out)

        h3 = QtWidgets.QHBoxLayout()
        h3.addWidget(self.del_); h3.addWidget(btn_del)

        form.addRow("Input JSON:", h1)
        form.addRow("Output JSON:", h2)
        form.addRow("Deleted JSON:", h3)

        layout.addWidget(box)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.log_view = QtWidgets.QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view, 1)

        buttons = QtWidgets.QHBoxLayout()
        self.run_btn = QtWidgets.QPushButton("ESEGUI PULIZIA")
        self.open_btn = QtWidgets.QPushButton("Apri cartella output")
        self.open_btn.setEnabled(False)
        buttons.addWidget(self.run_btn)
        buttons.addWidget(self.open_btn)
        layout.addLayout(buttons)

        btn_in.clicked.connect(self.browse_input)
        btn_out.clicked.connect(self.browse_output)
        btn_del.clicked.connect(self.browse_deleted)
        self.run_btn.clicked.connect(self.start)
        self.open_btn.clicked.connect(self.open_output_folder)

        self._last_output_dir = None

    def append_log(self, msg: str):
        self.log_view.append(msg)
        self.log_view.moveCursor(QtGui.QTextCursor.End)

    def browse_input(self):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Scegli export JSON", "", "JSON (*.json);;Tutti i file (*)")
        if fn:
            self.inp.setText(fn)
            # suggerisci output/deleted nella stessa cartella
            base_dir = os.path.dirname(fn)
            date = datetime.datetime.now().strftime("%Y%m%d")
            self.out.setText(os.path.join(base_dir, f"bitwarden_cleaned_{date}.json"))
            self.del_.setText(os.path.join(base_dir, f"bitwarden_deleted_{date}.json"))

    def browse_output(self):
        fn, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Salva output JSON", self.out.text(), "JSON (*.json)")
        if fn:
            self.out.setText(fn)

    def browse_deleted(self):
        fn, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Salva deleted JSON", self.del_.text(), "JSON (*.json)")
        if fn:
            self.del_.setText(fn)

    def start(self):
        input_file = self.inp.text().strip()
        output_file = self.out.text().strip()
        deleted_file = self.del_.text().strip()

        if not input_file:
            QtWidgets.QMessageBox.warning(self, "Errore", "Seleziona un file di input JSON.")
            return

        self.run_btn.setEnabled(False)
        self.open_btn.setEnabled(False)
        self.progress.setValue(0)
        self.log_view.clear()
        self.append_log("[GUI] Avvio elaborazione...")

        self.thread = QtCore.QThread(self)
        self.worker = Worker(input_file, output_file, deleted_file)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self.append_log)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)

        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def on_progress(self, done: int, total: int):
        if total <= 0:
            self.progress.setValue(0)
            return
        pct = int((done / total) * 100)
        self.progress.setValue(max(0, min(100, pct)))

    def on_finished(self, stats: dict):
        self.append_log("[GUI] ✅ Completato.")
        self.append_log(f"[GUI] Rimossi: {stats.get('removed')} | Totale finale: {stats.get('total_end')}")
        self.run_btn.setEnabled(True)
        self._last_output_dir = os.path.dirname(stats.get("output_file", "") or "") or None
        self.open_btn.setEnabled(bool(self._last_output_dir))

    def on_failed(self, err: str):
        self.append_log("[GUI] ❌ Errore: " + err)
        QtWidgets.QMessageBox.critical(self, "Errore", err)
        self.run_btn.setEnabled(True)

    def open_output_folder(self):
        if not self._last_output_dir:
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self._last_output_dir))

def main():
    app = QtWidgets.QApplication([])
    app.setStyleSheet(MATRIX_QSS)
    w = MainWindow()
    w.show()
    app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
