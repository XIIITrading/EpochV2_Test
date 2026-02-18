import importlib
import os
import sys
import subprocess
from datetime import datetime

from PIL import Image
from PyQt6.QtCore import Qt, QFileSystemWatcher
from PyQt6.QtGui import QColor, QPixmap, QImage
from PyQt6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import BASE_DIR, PLATFORMS, SUPPORTED_EXTENSIONS, TEMPLATE_REGISTRY


STUB_PLATFORMS = {"twitter", "discord"}


class SocialMediaProcessor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XIII Social Media Processor")
        self.setMinimumSize(960, 640)

        self._current_platform = "instagram"
        self._loaded_paths: list[str] = []
        self._bg_color = "#000000"
        self._preview_image: Image.Image | None = None

        self._build_ui()
        self._setup_watcher()
        self._on_platform_changed(0)

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        root.addLayout(self._build_left_panel(), 1)
        root.addLayout(self._build_center_panel(), 2)
        root.addLayout(self._build_right_panel(), 1)

    # ── Left panel ───────────────────────────────────────────────────

    def _build_left_panel(self) -> QVBoxLayout:
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Platform"))
        self.platform_combo = QComboBox()
        self.platform_combo.addItems([p.capitalize() for p in PLATFORMS])
        self.platform_combo.currentIndexChanged.connect(self._on_platform_changed)
        layout.addWidget(self.platform_combo)

        layout.addWidget(QLabel("Template"))
        self.template_list = QListWidget()
        self.template_list.currentRowChanged.connect(self._on_template_changed)
        layout.addWidget(self.template_list)

        self.load_btn = QPushButton("Load Sources")
        self.load_btn.clicked.connect(self._load_sources)
        layout.addWidget(self.load_btn)

        self.source_status = QLabel("No images loaded")
        self.source_status.setWordWrap(True)
        layout.addWidget(self.source_status)

        layout.addStretch()
        return layout

    # ── Center panel ─────────────────────────────────────────────────

    def _build_center_panel(self) -> QVBoxLayout:
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Preview"))
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(480, 480)
        self.preview_label.setStyleSheet("background-color: #1a1a1a; border: 1px solid #333;")
        layout.addWidget(self.preview_label, 1)

        self.dimensions_label = QLabel("Output: —")
        self.dimensions_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.dimensions_label)

        return layout

    # ── Right panel ──────────────────────────────────────────────────

    def _build_right_panel(self) -> QVBoxLayout:
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Output Filename"))
        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("auto-generated on process")
        layout.addWidget(self.filename_edit)

        layout.addWidget(QLabel("Output Format"))
        self.format_combo = QComboBox()
        layout.addWidget(self.format_combo)

        layout.addWidget(QLabel("Fit Mode"))
        self.fit_mode_combo = QComboBox()
        self.fit_mode_combo.addItems(["Cover", "Contain"])
        self.fit_mode_combo.currentIndexChanged.connect(lambda _: self._refresh_preview())
        layout.addWidget(self.fit_mode_combo)

        layout.addWidget(QLabel("Background Color"))
        bg_row = QHBoxLayout()
        self.bg_color_label = QLabel()
        self.bg_color_label.setFixedSize(28, 28)
        self._update_bg_swatch()
        bg_row.addWidget(self.bg_color_label)
        bg_pick_btn = QPushButton("Pick…")
        bg_pick_btn.clicked.connect(self._pick_bg_color)
        bg_row.addWidget(bg_pick_btn)
        bg_row.addStretch()
        layout.addLayout(bg_row)

        self.process_btn = QPushButton("Process && Save")
        self.process_btn.clicked.connect(self._process_and_save)
        layout.addWidget(self.process_btn)

        self.open_folder_btn = QPushButton("Open Output Folder")
        self.open_folder_btn.clicked.connect(self._open_output_folder)
        layout.addWidget(self.open_folder_btn)

        layout.addWidget(QLabel("Log"))
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(180)
        layout.addWidget(self.log_area)

        layout.addStretch()
        return layout

    # ── File system watcher ──────────────────────────────────────────

    def _setup_watcher(self):
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._on_source_dir_changed)

    def _watch_source_dir(self):
        watched = self._watcher.directories()
        if watched:
            self._watcher.removePaths(watched)
        source_dir = PLATFORMS[self._current_platform]["source_dir"]
        if os.path.isdir(source_dir):
            self._watcher.addPath(source_dir)

    def _on_source_dir_changed(self, _path: str):
        self._load_sources()

    # ── Slots ────────────────────────────────────────────────────────

    def _on_platform_changed(self, index: int):
        self._current_platform = list(PLATFORMS.keys())[index]

        if self._current_platform in STUB_PLATFORMS:
            QMessageBox.information(
                self,
                self._current_platform.capitalize(),
                f"{self._current_platform.capitalize()} support coming soon.",
            )

        self.template_list.clear()
        for tmpl in TEMPLATE_REGISTRY.get(self._current_platform, []):
            self.template_list.addItem(tmpl["label"])

        self._populate_formats()
        self._watch_source_dir()
        self._loaded_paths.clear()
        self._source_status_update()
        self._clear_preview()

    def _on_template_changed(self, _row: int):
        self._refresh_preview()

    def _populate_formats(self):
        self.format_combo.clear()
        formats = PLATFORMS[self._current_platform].get("formats", {})
        for name in formats:
            self.format_combo.addItem(name.capitalize())

    def _load_sources(self):
        source_dir = PLATFORMS[self._current_platform]["source_dir"]
        if not os.path.isdir(source_dir):
            self._loaded_paths = []
            self._source_status_update()
            return

        files = sorted(
            f
            for f in os.listdir(source_dir)
            if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS
        )
        self._loaded_paths = [os.path.join(source_dir, f) for f in files]
        self._source_status_update()
        self._refresh_preview()

    def _source_status_update(self):
        n = len(self._loaded_paths)
        if n == 0:
            self.source_status.setText("No images loaded")
        else:
            names = ", ".join(os.path.basename(p) for p in self._loaded_paths)
            self.source_status.setText(f"{n} image(s) found: {names}")

    # ── Background color ─────────────────────────────────────────────

    def _pick_bg_color(self):
        color = QColorDialog.getColor(QColor(self._bg_color), self, "Background Color")
        if color.isValid():
            self._bg_color = color.name()
            self._update_bg_swatch()
            self._refresh_preview()

    def _update_bg_swatch(self):
        self.bg_color_label.setStyleSheet(
            f"background-color: {self._bg_color}; border: 1px solid #555;"
        )

    # ── Preview ──────────────────────────────────────────────────────

    def _clear_preview(self):
        self.preview_label.clear()
        self.dimensions_label.setText("Output: —")
        self._preview_image = None

    def _refresh_preview(self):
        tmpl = self._selected_template()
        if tmpl is None or not self._loaded_paths:
            self._clear_preview()
            return

        canvas_size = self._selected_canvas_size()
        fit_mode = self._selected_fit_mode()
        try:
            mod = importlib.import_module(tmpl["module"])
            result = mod.render(self._loaded_paths, canvas_size, self._bg_color, fit_mode=fit_mode)
        except Exception as exc:
            self._log(f"Preview error: {exc}")
            self._clear_preview()
            return

        self._preview_image = result
        self._show_pil_preview(result)
        w, h = result.size
        self.dimensions_label.setText(f"Output: {w} x {h}")

    def _show_pil_preview(self, pil_img: Image.Image):
        pil_img = pil_img.convert("RGB")
        data = pil_img.tobytes("raw", "RGB")
        qimg = QImage(data, pil_img.width, pil_img.height, 3 * pil_img.width, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        max_w = 480
        if pixmap.width() > max_w:
            pixmap = pixmap.scaledToWidth(max_w, Qt.TransformationMode.SmoothTransformation)
        self.preview_label.setPixmap(pixmap)

    # ── Process & Save ───────────────────────────────────────────────

    def _process_and_save(self):
        if self._current_platform in STUB_PLATFORMS:
            QMessageBox.information(self, "Info", "This platform is not yet supported.")
            return

        tmpl = self._selected_template()
        if tmpl is None:
            QMessageBox.warning(self, "No Template", "Select a template first.")
            return

        self._load_sources()

        required = tmpl.get("required_images", 0)
        found = len(self._loaded_paths)
        if found != required:
            QMessageBox.warning(
                self,
                "Image Count Mismatch",
                f"Template '{tmpl['label']}' requires {required} images. "
                f"Found {found} in source folder.",
            )
            return

        canvas_size = self._selected_canvas_size()
        fit_mode = self._selected_fit_mode()

        try:
            mod = importlib.import_module(tmpl["module"])
            result = mod.render(self._loaded_paths, canvas_size, self._bg_color, fit_mode=fit_mode)
        except Exception as exc:
            self._log(f"Processing error: {exc}")
            QMessageBox.critical(self, "Error", str(exc))
            return

        output_dir = PLATFORMS[self._current_platform]["output_dir"]
        os.makedirs(output_dir, exist_ok=True)

        filename = self.filename_edit.text().strip()
        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{ts}_{tmpl['id']}.png"

        if not filename.lower().endswith(".png"):
            filename += ".png"

        filepath = self._unique_filepath(output_dir, filename)

        try:
            result.save(filepath, "PNG")
        except Exception as exc:
            self._log(f"Save error: {exc}")
            QMessageBox.critical(self, "Save Error", str(exc))
            return

        w, h = result.size
        rel = os.path.relpath(filepath, BASE_DIR)
        self._log(f"Saved: {rel} — {w}x{h} PNG")

        self._preview_image = result
        self._show_pil_preview(result)
        self.dimensions_label.setText(f"Output: {w} x {h}")

    # ── Helpers ───────────────────────────────────────────────────────

    def _selected_template(self) -> dict | None:
        row = self.template_list.currentRow()
        templates = TEMPLATE_REGISTRY.get(self._current_platform, [])
        if 0 <= row < len(templates):
            return templates[row]
        return None

    def _selected_fit_mode(self) -> str:
        return "contain" if self.fit_mode_combo.currentIndex() == 1 else "cover"

    def _selected_canvas_size(self) -> tuple[int, int]:
        fmt_name = self.format_combo.currentText().lower()
        formats = PLATFORMS[self._current_platform].get("formats", {})
        return formats.get(fmt_name, PLATFORMS[self._current_platform]["canvas_size"])

    @staticmethod
    def _unique_filepath(directory: str, filename: str) -> str:
        base, ext = os.path.splitext(filename)
        candidate = os.path.join(directory, filename)
        version = 2
        while os.path.exists(candidate):
            candidate = os.path.join(directory, f"{base}_v{version}{ext}")
            version += 1
        return candidate

    def _open_output_folder(self):
        output_dir = PLATFORMS[self._current_platform]["output_dir"]
        os.makedirs(output_dir, exist_ok=True)
        subprocess.Popen(["explorer", os.path.normpath(output_dir)])

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_area.append(f"[{ts}] {msg}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = SocialMediaProcessor()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
