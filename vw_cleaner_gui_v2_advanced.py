# vw_cleaner_gui_v2.py
"""
Bitwarden/Vaultwarden Vault Cleaner - Advanced GUI v2.0

Features:
- Strict mode toggle
- Normalization level selection
- Explain mode (decision log)
- Extended metrics display
- Tooltips and help text
- English interface

Author: Principal Engineer Review
Date: 2026-01-29
"""

import os
import datetime
from PySide6 import QtCore, QtGui, QtWidgets

from vw_cleaner_core_v2 import (
    clean_vault_advanced,
    CleanerConfig,
    MergePolicy,
    DEFAULT_OUTPUT,
    DEFAULT_DELETED,
)
from vw_normalization import NormalizationLevel


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

QLabel#versionLabel {
  color: #007733;
  font-size: 10px;
  font-style: italic;
}

QLabel#statsLabel {
  color: #00ff66;
  font-size: 14px;
  font-weight: bold;
  padding: 12px;
  background-color: #0d2418;
  border: 1px solid #00aa44;
  border-radius: 4px;
}

QTextEdit#logView {
  font-family: "Consolas", "Courier New", monospace;
  font-size: 11px;
  line-height: 1.4;
}

QCheckBox {
  spacing: 8px;
}

QCheckBox::indicator {
  width: 18px;
  height: 18px;
  border: 2px solid #00aa44;
  border-radius: 3px;
  background-color: #0d1612;
}

QCheckBox::indicator:hover {
  border-color: #00ff66;
  background-color: #0f1a15;
}

QCheckBox::indicator:checked {
  background-color: #00aa44;
  border-color: #00ff66;
}

QCheckBox::indicator:checked:hover {
  background-color: #00ff66;
}

QComboBox {
  background-color: #0d1612;
  border: 1px solid #00aa44;
  border-radius: 4px;
  padding: 6px 12px;
  min-width: 150px;
}

QComboBox:hover {
  border-color: #00ff66;
  background-color: #0f1a15;
}

QComboBox:focus {
  border: 1px solid #00ff66;
}

QComboBox::drop-down {
  border: none;
  width: 20px;
}

QComboBox::down-arrow {
  image: none;
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-top: 5px solid #00aa44;
  margin-right: 5px;
}

