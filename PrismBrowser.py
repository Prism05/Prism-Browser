from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QToolBar,
    QLineEdit,
    QPushButton,
    QStatusBar,
    QProgressBar,
    QMenu,
    QGraphicsDropShadowEffect,
    QTabWidget,
    QWidget,
    QColorDialog,
    QInputDialog,
    QVBoxLayout,
    QHBoxLayout,
    QToolButton,
    QDialog,
    QLabel,
    QListWidget,
    QDialogButtonBox,
    QFormLayout,
    QFileDialog,
    QComboBox,
    QListWidgetItem,
    QMessageBox,
    QFrame,
)
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QUrl, Qt, QTimer
from PyQt6.QtWebEngineWidgets import QWebEngineView
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

APP_VERSION = "0.13"
GITHUB_REPO = os.environ.get("PRISM_GITHUB_REPO", "your-username/prism-browser")
GITHUB_BRANCH = os.environ.get("PRISM_GITHUB_BRANCH", "main")


class AppUpdater:
    def __init__(self, script_path: str, repo: str, branch: str = "main"):
        self.script_path = os.path.abspath(script_path)
        self.script_dir = os.path.dirname(self.script_path)
        self.repo = repo
        self.branch = branch
        self.repo = self._resolve_repo(repo)

    def _resolve_repo(self, repo: str):
        if repo and not repo.startswith("your-username"):
            return repo

        try:
            remote_url = subprocess.check_output(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=self.script_dir,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return repo

        if remote_url.startswith("git@github.com:"):
            remote_url = remote_url.replace("git@github.com:", "https://github.com/")
        if remote_url.startswith("https://github.com/"):
            remote_url = remote_url[len("https://github.com/"):]
        if remote_url.endswith(".git"):
            remote_url = remote_url[:-4]
        parts = remote_url.split("/")[:2] if "/" in remote_url else []
        return "/".join(parts) if len(parts) == 2 else repo

    def _normalize_version(self, version: str):
        value = str(version or "").strip()
        if not value:
            return (0,)
        if value[0] in {"v", "V"}:
            value = value[1:]
        parts = re.findall(r"\d+", value)
        if not parts:
            return (0,)
        return tuple(int(part) for part in parts)

    def _download_file(self, url: str, destination: str):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Prism-Browser-Updater", "Accept": "application/octet-stream"},
        )
        with urllib.request.urlopen(request, timeout=20) as response, open(destination, "wb") as handle:
            shutil.copyfileobj(response, handle)

    def _fetch_latest_release(self):
        api_url = f"https://api.github.com/repos/{self.repo}/releases/latest"
        request = urllib.request.Request(
            api_url,
            headers={"User-Agent": "Prism-Browser-Updater", "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.load(response)
        return payload

    def check_for_updates(self, parent=None):
        if not self.repo or self.repo.startswith("your-username"):
            return None

        try:
            release = self._fetch_latest_release()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"Update check failed: {exc}")
            return None

        tag_name = (release.get("tag_name") or release.get("name") or "").strip()
        if not tag_name:
            return None

        current_version = self._normalize_version(APP_VERSION)
        latest_version = self._normalize_version(tag_name)
        if latest_version <= current_version:
            return None

        temp_dir = tempfile.mkdtemp(prefix="prism-update-", dir=self.script_dir)
        temp_file = os.path.join(temp_dir, os.path.basename(self.script_path))
        try:
            raw_url = f"https://raw.githubusercontent.com/{self.repo}/{self.branch}/{os.path.basename(self.script_path)}"
            self._download_file(raw_url, temp_file)
            os.replace(temp_file, self.script_path)
            if parent is not None:
                QMessageBox.information(
                    parent,
                    "Update installed",
                    f"Prism Browser updated to {tag_name}. The app will restart now.",
                )
            subprocess.Popen([sys.executable, self.script_path], cwd=self.script_dir)
            sys.exit(0)
        except Exception as exc:
            print(f"Update failed: {exc}")
            return None


class AddressBar(QLineEdit):
    def focusInEvent(self, event):
        super().focusInEvent(event)
        if self.text():
            self.selectAll()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if self.text():
            self.selectAll()


class DownloadToast(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.path = ""
        self.request = None
        self.collapsed = False
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("background: transparent;")
        self.setFixedSize(320, 104)

        self.card = QFrame(self)
        self.card.setObjectName("toastCard")
        self.card.setStyleSheet(
            "QFrame#toastCard { background: rgba(4, 20, 32, 0.94); border: 1px solid rgba(103, 232, 249, 0.35); border-radius: 16px; }"
        )
        self.card.setAutoFillBackground(True)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        self.title_label = QLabel("Download started")
        self.title_label.setStyleSheet("color: #f8fafc; font-weight: 700; font-size: 13px;")
        self.title_label.setWordWrap(True)
        top_row.addWidget(self.title_label, 1)

        self.toggle_button = QPushButton(">")
        self.toggle_button.setFixedSize(28, 28)
        self.toggle_button.setStyleSheet("QPushButton { background: rgba(255,255,255,0.08); border: 0; border-radius: 10px; color: #f8fafc; padding: 0; }")
        self.toggle_button.clicked.connect(self.toggle)
        top_row.addWidget(self.toggle_button)
        layout.addLayout(top_row)

        self.content_widget = QWidget(self.card)
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)

        self.status_label = QLabel("Preparing download…")
        self.status_label.setStyleSheet("color: #bae6fd; font-size: 12px;")
        self.status_label.setWordWrap(True)
        content_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar(self.content_widget)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet(
            "QProgressBar { border: 0; background: rgba(255,255,255,0.12); border-radius: 4px; }"
            "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #22c55e); border-radius: 4px; }"
        )
        content_layout.addWidget(self.progress_bar)

        self.open_button = QPushButton("Open in Files")
        self.open_button.setStyleSheet("QPushButton { background: rgba(56,189,248,0.18); border: 1px solid rgba(56,189,248,0.35); color: #f8fafc; border-radius: 10px; min-height: 28px; padding: 0 10px; }")
        self.open_button.clicked.connect(self.open_path)
        content_layout.addWidget(self.open_button, 0, Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(self.content_widget)

        self.hide()

    def set_download(self, title: str, path: str):
        self.path = path
        self.title_label.setText(title or "Download")
        self.status_label.setText("Preparing download…")
        self.progress_bar.setValue(0)
        self.open_button.setEnabled(os.path.exists(path))
        self.show()

    def set_progress(self, received: int, total: int):
        if total and total > 0:
            percent = int((received / total) * 100)
            self.progress_bar.setValue(max(1, min(99, percent)))
            self.status_label.setText("Downloading…")
        else:
            self.progress_bar.setValue(0)
            self.status_label.setText("Starting download…")
        self.open_button.setEnabled(os.path.exists(self.path))

    def set_complete(self):
        self.progress_bar.setValue(100)
        self.status_label.setText("Download complete")
        self.open_button.setEnabled(os.path.exists(self.path))

    def open_path(self):
        if self.path and os.path.exists(self.path):
            os.startfile(self.path)

    def toggle(self):
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.content_widget.hide()
            self.setFixedSize(56, 46)
            self.toggle_button.setText("<")
        else:
            self.content_widget.show()
            self.setFixedSize(320, 104)
            self.toggle_button.setText(">")
        if self.parent() is not None:
            self.parent().resizeEvent(None)


class SettingsDialog(QDialog):
    def __init__(self, browser_window, parent=None):
        super().__init__(parent)
        self.browser_window = browser_window
        self.setWindowTitle("Prism Settings")
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.home_url_edit = QLineEdit(self.browser_window.home_page_url)
        self.home_title_edit = QLineEdit(self.browser_window.home_page_title)
        self.home_text_edit = QLineEdit(self.browser_window.home_page_text)
        self.search_engine_combo = QComboBox()
        self.search_engine_combo.addItems(list(self.browser_window.search_engines.keys()))
        self.search_engine_combo.setCurrentText(self.browser_window.default_search_engine)
        self.theme_color_button = QPushButton("Choose color")
        self.theme_color_button.clicked.connect(self.pick_theme_color)
        self.image_path_edit = QLineEdit(self.browser_window.home_image_path)
        self.image_path_edit.setReadOnly(True)
        self.image_button = QPushButton("Choose image")
        self.image_button.clicked.connect(self.pick_image)

        form.addRow("Home URL", self.home_url_edit)
        form.addRow("Home title", self.home_title_edit)
        form.addRow("Home message", self.home_text_edit)
        form.addRow("Search engine", self.search_engine_combo)
        form.addRow("Theme color", self.theme_color_button)
        form.addRow("Background image", self.image_path_edit)
        form.addRow("", self.image_button)
        layout.addLayout(form)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def pick_theme_color(self):
        color = QColorDialog.getColor(self.browser_window.home_theme_color, self, "Pick theme color")
        if color.isValid():
            self.browser_window.home_theme_color = color.name()
            self.theme_color_button.setText(color.name())

    def pick_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose background image", os.path.expanduser("~"), "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        if path:
            self.image_path_edit.setText(path)

    def save_settings(self):
        self.browser_window.home_page_url = self.home_url_edit.text().strip()
        self.browser_window.home_page_title = self.home_title_edit.text().strip() or "Prism Browser"
        self.browser_window.home_page_text = self.home_text_edit.text().strip() or "Welcome to Prism Browser"
        self.browser_window.default_search_engine = self.search_engine_combo.currentText()
        self.browser_window.home_image_path = self.image_path_edit.text().strip()
        self.browser_window.home_page()
        self.browser_window.status.showMessage("Settings updated", 2500)
        self.accept()


class HistoryDialog(QDialog):
    def __init__(self, browser_window, parent=None):
        super().__init__(parent)
        self.browser_window = browser_window
        self.setWindowTitle("History")
        self.resize(540, 410)

        layout = QVBoxLayout(self)
        self.history_list = QListWidget()
        for item in self.browser_window.history:
            entry = QListWidgetItem(f"{item['title']} — {item['url']}")
            entry.setData(Qt.ItemDataRole.UserRole, item['url'])
            self.history_list.addItem(entry)
        self.history_list.itemDoubleClicked.connect(self.open_selected)
        layout.addWidget(self.history_list)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def open_selected(self, item):
        url = item.data(Qt.ItemDataRole.UserRole)
        if url:
            self.browser_window.open_url(url)
            self.accept()


class DownloadsDialog(QDialog):
    def __init__(self, browser_window, parent=None):
        super().__init__(parent)
        self.browser_window = browser_window
        self.setWindowTitle("Downloads")
        self.resize(540, 410)

        layout = QVBoxLayout(self)
        self.download_list = QListWidget()
        for item in self.browser_window.downloads:
            self.download_list.addItem(f"{item['name']} — {item['path']}")
        self.download_list.itemDoubleClicked.connect(self.open_selected)
        layout.addWidget(self.download_list)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def open_selected(self, item):
        path = item.text().split(" — ", 1)[1]
        if os.path.exists(path):
            os.startfile(path)


class Browser(QMainWindow):
    def __init__(self):
        super().__init__()

        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, "browser.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setWindowTitle("Prism Browser")
        self.resize(1100, 760)
        self.setStyleSheet(self.window_style())

        self.search_engines = {
            "Google": "https://www.google.com/search?q=",
            "DuckDuckGo": "https://duckduckgo.com/?q=",
            "Bing": "https://www.bing.com/search?q=",
        }
        self.default_search_engine = "Google"
        self.bookmarks = []
        self.home_theme_color = "#060914"
        self.home_page_url = ""
        self.home_page_title = "Prism Browser"
        self.home_page_text = "Welcome to Prism Browser"
        self.home_image_path = ""
        self.downloads = []
        self.history = []
        self.tab_browsers = {}
        self.tab_context_menu = QMenu(self)
        self._context_tab_index = None
        self._home_mode = True
        self.download_toast = DownloadToast(self)
        self.download_toast.hide()

        self.tab_context_menu.addAction("New tab", self.create_tab)
        self.tab_context_menu.addSeparator()
        self.tab_context_menu.addAction("Rename tab", self.rename_current_tab)
        self.tab_context_menu.addAction("Delete tab", self.delete_current_tab)

        toolbar = QToolBar("Navigation")
        toolbar.setMovable(False)
        toolbar.setStyleSheet("QToolBar { background: transparent; spacing: 8px; padding: 8px; }")
        self.addToolBar(toolbar)

        back = QPushButton("←")
        back.clicked.connect(self.go_back)
        toolbar.addWidget(back)

        forward = QPushButton("→")
        forward.clicked.connect(self.go_forward)
        toolbar.addWidget(forward)

        reload_btn = QPushButton("⟳")
        reload_btn.clicked.connect(self.reload_page)
        toolbar.addWidget(reload_btn)

        stop_btn = QPushButton("✕")
        stop_btn.clicked.connect(self.stop_page)
        toolbar.addWidget(stop_btn)

        home_btn = QPushButton("🏠")
        home_btn.clicked.connect(self.home_page)
        toolbar.addWidget(home_btn)

        self.bookmark_button = QPushButton("★")
        self.bookmark_button.clicked.connect(self.add_bookmark)
        toolbar.addWidget(self.bookmark_button)

        self.bookmark_menu = QMenu()
        self.bookmark_button.setMenu(self.bookmark_menu)

        self.search_engine_button = QPushButton(self.default_search_engine)
        self.search_engine_button.clicked.connect(self.change_search_engine)
        toolbar.addWidget(self.search_engine_button)

        self.url_bar = AddressBar()
        self.url_bar.setPlaceholderText("Search or enter website...")
        self.url_bar.returnPressed.connect(self.load_page)
        self.url_bar.setClearButtonEnabled(True)
        self.url_bar.setMinimumWidth(520)
        toolbar.addWidget(self.url_bar)

        self.main_menu_button = QToolButton()
        self.main_menu_button.setText("⋯")
        self.main_menu_button.setToolTip("Browser tools")
        self.main_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.main_menu_button.setMenu(self.build_main_menu())
        toolbar.addWidget(self.main_menu_button)

        self.status = QStatusBar()
        self.status.setStyleSheet("QStatusBar { background: transparent; color: #cbd5e1; }")
        self.setStatusBar(self.status)

        self.progress = QProgressBar()
        self.progress.setMaximum(100)
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(180)
        self.status.addPermanentWidget(self.progress)

        self.updater = AppUpdater(__file__, GITHUB_REPO, GITHUB_BRANCH)
        self.version_label = QLabel(f"v{APP_VERSION}")
        self.version_label.setStyleSheet("QLabel { color: #94a3b8; background: transparent; padding: 0 8px; }")
        self.status.addPermanentWidget(self.version_label)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.customContextMenuRequested.connect(self.show_tab_context_menu)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)

        self.tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self.show_tab_context_menu)

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)
        self.setCentralWidget(central_widget)

        self.apply_shadow(self.url_bar)
        self.apply_shadow(self.search_engine_button)
        self.apply_shadow(self.main_menu_button)

        self.browser = None
        self.check_for_updates_on_startup()
        self.create_tab()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.download_toast is not None:
            self.download_toast.move(self.width() - self.download_toast.width() - 22, 18)

    def window_style(self) -> str:
        return """
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #07213a, stop:1 #03131d);
            }
            QPushButton, QToolButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0f766e, stop:1 #0f172a);
                border: 1px solid rgba(125, 211, 252, 0.24);
                border-radius: 12px;
                color: #e2e8f0;
                min-height: 40px;
                padding: 0 14px;
                font-weight: 600;
            }
            QPushButton:hover, QToolButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #14b8a6, stop:1 #0f3d5c);
            }
            QLineEdit {
                background: rgba(2, 16, 30, 0.9);
                border: 1px solid rgba(125, 211, 252, 0.22);
                border-radius: 16px;
                color: #e2e8f0;
                padding: 10px 14px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
            }
            QProgressBar {
                background: rgba(255,255,255,0.1);
                border: 0;
                border-radius: 10px;
                height: 12px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #22c55e);
                border-radius: 10px;
            }
            QMenu {
                background: #07131f;
                color: #e2e8f0;
                border: 1px solid rgba(125, 211, 252, 0.2);
            }
            QMenu::item:selected {
                background: #123449;
            }
            QTabBar::tab {
                background: rgba(8, 28, 44, 0.9);
                color: #cbd5e1;
                border: 1px solid rgba(125, 211, 252, 0.18);
                border-radius: 10px;
                padding: 8px 12px;
                margin: 4px;
            }
            QTabBar::tab:selected {
                background: #0f766e;
                color: white;
            }
        """

    def apply_shadow(self, widget):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22)
        shadow.setOffset(0, 0)
        shadow.setColor(Qt.GlobalColor.black)
        widget.setGraphicsEffect(shadow)

    def build_main_menu(self):
        menu = QMenu(self)
        menu.addAction("New tab", self.create_tab)
        menu.addAction("Open home", self.home_page)
        menu.addSeparator()
        menu.addAction("Downloads", self.show_downloads)
        menu.addAction("History", self.show_history)
        menu.addAction("Bookmarks", self.show_bookmarks)
        menu.addSeparator()
        menu.addAction("Check for updates", self.check_updates_now)
        menu.addAction("Settings", self.show_settings)
        return menu

    def check_for_updates_on_startup(self):
        self.status.showMessage("Checking for updates...", 3000)
        self.version_label.setText(f"v{APP_VERSION}")
        self.updater.check_for_updates(self)

    def check_updates_now(self):
        self.status.showMessage("Checking for updates...", 2500)
        result = self.updater.check_for_updates(self)
        if result is None:
            QMessageBox.information(self, "No update found", "You are already on the latest version or the update check could not reach GitHub.")

    def widget_for_browser(self, browser):
        for widget, tab_browser in self.tab_browsers.items():
            if tab_browser is browser:
                return widget
        return None

    def set_tab_label(self, browser, title: str):
        widget = self.widget_for_browser(browser)
        if widget is None:
            return
        index = self.tabs.indexOf(widget)
        if index < 0:
            return
        label = (title or "New Tab").strip()
        if len(label) > 20:
            label = label[:17] + "..."
        self.tabs.setTabText(index, label)

    def show_tab_context_menu(self, pos):
        index = self.tabs.tabBar().tabAt(pos)
        self._context_tab_index = index if index >= 0 else None
        self.tab_context_menu.exec(self.tabs.mapToGlobal(pos))

    def rename_current_tab(self):
        if self._context_tab_index is None:
            return
        current_name = self.tabs.tabText(self._context_tab_index)
        title, ok = QInputDialog.getText(
            self,
            "Rename tab",
            "Enter a tab name:",
            text=current_name,
        )
        if ok and title.strip():
            self.tabs.setTabText(self._context_tab_index, title.strip())
        self._context_tab_index = None

    def delete_current_tab(self):
        if self._context_tab_index is None:
            self.close_tab(self.tabs.currentIndex())
            return
        self.close_tab(self._context_tab_index)
        self._context_tab_index = None

    def create_tab(self, url=None):
        browser = QWebEngineView()
        self._home_mode = True
        self.set_address_bar_visible(False)
        browser.setHtml(self.home_html())
        browser.urlChanged.connect(self.update_url)
        browser.titleChanged.connect(self.update_title)
        browser.loadProgress.connect(self.update_progress)
        browser.loadFinished.connect(self.load_finished)
        browser.page().profile().downloadRequested.connect(self.handle_download_requested)

        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(browser)

        self.tabs.addTab(tab_widget, "New Tab")
        self.tab_browsers[tab_widget] = browser
        self.tabs.setCurrentWidget(tab_widget)
        self.browser = browser
        self.set_tab_label(browser, "New Tab")

        if isinstance(url, str) and url:
            self._home_mode = False
            self.set_address_bar_visible(True)
            browser.setUrl(QUrl(url))
        else:
            self._home_mode = True
            self.set_address_bar_visible(False)
            browser.setHtml(self.home_html())

        self.on_tab_changed(self.tabs.currentIndex())
        return browser

    def current_browser(self):
        index = self.tabs.currentIndex()
        if index < 0:
            return None
        widget = self.tabs.widget(index)
        return self.tab_browsers.get(widget)

    def on_tab_changed(self, index):
        browser = self.current_browser()
        if browser is None:
            return
        self.browser = browser
        current_url = browser.url()
        if current_url.isValid() and current_url.toString() and not current_url.toString().startswith("data:"):
            self.url_bar.setText(current_url.toString())
            self.set_address_bar_visible(True)
        else:
            self.url_bar.clear()
            self.set_address_bar_visible(not self._home_mode)

        title = browser.title()
        if title:
            self.setWindowTitle(f"{title} - Prism Browser")
        else:
            self.setWindowTitle("Prism Browser")

    def set_address_bar_visible(self, visible: bool):
        self.url_bar.setVisible(visible)
        if visible:
            self.url_bar.setMinimumWidth(520)
        else:
            self.url_bar.setMinimumWidth(0)

    def home_html(self):
        engine = self.default_search_engine
        theme_title = {
            "Google": "Google-style Search",
            "DuckDuckGo": "DuckDuckGo-style Search",
            "Bing": "Bing-style Search",
        }.get(engine, "Search")

        background_style = f"background-color:{self.home_theme_color};"
        background_image = ""
        if self.home_image_path and os.path.exists(self.home_image_path):
            image_url = QUrl.fromLocalFile(self.home_image_path).toString()
            background_image = f"background-image: url('{image_url}'); background-size: cover; background-position: center;"

        return f"""
        <html>
        <body style="margin:0; min-height:100vh; color:#eaf8ff; font-family:'Segoe UI', Arial, sans-serif; {background_style} {background_image}">
            <div style="position:relative; min-height:100vh; overflow:hidden; background: radial-gradient(circle at 20% 20%, rgba(56,189,248,0.2), transparent 26%), radial-gradient(circle at 80% 0%, rgba(45,212,191,0.18), transparent 28%), linear-gradient(135deg, #05213f 0%, #071e2c 40%, #03131d 100%);">
                <div style="position:absolute; inset:0; background: linear-gradient(180deg, rgba(255,255,255,0.06), transparent 40%, rgba(255,255,255,0.04));"></div>
                <div style="position:absolute; left:8%; top:18%; width:220px; height:220px; border-radius:50%; background:rgba(56,189,248,0.14); filter:blur(12px);"></div>
                <div style="position:absolute; right:10%; bottom:12%; width:280px; height:280px; border-radius:50%; background:rgba(45,212,191,0.13); filter:blur(16px);"></div>
                <div style="position:relative; z-index:2; display:flex; min-height:100vh; align-items:center; justify-content:center; padding:32px;">
                    <div style="width:100%; max-width:920px; background:rgba(6,20,34,0.82); border:1px solid rgba(125,211,252,0.18); border-radius:32px; box-shadow: 0 30px 140px rgba(2,6,23,0.45); backdrop-filter: blur(16px); padding:42px;">
                        <div style="display:flex; justify-content:space-between; gap:18px; align-items:flex-start; flex-wrap:wrap; margin-bottom:22px;">
                            <div>
                                <div style="font-size:2.2rem; font-weight:700; letter-spacing:0.02em;">{self.home_page_title}</div>
                                <div style="color:#96cbdc; font-size:1rem; margin-top:8px; max-width:560px;">{self.home_page_text}</div>
                            </div>
                            <div style="padding:10px 14px; border-radius:999px; background:rgba(56,189,248,0.12); border:1px solid rgba(125,211,252,0.18); color:#bae6fd; font-size:0.92rem;">{engine} · calm search</div>
                        </div>
                        <form onsubmit="window.location = '{self.search_engines[engine]}' + encodeURIComponent(document.getElementById('home-search').value); return false;">
                            <input id="home-search" type="search" placeholder="Search the web with {engine}..." style="width:100%; padding:18px 20px; border-radius:18px; border:1px solid rgba(125,211,252,0.22); background:rgba(1,13,24,0.95); color:#f8fafc; font-size:1rem; outline:none; box-sizing:border-box;" />
                        </form>
                        <div style="display:grid; grid-template-columns:repeat(3, minmax(0,1fr)); gap:14px; margin-top:20px; text-align:left; color:#cbd5e1; font-size:0.95rem;">
                            <div style="background:rgba(125,211,252,0.07); border-radius:18px; padding:16px; border:1px solid rgba(125,211,252,0.12);">
                                <div style="font-weight:700; margin-bottom:8px; color:#f8fafc;">Fresh start</div>
                                <div>Open a site or search without the clutter of a busy page.</div>
                            </div>
                            <div style="background:rgba(125,211,252,0.07); border-radius:18px; padding:16px; border:1px solid rgba(125,211,252,0.12);">
                                <div style="font-weight:700; margin-bottom:8px; color:#f8fafc;">Search engine</div>
                                <div>{engine}</div>
                            </div>
                            <div style="background:rgba(125,211,252,0.07); border-radius:18px; padding:16px; border:1px solid rgba(125,211,252,0.12);">
                                <div style="font-weight:700; margin-bottom:8px; color:#f8fafc;">Quick tip</div>
                                <div>Use the menu to change the look, background, or update the app.</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

    def update_title(self, title: str):
        browser = self.sender()
        if browser is self.browser and title:
            self.setWindowTitle(f"{title} - Prism Browser")
            self.set_tab_label(browser, title)
        elif browser is self.browser:
            self.setWindowTitle("Prism Browser")
            self.set_tab_label(browser, "New Tab")

    def update_url(self, url: QUrl):
        browser = self.sender()
        if browser is self.browser:
            if url.isValid():
                self.url_bar.setText(url.toString())
                self.set_address_bar_visible(True)
                self._home_mode = False
            else:
                self.url_bar.clear()
                self.set_address_bar_visible(not self._home_mode)

    def update_progress(self, progress: int):
        self.progress.setValue(progress)
        if progress < 100 and self.browser is self.sender():
            self.status.showMessage(f"Loading... {progress}%")

    def load_finished(self, success: bool):
        browser = self.sender()
        if browser is self.browser:
            if success:
                self.status.showMessage("Page loaded", 3000)
                self.add_to_history(browser)
            else:
                self.status.showMessage("Failed to load page", 5000)

    def add_to_history(self, browser):
        if browser is None:
            return
        url = browser.url()
        if not url.isValid() or not url.toString() or url.toString().startswith("data:"):
            return
        current_url = url.toString()
        if self.history and self.history[-1]["url"] == current_url:
            return
        self.history.append({"title": browser.title() or current_url, "url": current_url})
        if len(self.history) > 120:
            self.history.pop(0)

    def go_back(self):
        if self.browser:
            self.browser.back()

    def go_forward(self):
        if self.browser:
            self.browser.forward()

    def reload_page(self):
        if self.browser:
            self.browser.reload()

    def stop_page(self):
        if self.browser:
            self.browser.stop()

    def home_page(self):
        if self.browser:
            if self.home_page_url.strip():
                self.open_url(self.home_page_url)
            else:
                self._home_mode = True
                self.set_address_bar_visible(False)
                self.browser.setHtml(self.home_html())
                self.url_bar.clear()
                self.setWindowTitle("Prism Browser")

    def choose_theme_color(self):
        color = QColorDialog.getColor(self.home_theme_color, self, "Choose home color")
        if color.isValid():
            self.home_theme_color = color.name()
            self.status.showMessage("Home color updated", 2500)
            self.home_page()

    def normalize_address(self, text: str) -> QUrl:
        text = text.strip()
        if not text:
            return QUrl()

        if " " in text or "." not in text:
            query = text.replace(" ", "+")
            return QUrl(self.search_engines[self.default_search_engine] + query)

        return QUrl.fromUserInput(text)

    def load_page(self):
        if not self.browser:
            return
        text = self.url_bar.text().strip()
        url = self.normalize_address(text)
        if url.isValid():
            self._home_mode = False
            self.set_address_bar_visible(True)
            self.browser.setUrl(url)

    def open_url(self, url: str):
        if not self.browser:
            return
        self._home_mode = False
        self.set_address_bar_visible(True)
        self.url_bar.setText(url)
        self.browser.setUrl(QUrl(url))

    def add_bookmark(self):
        if not self.browser:
            return
        current_url = self.browser.url().toString()
        if current_url and current_url not in self.bookmarks:
            self.bookmarks.append(current_url)
            self.bookmark_menu.addAction(current_url, lambda url=current_url: self.open_bookmark(url))
            self.status.showMessage("Bookmark added", 2000)

    def open_bookmark(self, url: str):
        if self.browser:
            self.url_bar.setText(url)
            self.browser.setUrl(QUrl(url))

    def change_search_engine(self):
        engines = list(self.search_engines.keys())
        current_index = engines.index(self.default_search_engine)
        self.default_search_engine = engines[(current_index + 1) % len(engines)]
        self.search_engine_button.setText(self.default_search_engine)
        self.home_page()
        self.status.showMessage(f"Search engine set to {self.default_search_engine}", 2500)

    def show_settings(self):
        dialog = SettingsDialog(self, self)
        dialog.exec()

    def show_history(self):
        dialog = HistoryDialog(self, self)
        dialog.exec()

    def show_downloads(self):
        dialog = DownloadsDialog(self, self)
        dialog.exec()

    def show_bookmarks(self):
        if not self.bookmarks:
            self.status.showMessage("No bookmarks yet", 2000)
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Bookmarks")
        dialog.resize(500, 320)
        layout = QVBoxLayout(dialog)
        list_widget = QListWidget()
        for bookmark in self.bookmarks:
            list_widget.addItem(bookmark)
        list_widget.itemDoubleClicked.connect(lambda item: self.open_bookmark(item.text()))
        layout.addWidget(list_widget)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def handle_download_requested(self, request):
        download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        os.makedirs(download_dir, exist_ok=True)
        default_name = request.suggestedFileName()
        save_path, _ = QFileDialog.getSaveFileName(self, "Save download", os.path.join(download_dir, default_name))
        if save_path:
            request.setDownloadDirectory(os.path.dirname(save_path))
            request.setDownloadFileName(os.path.basename(save_path))
            request.downloadProgress.connect(lambda received, total: self.update_download_progress(request, received, total))
            request.isFinishedChanged.connect(lambda: self.finish_download(request))
            request.accept()
            self.downloads.append({"name": os.path.basename(save_path), "path": save_path, "url": request.url().toString()})
            self.show_download_notification(os.path.basename(save_path), save_path)
            self.status.showMessage(f"Download started: {os.path.basename(save_path)}", 3000)
        else:
            request.cancel()

    def show_download_notification(self, name: str, path: str):
        self.download_toast.set_download(name, path)
        self.download_toast.show()
        self.resizeEvent(None)

    def update_download_progress(self, request, received: int, total: int):
        if self.download_toast is not None:
            self.download_toast.set_progress(received, total)

    def finish_download(self, request):
        if self.download_toast is not None:
            self.download_toast.set_complete()
            QTimer.singleShot(2200, lambda: self.download_toast.hide())

    def close_tab(self, index):
        if self.tabs.count() == 1:
            widget = self.tabs.widget(index)
            if widget is not None:
                self.tab_browsers.pop(widget, None)
                self.tabs.removeTab(index)
                widget.deleteLater()
            self.create_tab()
            return
        widget = self.tabs.widget(index)
        if widget is not None:
            self.tab_browsers.pop(widget, None)
            self.tabs.removeTab(index)
            widget.deleteLater()
        self.on_tab_changed(self.tabs.currentIndex())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(script_dir, "browser.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    window = Browser()
    window.show()
    sys.exit(app.exec())
