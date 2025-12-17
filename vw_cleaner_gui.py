# vw_cleaner_gui.py
import os
import datetime
from PySide6 import QtCore, QtGui, QtWidgets
from vw_cleaner_core import clean_vault, DEFAULT_OUTPUT, DEFAULT_DELETED

MATRIX_QSS = """
QWidget {
  background-color: #0a0e0d;
  color: #00ff66;
  font-family: "Consolas", "Courier New", monospace;
  font-size: 13px;
}

QMainWindow {
  background-color: #0a0e0d;
}

QLineEdit, QTextEdit {
  background-color: #0d1612;
  border: 1px solid #00aa44;
  border-radius: 4px;
  padding: 8px;
  selection-background-color: #00ff66;
  selection-color: #000000;
}

QLineEdit:focus, QTextEdit:focus {
  border: 1px solid #00ff66;
  background-color: #0f1a15;
}

QLineEdit:disabled, QTextEdit:disabled {
  background-color: #080b0a;
  color: #007733;
  border-color: #005522;
}

QPushButton {
  background-color: #0d2418;
  border: 1px solid #00aa44;
  border-radius: 4px;
  padding: 10px 16px;
  font-weight: bold;
}

QPushButton:hover {
  background-color: #11361f;
  border-color: #00ff66;
}

QPushButton:pressed {
  background-color: #00aa44;
  color: #000;
}

QPushButton:disabled {
  background-color: #070a08;
  border-color: #004422;
  color: #005522;
}

QPushButton#primaryButton {
  background-color: #0d4428;
  border: 2px solid #00ff66;
  padding: 12px 20px;
  font-size: 14px;
}

QPushButton#primaryButton:hover {
  background-color: #11562f;
  box-shadow: 0 0 10px #00aa44;
}

QPushButton#dangerButton {
  background-color: #4a1a1a;
  border-color: #ff4444;
  color: #ff6666;
}

QPushButton#dangerButton:hover {
  background-color: #5a2222;
  border-color: #ff6666;
}

QProgressBar {
  border: 1px solid #00aa44;
  border-radius: 4px;
  text-align: center;
  background-color: #0d1612;
  height: 24px;
}

QProgressBar::chunk {
  background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #00aa44, stop:1 #00ff66);
  border-radius: 3px;
}

QGroupBox {
  border: 1px solid #00aa44;
  border-radius: 6px;
  margin-top: 12px;
  padding-top: 12px;
  font-weight: bold;
}

QGroupBox::title {
  subcontrol-origin: margin;
  subcontrol-position: top left;
  left: 12px;
  padding: 0 6px;
  color: #00ff66;
}

QLabel {
  color: #9dffb8;
}

QLabel#warningLabel {
  color: #ffff66;
  background-color: #2a2a0a;
  border: 2px solid #ffcc00;
  border-radius: 6px;
  padding: 12px;
}

QLabel#titleLabel {
  color: #00ff66;
  font-size: 24px;
  font-weight: bold;
  padding: 10px;
}

QLabel#statsLabel {
  color: #00ff66;
  font-size: 16px;
  font-weight: bold;
  padding: 8px;
  background-color: #0d2418;
  border: 1px solid #00aa44;
  border-radius: 4px;
}

QTextEdit#logView {
  font-family: "Consolas", "Courier New", monospace;
  font-size: 11px;
  line-height: 1.4;
}

QScrollBar:vertical {
  border: 1px solid #00aa44;
  background: #0d1612;
  width: 14px;
  border-radius: 3px;
}

QScrollBar::handle:vertical {
  background: #00aa44;
  border-radius: 3px;
  min-height: 20px;
}

QScrollBar::handle:vertical:hover {
  background: #00ff66;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
  height: 0px;
}

QToolTip {
  background-color: #0d2418;
  color: #00ff66;
  border: 1px solid #00aa44;
  padding: 6px;
}
"""