QComboBox QAbstractItemView {
  background-color: #0d1612;
  border: 1px solid #00aa44;
  selection-background-color: #0d2418;
  selection-color: #00ff66;
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
  border: 2px solid #00aa44;
  padding: 8px;
  font-size: 12px;
}
"""


class AnimatedLabel(QtWidgets.QLabel):
    """Label with fade-in animation effect"""
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
    """Background worker for vault cleaning operations"""
    log = QtCore.Signal(str)
    progress = QtCore.Signal(int, int)
    finished = QtCore.Signal(object)  # CleanerStats object
    failed = QtCore.Signal(str)

    def __init__(self, input_file, output_file, deleted_file, config: CleanerConfig):
        super().__init__()
        self.input_file = input_file
        self.output_file = output_file
        self.deleted_file = deleted_file
        self.config = config

    @QtCore.Slot()
    def run(self):
        try:
            stats = clean_vault_advanced(
                input_file=self.input_file,
                output_file=self.output_file,
                deleted_file=self.deleted_file,
                config=self.config,
                log_cb=self.log.emit,
                progress_cb=lambda d, t: self.progress.emit(d, t),
            )
            self.finished.emit(stats)
        except Exception as e:
            self.failed.emit(str(e))


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bitwarden/Vaultwarden Vault Cleaner v2.0")
        self.resize(1200, 850)
        
        # Center window
        self.center_window()

        # Main layout
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # === HEADER ===
        header_layout = QtWidgets.QVBoxLayout()
        
        header = QtWidgets.QLabel("⚡ VAULT CLEANER")
        header.setObjectName("titleLabel")
        header.setAlignment(QtCore.Qt.AlignCenter)
        header_layout.addWidget(header)
        
        version = QtWidgets.QLabel("Advanced Edition v2.0 - Deterministic & Idempotent")
        version.setObjectName("versionLabel")
        version.setAlignment(QtCore.Qt.AlignCenter)
        header_layout.addWidget(version)
        
        main_layout.addLayout(header_layout)

        # === WARNING BOX ===
        warn_frame = QtWidgets.QFrame()
        warn_layout = QtWidgets.QVBoxLayout(warn_frame)
        warn = QtWidgets.QLabel(
            "⚠️  SECURITY WARNING\n\n"
            "• This file contains passwords in plain text during processing\n"
            "• Always work on a COPY of your vault export\n"
            "• The 'deleted' file contains credentials - delete it after verification\n"
            "• Use --dry-run first on production vaults"
        )
        warn.setObjectName("warningLabel")
        warn.setWordWrap(True)
        warn_layout.addWidget(warn)
        main_layout.addWidget(warn_frame)

        # === FILE SELECTION ===
        file_box = QtWidgets.QGroupBox("📁 File Selection")
        file_layout = QtWidgets.QGridLayout(file_box)
        file_layout.setSpacing(12)
        file_layout.setColumnStretch(1, 1)

        # Input file
        lbl_in = QtWidgets.QLabel("Input File (JSON):")
        lbl_in.setToolTip("Select your Bitwarden/Vaultwarden export JSON file")
        self.inp = QtWidgets.QLineEdit()
        self.inp.setPlaceholderText("Select Bitwarden export file...")
        self.inp.setToolTip("The vault export file to process")
        btn_in = QtWidgets.QPushButton("🔍 Browse")
        btn_in.setMaximumWidth(120)
        btn_in.setToolTip("Browse for input file")
        
        file_layout.addWidget(lbl_in, 0, 0)
        file_layout.addWidget(self.inp, 0, 1)
        file_layout.addWidget(btn_in, 0, 2)

        # Output file
        lbl_out = QtWidgets.QLabel("Output File (cleaned):")
        lbl_out.setToolTip("Where to save the cleaned vault")
        self.out = QtWidgets.QLineEdit()
        self.out.setPlaceholderText("Cleaned vault (auto-generated)")
        self.out.setToolTip("Output file path (auto-generated based on input)")
        btn_out = QtWidgets.QPushButton("🔍 Browse")
        btn_out.setMaximumWidth(120)
        btn_out.setToolTip("Browse for output location")
        
        file_layout.addWidget(lbl_out, 1, 0)
        file_layout.addWidget(self.out, 1, 1)
        file_layout.addWidget(btn_out, 1, 2)

        # Deleted file
        lbl_del = QtWidgets.QLabel("Deleted Items File:")
        lbl_del.setToolTip("Where removed duplicates will be saved for verification")
        self.del_ = QtWidgets.QLineEdit()
        self.del_.setPlaceholderText("Removed items (auto-generated)")
        self.del_.setToolTip("File containing removed duplicates (DELETE after verification!)")
        btn_del = QtWidgets.QPushButton("🔍 Browse")
        btn_del.setMaximumWidth(120)
        btn_del.setToolTip("Browse for deleted items location")
        
        file_layout.addWidget(lbl_del, 2, 0)
        file_layout.addWidget(self.del_, 2, 1)
        file_layout.addWidget(btn_del, 2, 2)

        main_layout.addWidget(file_box)

        # === ADVANCED OPTIONS ===
        options_box = QtWidgets.QGroupBox("⚙️ Advanced Options")
        options_layout = QtWidgets.QGridLayout(options_box)
        options_layout.setSpacing(12)

        # Normalization level
        norm_label = QtWidgets.QLabel("Normalization Level:")
        norm_label.setToolTip(
            "Controls how aggressive matching is:\n\n"
            "• min (default): Trim whitespace, lowercase hostname\n"
            "  → SAFE, recommended for first use\n\n"
            "• std: + case-insensitive username, default port removal\n"
            "  → More duplicates found, still conservative\n\n"
            "• none: Exact match only\n"
            "  → Debug mode, very strict"
        )
        
        self.norm_combo = QtWidgets.QComboBox()
        self.norm_combo.addItem("Minimal (default - recommended)", "min")
        self.norm_combo.addItem("Standard (more aggressive)", "std")
        self.norm_combo.addItem("None (exact match only)", "none")
        self.norm_combo.setCurrentIndex(0)
        self.norm_combo.setToolTip(
            "min: Safe, trims whitespace and normalizes hostname\n"
            "std: Also makes username case-insensitive\n"
            "none: Exact match, no normalization"
        )
        
        options_layout.addWidget(norm_label, 0, 0)
        options_layout.addWidget(self.norm_combo, 0, 1)

        # Strict mode checkbox
        self.strict_check = QtWidgets.QCheckBox("Strict Mode (require shared URIs)")
        self.strict_check.setToolTip(
            "RECOMMENDED for maximum safety!\n\n"
            "✅ Enabled: Only merge if items share at least 1 URI\n"
            "   → Prevents false positives (e.g., admin/pass123 on bank.com vs shop.com)\n\n"
            "❌ Disabled: Merge if URIs match OR if one has no URIs (v1.0 behavior)\n"
            "   → More merges, but higher risk of mistakes\n\n"
            "💡 Use strict mode if you reuse credentials across services"
        )
        options_layout.addWidget(self.strict_check, 1, 0, 1, 2)

        # Explain mode checkbox
        self.explain_check = QtWidgets.QCheckBox("Explain Mode (generate decision log)")
        self.explain_check.setToolTip(
            "Generate a JSON file with detailed explanations:\n\n"
            "• Why each pair was merged (or not)\n"
            "• Which URIs were shared\n"
            "• Which fields were merged\n\n"
            "Useful for auditing and understanding the cleaning process"
        )
        options_layout.addWidget(self.explain_check, 2, 0, 1, 2)

        # Dry run checkbox
        self.dryrun_check = QtWidgets.QCheckBox("Dry Run (preview only, don't write files)")
        self.dryrun_check.setToolTip(
            "Preview mode - see what WOULD happen without making changes:\n\n"
            "✅ Safe to test settings\n"
            "✅ See metrics before committing\n"
            "✅ No files are modified\n\n"
            "💡 ALWAYS use this first on production vaults!"
        )
        options_layout.addWidget(self.dryrun_check, 3, 0, 1, 2)

        # Preserve metadata checkbox
        self.preserve_meta_check = QtWidgets.QCheckBox("Preserve Metadata (favorite, folders)")
        self.preserve_meta_check.setToolTip(
            "Preserve additional metadata from duplicates:\n\n"
            "• Favorite status\n"
            "• Folder assignments\n\n"
            "Note: URIs, notes, and TOTP are ALWAYS preserved regardless of this setting"
        )
        options_layout.addWidget(self.preserve_meta_check, 4, 0, 1, 2)

        main_layout.addWidget(options_box)

        # === PROGRESS ===
        prog_box = QtWidgets.QGroupBox("📊 Progress")
        prog_layout = QtWidgets.QVBoxLayout(prog_box)
        
        self.progress = QtWidgets.QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setFormat("Waiting...")
        prog_layout.addWidget(self.progress)
        
        main_layout.addWidget(prog_box)

        # === STATS PANEL (Extended) ===
        self.stats_panel = AnimatedLabel()
        self.stats_panel.setObjectName("statsLabel")
        self.stats_panel.setAlignment(QtCore.Qt.AlignLeft)
        self.stats_panel.setWordWrap(True)
        self.stats_panel.hide()
        main_layout.addWidget(self.stats_panel)

        # === LOG ===
        log_box = QtWidgets.QGroupBox("📝 Operation Log")
        log_layout = QtWidgets.QVBoxLayout(log_box)
        
        self.log_view = QtWidgets.QTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(180)
        log_layout.addWidget(self.log_view)
        
        main_layout.addWidget(log_box)

        # === BUTTONS ===
        btn_container = QtWidgets.QWidget()
        btn_layout = QtWidgets.QHBoxLayout(btn_container)
        btn_layout.setSpacing(12)
        
        self.run_btn = QtWidgets.QPushButton("▶️  RUN CLEANING")
        self.run_btn.setObjectName("primaryButton")
        self.run_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.run_btn.setMinimumHeight(50)
        self.run_btn.setToolTip("Start the vault cleaning process")
        
        self.open_btn = QtWidgets.QPushButton("📂 Open Output Folder")
        self.open_btn.setEnabled(False)
        self.open_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.open_btn.setMinimumHeight(50)
        self.open_btn.setToolTip("Open the folder containing output files")
        
        self.clear_btn = QtWidgets.QPushButton("🗑️  Clear Log")
        self.clear_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.clear_btn.setMinimumHeight(50)
        self.clear_btn.setToolTip("Clear the operation log")
        
        self.help_btn = QtWidgets.QPushButton("❓ Help")
        self.help_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.help_btn.setMinimumHeight(50)
        self.help_btn.setToolTip("Show detailed help and documentation")
        
        btn_layout.addWidget(self.run_btn, 3)
        btn_layout.addWidget(self.open_btn, 2)
        btn_layout.addWidget(self.clear_btn, 1)
        btn_layout.addWidget(self.help_btn, 1)
        
        main_layout.addWidget(btn_container)

        # === CONNECTIONS ===
        btn_in.clicked.connect(self.browse_input)
        btn_out.clicked.connect(self.browse_output)
        btn_del.clicked.connect(self.browse_deleted)
        self.run_btn.clicked.connect(self.start)
        self.open_btn.clicked.connect(self.open_output_folder)
        self.clear_btn.clicked.connect(self.clear_log)
        self.help_btn.clicked.connect(self.show_help)

        # Drag & Drop
        self.setAcceptDrops(True)

        self._last_output_dir = None
        self._processing = False

    def center_window(self):
        """Center window on screen"""
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
        """Append message to log with color coding"""
        if "✅" in msg or "Completed" in msg or "success" in msg.lower():
            color = "#00ff66"
        elif "❌" in msg or "Error" in msg or "Failed" in msg:
            color = "#ff6666"
        elif "⚠" in msg or "WARNING" in msg or "ATTENTION" in msg:
            color = "#ffff66"
        else:
            color = "#9dffb8"
        
        self.log_view.append(f'<span style="color: {color};">{msg}</span>')
        self.log_view.moveCursor(QtGui.QTextCursor.End)

    def clear_log(self):
        """Clear the log"""
        self.log_view.clear()
        self.append_log("[GUI] Log cleared.")

    def update_output_paths(self, input_path: str):
        """Update output paths based on input"""
        base_dir = os.path.dirname(input_path)
        date = datetime.datetime.now().strftime("%Y%m%d")
        self.out.setText(os.path.join(base_dir, f"bitwarden_cleaned_{date}.json"))
        self.del_.setText(os.path.join(base_dir, f"bitwarden_deleted_{date}.json"))

    def browse_input(self):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 
            "Select Bitwarden Export JSON", 
            "", 
            "JSON Files (*.json);;All Files (*)"
        )
        if fn:
            self.inp.setText(fn)
            self.update_output_paths(fn)

    def browse_output(self):
        fn, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 
            "Save Cleaned Output", 
            self.out.text(), 
            "JSON Files (*.json)"
        )
        if fn:
            self.out.setText(fn)

    def browse_deleted(self):
        fn, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 
            "Save Deleted Items", 
            self.del_.text(), 
            "JSON Files (*.json)"
        )
        if fn:
            self.del_.setText(fn)

    def validate_inputs(self) -> tuple[bool, str]:
        """Validate inputs before execution"""
        input_file = self.inp.text().strip()
        output_file = self.out.text().strip()
        deleted_file = self.del_.text().strip()

        if not input_file:
            return False, "Please select an input JSON file."
        
        if not os.path.exists(input_file):
            return False, f"Input file does not exist:\n{input_file}"
        
        if not output_file:
            return False, "Please specify an output file name."
        
        if not deleted_file:
            return False, "Please specify a deleted items file name."
        
        if input_file == output_file:
            return False, "Output file cannot be the same as input file."
        
        return True, ""

    def build_config(self) -> CleanerConfig:
        """Build CleanerConfig from UI state"""
        # Get normalization level
        norm_data = self.norm_combo.currentData()
        norm_level = NormalizationLevel(norm_data)
        
        # Get merge policy
        merge_policy = MergePolicy.STRICT if self.strict_check.isChecked() else MergePolicy.LENIENT
        
        # Build config
        config = CleanerConfig(
            normalization_level=norm_level,
            merge_policy=merge_policy,
            require_shared_uri=self.strict_check.isChecked(),
            preserve_all_metadata=self.preserve_meta_check.isChecked(),
            enable_explain=self.explain_check.isChecked(),
            enable_dry_run=self.dryrun_check.isChecked(),
        )
        
        return config

    def start(self):
        if self._processing:
            return

        # Validate
        valid, error_msg = self.validate_inputs()
        if not valid:
            QtWidgets.QMessageBox.warning(self, "Validation Error", error_msg)
            return

        input_file = self.inp.text().strip()
        output_file = self.out.text().strip()
        deleted_file = self.del_.text().strip()

        # Confirm overwrite
        if os.path.exists(output_file) and not self.dryrun_check.isChecked():
            reply = QtWidgets.QMessageBox.question(
                self,
                "Confirm Overwrite",
                f"Output file already exists:\n{output_file}\n\nOverwrite?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                return

        # Build config
        config = self.build_config()

        # UI state
        self._processing = True
        self.run_btn.setEnabled(False)
        self.open_btn.setEnabled(False)
        self.inp.setEnabled(False)
        self.out.setEnabled(False)
        self.del_.setEnabled(False)
        self.norm_combo.setEnabled(False)
        self.strict_check.setEnabled(False)
        self.explain_check.setEnabled(False)
        self.dryrun_check.setEnabled(False)
        self.preserve_meta_check.setEnabled(False)
        self.stats_panel.hide()
        self.progress.setValue(0)
        self.progress.setFormat("Initializing...")
        self.log_view.clear()
        
        mode_info = " [DRY RUN]" if config.enable_dry_run else ""
        self.append_log(f"[GUI] 🚀 Starting cleaning process{mode_info}...")
        self.append_log(f"[GUI] Normalization: {config.normalization_level.value}")
        self.append_log(f"[GUI] Merge Policy: {config.merge_policy.value}")
        if config.enable_explain:
            self.append_log("[GUI] Explain mode: Decision log will be generated")

        # Worker thread
        self.thread = QtCore.QThread(self)
        self.worker = Worker(input_file, output_file, deleted_file, config)
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
        self.progress.setFormat(f"%p% - {done}/{total} items")

    def on_finished(self, stats):
        """Handle completion with extended stats display"""
        self._processing = False
        
        self.append_log("[GUI] ✅ Processing completed successfully!")
        
        # Build extended stats text
        stats_lines = [
            "📊 RESULTS:",
            f"  Total items (start):     {stats.total_start}",
            f"  Total items (end):       {stats.total_end}",
            f"  Items removed:           {stats.removed}",
            "",
            f"  Groups analyzed:         {stats.groups_analyzed}",
            f"  Groups merged:           {stats.groups_merged}",
            f"  Groups kept separate:    {stats.groups_kept_separate}",
            "",
            f"  Merge operations:        {stats.merges_count}",
            f"  URI collisions avoided:  {stats.uri_collisions_avoided}",
            f"  TOTP seeds preserved:    {stats.totp_preserved}",
            f"  Notes concatenated:      {stats.notes_concatenated}",
            "",
            f"  Processing time:         {stats.processing_time_ms} ms",
        ]
        
        self.stats_panel.setText("\n".join(stats_lines))
        self.stats_panel.show()
        self.stats_panel.fade_in()
        
        # Re-enable UI
        self.run_btn.setEnabled(True)
        self.inp.setEnabled(True)
        self.out.setEnabled(True)
        self.del_.setEnabled(True)
        self.norm_combo.setEnabled(True)
        self.strict_check.setEnabled(True)
        self.explain_check.setEnabled(True)
        self.dryrun_check.setEnabled(True)
        self.preserve_meta_check.setEnabled(True)
        
        self._last_output_dir = os.path.dirname(stats.output_file or "")
        self.open_btn.setEnabled(bool(self._last_output_dir))
        
        # Success dialog
        msg_lines = [
            "Vault cleaning completed successfully!",
            "",
            f"Initial items:     {stats.total_start}",
            f"Final items:       {stats.total_end}",
            f"Duplicates removed: {stats.removed}",
            "",
            f"Groups analyzed:   {stats.groups_analyzed}",
            f"Groups merged:     {stats.groups_merged}",
        ]
        
        if stats.uri_collisions_avoided > 0:
            msg_lines.append(f"\n✅ URI collisions avoided: {stats.uri_collisions_avoided}")
            msg_lines.append("(Items with same credentials but different URIs were kept separate)")
        
        if stats.totp_preserved > 0:
            msg_lines.append(f"\n🔐 TOTP seeds preserved: {stats.totp_preserved}")
        
        if stats.decision_log_file:
            msg_lines.append(f"\n📋 Decision log saved: {os.path.basename(stats.decision_log_file)}")
        
        if stats.removed > 0:
            msg_lines.append("\n⚠️ REMEMBER:")
            msg_lines.append("• Verify the results before importing")
            msg_lines.append("• Delete the 'deleted' file after verification (contains credentials!)")
        
        QtWidgets.QMessageBox.information(
            self,
            "✅ Completed",
            "\n".join(msg_lines)
        )

    def on_failed(self, err: str):
        self._processing = False
        
        self.append_log(f"[GUI] ❌ Error: {err}")
        
        # Re-enable UI
        self.run_btn.setEnabled(True)
        self.inp.setEnabled(True)
        self.out.setEnabled(True)
        self.del_.setEnabled(True)
        self.norm_combo.setEnabled(True)
        self.strict_check.setEnabled(True)
        self.explain_check.setEnabled(True)
        self.dryrun_check.setEnabled(True)
        self.preserve_meta_check.setEnabled(True)
        
        QtWidgets.QMessageBox.critical(
            self,
            "❌ Error",
            f"An error occurred during processing:\n\n{err}\n\n"
            f"Check the log for more details."
        )

    def open_output_folder(self):
        if not self._last_output_dir:
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self._last_output_dir))

    def show_help(self):
        """Show comprehensive help dialog"""
        help_text = """
<h2 style="color: #00ff66;">Bitwarden/Vaultwarden Vault Cleaner v2.0</h2>

<h3 style="color: #00aa44;">Quick Start</h3>
<ol>
<li><b>Select input file:</b> Your Bitwarden/Vaultwarden export JSON</li>
<li><b>Configure options:</b> Use defaults for first time, or customize</li>
<li><b>Enable Dry Run:</b> Preview changes without modifying files</li>
<li><b>Click RUN CLEANING</b></li>
<li><b>Review results</b> and verify the 'deleted' file</li>
<li><b>Import</b> the cleaned vault back to Bitwarden/Vaultwarden</li>
</ol>

<h3 style="color: #00aa44;">Option Guide</h3>

<p><b>Normalization Level:</b></p>
<ul>
<li><b>Minimal (default):</b> Safe, trim whitespace, lowercase hostname - RECOMMENDED</li>
<li><b>Standard:</b> Also makes username case-insensitive - finds more duplicates</li>
<li><b>None:</b> Exact match only - very strict, for debugging</li>
</ul>

<p><b>Strict Mode:</b></p>
<ul>
<li><b>✅ Enabled:</b> Only merge if items share at least 1 URI</li>
<li>Prevents merging credentials reused across different services</li>
<li>Example: admin/pass123 on bank.com and shop.com → kept separate</li>
<li><b>RECOMMENDED</b> for maximum safety</li>
</ul>