class AnimatedLabel(QtWidgets.QLabel):
    """Label con effetto fade-in per le statistiche"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.effect = QtWidgets.QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.animation = QtCore.QPropertyAnimation(self.effect, b"opacity")
        
    def fade_in(self):
        self.animation.setDuration(600)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QtCore.QEasingCurve.InOutQuad)
        self.animation.start()


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
        self.setWindowTitle("Bitwarden/Vaultwarden Vault Cleaner")
        self.resize(1100, 750)
        
        # Centra la finestra
        self.center_window()

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header con titolo
        header = QtWidgets.QLabel("⚡ VAULT CLEANER")
        header.setObjectName("titleLabel")
        header.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(header)

        # Warning box
        warn_frame = QtWidgets.QFrame()
        warn_layout = QtWidgets.QVBoxLayout(warn_frame)
        warn = QtWidgets.QLabel(
            "⚠️  ATTENZIONE SICUREZZA\n\n"
            "• Il file contiene password in chiaro durante l'elaborazione\n"
            "• Lavora sempre su una COPIA del tuo export\n"
            "• Il file 'deleted' contiene credenziali: eliminalo subito dopo la verifica"
        )
        warn.setObjectName("warningLabel")
        warn.setWordWrap(True)
        warn_layout.addWidget(warn)
        layout.addWidget(warn_frame)

        # File selection group
        file_box = QtWidgets.QGroupBox("📁 Selezione File")
        file_layout = QtWidgets.QGridLayout(file_box)
        file_layout.setSpacing(12)
        file_layout.setColumnStretch(1, 1)

        # Input file
        lbl_in = QtWidgets.QLabel("File Input (JSON):")
        self.inp = QtWidgets.QLineEdit()
        self.inp.setPlaceholderText("Seleziona il file export di Bitwarden...")
        btn_in = QtWidgets.QPushButton("🔍 Sfoglia")
        btn_in.setMaximumWidth(120)
        
        file_layout.addWidget(lbl_in, 0, 0)
        file_layout.addWidget(self.inp, 0, 1)
        file_layout.addWidget(btn_in, 0, 2)

        # Output file
        lbl_out = QtWidgets.QLabel("File Output (pulito):")
        self.out = QtWidgets.QLineEdit(DEFAULT_OUTPUT)
        self.out.setPlaceholderText("File vault pulito...")
        btn_out = QtWidgets.QPushButton("📝 Scegli")
        btn_out.setMaximumWidth(120)
        
        file_layout.addWidget(lbl_out, 1, 0)
        file_layout.addWidget(self.out, 1, 1)
        file_layout.addWidget(btn_out, 1, 2)

        # Deleted file
        lbl_del = QtWidgets.QLabel("File Eliminati:")
        self.del_ = QtWidgets.QLineEdit(DEFAULT_DELETED)
        self.del_.setPlaceholderText("File con elementi rimossi...")
        btn_del = QtWidgets.QPushButton("📝 Scegli")
        btn_del.setMaximumWidth(120)
        
        file_layout.addWidget(lbl_del, 2, 0)
        file_layout.addWidget(self.del_, 2, 1)
        file_layout.addWidget(btn_del, 2, 2)

        layout.addWidget(file_box)

        # Progress section
        progress_container = QtWidgets.QWidget()
        progress_layout = QtWidgets.QVBoxLayout(progress_container)
        progress_layout.setSpacing(8)
        
        progress_label = QtWidgets.QLabel("Avanzamento:")
        progress_layout.addWidget(progress_label)
        
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p% - %v/%m elementi")
        progress_layout.addWidget(self.progress)
        
        layout.addWidget(progress_container)

        # Stats panel (inizialmente nascosto)
        self.stats_panel = AnimatedLabel()
        self.stats_panel.setObjectName("statsLabel")
        self.stats_panel.setAlignment(QtCore.Qt.AlignCenter)
        self.stats_panel.hide()
        layout.addWidget(self.stats_panel)

        # Log view
        log_group = QtWidgets.QGroupBox("📊 Log Elaborazione")
        log_layout = QtWidgets.QVBoxLayout(log_group)
        
        self.log_view = QtWidgets.QTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        log_layout.addWidget(self.log_view)
        
        layout.addWidget(log_group, 1)

        # Action buttons
        btn_container = QtWidgets.QWidget()
        btn_layout = QtWidgets.QHBoxLayout(btn_container)
        btn_layout.setSpacing(12)
        
        self.run_btn = QtWidgets.QPushButton("▶️  ESEGUI PULIZIA")
        self.run_btn.setObjectName("primaryButton")
        self.run_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.run_btn.setMinimumHeight(50)
        
        self.open_btn = QtWidgets.QPushButton("📂 Apri Cartella Output")
        self.open_btn.setEnabled(False)
        self.open_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.open_btn.setMinimumHeight(50)
        
        self.clear_btn = QtWidgets.QPushButton("🗑️  Pulisci Log")
        self.clear_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.clear_btn.setMinimumHeight(50)
        
        btn_layout.addWidget(self.run_btn, 2)
        btn_layout.addWidget(self.open_btn, 1)
        btn_layout.addWidget(self.clear_btn, 1)
        
        layout.addWidget(btn_container)

        # Connections
        btn_in.clicked.connect(self.browse_input)
        btn_out.clicked.connect(self.browse_output)
        btn_del.clicked.connect(self.browse_deleted)
        self.run_btn.clicked.connect(self.start)
        self.open_btn.clicked.connect(self.open_output_folder)
        self.clear_btn.clicked.connect(self.clear_log)

        # Drag & Drop
        self.setAcceptDrops(True)

        self._last_output_dir = None
        self._processing = False

    def center_window(self):
        """Centra la finestra sullo schermo"""
        screen = QtWidgets.QApplication.primaryScreen().geometry()
        size = self.geometry()
        self.move(
            (screen.width() - size.width()) // 2,
            (screen.height() - size.height()) // 2
        )

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QtGui.QDropEvent):
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith('.json'):
                self.inp.setText(file_path)
                self.update_output_paths(file_path)

    def append_log(self, msg: str):
        """Aggiunge messaggio al log con colorazione"""
        # Colora i messaggi in base al contenuto
        if "✅" in msg or "Completato" in msg:
            color = "#00ff66"
        elif "❌" in msg or "Errore" in msg:
            color = "#ff6666"
        elif "⚠" in msg or "ATTENZIONE" in msg:
            color = "#ffff66"
        else:
            color = "#9dffb8"
        
        self.log_view.append(f'<span style="color: {color};">{msg}</span>')
        self.log_view.moveCursor(QtGui.QTextCursor.End)

    def clear_log(self):
        """Pulisce il log"""
        self.log_view.clear()
        self.append_log("[GUI] Log pulito.")

    def update_output_paths(self, input_path: str):
        """Aggiorna i path di output basandosi sull'input"""
        base_dir = os.path.dirname(input_path)
        date = datetime.datetime.now().strftime("%Y%m%d")
        self.out.setText(os.path.join(base_dir, f"bitwarden_cleaned_{date}.json"))
        self.del_.setText(os.path.join(base_dir, f"bitwarden_deleted_{date}.json"))

    def browse_input(self):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 
            "Scegli export JSON Bitwarden", 
            "", 
            "JSON Files (*.json);;All Files (*)"
        )
        if fn:
            self.inp.setText(fn)
            self.update_output_paths(fn)

    def browse_output(self):
        fn, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 
            "Salva output pulito", 
            self.out.text(), 
            "JSON Files (*.json)"
        )
        if fn:
            self.out.setText(fn)

    def browse_deleted(self):
        fn, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 
            "Salva file elementi eliminati", 
            self.del_.text(), 
            "JSON Files (*.json)"
        )
        if fn:
            self.del_.setText(fn)

    def validate_inputs(self) -> tuple[bool, str]:
        """Valida gli input prima dell'esecuzione"""
        input_file = self.inp.text().strip()
        output_file = self.out.text().strip()
        deleted_file = self.del_.text().strip()

        if not input_file:
            return False, "Seleziona un file di input JSON."
        
        if not os.path.exists(input_file):
            return False, f"Il file di input non esiste:\n{input_file}"
        
        if not output_file:
            return False, "Specifica un nome per il file di output."
        
        if not deleted_file:
            return False, "Specifica un nome per il file degli elementi eliminati."
        
        if input_file == output_file:
            return False, "Il file di output non può essere uguale all'input."
        
        return True, ""

    def start(self):
        if self._processing:
            return

        # Valida input
        valid, error_msg = self.validate_inputs()
        if not valid:
            QtWidgets.QMessageBox.warning(self, "Errore", error_msg)
            return

        input_file = self.inp.text().strip()
        output_file = self.out.text().strip()
        deleted_file = self.del_.text().strip()

        # Conferma sovrascrittura
        if os.path.exists(output_file):
            reply = QtWidgets.QMessageBox.question(
                self,
                "Conferma Sovrascrittura",
                f"Il file di output esiste già:\n{output_file}\n\nSovrascrivere?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                return

        # UI state
        self._processing = True
        self.run_btn.setEnabled(False)
        self.open_btn.setEnabled(False)
        self.inp.setEnabled(False)
        self.out.setEnabled(False)
        self.del_.setEnabled(False)
        self.stats_panel.hide()
        self.progress.setValue(0)
        self.progress.setFormat("Inizializzazione...")
        self.log_view.clear()
        self.append_log("[GUI] 🚀 Avvio elaborazione...")

        # Worker thread
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
        
        self.progress.setMaximum(total)
        self.progress.setValue(done)
        self.progress.setFormat(f"%p% - {done}/{total} elementi")

    def on_finished(self, stats: dict):
        self._processing = False
        
        self.append_log("[GUI] ✅ Elaborazione completata con successo!")
        
        # Mostra statistiche
        stats_text = (
            f"📊 RISULTATI: "
            f"Totale iniziale: {stats.get('total_start', 0)} | "
            f"Totale finale: {stats.get('total_end', 0)} | "
            f"Rimossi: {stats.get('removed', 0)} duplicati"
        )
        self.stats_panel.setText(stats_text)
        self.stats_panel.show()
        self.stats_panel.fade_in()
        
        # Re-enable UI
        self.run_btn.setEnabled(True)
        self.inp.setEnabled(True)
        self.out.setEnabled(True)
        self.del_.setEnabled(True)
        
        self._last_output_dir = os.path.dirname(stats.get("output_file", "") or "")
        self.open_btn.setEnabled(bool(self._last_output_dir))
        
        # Success dialog
        QtWidgets.QMessageBox.information(
            self,
            "✅ Completato",
            f"Vault pulito con successo!\n\n"
            f"Elementi iniziali: {stats.get('total_start', 0)}\n"
            f"Elementi finali: {stats.get('total_end', 0)}\n"
            f"Duplicati rimossi: {stats.get('removed', 0)}\n\n"
            f"⚠️ RICORDA: Elimina il file 'deleted' dopo aver verificato il risultato!"
        )

    def on_failed(self, err: str):
        self._processing = False
        
        self.append_log(f"[GUI] ❌ Errore: {err}")
        
        # Re-enable UI
        self.run_btn.setEnabled(True)
        self.inp.setEnabled(True)
        self.out.setEnabled(True)
        self.del_.setEnabled(True)
        
        QtWidgets.QMessageBox.critical(
            self,
            "❌ Errore",
            f"Si è verificato un errore durante l'elaborazione:\n\n{err}\n\n"
            f"Controlla il log per maggiori dettagli."
        )

    def open_output_folder(self):
        if not self._last_output_dir:
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self._last_output_dir))


def main():
    app = QtWidgets.QApplication([])
    app.setStyleSheet(MATRIX_QSS)
    
    # Icon (opzionale - richiede un file icon)
    # app.setWindowIcon(QtGui.QIcon("icon.png"))
    
    window = MainWindow()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