<p><b>Explain Mode:</b></p>
<ul>
<li>Generates a JSON decision log</li>
<li>Shows why each pair was merged (or not)</li>
<li>Useful for auditing and understanding the process</li>
</ul>

<p><b>Dry Run:</b></p>
<ul>
<li>Preview mode - no files are written</li>
<li>See what WOULD happen without making changes</li>
<li><b>ALWAYS use this first</b> on production vaults!</li>
</ul>

<h3 style="color: #00aa44;">Merge Rules</h3>
<ul>
<li><b>URIs:</b> All URIs from all duplicates are preserved (union)</li>
<li><b>Notes:</b> Notes are concatenated with a separator</li>
<li><b>TOTP:</b> Seeds are preserved if master doesn't have one</li>
<li><b>Master selection:</b> Most recently updated item becomes master</li>
</ul>

<h3 style="color: #00aa44;">Safety Features</h3>
<ul>
<li>✅ Automatic backup before processing</li>
<li>✅ File permissions set to 0600 (owner-only)</li>
<li>✅ Passwords never printed in logs</li>
<li>✅ Idempotent: running twice gives same result</li>
<li>✅ Deterministic: same input always gives same output</li>
</ul>

<h3 style="color: #00aa44;">Important Notes</h3>
<ul>
<li>⚠️ <b>Always work on a COPY</b> of your vault export</li>
<li>⚠️ The 'deleted' file <b>contains credentials</b> - delete after verification</li>
<li>⚠️ Verify results before importing back to Bitwarden/Vaultwarden</li>
<li>⚠️ Test on a non-production account first if possible</li>
</ul>

<h3 style="color: #00aa44;">Support & Documentation</h3>
<p>For detailed documentation, visit:<br>
<a href="https://github.com/gulp79/Bitwarden-Vaultwarden-vault-cleaner">GitHub Repository</a>
</p>

<p style="color: #007733; font-size: 10px; margin-top: 20px;">
Version 2.0.0 - Advanced Edition<br>
Deterministic, Idempotent, and Explainable
</p>
        """
        
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle("Help - Vault Cleaner v2.0")
        msg_box.setTextFormat(QtCore.Qt.RichText)
        msg_box.setText(help_text)
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg_box.setMinimumWidth(600)
        msg_box.exec()


def main():
    app = QtWidgets.QApplication([])
    app.setStyleSheet(MATRIX_QSS)
    
    # Set application icon (if available)
    # app.setWindowIcon(QtGui.QIcon("icon.png"))
    
    window = MainWindow()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
