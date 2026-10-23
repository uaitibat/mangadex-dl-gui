#!/usr/bin/env python3
from __future__ import annotations

import atexit
import hashlib
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import gi
from services.comick_api import (
    ComickApiClient,
    ComickApiError,
)
from services.mangadex_api import (
    ChapterGroup,
    ChapterPages,
    MangaDetails,
    MangaDexApiClient,
    MangaDexApiError,
    MdListDetails,
    UserMdList,
    UserProfile,
)

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GLib", "2.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango


APP_ID = "io.github.uaiti.MangaDexDl"
BASE_DIR = Path(__file__).resolve().parent
ASSET_DIR = BASE_DIR / "assets"
LEGACY_CONFIG_PATH = BASE_DIR / "config.json"
XDG_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
CONFIG_DIR = XDG_CONFIG_HOME / "mangadex_dl"
CONFIG_PATH = Path(os.environ.get("MANGADEX_DL_CONFIG", str(CONFIG_DIR / "config.json")))
FALLBACK_WALLPAPER = ASSET_DIR / "home.png"
API_GUIDE_GIF = ASSET_DIR / "api-guide.gif"
COVER_CACHE_DIR = ASSET_DIR / "covers"
CACHE_ROOT = Path(tempfile.gettempdir()) / "mangadex_dl_cache"
CUSTOM_WALLPAPER_DIR = CACHE_ROOT / "wallpapers"
PROFILE_CACHE_DIR = CACHE_ROOT / "profile"
READER_CACHE_DIR = CACHE_ROOT / "reader"
ACCOUNT_CACHE_PATH = CONFIG_DIR / "account_cache.json"
ACCOUNT_BANNER_WIDTH = 1280
ACCOUNT_BANNER_HEIGHT = 180
ACCOUNT_AVATAR_SIZE = 56
ACCOUNT_AVATAR_TEXTURE_SIZE = 168
SETTINGS_AVATAR_SIZE = 12

IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
}

UI_TEXT = {
    "pt-BR": {
        "home_subtitle": "Cole a URL do manga no MangaDex para carregar a pagina de download.",
        "load": "Carregar",
        "loading_title": "Carregando mangá",
        "loading_status": "Buscando dados no MangaDex...",
        "settings_tooltip": "Configuracoes",
        "settings_config": "Configuracoes",
        "settings_account": "Conta",
        "wallpaper": "Wallpaper",
        "wallpaper_title": "Wallpaper da home",
        "reset": "Redefinir",
        "save": "Salvar",
        "back": "Voltar",
        "config_title": "Configuração",
        "username": "Usuario",
        "password": "Senha",
        "login": "Logar",
        "api_gif_missing": "Coloque o GIF em assets/api-guide.gif",
        "api_guide_title": "Como pegar a API do MangaDex",
        "api_guide_steps": (
            "1. Entre na sua conta no site do MangaDex.\n"
            "2. Abra as configuracoes da conta e va em API Client.\n"
            "3. Crie um client pessoal e copie o Client ID e o Client Secret.\n"
            "4. Cole os dados aqui junto com usuario e senha."
        ),
        "login_info_question": "O que voce vai poder fazer depois do login?",
        "login_info_answer": (
            "Acessar recursos da sua conta MangaDex e preparar downloads "
            "com preferencias salvas no app."
        ),
        "empty_manga": "Nenhum manga carregado",
        "download": "Download",
        "folder": "Folder",
        "language": "Idioma",
        "reader": "Reader",
        "account_title": "Conta MangaDex",
        "home": "Home",
        "login_required": "Faça login para carregar suas MDLists.",
        "not_logged": "Nao logado",
        "refresh": "Recarregar",
        "logout": "Sair",
        "your_mdlists": "Suas MDLists",
        "refresh_mdlists": "Atualizar MDLists",
        "list_manga": "Mangás da lista",
        "list_manga_named": "Mangás da lista: {name}",
        "url_required": "Cole uma URL do MangaDex primeiro.",
        "invalid_url": "Use uma URL valida do mangadex.org.",
        "invalid_url_comick": "Use uma URL válida do comick.io.",
        "loading_chapters": "Carregando capítulos...",
        "no_chapters_language": "Nenhum capítulo encontrado para esse idioma.",
        "chapter_loading_pages": "Carregando páginas...",
        "reader_no_pages": "Nenhuma página encontrada.",
        "reader_loading_page": "Carregando página...",
        "language_empty": "Idiomas ainda nao carregados.",
        "all": "Todos",
        "folder_dialog_title": "Pasta selecionada",
        "use_now": "Usar agora",
        "set_default": "Deixar padrão",
        "download_dialog_title": "Capítulos para baixar",
        "unselect_all": "Desmarcar tudo",
        "select_all": "Marcar tudo",
        "cancel": "Cancelar",
        "download_start": "Baixar",
        "no_download_chapters": "Nenhum capítulo para esse idioma.",
        "select_one_chapter": "Selecione pelo menos um capítulo.",
        "download_waiting_pages": "Aguardando páginas do primeiro capítulo...",
        "download_cancelled": "Download cancelado.",
        "download_process_stopped": "Processo interrompido.",
        "download_stopped": "Download parado.",
        "download_done": "Concluído.",
        "download_status_title": "Status do download",
        "close": "Fechar",
        "folder_create_error": "Falha ao criar pasta: {error}",
        "download_selected": "{count} capítulo(s) selecionado(s).",
        "download_starting": "Baixando {count} capítulo(s)...",
        "download_progress": "Baixando capítulo {current} de {total}.",
        "download_prepare_pages": "{chapter}: preparando páginas...",
        "download_chapter_done": "{chapter}: capítulo finalizado.",
        "download_finished_in": "Download concluído em {folder}",
        "download_missing_cli": "Nao encontrei o mangadex-downloader no PATH.",
        "download_failed_url": "Falha ao baixar {url}",
        "page_progress_total": "{chapter}: página {current} de {total}.",
        "page_progress_single": "{chapter}: página {current}.",
        "page_downloading": "{chapter}: baixando páginas...",
        "no_active_download": "Nenhum download ativo.",
        "no_mdlists": "Nenhuma MDList encontrada.",
        "login_done": "Logado. Suas listas e dados privados podem ser acessados.",
        "login_loading": "Login ainda esta carregando...",
        "loading_mdlists": "Carregando MDLists...",
        "selected_manga_loading": "Carregando mangá selecionado...",
        "language_status": "Idioma atual: pt-BR.",
        "wallpaper_downloading": "Baixando wallpaper...",
        "wallpaper_reset": "Wallpaper redefinido para o padrao.",
        "wallpaper_saved": "Wallpaper salvo.",
        "wallpaper_download_error": "Falha ao baixar wallpaper: {error}",
        "no_synopsis": "Sem sinopse disponível.",
        "publication": "PUBLICAÇÃO",
        "group_none": "Sem grupo",
        "chapter": "Capítulo",
        "manga_count": "{count} mangas",
        "mdlist_found_count": "{count} mangas encontrados nessa lista.",
        "profile_refresh_error": "Erro ao recarregar perfil: {message}",
        "looking_for_new_manga": "Procurando mangas novos...",
    },
    "en": {
        "home_subtitle": "Paste a MangaDex manga URL to load the download page.",
        "load": "Load",
        "loading_title": "Loading manga",
        "loading_status": "Fetching data from MangaDex...",
        "settings_tooltip": "Settings",
        "settings_config": "Settings",
        "settings_account": "Account",
        "wallpaper": "Wallpaper",
        "wallpaper_title": "Home wallpaper",
        "reset": "Reset",
        "save": "Save",
        "back": "Back",
        "config_title": "Settings",
        "username": "Username",
        "password": "Password",
        "login": "Log in",
        "api_gif_missing": "Put the GIF in assets/api-guide.gif",
        "api_guide_title": "How to get the MangaDex API",
        "api_guide_steps": (
            "1. Sign in to your MangaDex account on the website.\n"
            "2. Open account settings and go to API Client.\n"
            "3. Create a personal client and copy the Client ID and Client Secret.\n"
            "4. Paste the data here with your username and password."
        ),
        "login_info_question": "What can you do after logging in?",
        "login_info_answer": (
            "Access your MangaDex account resources and prepare downloads "
            "with preferences saved in the app."
        ),
        "empty_manga": "No manga loaded",
        "download": "Download",
        "folder": "folder",
        "language": "Language",
        "reader": "Reader",
        "account_title": "MangaDex Account",
        "home": "Home",
        "login_required": "Log in to load your MDLists.",
        "not_logged": "Not logged in",
        "refresh": "Refresh",
        "logout": "Log out",
        "your_mdlists": "Your MDLists",
        "refresh_mdlists": "Refresh MDLists",
        "list_manga": "List manga",
        "list_manga_named": "List manga: {name}",
        "url_required": "Paste a MangaDex URL first.",
        "invalid_url": "Use a valid mangadex.org URL.",
        "invalid_url_comick": "Use a valid comick.io URL.",
        "loading_chapters": "Loading chapters...",
        "no_chapters_language": "No chapters found for this language.",
        "chapter_loading_pages": "Loading pages...",
        "reader_no_pages": "No pages found.",
        "reader_loading_page": "Loading page...",
        "language_empty": "Languages are not loaded yet.",
        "all": "All",
        "folder_dialog_title": "Selected folder",
        "use_now": "Use now",
        "set_default": "Make default",
        "download_dialog_title": "Chapters to download",
        "unselect_all": "Unselect all",
        "select_all": "Select all",
        "cancel": "Cancel",
        "download_start": "Download",
        "no_download_chapters": "No chapters for this language.",
        "select_one_chapter": "Select at least one chapter.",
        "download_waiting_pages": "Waiting for the first chapter pages...",
        "download_cancelled": "Download cancelled.",
        "download_process_stopped": "Process stopped.",
        "download_stopped": "Download stopped.",
        "download_done": "Done.",
        "download_status_title": "Download status",
        "close": "Close",
        "folder_create_error": "Failed to create folder: {error}",
        "download_selected": "{count} chapter(s) selected.",
        "download_starting": "Downloading {count} chapter(s)...",
        "download_progress": "Downloading chapter {current} of {total}.",
        "download_prepare_pages": "{chapter}: preparing pages...",
        "download_chapter_done": "{chapter}: chapter finished.",
        "download_finished_in": "Download completed in {folder}",
        "download_missing_cli": "Could not find mangadex-downloader in PATH.",
        "download_failed_url": "Failed to download {url}",
        "page_progress_total": "{chapter}: page {current} of {total}.",
        "page_progress_single": "{chapter}: page {current}.",
        "page_downloading": "{chapter}: downloading pages...",
        "no_active_download": "No active download.",
        "no_mdlists": "No MDList found.",
        "login_done": "Logged in. Your private lists and data can be accessed.",
        "login_loading": "Login is still loading...",
        "loading_mdlists": "Loading MDLists...",
        "selected_manga_loading": "Loading selected manga...",
        "language_status": "Current language: English.",
        "wallpaper_downloading": "Downloading wallpaper...",
        "wallpaper_reset": "Wallpaper reset to default.",
        "wallpaper_saved": "Wallpaper saved.",
        "wallpaper_download_error": "Failed to download wallpaper: {error}",
        "no_synopsis": "No synopsis available.",
        "publication": "PUBLICATION",
        "group_none": "No group",
        "chapter": "Chapter",
        "manga_count": "{count} manga",
        "mdlist_found_count": "{count} manga found in this list.",
        "profile_refresh_error": "Error refreshing profile: {message}",
        "looking_for_new_manga": "Looking for new manga...",
    },
}


class AnimatedGifPicture(Gtk.Picture):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self._animation: GdkPixbuf.PixbufAnimation | None = None
        self._iter: GdkPixbuf.PixbufAnimationIter | None = None
        self._timer_id: int | None = None
        self.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.set_can_shrink(True)
        self.set_hexpand(True)
        self.set_vexpand(False)
        self.load(path)

    def load(self, path: Path) -> None:
        self._stop()
        if path.suffix.lower() != ".gif":
            self.set_filename(str(path))
            return

        self._animation = GdkPixbuf.PixbufAnimation.new_from_file(str(path))
        if self._animation.is_static_image():
            self.set_paintable(Gdk.Texture.new_for_pixbuf(self._animation.get_static_image()))
            return

        self._iter = self._animation.get_iter(None)
        self._show_frame()
        self._queue_next_frame()

    def _show_frame(self) -> None:
        if self._iter is None:
            return
        self.set_paintable(Gdk.Texture.new_for_pixbuf(self._iter.get_pixbuf()))

    def _queue_next_frame(self) -> None:
        if self._iter is None:
            return

        delay = self._iter.get_delay_time()
        if delay < 0:
            delay = 100
        delay = max(delay, 20)

        def tick() -> bool:
            if self._iter is None:
                self._timer_id = None
                return False

            self._iter.advance(None)
            self._show_frame()
            self._timer_id = None
            self._queue_next_frame()
            return False

        self._timer_id = GLib.timeout_add(delay, tick)

    def _stop(self) -> None:
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
        self._iter = None
        self._animation = None


class MangaDexWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app, title="MangaDex-dl")
        self.set_default_size(1366, 768)
        self.set_size_request(720, 420)

        self.url_entry = Gtk.Entry()
        self.status_label = Gtk.Label()
        self.stack: Gtk.Stack | None = None
        self.app_overlay: Gtk.Overlay | None = None
        self.background_picture: Gtk.Picture | None = None
        self.settings_button: Gtk.Button | None = None
        self.settings_icon_picture: Gtk.Picture | None = None
        self.settings_menu: Gtk.Widget | None = None
        self.settings_revealer: Gtk.Revealer | None = None
        self.wallpaper_dialog: Gtk.Widget | None = None
        self.wallpaper_entry: Gtk.Entry | None = None
        self.current_wallpaper_path: Path = FALLBACK_WALLPAPER
        self.username_entry: Gtk.Entry | None = None
        self.password_entry: Gtk.Entry | None = None
        self.client_id_entry: Gtk.Entry | None = None
        self.client_secret_entry: Gtk.Entry | None = None
        self.config_status_label: Gtk.Label | None = None
        self.result_title_label: Gtk.Label | None = None
        self.result_subtitle_label: Gtk.Label | None = None
        self.result_meta_box: Gtk.Box | None = None
        self.result_cover_picture: Gtk.Picture | None = None
        self.result_banner_picture: Gtk.Picture | None = None
        self.result_overlay: Gtk.Overlay | None = None
        self.result_actions_box: Gtk.Box | None = None
        self.result_folder_button: Gtk.Button | None = None
        self.result_download_button: Gtk.Button | None = None
        self.result_language_button: Gtk.Button | None = None
        self.result_language_dialog: Gtk.Widget | None = None
        self.result_folder_dialog: Gtk.Widget | None = None
        self.result_download_dialog: Gtk.Widget | None = None
        self.download_progress_button: Gtk.Button | None = None
        self.download_progress_dialog: Gtk.Widget | None = None
        self.download_chapter_list_box: Gtk.Box | None = None
        self.download_status_label: Gtk.Label | None = None
        self.download_progress_chapters_label: Gtk.Label | None = None
        self.download_progress_pages_label: Gtk.Label | None = None
        self.download_cancel_button: Gtk.Button | None = None
        self.download_toggle_button: Gtk.Button | None = None
        self.download_language_button: Gtk.Button | None = None
        self.result_list_box: Gtk.Box | None = None
        self.loading_picture: Gtk.Picture | None = None
        self.loading_status_label: Gtk.Label | None = None
        self.loading_back_button: Gtk.Button | None = None
        self._image_download_lock = threading.Semaphore(2)
        self._download_threads = 2
        self.reader_title_label: Gtk.Label | None = None
        self.reader_page_picture: Gtk.Picture | None = None
        self.reader_status_label: Gtk.Label | None = None
        self.reader_page_counter_label: Gtk.Label | None = None
        self.current_reader_chapter_id: str | None = None
        self.current_reader_page_urls: list[str] = []
        self.current_reader_page_paths: list[Path | None] = []
        self.current_reader_page_index = 0
        self.current_reader_open_at_end = False
        self.current_reader_total_pages = 0
        self.current_result_manga_id: str | None = None
        self.current_result_manga_title = ""
        self.current_result_manga: MangaDetails | None = None
        self.current_download_folder: str | None = None
        self.current_chapters: list[ChapterGroup] = []
        self.current_chapter_language: str | None = None
        self.current_download_language: str | None = None
        self.download_chapter_checks: list[tuple[Gtk.CheckButton, ChapterGroup]] = []
        self.download_cancel_event: threading.Event | None = None
        self.download_process: subprocess.Popen[str] | None = None
        self.download_active = False
        self.download_total_chapters = 0
        self.download_finished_chapters = 0
        self.account_username_label: Gtk.Label | None = None
        self.account_user_id_label: Gtk.Label | None = None
        self.account_avatar_picture: Gtk.Picture | None = None
        self.account_avatar_fallback: Gtk.Label | None = None
        self.account_banner_picture: Gtk.Picture | None = None
        self.account_lists_header: Gtk.Widget | None = None
        self.account_mdlists_scroller: Gtk.Widget | None = None
        self.account_mdlists_box: Gtk.Box | None = None
        self.account_manga_panel: Gtk.Widget | None = None
        self.account_manga_title_label: Gtk.Label | None = None
        self.account_manga_grid: Gtk.FlowBox | None = None
        self.account_selected_mdlist_id: str | None = None
        self.result_back_target = "home"
        self.auto_login_in_progress = False
        self.account_profile_refreshing = False
        self.account_profile: UserProfile | None = None
        self.account_mdlists: list[UserMdList] | None = None
        self.account_details_loading = False
        self.settings_animation_id: int | None = None
        self.gif_animation_id: int | None = None
        self.status_clear_id: int | None = None
        self.gif_animation_iter: GdkPixbuf.PixbufAnimationIter | None = None
        self.mangadex_client = MangaDexApiClient()
        self.comick_client = ComickApiClient()
        self.config = self._load_config()
        self.current_source = self.config.get("source", "mangadex") if self.config.get("source") in ("mangadex", "comick") else "mangadex"
        self.current_result_source = self.current_source
        self.source_switch: Gtk.ToggleButton | None = None
        self.ui_language = self._normalize_ui_language(self.config.get("ui_language", "pt-BR"))
        self._translated_labels: dict[Gtk.Label, str] = {}
        self._translated_buttons: dict[Gtk.Button, str] = {}
        self._translated_entries: dict[Gtk.Entry, str] = {}
        self.session_avatar_path: str | None = None
        self.session_banner_path: str | None = None
        self._prepare_volatile_cache()
        self._load_account_cache()

        self._load_css()
        account_key_controller = Gtk.EventControllerKey()
        account_key_controller.connect("key-pressed", self._on_window_key_pressed)
        self.add_controller(account_key_controller)

        self.stack = Gtk.Stack()
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(180)
        self.stack.connect("notify::visible-child-name", self._on_visible_screen_changed)
        self.stack.add_named(self._build_home(), "home")
        self.stack.add_named(self._build_loading_screen(), "loading")
        self.stack.add_named(self._build_config_screen(), "config")
        self.stack.add_named(self._build_result_screen(), "result")
        self.stack.add_named(self._build_reader_screen(), "reader")
        self.stack.add_named(self._build_account_screen(), "account")

        self.app_overlay = Gtk.Overlay()
        self.app_overlay.set_hexpand(True)
        self.app_overlay.set_vexpand(True)
        self.app_overlay.set_child(self.stack)
        self.set_child(self.app_overlay)
        self._apply_cached_account_view()
        self._auto_login_if_configured()

    def _load_css(self) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_path(str(BASE_DIR / "style.css"))
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_USER,
            )

    def _show_screen(self, name: str) -> None:
        if self.stack is None:
            return
        self.stack.set_visible_child_name(name)
        self._position_download_progress_button()

    def _on_visible_screen_changed(self, *_args) -> None:
        self._position_download_progress_button()

    def _normalize_ui_language(self, language: object) -> str:
        if str(language).lower() == "en":
            return "en"
        if str(language).lower().startswith("pt"):
            return "pt-BR"
        # fallback para locale do sistema
        try:
            import locale

            loc = (locale.getdefaultlocale()[0] or "").lower()
            if loc.startswith("pt"):
                return "pt-BR"
        except Exception:
            pass
        return "pt-BR"

    def _t(self, key: str, **kwargs: object) -> str:
        text = UI_TEXT.get(self.ui_language, UI_TEXT["pt-BR"]).get(key, UI_TEXT["pt-BR"].get(key, key))
        return text.format(**kwargs) if kwargs else text

    def _track_label(self, label: Gtk.Label, key: str) -> Gtk.Label:
        self._translated_labels[label] = key
        label.set_text(self._t(key))
        return label

    def _track_button(self, button: Gtk.Button, key: str) -> Gtk.Button:
        self._translated_buttons[button] = key
        button.set_label(self._t(key))
        return button

    def _track_entry_placeholder(self, entry: Gtk.Entry, key: str) -> Gtk.Entry:
        self._translated_entries[entry] = key
        entry.set_placeholder_text(self._t(key))
        return entry

    def _set_ui_language(self, language: str) -> None:
        self.ui_language = self._normalize_ui_language(language)
        self.config["ui_language"] = self.ui_language
        self._save_config()

        for label, key in list(self._translated_labels.items()):
            label.set_text(self._t(key))
        for button, key in list(self._translated_buttons.items()):
            button.set_label(self._t(key))
        for entry, key in list(self._translated_entries.items()):
            entry.set_placeholder_text(self._t(key))

        if self.settings_button is not None:
            self.settings_button.set_tooltip_text(self._t("settings_tooltip"))
        self._update_settings_language_button()
        self._update_settings_account_button()
        self._update_folder_button_label()
        self._update_result_description_language()
        self._update_language_button_label()
        if self.download_language_button is not None:
            self.download_language_button.set_label(self._download_language_label())
        self._update_download_toggle_button()
        if self.current_chapters:
            self._render_chapter_list()
        if self.download_chapter_list_box is not None and self.download_chapter_checks:
            self._render_download_chapter_list()
        if self.account_mdlists is not None:
            self._update_account_mdlists(self.account_mdlists)
        if self.account_profile is None:
            self._clear_account_view()
        selected = self._selected_mdlist()
        if selected is not None and self.account_manga_panel is not None and self.account_manga_panel.get_visible():
            self._show_mdlist_manga(selected)

    def _update_settings_language_button(self) -> None:
        button = getattr(self, "settings_language_button", None)
        if button is not None:
            button.set_label(self.ui_language)

    def _update_settings_account_button(self) -> None:
        button = getattr(self, "settings_config_button", None)
        if button is not None:
            button.set_label(self._t("settings_account" if self._has_saved_login() else "settings_config"))

    def _build_home(self) -> Gtk.Widget:
        overlay = Gtk.Overlay()
        overlay.add_css_class("home")
        self.home_overlay = overlay

        picture = Gtk.Picture()
        picture.set_content_fit(Gtk.ContentFit.COVER)
        picture.set_can_shrink(True)
        picture.set_hexpand(True)
        picture.set_vexpand(True)
        self.background_picture = picture
        self._set_wallpaper(self._current_wallpaper_path())
        self._restore_custom_wallpaper()
        overlay.set_child(picture)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=26)
        content.add_css_class("home-content")
        content.set_halign(Gtk.Align.CENTER)
        content.set_valign(Gtk.Align.CENTER)
        content.set_hexpand(False)
        content.set_vexpand(False)

        title = Gtk.Label(label="MangaDex-dl")
        title.add_css_class("app-title")
        title.set_halign(Gtk.Align.CENTER)
        title.set_xalign(0.5)

        subtitle = self._track_label(Gtk.Label(), "home_subtitle")
        subtitle.add_css_class("subtitle")
        subtitle.set_wrap(True)
        subtitle.set_justify(Gtk.Justification.CENTER)
        subtitle.set_xalign(0.5)
        subtitle.set_halign(Gtk.Align.CENTER)
        subtitle.set_size_request(560, -1)
        subtitle.set_max_width_chars(58)

        form = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        form.add_css_class("url-form")
        form.set_halign(Gtk.Align.CENTER)
        form.set_hexpand(False)
        form.set_homogeneous(False)

        # Switch para alternar entre MangaDex e Comick
        self.source_switch = Gtk.ToggleButton()
        is_comick = self.current_source == "comick"
        self.source_switch.set_label("Comick" if is_comick else "MangaDex")
        self.source_switch.add_css_class("source-switch")
        self.source_switch.set_active(is_comick)
        self.source_switch.connect("clicked", self._on_source_switch_clicked)

        self.url_entry.set_placeholder_text("https://mangadex.org/title/...")
        self.url_entry.add_css_class("url-entry")
        self.url_entry.add_css_class("flat")
        self.url_entry.set_has_frame(False)
        self.url_entry.set_hexpand(False)
        self.url_entry.set_size_request(300, -1)
        self.url_entry.connect("activate", self._on_load_clicked)

        load_button = self._track_button(Gtk.Button(), "load")
        load_button.add_css_class("load-button")
        load_button.set_focus_on_click(False)
        load_button.connect("clicked", self._on_load_clicked)

        form.append(self.source_switch)
        form.append(self.url_entry)
        form.append(load_button)

        self.status_label.add_css_class("status")
        self.status_label.set_halign(Gtk.Align.CENTER)
        self.status_label.set_visible(False)

        content.append(title)
        content.append(subtitle)
        content.append(form)
        overlay.add_overlay(content)
        overlay.add_overlay(self._build_settings_button())

        return overlay

    def _scrollable_page(self, child: Gtk.Widget) -> Gtk.Widget:
        scroller = Gtk.ScrolledWindow()
        scroller.add_css_class("page-scroll")
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        scroller.set_child(child)
        return scroller

    def _build_loading_screen(self) -> Gtk.Widget:
        overlay = Gtk.Overlay()
        overlay.add_css_class("manga-loading")

        picture = Gtk.Picture()
        picture.set_content_fit(Gtk.ContentFit.COVER)
        picture.set_can_shrink(True)
        picture.set_hexpand(True)
        picture.set_vexpand(True)
        self.loading_picture = picture
        overlay.set_child(picture)

        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        panel.add_css_class("manga-loading-panel")
        panel.set_halign(Gtk.Align.CENTER)
        panel.set_valign(Gtk.Align.CENTER)

        title = self._track_label(Gtk.Label(), "loading_title")
        title.add_css_class("manga-loading-title")
        title.set_halign(Gtk.Align.CENTER)

        self.loading_status_label = self._track_label(Gtk.Label(), "loading_status")
        self.loading_status_label.add_css_class("manga-loading-status")
        self.loading_status_label.set_halign(Gtk.Align.CENTER)

        panel.append(title)
        panel.append(self.loading_status_label)

        self.loading_back_button = self._track_button(Gtk.Button(), "back")
        self.loading_back_button.add_css_class("config-back-button")
        self.loading_back_button.set_visible(False)
        self.loading_back_button.connect("clicked", lambda *_: self._show_screen("home"))
        panel.append(self.loading_back_button)

        # clicar no overlay volta para home quando está em erro
        click = Gtk.GestureClick()
        click.connect("pressed", lambda *_: self._show_screen("home") if self.loading_back_button and self.loading_back_button.get_visible() else None)
        overlay.add_controller(click)
        overlay.add_overlay(panel)
        return overlay

    def _build_settings_button(self) -> Gtk.Widget:
        settings_button = Gtk.Button()
        settings_button.add_css_class("settings-button")

        icon_frame = Gtk.Box()
        icon_frame.add_css_class("settings-icon-frame")
        icon_frame.set_halign(Gtk.Align.CENTER)
        icon_frame.set_valign(Gtk.Align.CENTER)
        icon_frame.set_size_request(SETTINGS_AVATAR_SIZE, SETTINGS_AVATAR_SIZE)

        settings_icon = Gtk.Picture()
        settings_icon.add_css_class("settings-avatar-icon")
        settings_icon.set_content_fit(Gtk.ContentFit.COVER)
        settings_icon.set_can_shrink(True)
        settings_icon.set_hexpand(False)
        settings_icon.set_vexpand(False)
        settings_icon.set_size_request(SETTINGS_AVATAR_SIZE, SETTINGS_AVATAR_SIZE)
        self.settings_icon_picture = settings_icon
        self._update_settings_avatar_icon()
        icon_frame.append(settings_icon)
        settings_button.set_child(icon_frame)

        settings_button.set_size_request(42, 42)
        settings_button.set_halign(Gtk.Align.END)
        settings_button.set_valign(Gtk.Align.START)
        settings_button.set_margin_top(24)
        settings_button.set_margin_end(28)
        settings_button.set_tooltip_text(self._t("settings_tooltip"))
        settings_button.set_focus_on_click(False)
        settings_button.connect("clicked", self._on_settings_clicked)
        self.settings_button = settings_button
        return settings_button

    def _build_settings_menu(self) -> Gtk.Widget:
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        menu.add_css_class("settings-menu")

        config_button = Gtk.Button(label=self._t("settings_account" if self._has_saved_login() else "settings_config"))
        config_button.add_css_class("settings-menu-button")
        config_button.set_focus_on_click(False)
        config_button.connect("clicked", self._on_account_or_config_clicked)
        self.settings_config_button = config_button

        wallpaper_button = self._track_button(Gtk.Button(), "wallpaper")
        wallpaper_button.add_css_class("settings-menu-button")
        wallpaper_button.set_focus_on_click(False)
        wallpaper_button.connect("clicked", self._on_wallpaper_clicked)

        language_button = Gtk.Button(label=self.ui_language)
        language_button.add_css_class("settings-menu-button")
        language_button.set_focus_on_click(False)
        language_button.connect("clicked", self._on_language_clicked)
        self.settings_language_button = language_button

        menu.append(config_button)
        menu.append(wallpaper_button)
        menu.append(language_button)

        revealer = Gtk.Revealer()
        revealer.set_transition_type(Gtk.RevealerTransitionType.CROSSFADE)
        revealer.set_transition_duration(180)
        revealer.set_child(menu)
        revealer.set_halign(Gtk.Align.END)
        revealer.set_valign(Gtk.Align.START)
        revealer.set_margin_top(76)
        revealer.set_margin_end(28)
        self.settings_revealer = revealer
        return revealer

    def _build_wallpaper_dialog(self) -> Gtk.Widget:
        backdrop = Gtk.Box()
        backdrop.add_css_class("dialog-backdrop")
        backdrop.set_halign(Gtk.Align.FILL)
        backdrop.set_valign(Gtk.Align.FILL)
        backdrop.set_hexpand(True)
        backdrop.set_vexpand(True)
        backdrop.set_focusable(True)

        outside_click = Gtk.GestureClick()
        outside_click.connect("pressed", self._on_wallpaper_backdrop_clicked)
        backdrop.add_controller(outside_click)

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_wallpaper_key_pressed)
        backdrop.add_controller(key_controller)

        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        panel.add_css_class("wallpaper-dialog")
        panel.set_halign(Gtk.Align.CENTER)
        panel.set_valign(Gtk.Align.CENTER)

        title = self._track_label(Gtk.Label(), "wallpaper_title")
        title.add_css_class("dialog-title")
        title.set_halign(Gtk.Align.CENTER)

        self.wallpaper_entry = Gtk.Entry()
        self.wallpaper_entry.add_css_class("wallpaper-entry")
        self.wallpaper_entry.add_css_class("flat")
        self.wallpaper_entry.set_has_frame(False)
        self.wallpaper_entry.set_placeholder_text("https://exemplo.com/wallpaper.gif")
        self.wallpaper_entry.set_text(self.config.get("wallpaper_url", ""))
        self.wallpaper_entry.connect("activate", self._on_save_wallpaper_clicked)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        actions.add_css_class("dialog-actions")

        reset_button = self._track_button(Gtk.Button(), "reset")
        reset_button.add_css_class("reset-button")
        reset_button.set_focus_on_click(False)
        reset_button.connect("clicked", self._on_reset_wallpaper_clicked)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)

        save_button = self._track_button(Gtk.Button(), "save")
        save_button.add_css_class("save-button")
        save_button.set_focus_on_click(False)
        save_button.connect("clicked", self._on_save_wallpaper_clicked)

        actions.append(reset_button)
        actions.append(spacer)
        actions.append(save_button)

        panel.append(title)
        panel.append(self.wallpaper_entry)
        panel.append(actions)

        panel_click = Gtk.GestureClick()
        panel_click.connect("pressed", lambda *_args: None)
        panel.add_controller(panel_click)

        backdrop.append(panel)
        return backdrop

    def _build_config_screen(self) -> Gtk.Widget:
        screen = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        screen.add_css_class("config-screen")
        screen.add_css_class("config-layout")
        screen.set_hexpand(True)
        screen.set_vexpand(True)

        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        top_bar.add_css_class("config-topbar")

        back_button = self._track_button(Gtk.Button(), "back")
        back_button.add_css_class("config-back-button")
        back_button.set_focus_on_click(False)
        back_button.connect("clicked", self._on_back_home_clicked)

        heading = self._track_label(Gtk.Label(), "config_title")
        heading.add_css_class("config-heading")
        heading.set_hexpand(True)
        heading.set_halign(Gtk.Align.CENTER)
        heading.set_xalign(0.5)

        top_spacer = Gtk.Box()
        top_spacer.set_size_request(88, -1)

        top_bar.append(back_button)
        top_bar.append(heading)
        top_bar.append(top_spacer)

        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        body.add_css_class("config-body")
        body.set_hexpand(True)
        body.set_vexpand(True)

        api_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        api_panel.add_css_class("config-api-panel")
        api_panel.set_halign(Gtk.Align.START)
        api_panel.set_valign(Gtk.Align.START)

        api_title = Gtk.Label(label="Login MangaDex")
        api_title.add_css_class("config-section-title")
        api_title.set_halign(Gtk.Align.START)

        self.username_entry = self._build_config_entry("username")
        self.username_entry.set_text(self.config.get("mangadex_username", ""))
        self.password_entry = self._build_config_entry("password")
        self.password_entry.set_visibility(False)
        self.password_entry.set_text(self.config.get("mangadex_password", ""))
        self.client_id_entry = self._build_config_entry("Client ID")
        self.client_id_entry.set_text(self.config.get("mangadex_client_id", ""))
        self.client_secret_entry = self._build_config_entry("Client Secret")
        self.client_secret_entry.set_visibility(False)
        self.client_secret_entry.set_text(self.config.get("mangadex_client_secret", ""))
        self.config_status_label = Gtk.Label()
        self.config_status_label.add_css_class("config-status")
        self.config_status_label.set_halign(Gtk.Align.START)

        save_button = self._track_button(Gtk.Button(), "login")
        save_button.add_css_class("config-save-button")
        save_button.set_focus_on_click(False)
        save_button.connect("clicked", self._on_config_save_clicked)

        api_panel.append(api_title)
        api_panel.append(self.username_entry)
        api_panel.append(self.password_entry)
        api_panel.append(self.client_id_entry)
        api_panel.append(self.client_secret_entry)
        api_panel.append(save_button)
        api_panel.append(self.config_status_label)

        guide_panel = self._build_api_guide()

        body.append(api_panel)
        body.append(guide_panel)
        screen.append(top_bar)
        screen.append(body)
        screen.append(self._build_login_info())
        return self._scrollable_page(screen)

    def _build_api_guide(self) -> Gtk.Widget:
        guide = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        guide.add_css_class("api-guide")
        guide.set_halign(Gtk.Align.CENTER)
        guide.set_valign(Gtk.Align.START)
        guide.set_hexpand(True)

        if API_GUIDE_GIF.exists():
            gif = AnimatedGifPicture(API_GUIDE_GIF)
            gif.add_css_class("api-guide-gif")
            gif.set_size_request(360, 220)
            guide.append(gif)
        else:
            missing = self._track_label(Gtk.Label(), "api_gif_missing")
            missing.add_css_class("api-guide-missing")
            missing.set_size_request(360, 180)
            missing.set_halign(Gtk.Align.CENTER)
            missing.set_valign(Gtk.Align.CENTER)
            guide.append(missing)

        title = self._track_label(Gtk.Label(), "api_guide_title")
        title.add_css_class("api-guide-title")
        title.set_halign(Gtk.Align.CENTER)
        title.set_xalign(0.5)

        steps = self._track_label(Gtk.Label(), "api_guide_steps")
        steps.add_css_class("api-guide-steps")
        steps.set_wrap(True)
        steps.set_max_width_chars(56)
        steps.set_halign(Gtk.Align.CENTER)
        steps.set_xalign(0.0)

        guide.append(title)
        guide.append(steps)
        return guide

    def _build_login_info(self) -> Gtk.Widget:
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        info.add_css_class("login-info")
        info.set_halign(Gtk.Align.CENTER)
        info.set_valign(Gtk.Align.END)

        question = self._track_label(Gtk.Label(), "login_info_question")
        question.add_css_class("login-info-question")
        question.set_halign(Gtk.Align.CENTER)
        question.set_xalign(0.5)

        answer = self._track_label(Gtk.Label(), "login_info_answer")
        answer.add_css_class("login-info-answer")
        answer.set_wrap(True)
        answer.set_justify(Gtk.Justification.CENTER)
        answer.set_max_width_chars(78)
        answer.set_halign(Gtk.Align.CENTER)
        answer.set_xalign(0.5)

        info.append(question)
        info.append(answer)
        return info

    def _build_config_entry(self, placeholder_key: str) -> Gtk.Entry:
        entry = Gtk.Entry()
        entry.add_css_class("config-entry")
        entry.add_css_class("flat")
        entry.set_has_frame(False)
        self._track_entry_placeholder(entry, placeholder_key)
        entry.set_size_request(320, -1)
        return entry

    def _build_result_screen(self) -> Gtk.Widget:
        overlay = Gtk.Overlay()
        overlay.add_css_class("result-screen")
        overlay.set_hexpand(True)
        overlay.set_vexpand(True)
        self.result_overlay = overlay

        self.result_banner_picture = Gtk.Picture()
        self.result_banner_picture.add_css_class("result-page-background")
        self.result_banner_picture.set_content_fit(Gtk.ContentFit.COVER)
        self.result_banner_picture.set_can_shrink(True)
        self.result_banner_picture.set_hexpand(True)
        self.result_banner_picture.set_vexpand(True)
        overlay.set_child(self.result_banner_picture)

        shade = Gtk.Box()
        shade.add_css_class("result-page-shade")
        shade.set_hexpand(True)
        shade.set_vexpand(True)
        overlay.add_overlay(shade)

        screen = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        screen.add_css_class("result-screen")
        screen.set_hexpand(True)
        screen.set_vexpand(True)

        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        top_bar.add_css_class("result-topbar")

        back_button = self._track_button(Gtk.Button(), "back")
        back_button.add_css_class("config-back-button")
        back_button.add_css_class("result-back-button")
        back_button.set_focus_on_click(False)
        back_button.set_valign(Gtk.Align.CENTER)
        back_button.set_size_request(74, 24)
        back_button.connect("clicked", self._on_result_back_clicked)

        heading = Gtk.Label(label="MangaDex")
        heading.add_css_class("result-heading")
        heading.set_hexpand(True)
        heading.set_halign(Gtk.Align.CENTER)

        top_spacer = Gtk.Box()
        top_spacer.set_size_request(88, -1)

        top_bar.append(back_button)
        top_bar.append(heading)
        top_bar.append(top_spacer)

        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=28)
        body.add_css_class("result-body")
        body.set_hexpand(True)
        body.set_vexpand(True)

        self.result_cover_picture = Gtk.Picture()
        self.result_cover_picture.add_css_class("result-cover")
        self.result_cover_picture.set_content_fit(Gtk.ContentFit.COVER)
        self.result_cover_picture.set_size_request(260, 370)
        self.result_cover_picture.set_hexpand(False)
        self.result_cover_picture.set_vexpand(False)

        details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        details.add_css_class("result-details")
        details.set_hexpand(True)
        details.set_vexpand(True)

        self.result_title_label = self._track_label(Gtk.Label(), "empty_manga")
        self.result_title_label.add_css_class("result-title")
        self.result_title_label.set_wrap(True)
        self.result_title_label.set_lines(3)
        self.result_title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.result_title_label.set_halign(Gtk.Align.START)
        self.result_title_label.set_xalign(0.0)

        self.result_subtitle_label = Gtk.Label()
        self.result_subtitle_label.add_css_class("result-subtitle")
        self.result_subtitle_label.set_wrap(True)
        self.result_subtitle_label.set_lines(4)
        self.result_subtitle_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.result_subtitle_label.set_halign(Gtk.Align.START)
        self.result_subtitle_label.set_xalign(0.0)

        self.result_meta_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.result_meta_box.add_css_class("result-meta")
        self.result_meta_box.set_halign(Gtk.Align.START)

        self.result_actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.result_actions_box.add_css_class("result-actions")
        for key in ("download", "folder", "language"):
            action = self._track_button(Gtk.Button(), key)
            action.add_css_class("result-action-button")
            action.set_focus_on_click(False)
            if key == "download":
                action.connect("clicked", self._on_download_clicked)
                self.result_download_button = action
            if key == "folder":
                action.connect("clicked", self._on_folder_clicked)
                self.result_folder_button = action
            if key == "language":
                action.connect("clicked", self._on_language_filter_clicked)
                self.result_language_button = action
            self.result_actions_box.append(action)

        scroller = Gtk.ScrolledWindow()
        scroller.add_css_class("result-scroller")
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        self.result_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.result_list_box.add_css_class("result-list")
        scroller.set_child(self.result_list_box)

        details.append(self.result_title_label)
        details.append(self.result_subtitle_label)
        details.append(self.result_meta_box)
        details.append(self.result_actions_box)
        details.append(scroller)

        body.append(self.result_cover_picture)
        body.append(details)
        screen.append(top_bar)
        screen.append(body)
        overlay.add_overlay(screen)
        return self._scrollable_page(overlay)

    def _build_reader_screen(self) -> Gtk.Widget:
        screen = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        screen.add_css_class("reader-screen")
        screen.set_hexpand(True)
        screen.set_vexpand(True)

        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        top_bar.add_css_class("reader-topbar")

        self.reader_title_label = self._track_label(Gtk.Label(), "reader")
        self.reader_title_label.add_css_class("reader-title")
        self.reader_title_label.set_hexpand(True)
        self.reader_title_label.set_halign(Gtk.Align.START)
        self.reader_title_label.set_xalign(0.0)
        self.reader_title_label.set_wrap(True)

        back_button = self._track_button(Gtk.Button(), "back")
        back_button.add_css_class("reader-back-button")
        back_button.set_focus_on_click(False)
        back_button.set_valign(Gtk.Align.CENTER)
        back_button.set_size_request(74, 24)
        back_button.connect("clicked", self._on_reader_back_clicked)

        top_bar.append(self.reader_title_label)
        top_bar.append(back_button)

        page_area = Gtk.Overlay()
        page_area.add_css_class("reader-page-area")
        page_area.set_hexpand(True)
        page_area.set_vexpand(True)

        click = Gtk.GestureClick()
        click.connect("pressed", self._on_reader_page_clicked)
        page_area.add_controller(click)

        self.reader_page_picture = Gtk.Picture()
        self.reader_page_picture.add_css_class("reader-page")
        self.reader_page_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.reader_page_picture.set_can_shrink(True)
        self.reader_page_picture.set_hexpand(True)
        self.reader_page_picture.set_vexpand(True)
        page_area.set_child(self.reader_page_picture)

        self.reader_status_label = Gtk.Label(label="")
        self.reader_status_label.add_css_class("reader-status")
        self.reader_status_label.set_halign(Gtk.Align.CENTER)
        self.reader_status_label.set_valign(Gtk.Align.CENTER)
        self.reader_status_label.set_wrap(True)
        page_area.add_overlay(self.reader_status_label)

        self.reader_page_counter_label = Gtk.Label(label="00/00")
        self.reader_page_counter_label.add_css_class("reader-page-counter")
        self.reader_page_counter_label.set_halign(Gtk.Align.END)
        self.reader_page_counter_label.set_valign(Gtk.Align.END)
        self.reader_page_counter_label.set_margin_end(18)
        self.reader_page_counter_label.set_margin_bottom(14)
        self.reader_page_counter_label.set_visible(False)
        page_area.add_overlay(self.reader_page_counter_label)

        screen.append(top_bar)
        screen.append(page_area)
        return screen

    def _build_account_screen(self) -> Gtk.Widget:
        screen = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        screen.add_css_class("account-screen")
        screen.set_hexpand(True)
        screen.set_vexpand(True)

        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        top_bar.add_css_class("account-topbar")

        left_spacer = Gtk.Box()
        left_spacer.set_size_request(88, -1)

        heading = self._track_label(Gtk.Label(), "account_title")
        heading.add_css_class("result-heading")
        heading.set_hexpand(True)
        heading.set_halign(Gtk.Align.CENTER)

        home_button = self._track_button(Gtk.Button(), "home")
        home_button.add_css_class("config-back-button")
        home_button.add_css_class("account-home-button")
        home_button.set_focus_on_click(False)
        home_button.set_valign(Gtk.Align.CENTER)
        home_button.set_size_request(88, 34)
        home_button.connect("clicked", self._on_back_home_clicked)

        top_bar.append(left_spacer)
        top_bar.append(heading)
        top_bar.append(home_button)

        banner = Gtk.Overlay()
        banner.add_css_class("account-banner")
        banner.set_size_request(-1, ACCOUNT_BANNER_HEIGHT)
        banner.set_vexpand(False)

        self.account_banner_picture = Gtk.Picture()
        self.account_banner_picture.add_css_class("account-banner-picture")
        self.account_banner_picture.set_content_fit(Gtk.ContentFit.COVER)
        self.account_banner_picture.set_can_shrink(True)
        self.account_banner_picture.set_hexpand(True)
        self.account_banner_picture.set_vexpand(True)
        self.account_banner_picture.set_halign(Gtk.Align.FILL)
        self.account_banner_picture.set_valign(Gtk.Align.FILL)
        self.account_banner_picture.set_size_request(-1, ACCOUNT_BANNER_HEIGHT)
        banner.set_child(self.account_banner_picture)

        banner_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        banner_content.add_css_class("account-banner-content")
        banner_content.set_size_request(-1, ACCOUNT_BANNER_HEIGHT)
        banner_content.set_hexpand(True)
        banner_content.set_vexpand(True)
        banner_content.set_halign(Gtk.Align.FILL)
        banner_content.set_valign(Gtk.Align.END)
        banner_content.set_margin_start(16)
        banner_content.set_margin_end(16)
        banner_content.set_margin_bottom(12)

        avatar_stack = Gtk.Overlay()
        avatar_stack.add_css_class("account-avatar")
        avatar_stack.set_size_request(ACCOUNT_AVATAR_SIZE, ACCOUNT_AVATAR_SIZE)
        avatar_stack.set_hexpand(False)
        avatar_stack.set_vexpand(False)
        avatar_stack.set_valign(Gtk.Align.END)
        avatar_stack.set_visible(False)

        self.account_avatar_picture = Gtk.Picture()
        self.account_avatar_picture.add_css_class("account-avatar-picture")
        self.account_avatar_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.account_avatar_picture.set_can_shrink(True)
        self.account_avatar_picture.set_size_request(ACCOUNT_AVATAR_SIZE, ACCOUNT_AVATAR_SIZE)
        avatar_stack.set_child(self.account_avatar_picture)

        self.account_avatar_fallback = Gtk.Label(label="MD")
        self.account_avatar_fallback.add_css_class("account-avatar-fallback")
        avatar_stack.add_overlay(self.account_avatar_fallback)

        self.account_username_label = self._track_label(Gtk.Label(), "not_logged")
        self.account_username_label.add_css_class("account-username")
        self.account_username_label.set_halign(Gtk.Align.START)
        self.account_username_label.set_valign(Gtk.Align.END)
        self.account_username_label.set_margin_start(4)

        self.account_user_id_label = self._track_label(Gtk.Label(), "login_required")
        self.account_user_id_label.add_css_class("account-user-id")
        self.account_user_id_label.set_halign(Gtk.Align.START)
        self.account_user_id_label.set_visible(False)

        banner_content.append(self.account_username_label)
        # mantém avatar/id escondidos mas no hierarchy para não quebrar _update_account_profile
        banner_content.append(avatar_stack)
        banner_content.append(self.account_user_id_label)
        banner.add_overlay(banner_content)

        profile_refresh_button = self._track_button(Gtk.Button(), "refresh")
        profile_refresh_button.add_css_class("account-profile-refresh-button")
        profile_refresh_button.set_focus_on_click(False)
        profile_refresh_button.set_halign(Gtk.Align.END)
        profile_refresh_button.set_valign(Gtk.Align.END)
        profile_refresh_button.set_margin_end(10)
        profile_refresh_button.set_margin_bottom(8)
        profile_refresh_button.connect("clicked", self._on_refresh_account_profile_clicked)
        banner.add_overlay(profile_refresh_button)

        logout_button = self._track_button(Gtk.Button(), "logout")
        logout_button.add_css_class("account-logout-button")
        logout_button.set_focus_on_click(False)
        logout_button.set_halign(Gtk.Align.END)
        logout_button.set_valign(Gtk.Align.START)
        logout_button.set_margin_top(10)
        logout_button.set_margin_end(10)
        logout_button.connect("clicked", self._on_logout_clicked)
        banner.add_overlay(logout_button)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.add_css_class("account-content")
        content.set_hexpand(True)
        content.set_vexpand(True)

        lists_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lists_title = self._track_label(Gtk.Label(), "your_mdlists")
        lists_title.add_css_class("account-section-title")
        lists_title.set_halign(Gtk.Align.START)
        lists_title.set_hexpand(True)

        refresh_button = self._track_button(Gtk.Button(), "refresh_mdlists")
        refresh_button.add_css_class("account-refresh-button")
        refresh_button.set_focus_on_click(False)
        refresh_button.connect("clicked", self._on_refresh_mdlists_clicked)

        lists_header.append(lists_title)
        lists_header.append(refresh_button)
        self.account_lists_header = lists_header

        scroller = Gtk.ScrolledWindow()
        scroller.add_css_class("account-mdlists-scroller")
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_hexpand(True)
        scroller.set_vexpand(False)
        scroller.set_size_request(-1, 180)
        self.account_mdlists_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.account_mdlists_box.add_css_class("account-mdlists")
        scroller.set_child(self.account_mdlists_box)
        self.account_mdlists_scroller = scroller

        manga_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        manga_title = self._track_label(Gtk.Label(), "list_manga")
        manga_title.add_css_class("account-section-title")
        manga_title.set_halign(Gtk.Align.START)
        manga_title.set_hexpand(True)
        self.account_manga_title_label = manga_title

        manga_back_button = self._track_button(Gtk.Button(), "back")
        manga_back_button.add_css_class("account-manga-back-button")
        manga_back_button.set_focus_on_click(False)
        manga_back_button.connect("clicked", self._on_mdlist_back_clicked)

        manga_header.append(manga_title)
        manga_header.append(manga_back_button)

        manga_scroller = Gtk.ScrolledWindow()
        manga_scroller.add_css_class("account-manga-scroller")
        manga_scroller.set_hexpand(True)
        manga_scroller.set_vexpand(True)
        self.account_manga_grid = Gtk.FlowBox()
        self.account_manga_grid.add_css_class("account-manga-grid")
        self.account_manga_grid.set_selection_mode(Gtk.SelectionMode.NONE)
        self.account_manga_grid.set_max_children_per_line(7)
        self.account_manga_grid.set_min_children_per_line(7)
        self.account_manga_grid.set_row_spacing(12)
        self.account_manga_grid.set_column_spacing(12)
        manga_scroller.set_child(self.account_manga_grid)

        self.account_manga_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.account_manga_panel.add_css_class("account-manga-panel")
        self.account_manga_panel.set_visible(False)
        self.account_manga_panel.append(manga_header)
        self.account_manga_panel.append(manga_scroller)

        content.append(lists_header)
        content.append(scroller)
        content.append(self.account_manga_panel)
        screen.append(top_bar)
        screen.append(banner)
        screen.append(content)
        return self._scrollable_page(screen)

    def _on_source_switch_clicked(self, button: Gtk.ToggleButton) -> None:
        if button.get_active():
            self.current_source = "comick"
            button.set_label("Comick")
            self.url_entry.set_placeholder_text("https://comickz.co.uk/comic/...")
        else:
            self.current_source = "mangadex"
            button.set_label("MangaDex")
        self.url_entry.set_placeholder_text("https://comickz.co.uk/comic/..." if self.current_source == "comick" else "https://mangadex.org/title/...")
        self.config["source"] = self.current_source
        self._save_config()

    def _on_load_clicked(self, *_args) -> None:
        url = self.url_entry.get_text().strip()
        self.url_entry.remove_css_class("invalid")

        if not url:
            self.url_entry.add_css_class("invalid")
            self._set_home_status(self._t("url_required"), clear_after_ms=4000)
            return

        # auto-detecta comickz/mangadex pela URL se switch estiver errado
        is_comick_url = any(
            url.startswith(p)
            for p in (
                "https://comick.io/",
                "https://comick.app/",
                "https://comick.cc/",
                "https://comick.ink/",
                "https://comick.dev/",
                "https://comickz.co.uk/",
                "https://comickz.cc/",
                "https://comickz.app/",
                "https://comick.live/",
            )
        )
        is_mangadex_url = url.startswith("https://mangadex.org/")
        if is_comick_url and self.current_source != "comick":
            # auto-switch para comick
            self.current_source = "comick"
            self.config["source"] = "comick"
            self._save_config()
            if self.source_switch:
                self.source_switch.set_active(True)
                self.source_switch.set_label("Comick")

        if self.current_source == "mangadex":
            if not is_mangadex_url:
                self.url_entry.add_css_class("invalid")
                self._set_home_status(self._t("invalid_url"), clear_after_ms=4000)
                self.status_label.set_visible(True)
                return
        else:
            if not is_comick_url:
                self.url_entry.add_css_class("invalid")
                self._set_home_status(self._t("invalid_url_comick"), clear_after_ms=4000)
                self.status_label.set_visible(True)
                return
        # limpa status anterior
        self.status_label.set_visible(False)

        self.result_back_target = "home"
        source = self.current_source
        loading_text = self._t("loading_status") if source == "mangadex" else "Buscando dados no Comick..."
        self._show_manga_loading(loading_text)
        threading.Thread(target=self._load_resource, args=(url, source), daemon=True).start()

    def _load_resource(self, url: str, source: str | None = None) -> None:
        src = source or self.current_source
        if src == "mangadex":
            self._load_mangadex_resource(url)
        else:
            self._load_comick_resource(url)

    def _load_mangadex_resource(self, url: str) -> None:
        try:
            result = self.mangadex_client.load_from_url(url)
        except MangaDexApiError as error:
            GLib.idle_add(self._finish_mangadex_error, str(error))
            return

        GLib.idle_add(self._finish_mangadex_load, result)

    def _load_comick_resource(self, url: str) -> None:
        try:
            result = self.comick_client.load_from_url(url)
            GLib.idle_add(self._finish_comick_load, result)
        except ComickApiError as error:
            GLib.idle_add(self._finish_comick_error, str(error))
        except Exception as error:
            GLib.idle_add(self._finish_comick_error, f"Erro inesperado: {error}")

    def _finish_comick_load(self, result: MangaDetails) -> bool:
        self.current_result_source = "comick"
        self._show_mangadex_result(result)
        self._clear_home_status()
        self.url_entry.set_text("")
        return False

    def _finish_comick_error(self, message: str) -> bool:
        if self.loading_status_label is not None:
            self.loading_status_label.set_text(message)
            self.loading_status_label.set_wrap(True)
            self.loading_status_label.set_max_width_chars(48)
        if self.loading_back_button is not None:
            self.loading_back_button.set_visible(True)
        # permite voltar com ESC
        if self.stack and self.stack.get_visible_child_name() != "loading":
            self._show_screen("loading")
        return False

    def _show_manga_loading(self, message: str) -> None:
        if self.loading_picture is not None:
            self.loading_picture.set_paintable(None)
            self.loading_picture.set_filename(str(self.current_wallpaper_path))
        if self.loading_status_label is not None:
            self.loading_status_label.set_text(message)
            self.loading_status_label.set_max_width_chars(0)
        if self.loading_back_button is not None:
            self.loading_back_button.set_visible(False)
        self._show_screen("loading")

    def _finish_mangadex_load(self, result: MangaDetails | MdListDetails) -> bool:
        # se for MdList não é manga, mantém source atual; se for MangaDetails vindo de MangaDex, seta
        if isinstance(result, MangaDetails):
            self.current_result_source = "mangadex"
        self._show_mangadex_result(result)
        self._clear_home_status()
        self.url_entry.set_text("")
        return False

    def _finish_mangadex_error(self, message: str) -> bool:
        if self.loading_status_label is not None:
            self.loading_status_label.set_text(message)
            self.loading_status_label.set_wrap(True)
            self.loading_status_label.set_max_width_chars(48)
        if self.loading_back_button is not None:
            self.loading_back_button.set_visible(True)
        return False

    def _show_mangadex_result(self, result: MangaDetails | MdListDetails) -> None:
        if self.result_title_label is None or self.result_subtitle_label is None:
            return

        if self.result_list_box is not None:
            while child := self.result_list_box.get_first_child():
                self.result_list_box.remove(child)

        if isinstance(result, MangaDetails):
            self.current_result_manga_id = result.id
            self.current_result_manga_title = result.title or result.id
            self.current_result_manga = result
            self.current_download_folder = self.config.get("default_download_folder")
            self.current_chapters = []
            self.current_chapter_language = None
            self.current_download_language = None
            if self.result_language_button is not None:
                self.result_language_button.set_label(self._t("language"))
            if self.download_language_button is not None:
                self.download_language_button.set_label(self._t("language"))
            self._update_folder_button_label()
            self.result_title_label.set_text(result.title or "Manga sem titulo")
            self.result_subtitle_label.set_text(self._manga_description_text(result))
            self._update_result_meta(result)
            if result.cover_url:
                self._load_cover_into_result(result.cover_url)
            if self.result_list_box is not None:
                self.result_list_box.append(self._build_result_row(self._t("loading_chapters")))
            self._load_chapters_into_result(result.id)
        else:
            self.current_result_manga_id = None
            self.current_result_manga_title = ""
            self.current_result_manga = None
            self.result_title_label.set_text(result.name or "MDList")
            self.result_subtitle_label.set_text(self._t("mdlist_found_count", count=len(result.manga)))
            self._clear_result_meta()
            if result.manga and result.manga[0].cover_url:
                self._load_cover_into_result(result.manga[0].cover_url)
            if self.result_list_box is not None:
                for manga in result.manga:
                    self.result_list_box.append(self._build_result_row(manga.title or manga.id))

        self._show_screen("result")

    def _update_result_description_language(self) -> None:
        if self.current_result_manga is None or self.result_subtitle_label is None:
            return
        self.result_subtitle_label.set_text(self._manga_description_text(self.current_result_manga))

    def _manga_description_text(self, manga: MangaDetails) -> str:
        descriptions = manga.descriptions or {}
        if self.ui_language == "en":
            description = descriptions.get("en") or manga.description
        else:
            description = descriptions.get("pt-br") or descriptions.get("pt") or manga.description
        return self._display_manga_description(description)

    def _display_manga_description(self, description: str) -> str:
        cleaned = self._clean_mangadex_text(description)
        if not cleaned:
            return self._t("no_synopsis")
        lower = cleaned.lower()
        if lower.startswith("the fanbox side story/extra content"):
            return self._t("no_synopsis")
        return cleaned[:520]

    def _clean_mangadex_text(self, value: str) -> str:
        cleaned = value.strip()
        cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
        cleaned = re.sub(r"https?://\S+", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    def _clear_result_meta(self) -> None:
        if self.result_meta_box is None:
            return
        while child := self.result_meta_box.get_first_child():
            self.result_meta_box.remove(child)

    def _update_result_meta(self, manga: MangaDetails) -> None:
        if self.result_meta_box is None:
            return
        self._clear_result_meta()

        for tag in (manga.tags or [])[:8]:
            self.result_meta_box.append(self._build_result_meta_chip(tag.upper(), "result-tag-chip"))

        publish_parts: list[str] = []
        if manga.year:
            publish_parts.append(str(manga.year))
        if manga.status:
            publish_parts.append(manga.status.upper())
        if publish_parts:
            status = Gtk.Label(label="")
            status.add_css_class("result-publication-dot")
            self.result_meta_box.append(status)
            self.result_meta_box.append(
                self._build_result_meta_chip(f"{self._t('publication')}: {', '.join(publish_parts)}", "result-publication-chip")
            )

    def _build_result_meta_chip(self, text: str, css_class: str) -> Gtk.Widget:
        label = Gtk.Label(label=text)
        label.add_css_class(css_class)
        label.set_halign(Gtk.Align.START)
        return label

    def _build_result_row(self, text: str) -> Gtk.Widget:
        row = Gtk.Label(label=text)
        row.add_css_class("result-row")
        row.set_halign(Gtk.Align.FILL)
        row.set_xalign(0.0)
        row.set_wrap(True)
        return row

    def _load_chapters_into_result(self, manga_id: str) -> None:
        source = getattr(self, "current_result_source", self.current_source)
        threading.Thread(target=self._download_chapters, args=(manga_id, source), daemon=True).start()

    def _download_chapters(self, manga_id: str, source: str | None = None) -> None:
        src = source or getattr(self, "current_result_source", self.current_source)
        try:
            if src == "mangadex":
                chapters = self.mangadex_client.get_manga_chapters(manga_id)
            else:
                chapters = self.comick_client.get_manga_chapters(manga_id)
        except (MangaDexApiError, ComickApiError) as error:
            GLib.idle_add(self._finish_chapters_error, manga_id, str(error))
            return
        GLib.idle_add(self._finish_chapters_load, manga_id, chapters)

    def _finish_chapters_load(self, manga_id: str, chapters: list[ChapterGroup]) -> bool:
        if manga_id != self.current_result_manga_id or self.result_list_box is None:
            return False

        self.current_chapters = chapters
        self.current_chapter_language = None
        self._update_language_button_label()
        self._render_chapter_list()
        return False

    def _render_chapter_list(self) -> None:
        if self.result_list_box is None:
            return

        while child := self.result_list_box.get_first_child():
            self.result_list_box.remove(child)

        chapters = self._filtered_chapters()
        if not chapters:
            self.result_list_box.append(self._build_result_row(self._t("no_chapters_language")))
            return

        for chapter in chapters:
            self.result_list_box.append(self._build_chapter_row(chapter))

    def _finish_chapters_error(self, manga_id: str, message: str) -> bool:
        if manga_id == self.current_result_manga_id and self.result_list_box is not None:
            while child := self.result_list_box.get_first_child():
                self.result_list_box.remove(child)
            self.result_list_box.append(self._build_result_row(message))
        return False

    def _build_chapter_volume_header(self, volume: str) -> Gtk.Widget:
        label = Gtk.Label(label=f"Volume {volume}" if volume != "Sem volume" else volume)
        label.add_css_class("chapter-volume-header")
        label.set_halign(Gtk.Align.FILL)
        label.set_xalign(0.0)
        return label

    def _build_chapter_row(self, chapter: ChapterGroup) -> Gtk.Widget:
        button = Gtk.Button()
        button.add_css_class("chapter-button")
        button.set_focus_on_click(False)
        button.connect("clicked", self._on_chapter_clicked, chapter)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.add_css_class("chapter-row")
        row.set_hexpand(True)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        info.set_hexpand(True)

        title = Gtk.Label(label=self._chapter_label(chapter))
        title.add_css_class("chapter-title")
        title.set_halign(Gtk.Align.START)
        title.set_xalign(0.0)
        title.set_wrap(True)

        meta = Gtk.Label(label=", ".join(chapter.groups[:2]) or self._t("group_none"))
        meta.add_css_class("chapter-meta")
        meta.set_halign(Gtk.Align.START)
        meta.set_xalign(0.0)

        info.append(title)
        info.append(meta)

        languages = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        languages.set_halign(Gtk.Align.END)
        if self._chapter_was_read(chapter.id):
            read_mark = Gtk.Label(label="✓")
            read_mark.add_css_class("chapter-read-mark")
            languages.append(read_mark)
        for language in chapter.languages or ["N/A"]:
            chip = Gtk.Label(label=self._language_label(language))
            chip.add_css_class("chapter-language-chip")
            languages.append(chip)

        row.append(info)
        row.append(languages)
        button.set_child(row)
        return button

    def _on_chapter_clicked(self, _button: Gtk.Button, chapter: ChapterGroup) -> None:
        self._open_reader_chapter(chapter)

    def _open_reader_chapter(self, chapter: ChapterGroup, start_at_end: bool = False) -> None:
        self._mark_chapter_as_read(chapter.id)
        self.current_reader_chapter_id = chapter.id
        self.current_reader_page_urls = []
        self.current_reader_page_paths = []
        self.current_reader_page_index = 0
        self.current_reader_open_at_end = start_at_end
        self.current_reader_total_pages = 0
        title = f"{self.current_result_manga_title} - {self._chapter_label(chapter)}"
        if self.reader_title_label is not None:
            self.reader_title_label.set_text(title)
        if self.reader_page_picture is not None:
            self.reader_page_picture.set_paintable(None)
        if self.reader_status_label is not None:
            self.reader_status_label.set_text(self._t("chapter_loading_pages"))
            self.reader_status_label.set_visible(True)
        self._update_reader_page_counter()
        self._show_screen("reader")
        source = getattr(self, "current_result_source", self.current_source)
        threading.Thread(target=self._load_reader_pages, args=(chapter, title, source), daemon=True).start()

    def _chapter_was_read(self, chapter_id: str) -> bool:
        read_ids = self.config.get("read_chapter_ids", [])
        return isinstance(read_ids, list) and chapter_id in read_ids

    def _mark_chapter_as_read(self, chapter_id: str) -> None:
        read_ids = self.config.get("read_chapter_ids", [])
        if not isinstance(read_ids, list):
            read_ids = []
        if chapter_id in read_ids:
            return
        read_ids.append(chapter_id)
        self.config["read_chapter_ids"] = read_ids
        self._save_config()
        self._render_chapter_list()

    def _load_reader_pages(self, chapter: ChapterGroup, title: str, source: str | None = None) -> None:
        src = source or getattr(self, "current_result_source", self.current_source)
        try:
            if src == "mangadex":
                pages = self.mangadex_client.get_chapter_pages(chapter.id)
            else:
                pages = self.comick_client.get_chapter_pages(chapter.id)
        except (MangaDexApiError, ComickApiError) as error:
            GLib.idle_add(self._finish_reader_error, chapter.id, str(error))
            return
        GLib.idle_add(self._start_reader_pages, chapter.id, title, pages)

    def _start_reader_pages(self, chapter_id: str, title: str, pages: ChapterPages) -> bool:
        if chapter_id != self.current_reader_chapter_id:
            return False
        if self.reader_title_label is not None:
            self.reader_title_label.set_text(title)
        self.current_reader_page_urls = pages.pages
        self.current_reader_total_pages = len(pages.pages)
        self.current_reader_page_paths = [None] * self.current_reader_total_pages
        self.current_reader_page_index = self.current_reader_total_pages - 1 if self.current_reader_open_at_end else 0
        self.current_reader_open_at_end = False
        self._update_reader_page_counter()
        if not pages.pages:
            self._show_reader_page()
            return False
        threading.Thread(target=self._cache_reader_pages_progressively, args=(pages,), daemon=True).start()
        return False

    def _cache_reader_pages_progressively(self, pages: ChapterPages) -> None:
        indexes = list(range(len(pages.pages)))
        if self.current_reader_open_at_end:
            indexes.reverse()
        elif self.current_reader_page_index in indexes:
            indexes.remove(self.current_reader_page_index)
            indexes.insert(0, self.current_reader_page_index)

        # baixa primeira página síncrona para abrir rápido
        if indexes:
            first = indexes[0]
            if pages.chapter_id == self.current_reader_chapter_id:
                try:
                    p = self._cache_reader_page(pages.chapter_id, first, pages.pages[first])
                    GLib.idle_add(self._finish_reader_page, pages.chapter_id, first, p)
                except OSError as e:
                    GLib.idle_add(self._finish_reader_error, pages.chapter_id, str(e))
                indexes = indexes[1:]
                if not indexes:
                    return
        # resto em paralelo (3 threads)
        with ThreadPoolExecutor(max_workers=self._download_threads) as ex:
            futures = {}
            for idx in indexes:
                if pages.chapter_id != self.current_reader_chapter_id:
                    ex.shutdown(wait=False, cancel_futures=True)
                    return
                fut = ex.submit(self._cache_reader_page, pages.chapter_id, idx, pages.pages[idx])
                futures[fut] = idx
            for fut in as_completed(futures):
                idx = futures[fut]
                if pages.chapter_id != self.current_reader_chapter_id:
                    return
                try:
                    page_path = fut.result()
                    GLib.idle_add(self._finish_reader_page, pages.chapter_id, idx, page_path)
                except OSError as e:
                    if "429" in str(e) or "rate-limit" in str(e).lower():
                        GLib.idle_add(self._finish_reader_error, pages.chapter_id, f"Rate-limit (429) {e}")
                    else:
                        GLib.idle_add(self._finish_reader_error, pages.chapter_id, str(e))

    def _headers_for_url(self, url: str) -> dict[str, str]:
        if "cdn1.comicknew.pictures" in url or "comickz.co.uk" in url or "comick.live" in url or "cdn.comick" in url:
            return {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://comick.live/",
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            }
        if "meo.comick.pictures" in url or "comick.io" in url:
            return {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://comick.io/",
                "Accept": "image/webp,image/*,*/*;q=0.8",
            }
        return {"User-Agent": "MangaDex-dl GTK prototype"}

    def _fetch_with_retry(self, url: str, max_retries: int = 5) -> bytes:
        last_err: Exception | None = None
        # serializa downloads de imagem para evitar 429 por concorrência
        with self._image_download_lock:
            for attempt in range(max_retries):
                try:
                    req = urllib.request.Request(url, headers=self._headers_for_url(url))
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        if resp.status == 429:
                            retry_after = resp.headers.get("Retry-After")
                            wait = int(retry_after) if retry_after and retry_after.isdigit() else (3 ** attempt)
                            time.sleep(min(wait, 12) + 0.5 * attempt)
                            last_err = OSError(f"HTTP 429 rate-limit")
                            continue
                        data = resp.read()
                        # empty ou muito pequeno é erro (cdn retornou 0 bytes em 429)
                        if len(data) == 0 or (len(data) < 800 and b"<html" not in data[:800].lower()):
                            if attempt < max_retries - 1:
                                time.sleep(1.2 * (attempt + 1))
                                last_err = OSError(f"Resposta vazia/muito pequena: {len(data)} bytes")
                                continue
                            raise OSError(f"Resposta vazia: {len(data)} bytes")
                        if data[:800].lower().find(b"<html") != -1 and len(data) < 30000 and (b"<title>Just a moment" in data or b"429" in data[:500]):
                            # pode ser 429 disfarçado de html
                            if attempt < max_retries - 1:
                                time.sleep(1.5 * (attempt + 1))
                                last_err = OSError("HTML 429")
                                continue
                            raise OSError("Cloudflare/429 HTML")
                    # throttle global para cdn1 (0.80s entre requisições com 2 threads = 2.5 req/s)
                    time.sleep(0.80)
                    return data
                except urllib.error.HTTPError as e:
                    body = b""
                    try:
                        body = e.read()
                    except Exception:
                        pass
                    if e.code == 429:
                        retry_after = e.headers.get("Retry-After") if hasattr(e, "headers") else None
                        wait = int(retry_after) if retry_after and retry_after.isdigit() else (3 ** attempt + 1)
                        time.sleep(min(wait, 12))
                        last_err = e
                        continue
                    if e.code in (403, 503) and b"cloudflare" in body.lower():
                        raise OSError("Cloudflare 403") from e
                    last_err = e
                    if attempt < max_retries - 1:
                        time.sleep(0.8 * (attempt + 1))
                        continue
                    raise
                except OSError as e:
                    last_err = e
                    if "429" in str(e) or "rate-limit" in str(e).lower():
                        time.sleep(2.5 * (attempt + 1))
                    elif attempt < max_retries - 1:
                        time.sleep(0.8 * (attempt + 1))
                    if attempt < max_retries - 1:
                        continue
                    raise
            raise OSError(f"Falha após {max_retries} tentativas: {last_err}") from last_err

    def _cache_reader_page(self, chapter_id: str, index: int, page_url: str) -> Path:
        chapter_dir = READER_CACHE_DIR / chapter_id
        chapter_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(urllib.parse.urlparse(page_url).path).suffix or ".jpg"
        page_path = chapter_dir / f"{index + 1:04d}{suffix}"
        # invalida cache HTML (403/429) - verifica sempre os primeiros bytes
        if page_path.exists():
            try:
                head = page_path.read_bytes()[:1024]
                if b"<html" in head.lower() or b"<!doctype" in head.lower() or b"429" in head or b"Too Many" in head or page_path.stat().st_size == 0:
                    page_path.unlink()
            except OSError:
                pass
        if not page_path.exists() or page_path.stat().st_size == 0:
            data = self._fetch_with_retry(page_url)
            if data[:800].lower().find(b"<html") != -1 and len(data) < 30000:
                raise OSError("Resposta HTML em vez de imagem (403/429)")
            page_path.write_bytes(data)
        return page_path

    def _finish_reader_page(self, chapter_id: str, index: int, page_path: Path) -> bool:
        if chapter_id != self.current_reader_chapter_id:
            return False
        if 0 <= index < len(self.current_reader_page_paths):
            self.current_reader_page_paths[index] = page_path
        if index == self.current_reader_page_index:
            self._show_reader_page()
        self._update_reader_page_counter()
        return False

    def _finish_reader_error(self, chapter_id: str, message: str) -> bool:
        if chapter_id == self.current_reader_chapter_id and self.reader_status_label is not None:
            self.reader_status_label.set_text(message)
            self.reader_status_label.set_visible(True)
        return False

    def _show_reader_page(self) -> None:
        if self.reader_page_picture is None:
            return
        if not self.current_reader_page_paths:
            if self.reader_status_label is not None:
                self.reader_status_label.set_text(self._t("reader_no_pages"))
                self.reader_status_label.set_visible(True)
            return
        self.current_reader_page_index = max(
            0,
            min(self.current_reader_page_index, len(self.current_reader_page_paths) - 1),
        )
        page_path = self.current_reader_page_paths[self.current_reader_page_index]
        if page_path is None:
            self.reader_page_picture.set_paintable(None)
            if self.reader_status_label is not None:
                self.reader_status_label.set_text(self._t("reader_loading_page"))
                self.reader_status_label.set_visible(True)
            self._update_reader_page_counter()
            return
        # debug: log tentativa de carregamento
        try:
            with open("/tmp/mangadex_reader.log", "a") as f:
                f.write(f"show page {self.current_reader_page_index} {page_path} exists={page_path.exists()} size={page_path.stat().st_size if page_path.exists() else 0}\n")
        except Exception:
            pass
        # tenta via Texture primeiro (mais confiável para WebP no GTK4)
        try:
            from gi.repository import Gdk, GdkPixbuf
            texture = Gdk.Texture.new_from_filename(str(page_path))
            self.reader_page_picture.set_paintable(texture)
            with open("/tmp/mangadex_reader.log", "a") as f:
                f.write(f"  texture ok {texture.get_width()}x{texture.get_height()}\n")
            # também testa pixbuf para log
            try:
                pix = GdkPixbuf.Pixbuf.new_from_file(str(page_path))
                with open("/tmp/mangadex_reader.log", "a") as f:
                    f.write(f"  pixbuf ok {pix.get_width()}x{pix.get_height()}\n")
            except Exception as e:
                with open("/tmp/mangadex_reader.log", "a") as f:
                    f.write(f"  pixbuf fail {e}\n")
        except Exception as e:
            with open("/tmp/mangadex_reader.log", "a") as f:
                f.write(f"  texture fail {e}, fallback set_filename\n")
            try:
                self.reader_page_picture.set_filename(str(page_path))
            except Exception as e2:
                with open("/tmp/mangadex_reader.log", "a") as f:
                    f.write(f"  set_filename fail {e2}\n")
        # log paintable após set
        try:
            p = self.reader_page_picture.get_paintable()
            with open("/tmp/mangadex_reader.log", "a") as f:
                f.write(f"  paintable={p} file={self.reader_page_picture.get_file()}\n")
        except Exception as e:
            with open("/tmp/mangadex_reader.log", "a") as f:
                f.write(f"  get_paintable fail {e}\n")
        if self.reader_status_label is not None:
            self.reader_status_label.set_visible(False)
        self._update_reader_page_counter()

    def _update_reader_page_counter(self) -> None:
        if self.reader_page_counter_label is None:
            return
        total = self.current_reader_total_pages
        if total <= 0:
            self.reader_page_counter_label.set_text("00/00")
            self.reader_page_counter_label.set_visible(False)
            return
        self.reader_page_counter_label.set_text(f"{self.current_reader_page_index + 1:02d}/{total:02d}")
        self.reader_page_counter_label.set_visible(True)

    def _on_reader_page_clicked(self, gesture: Gtk.GestureClick, _presses: int, x: float, _y: float) -> None:
        widget = gesture.get_widget()
        width = widget.get_width() if widget is not None else 0
        if width <= 0:
            return
        if x >= width / 2:
            self._reader_next_page()
        else:
            self._reader_previous_page()

    def _reader_next_page(self) -> None:
        if not self.current_reader_page_paths:
            return
        if self.current_reader_page_index < len(self.current_reader_page_paths) - 1:
            self.current_reader_page_index += 1
            self._show_reader_page()
            return

        next_chapter = self._next_reader_chapter()
        if next_chapter is not None:
            self._open_reader_chapter(next_chapter)

    def _reader_previous_page(self) -> None:
        if not self.current_reader_page_paths:
            return
        if self.current_reader_page_index > 0:
            self.current_reader_page_index -= 1
            self._show_reader_page()
            return

        previous_chapter = self._previous_reader_chapter()
        if previous_chapter is not None:
            self._open_reader_chapter(previous_chapter, start_at_end=True)

    def _next_reader_chapter(self) -> ChapterGroup | None:
        if self.current_reader_chapter_id is None:
            return None
        chapters = self._reader_chapter_sequence()
        for index, chapter in enumerate(chapters):
            if chapter.id == self.current_reader_chapter_id and index + 1 < len(chapters):
                return chapters[index + 1]
        return None

    def _previous_reader_chapter(self) -> ChapterGroup | None:
        if self.current_reader_chapter_id is None:
            return None
        chapters = self._reader_chapter_sequence()
        for index, chapter in enumerate(chapters):
            if chapter.id == self.current_reader_chapter_id and index > 0:
                return chapters[index - 1]
        return None

    def _reader_chapter_sequence(self) -> list[ChapterGroup]:
        source = self._filtered_chapters()

        def key(chapter: ChapterGroup) -> tuple[float, str]:
            try:
                number = float(chapter.chapter)
            except (TypeError, ValueError):
                number = float("inf")
            return (number, chapter.id)

        return sorted(source, key=key)

    def _on_reader_back_clicked(self, *_args) -> None:
        self._show_screen("result")

    def _filtered_chapters(self) -> list[ChapterGroup]:
        if self.current_chapter_language is None:
            return self.current_chapters
        return [
            chapter
            for chapter in self.current_chapters
            if self.current_chapter_language in chapter.languages
        ]

    def _available_chapter_languages(self, chapters: list[ChapterGroup] | None = None) -> list[str]:
        source = self.current_chapters if chapters is None else chapters
        languages = {
            language
            for chapter in source
            for language in chapter.languages
            if language
        }
        return sorted(languages, key=lambda language: self._language_label(language))

    def _update_language_button_label(self) -> None:
        if self.result_language_button is None:
            return
        if self.current_chapter_language is None:
            self.result_language_button.set_label(self._t("language"))
            return
        self.result_language_button.set_label(self._language_label(self.current_chapter_language))

    def _on_language_filter_clicked(self, button: Gtk.Button) -> None:
        if self.result_overlay is None:
            return

        self._close_language_dialog()
        languages = self._available_chapter_languages()

        backdrop = Gtk.Overlay()
        backdrop.add_css_class("language-dialog-backdrop")
        backdrop.set_halign(Gtk.Align.FILL)
        backdrop.set_valign(Gtk.Align.FILL)
        backdrop.set_hexpand(True)
        backdrop.set_vexpand(True)

        outside_click = Gtk.GestureClick()
        outside_click.connect("pressed", self._on_language_backdrop_clicked)
        backdrop.add_controller(outside_click)

        grid = Gtk.Grid()
        grid.add_css_class("language-dialog")
        grid.set_column_spacing(6)
        grid.set_row_spacing(6)
        grid.set_halign(Gtk.Align.START)
        grid.set_valign(Gtk.Align.START)
        grid.set_margin_top(274)
        grid.set_margin_start(469)

        if not languages:
            empty = Gtk.Label(label=self._t("language_empty"))
            empty.add_css_class("language-empty-label")
            grid.attach(empty, 0, 0, 4, 1)
        else:
            all_option = Gtk.Button(label=self._t("all"))
            all_option.add_css_class("language-option-button")
            all_option.set_focus_on_click(False)
            all_option.connect("clicked", self._on_language_option_clicked, None)
            grid.attach(all_option, 0, 0, 1, 1)

            for index, language in enumerate(languages, start=1):
                option = Gtk.Button(label=self._language_label(language))
                option.add_css_class("language-option-button")
                option.set_focus_on_click(False)
                option.connect("clicked", self._on_language_option_clicked, language)
                grid.attach(option, index % 4, index // 4, 1, 1)

        panel_click = Gtk.GestureClick()
        panel_click.connect("pressed", lambda *_args: None)
        grid.add_controller(panel_click)

        backdrop.add_overlay(grid)
        self.result_language_dialog = backdrop
        self.result_overlay.add_overlay(backdrop)

    def _on_language_option_clicked(
        self,
        _button: Gtk.Button,
        language: str | None,
    ) -> None:
        self.current_chapter_language = language
        self._update_language_button_label()
        self._render_chapter_list()
        self._close_language_dialog()

    def _on_language_backdrop_clicked(self, gesture: Gtk.GestureClick, *_args) -> None:
        _, x, y = gesture.get_point()
        widget = gesture.get_widget()
        picked = widget.pick(x, y, Gtk.PickFlags.DEFAULT)
        if picked is widget:
            self._close_language_dialog()

    def _close_language_dialog(self) -> None:
        if self.result_overlay is not None and self.result_language_dialog is not None:
            self.result_overlay.remove_overlay(self.result_language_dialog)
        self.result_language_dialog = None

    def _on_folder_clicked(self, *_args) -> None:
        dialog = Gtk.FileChooserNative.new(
            self._t("folder_dialog_title"),
            self,
            Gtk.FileChooserAction.SELECT_FOLDER,
            self._t("folder_dialog_title"),
            self._t("cancel"),
        )
        default_folder = self.current_download_folder or self.config.get("default_download_folder")
        if default_folder and Path(default_folder).exists():
            dialog.set_current_folder(Gio.File.new_for_path(default_folder))
        dialog.connect("response", self._on_folder_dialog_response)
        dialog.show()

    def _on_folder_dialog_response(
        self,
        dialog: Gtk.FileChooserNative,
        response: int,
    ) -> None:
        if response != Gtk.ResponseType.ACCEPT:
            dialog.destroy()
            return

        file = dialog.get_file()
        dialog.destroy()
        if file is None:
            return

        path = file.get_path()
        if not path:
            return

        self.current_download_folder = path
        self._update_folder_button_label()
        self._show_folder_default_dialog(path)

    def _show_folder_default_dialog(self, path: str) -> None:
        if self.result_overlay is None:
            return

        self._close_folder_default_dialog()

        backdrop = Gtk.Overlay()
        backdrop.add_css_class("folder-dialog-backdrop")
        backdrop.set_halign(Gtk.Align.FILL)
        backdrop.set_valign(Gtk.Align.FILL)
        backdrop.set_hexpand(True)
        backdrop.set_vexpand(True)

        outside_click = Gtk.GestureClick()
        outside_click.connect("pressed", self._on_folder_backdrop_clicked)
        backdrop.add_controller(outside_click)

        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        panel.add_css_class("folder-default-dialog")
        panel.set_halign(Gtk.Align.CENTER)
        panel.set_valign(Gtk.Align.CENTER)

        title = Gtk.Label(label=self._t("folder_dialog_title"))
        title.add_css_class("folder-dialog-title")
        title.set_halign(Gtk.Align.CENTER)

        path_label = Gtk.Label(label=path)
        path_label.add_css_class("folder-dialog-path")
        path_label.set_wrap(True)
        path_label.set_max_width_chars(54)
        path_label.set_halign(Gtk.Align.CENTER)
        path_label.set_xalign(0.5)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        actions.set_halign(Gtk.Align.CENTER)

        use_button = Gtk.Button(label=self._t("use_now"))
        use_button.add_css_class("folder-dialog-button")
        use_button.set_focus_on_click(False)
        use_button.connect("clicked", self._on_use_folder_once_clicked)

        default_button = Gtk.Button(label=self._t("set_default"))
        default_button.add_css_class("folder-dialog-button")
        default_button.set_focus_on_click(False)
        default_button.connect("clicked", self._on_set_default_folder_clicked, path)

        actions.append(use_button)
        actions.append(default_button)

        panel_click = Gtk.GestureClick()
        panel_click.connect("pressed", lambda *_args: None)
        panel.add_controller(panel_click)

        panel.append(title)
        panel.append(path_label)
        panel.append(actions)

        backdrop.add_overlay(panel)
        self.result_folder_dialog = backdrop
        self.result_overlay.add_overlay(backdrop)

    def _on_use_folder_once_clicked(self, *_args) -> None:
        self._close_folder_default_dialog()

    def _on_set_default_folder_clicked(self, _button: Gtk.Button, path: str) -> None:
        self.config["default_download_folder"] = path
        self._save_config()
        self.current_download_folder = path
        self._update_folder_button_label()
        self._close_folder_default_dialog()

    def _on_folder_backdrop_clicked(self, gesture: Gtk.GestureClick, *_args) -> None:
        _, x, y = gesture.get_point()
        widget = gesture.get_widget()
        picked = widget.pick(x, y, Gtk.PickFlags.DEFAULT)
        if picked is widget:
            self._close_folder_default_dialog()

    def _close_folder_default_dialog(self) -> None:
        if self.result_overlay is not None and self.result_folder_dialog is not None:
            self.result_overlay.remove_overlay(self.result_folder_dialog)
        self.result_folder_dialog = None

    def _update_folder_button_label(self) -> None:
        if self.result_folder_button is None:
            return
        self.result_folder_button.set_label(self._t("folder"))

    def _on_download_clicked(self, *_args) -> None:
        if self.result_overlay is None:
            return
        if self.download_active:
            self._show_download_progress_dialog()
            return
        self._close_download_dialog()

        backdrop = Gtk.Overlay()
        backdrop.add_css_class("download-dialog-backdrop")
        backdrop.set_halign(Gtk.Align.FILL)
        backdrop.set_valign(Gtk.Align.FILL)
        backdrop.set_hexpand(True)
        backdrop.set_vexpand(True)

        outside_click = Gtk.GestureClick()
        outside_click.connect("pressed", self._on_download_backdrop_clicked)
        backdrop.add_controller(outside_click)

        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        panel.add_css_class("download-dialog")
        panel.set_halign(Gtk.Align.CENTER)
        panel.set_valign(Gtk.Align.CENTER)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title = Gtk.Label(label=self._t("download_dialog_title"))
        title.add_css_class("download-dialog-title")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)

        self.download_toggle_button = Gtk.Button(label=self._t("unselect_all"))
        self.download_toggle_button.add_css_class("download-toggle-button")
        self.download_toggle_button.set_focus_on_click(False)
        self.download_toggle_button.connect("clicked", self._on_toggle_download_selection_clicked)

        self.download_language_button = Gtk.Button(label=self._download_language_label())
        self.download_language_button.add_css_class("download-language-button")
        self.download_language_button.set_focus_on_click(False)
        self.download_language_button.connect("clicked", self._on_download_language_clicked)

        header.append(title)
        header.append(self.download_toggle_button)
        header.append(self.download_language_button)

        scroller = Gtk.ScrolledWindow()
        scroller.add_css_class("download-chapter-scroller")
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)

        self.download_chapter_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.download_chapter_list_box.add_css_class("download-chapter-list")
        scroller.set_child(self.download_chapter_list_box)

        self.download_status_label = Gtk.Label()
        self.download_status_label.add_css_class("download-status")
        self.download_status_label.set_halign(Gtk.Align.START)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        actions.set_halign(Gtk.Align.END)

        close_button = Gtk.Button(label=self._t("cancel"))
        close_button.add_css_class("folder-dialog-button")
        close_button.set_focus_on_click(False)
        close_button.connect("clicked", lambda *_args: self._close_download_dialog())

        start_button = Gtk.Button(label=self._t("download_start"))
        start_button.add_css_class("folder-dialog-button")
        start_button.set_focus_on_click(False)
        start_button.connect("clicked", self._on_start_download_clicked)

        actions.append(close_button)
        actions.append(start_button)

        panel_click = Gtk.GestureClick()
        panel_click.connect("pressed", lambda *_args: None)
        panel.add_controller(panel_click)

        panel.append(header)
        panel.append(scroller)
        panel.append(self.download_status_label)
        panel.append(actions)

        backdrop.add_overlay(panel)
        self.result_download_dialog = backdrop
        self.result_overlay.add_overlay(backdrop)
        self._render_download_chapter_list()

    def _download_language_label(self) -> str:
        if self.current_download_language is None:
            return self._t("language")
        return self._language_label(self.current_download_language)

    def _download_chapters_for_language(self) -> list[ChapterGroup]:
        if self.current_download_language is None:
            return self.current_chapters
        return [
            chapter
            for chapter in self.current_chapters
            if self.current_download_language in chapter.languages
        ]

    def _render_download_chapter_list(self) -> None:
        if self.download_chapter_list_box is None:
            return

        while child := self.download_chapter_list_box.get_first_child():
            self.download_chapter_list_box.remove(child)

        self.download_chapter_checks = []
        chapters = self._download_chapters_for_language()
        if not chapters:
            self.download_chapter_list_box.append(self._build_result_row(self._t("no_download_chapters")))
            self._update_download_toggle_button()
            return

        for chapter in chapters:
            check = Gtk.CheckButton(label=self._chapter_label(chapter))
            check.add_css_class("download-chapter-check")
            check.set_active(True)
            check.connect("toggled", lambda *_args: self._update_download_toggle_button())
            self.download_chapter_list_box.append(check)
            self.download_chapter_checks.append((check, chapter))
        self._update_download_toggle_button()

    def _on_toggle_download_selection_clicked(self, *_args) -> None:
        if not self.download_chapter_checks:
            return

        should_select = not all(check.get_active() for check, _chapter in self.download_chapter_checks)
        for check, _chapter in self.download_chapter_checks:
            check.set_active(should_select)
        self._update_download_toggle_button()

    def _update_download_toggle_button(self) -> None:
        if self.download_toggle_button is None:
            return

        has_chapters = bool(self.download_chapter_checks)
        all_selected = has_chapters and all(check.get_active() for check, _chapter in self.download_chapter_checks)
        self.download_toggle_button.set_sensitive(has_chapters)
        self.download_toggle_button.set_label(self._t("unselect_all") if all_selected else self._t("select_all"))

    def _on_download_language_clicked(self, *_args) -> None:
        if self.download_chapter_list_box is None:
            return

        if self.download_chapter_list_box.get_first_child() is not None:
            while child := self.download_chapter_list_box.get_first_child():
                self.download_chapter_list_box.remove(child)

        self.download_chapter_checks = []
        self._update_download_toggle_button()

        grid = Gtk.Grid()
        grid.add_css_class("download-language-grid")
        grid.set_column_spacing(6)
        grid.set_row_spacing(6)

        languages = self._available_chapter_languages()
        all_option = Gtk.Button(label=self._t("all"))
        all_option.add_css_class("language-option-button")
        all_option.set_focus_on_click(False)
        all_option.connect("clicked", self._on_download_language_option_clicked, None)
        grid.attach(all_option, 0, 0, 1, 1)

        for index, language in enumerate(languages, start=1):
            option = Gtk.Button(label=self._language_label(language))
            option.add_css_class("language-option-button")
            option.set_focus_on_click(False)
            option.connect("clicked", self._on_download_language_option_clicked, language)
            grid.attach(option, index % 4, index // 4, 1, 1)

        self.download_chapter_list_box.append(grid)

    def _on_download_language_option_clicked(
        self,
        _button: Gtk.Button,
        language: str | None,
    ) -> None:
        self.current_download_language = language
        if self.download_language_button is not None:
            self.download_language_button.set_label(self._download_language_label())
        self._render_download_chapter_list()

    def _on_start_download_clicked(self, *_args) -> None:
        if self.download_active:
            self._close_download_dialog()
            self._show_download_progress_dialog()
            return

        selected = self._sort_download_queue([
            chapter for check, chapter in self.download_chapter_checks if check.get_active()
        ])
        if not selected:
            if self.download_status_label is not None:
                self.download_status_label.set_text(self._t("select_one_chapter"))
            return

        base_folder = self.current_download_folder or self.config.get("default_download_folder")
        if not base_folder:
            base_folder = str(Path.home() / "Downloads")

        manga_folder = Path(base_folder) / self._safe_folder_name(self.current_result_manga_title or "MangaDex")
        try:
            manga_folder.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            if self.download_status_label is not None:
                self.download_status_label.set_text(self._t("folder_create_error", error=error))
            return

        if self.download_status_label is not None:
            self.download_status_label.set_text(self._download_count_text(len(selected), "starting"))

        self._close_download_dialog()
        self._start_download_progress(selected)
        threading.Thread(target=self._download_selected_chapters, args=(selected, manga_folder), daemon=True).start()

    def _start_download_progress(self, chapters: list[ChapterGroup]) -> None:
        self.download_active = True
        self.download_total_chapters = len(chapters)
        self.download_finished_chapters = 0
        self.download_cancel_event = threading.Event()
        self._ensure_download_progress_button()
        self._update_download_progress(
            self._download_count_text(self.download_total_chapters, "selected"),
            self._t("download_waiting_pages"),
        )

    def _download_count_text(self, count: int, mode: str) -> str:
        key = "download_starting" if mode == "starting" else "download_selected"
        return self._t(key, count=count)

    def _download_progress_text(self, current: int, total: int) -> str:
        return self._t("download_progress", current=current, total=total)

    def _ensure_download_progress_button(self) -> None:
        parent = self._download_overlay_parent()
        if parent is None:
            return
        if self.download_progress_button is not None:
            return

        button = Gtk.Button()
        button.add_css_class("download-progress-button")
        button.set_focus_on_click(False)
        button.set_valign(Gtk.Align.START)
        button.connect("clicked", lambda *_args: self._show_download_progress_dialog())

        spinner = Gtk.Spinner()
        spinner.add_css_class("download-progress-spinner")
        spinner.start()
        button.set_child(spinner)

        self.download_progress_button = button
        self._position_download_progress_button()
        parent.add_overlay(button)

    def _position_download_progress_button(self) -> None:
        button = self.download_progress_button
        if button is None:
            return

        button.set_valign(Gtk.Align.START)
        button.set_margin_top(18)
        if self._download_progress_on_result_screen():
            button.set_halign(Gtk.Align.END)
            button.set_margin_start(0)
            if self._download_progress_on_reader_screen():
                button.set_margin_end(184)
                return
            button.set_margin_end(28)
            return

        button.set_halign(Gtk.Align.START)
        button.set_margin_start(28)
        button.set_margin_end(0)

    def _download_progress_on_result_screen(self) -> bool:
        return self.stack is not None and self.stack.get_visible_child_name() in {"result", "reader"}

    def _download_progress_on_reader_screen(self) -> bool:
        return self.stack is not None and self.stack.get_visible_child_name() == "reader"

    def _show_download_progress_dialog(self) -> None:
        parent = self._download_overlay_parent()
        if parent is None:
            return

        self._close_download_progress_dialog()

        backdrop = Gtk.Overlay()
        backdrop.add_css_class("download-status-backdrop")
        backdrop.set_halign(Gtk.Align.FILL)
        backdrop.set_valign(Gtk.Align.FILL)
        backdrop.set_hexpand(True)
        backdrop.set_vexpand(True)

        outside_click = Gtk.GestureClick()
        outside_click.connect("pressed", self._on_download_status_backdrop_clicked)
        backdrop.add_controller(outside_click)

        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        panel.add_css_class("download-status-panel")
        panel.set_halign(Gtk.Align.END if self._download_progress_on_result_screen() else Gtk.Align.START)
        panel.set_valign(Gtk.Align.START)
        panel.set_margin_top(72)
        if self._download_progress_on_result_screen():
            panel.set_margin_end(28)
        else:
            panel.set_margin_start(28)

        title = Gtk.Label(label=self._t("download_status_title"))
        title.add_css_class("download-dialog-title")
        title.set_halign(Gtk.Align.START)

        self.download_progress_chapters_label = Gtk.Label()
        self.download_progress_chapters_label.add_css_class("download-status-line")
        self.download_progress_chapters_label.set_halign(Gtk.Align.START)
        self.download_progress_chapters_label.set_xalign(0.0)
        self.download_progress_chapters_label.set_wrap(True)

        self.download_progress_pages_label = Gtk.Label()
        self.download_progress_pages_label.add_css_class("download-status-line")
        self.download_progress_pages_label.set_halign(Gtk.Align.START)
        self.download_progress_pages_label.set_xalign(0.0)
        self.download_progress_pages_label.set_wrap(True)

        cancel_button = Gtk.Button(label=self._t("cancel"))
        cancel_button.add_css_class("download-cancel-button")
        cancel_button.set_focus_on_click(False)
        cancel_button.set_halign(Gtk.Align.END)
        if self.download_active:
            cancel_button.connect("clicked", self._cancel_current_download)
        else:
            cancel_button.set_label(self._t("close"))
            cancel_button.connect("clicked", lambda *_args: self._close_download_progress_dialog())
        self.download_cancel_button = cancel_button

        panel.append(title)
        panel.append(self.download_progress_chapters_label)
        panel.append(self.download_progress_pages_label)
        panel.append(cancel_button)

        backdrop.add_overlay(panel)
        self.download_progress_dialog = backdrop
        parent.add_overlay(backdrop)
        self._update_download_progress_labels()

    def _on_download_status_backdrop_clicked(self, gesture: Gtk.GestureClick, *_args) -> None:
        _, x, y = gesture.get_point()
        widget = gesture.get_widget()
        picked = widget.pick(x, y, Gtk.PickFlags.DEFAULT)
        if picked is widget:
            self._close_download_progress_dialog()

    def _close_download_progress_dialog(self) -> None:
        parent = self._download_overlay_parent()
        if parent is not None and self.download_progress_dialog is not None:
            parent.remove_overlay(self.download_progress_dialog)
        self.download_progress_dialog = None
        self.download_progress_chapters_label = None
        self.download_progress_pages_label = None
        self.download_cancel_button = None

    def _cancel_current_download(self, *_args) -> None:
        if self.download_cancel_event is not None:
            self.download_cancel_event.set()
        self.download_active = False
        self._stop_download_process()
        self._update_download_progress(self._t("download_cancelled"), self._t("download_process_stopped"))
        self._set_download_status_finished()

    def _stop_download_process(self) -> None:
        process = self.download_process
        if process is None or process.poll() is not None:
            return

        try:
            os.killpg(process.pid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            process.terminate()

        def force_kill() -> bool:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    process.kill()
            return False

        GLib.timeout_add(1200, force_kill)

    def _set_download_status_finished(self) -> None:
        if self.download_cancel_button is not None:
            self.download_cancel_button.set_label(self._t("close"))
            try:
                self.download_cancel_button.disconnect_by_func(self._cancel_current_download)
            except TypeError:
                pass
            self.download_cancel_button.connect("clicked", lambda *_args: self._close_download_progress_dialog())
        GLib.timeout_add(1800, self._remove_download_progress_button)

    def _update_download_progress(self, chapters_status: str, pages_status: str) -> bool:
        self._last_download_chapters_status = chapters_status
        self._last_download_pages_status = pages_status
        self._update_download_progress_labels()
        return False

    def _update_download_progress_labels(self) -> None:
        chapters_status = getattr(self, "_last_download_chapters_status", self._t("no_active_download"))
        pages_status = getattr(self, "_last_download_pages_status", "")
        if self.download_progress_chapters_label is not None:
            self.download_progress_chapters_label.set_text(chapters_status)
        if self.download_progress_pages_label is not None:
            self.download_progress_pages_label.set_text(pages_status)

    def _remove_download_progress_button(self) -> bool:
        parent = self._download_overlay_parent()
        if parent is not None and self.download_progress_button is not None:
            parent.remove_overlay(self.download_progress_button)
        self.download_progress_button = None
        return False

    def _download_overlay_parent(self) -> Gtk.Overlay | None:
        return self.app_overlay or self.result_overlay

    def _download_selected_chapters(self, chapters: list[ChapterGroup], manga_folder: Path) -> None:
        # Comick: download nativo via API (não depende do mangadex-downloader)
        # usa current_result_source (mangá aberto), não current_source (switch)
        src = getattr(self, "current_result_source", self.current_source)
        if src == "comick":
            self._download_comick_chapters(chapters, manga_folder)
            return

        command = self._find_mangadex_downloader()
        if command is None:
            GLib.idle_add(self._finish_chapter_download, self._t("download_missing_cli"), False)
            return

        for index, chapter in enumerate(chapters, start=1):
            if self.download_cancel_event is not None and self.download_cancel_event.is_set():
                GLib.idle_add(self._finish_chapter_download, self._t("download_cancelled"), False)
                return

            url = f"https://mangadex.org/chapter/{chapter.id}"
            GLib.idle_add(
                self._update_download_progress,
                self._download_progress_text(index, len(chapters)),
                self._t("download_prepare_pages", chapter=self._chapter_label(chapter)),
            )
            process = subprocess.Popen(
                self._build_download_command(command, url, manga_folder),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
            self.download_process = process
            last_output = ""
            output_lines: list[str] = []
            if process.stdout is not None:
                for line in process.stdout:
                    last_output = line.strip() or last_output
                    if last_output:
                        output_lines.append(last_output)
                        output_lines = output_lines[-12:]
                    if self.download_cancel_event is not None and self.download_cancel_event.is_set():
                        self._stop_download_process()
                        break
                    pages_status = self._parse_download_page_status(last_output, chapter)
                    GLib.idle_add(
                        self._update_download_progress,
                        self._download_progress_text(index, len(chapters)),
                        pages_status,
                    )

            return_code = process.wait()
            self.download_process = None
            if self.download_cancel_event is not None and self.download_cancel_event.is_set():
                GLib.idle_add(self._finish_chapter_download, self._t("download_cancelled"), False)
                return
            if return_code != 0 and not self._download_output_finished_chapter(output_lines):
                message = "\n".join(output_lines).strip() or last_output or self._t("download_failed_url", url=url)
                GLib.idle_add(self._finish_chapter_download, message, False)
                return

            self.download_finished_chapters = index
            GLib.idle_add(
                self._update_download_progress,
                self._download_progress_text(index, len(chapters)),
                self._t("download_chapter_done", chapter=self._chapter_label(chapter)),
            )

        GLib.idle_add(self._finish_chapter_download, self._t("download_finished_in", folder=manga_folder), True)

    def _download_comick_chapters(self, chapters: list[ChapterGroup], manga_folder: Path) -> None:
        for index, chapter in enumerate(chapters, start=1):
            if self.download_cancel_event is not None and self.download_cancel_event.is_set():
                GLib.idle_add(self._finish_chapter_download, self._t("download_cancelled"), False)
                return
            GLib.idle_add(
                self._update_download_progress,
                self._download_progress_text(index, len(chapters)),
                self._t("download_prepare_pages", chapter=self._chapter_label(chapter)),
            )
            try:
                pages = self.comick_client.get_chapter_pages(chapter.id)
            except ComickApiError as error:
                GLib.idle_add(self._finish_chapter_download, str(error), False)
                return
            chapter_folder = manga_folder / self._safe_folder_name(f"Ch {chapter.chapter} - {chapter.title or chapter.id}")
            chapter_folder.mkdir(parents=True, exist_ok=True)
            # download páginas em paralelo (2 threads) para acelerar sem tomar 429
            total_pages = len(pages.pages)
            def _dl_page(args):
                p_idx, p_url = args
                ext = Path(urllib.parse.urlparse(p_url).path).suffix or ".jpg"
                dest = chapter_folder / f"{p_idx:03d}{ext}"
                if dest.exists():
                    # verifica se não é HTML vazio
                    try:
                        if dest.stat().st_size > 0 and b"<html" not in dest.read_bytes()[:800].lower():
                            return p_idx, None
                        else:
                            dest.unlink()
                    except OSError:
                        pass
                # retry mais agressivo para 429
                for attempt in range(3):
                    try:
                        data = self._fetch_with_retry(p_url, max_retries=5)
                        if len(data) < 500:
                            raise OSError(f"Resposta pequena {len(data)}")
                        dest.write_bytes(data)
                        return p_idx, None
                    except OSError as e:
                        if "429" in str(e) or "rate-limit" in str(e).lower():
                            time.sleep(4 * (attempt + 1))
                            continue
                        raise
                raise OSError(f"Falha página {p_idx} após 3 tentativas")

            # mostra progresso e baixa em paralelo
            with ThreadPoolExecutor(max_workers=self._download_threads) as ex:
                futures = {ex.submit(_dl_page, (i+1, url)): i+1 for i, url in enumerate(pages.pages)}
                completed = 0
                failed = 0
                for fut in as_completed(futures):
                    if self.download_cancel_event is not None and self.download_cancel_event.is_set():
                        ex.shutdown(wait=False, cancel_futures=True)
                        GLib.idle_add(self._finish_chapter_download, self._t("download_cancelled"), False)
                        return
                    p_idx = futures[fut]
                    try:
                        fut.result()
                    except OSError as error:
                        failed += 1
                        # não aborta em 429, apenas loga e continua (pula página)
                        if "429" in str(error) or "rate-limit" in str(error).lower():
                            GLib.idle_add(
                                self._update_download_progress,
                                self._download_progress_text(index, len(chapters)),
                                f"Página {p_idx} com 429, pulando (continuando)...",
                            )
                            # espera um pouco antes de continuar para não floodar
                            time.sleep(2)
                        else:
                            GLib.idle_add(self._finish_chapter_download, str(error), False)
                            return
                    completed += 1
                    GLib.idle_add(
                        self._update_download_progress,
                        self._download_progress_text(index, len(chapters)),
                        self._t("page_progress_total", chapter=self._chapter_label(chapter), current=completed, total=total_pages),
                    )
                if failed > 0:
                    GLib.idle_add(
                        self._update_download_progress,
                        self._download_progress_text(index, len(chapters)),
                        f"{failed} página(s) com 429, tente novamente",
                    )
            self.download_finished_chapters = index
            GLib.idle_add(
                self._update_download_progress,
                self._download_progress_text(index, len(chapters)),
                self._t("download_chapter_done", chapter=self._chapter_label(chapter)),
            )
        GLib.idle_add(self._finish_chapter_download, self._t("download_finished_in", folder=manga_folder), True)

    def _sort_download_queue(self, chapters: list[ChapterGroup]) -> list[ChapterGroup]:
        def key(chapter: ChapterGroup) -> tuple[float, str]:
            try:
                chapter_number = float(chapter.chapter)
            except (TypeError, ValueError):
                chapter_number = float("inf")
            return (chapter_number, chapter.id)

        return sorted(chapters, key=key)

    def _download_output_finished_chapter(self, output_lines: list[str]) -> bool:
        pat = re.compile(r"finished\s+download\s+chapter", re.IGNORECASE)
        return any(pat.search(line) for line in output_lines)

    def _find_mangadex_downloader(self) -> str | list[str] | None:
        for name in ("mangadex-dl", "mangadex-downloader"):
            p = shutil.which(name)
            if p:
                return p
            # pipx e pip --user instalam em ~/.local/bin
            for cand in [
                Path.home() / ".local" / "bin" / name,
                Path("/usr/local/bin") / name,
                Path("/opt/pipx/bin") / name,
            ]:
                if cand.exists() and os.access(cand, os.X_OK):
                    return str(cand)
            # tenta via python -m
            try:
                __import__("mangadex_downloader")
                return [sys.executable, "-m", "mangadex_downloader"]
            except ImportError:
                pass
        return None

    def _build_download_command(self, command: str | list[str], url: str, manga_folder: Path) -> list[str]:
        base = command if isinstance(command, list) else [command]
        return [
            *base,
            "--type",
            "chapter",
            "--path",
            str(manga_folder),
            "--replace",
            "--progress-bar-layout",
            "none",
            url,
        ]

    def _parse_download_page_status(self, output: str, chapter: ChapterGroup) -> str:
        compact = output.strip()
        # Fração tipo "3/12" ou "Downloading 3/12"
        match = re.search(r"(\d+)\s*/\s*(\d+)", compact)
        if match:
            return self._t(
                "page_progress_total",
                chapter=self._chapter_label(chapter),
                current=match.group(1),
                total=match.group(2),
            )
        # "página 5" / "page 5" / "downloading page 5"
        page_match = re.search(r"(?:p[aá]g(?:ina)?|page)\D+(\d+)", compact, re.IGNORECASE)
        if page_match:
            return self._t("page_progress_single", chapter=self._chapter_label(chapter), current=page_match.group(1))
        # Detecta erro no output
        if re.search(r"(error|failed|exception|traceback)", compact, re.IGNORECASE):
            return compact[:160]
        if compact:
            return compact[:160]
        return self._t("page_downloading", chapter=self._chapter_label(chapter))

    def _finish_chapter_download(self, message: str, completed: bool) -> bool:
        self.download_active = False
        self.download_process = None
        self.download_cancel_event = None
        self._update_download_progress(
            message,
            self._t("download_done") if completed else self._t("download_stopped"),
        )
        self._set_download_status_finished()
        if completed:
            GLib.timeout_add(4500, self._remove_download_progress_button)
        return False

    def _safe_folder_name(self, value: str) -> str:
        cleaned = "".join(c if c not in '<>:"/\\|?*' else "_" for c in value)
        cleaned = cleaned.strip().strip(".")
        cleaned = cleaned or "MangaDex"
        if len(cleaned) > 255:
            cleaned = cleaned[:255].rstrip(" .")
        return cleaned

    def _on_download_backdrop_clicked(self, gesture: Gtk.GestureClick, *_args) -> None:
        _, x, y = gesture.get_point()
        widget = gesture.get_widget()
        picked = widget.pick(x, y, Gtk.PickFlags.DEFAULT)
        if picked is widget:
            self._close_download_dialog()

    def _close_download_dialog(self) -> None:
        if self.result_overlay is not None and self.result_download_dialog is not None:
            self.result_overlay.remove_overlay(self.result_download_dialog)
        self.result_download_dialog = None
        self.download_chapter_list_box = None
        self.download_status_label = None
        self.download_toggle_button = None
        self.download_language_button = None
        self.download_chapter_checks = []

    def _chapter_label(self, chapter: ChapterGroup) -> str:
        title = f"{self._t('chapter')} {chapter.chapter}"
        if chapter.title:
            title = f"{title}: {chapter.title}"
        return title

    def _language_label(self, language: str) -> str:
        labels = {
            "pt-br": "PT-BR",
            "en": "EN",
            "es-la": "ES-LA",
            "es": "ES",
            "ja": "JA",
        }
        return labels.get(language, language.upper())

    def _load_cover_into_result(self, cover_url: str) -> None:
        threading.Thread(target=self._download_cover, args=(cover_url,), daemon=True).start()

    def _download_cover(self, cover_url: str) -> None:
        try:
            COVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            extension = Path(urllib.parse.urlparse(cover_url).path).suffix or ".jpg"
            file_name = hashlib.sha256(cover_url.encode("utf-8")).hexdigest()[:16] + extension
            cover_path = COVER_CACHE_DIR / file_name
            # invalida cache ruim (HTML de 403)
            if cover_path.exists():
                try:
                    head = cover_path.read_bytes()[:200]
                    if b"<html" in head.lower() or b"<!doctype" in head.lower():
                        cover_path.unlink()
                except OSError:
                    pass
            if not cover_path.exists():
                try:
                    data = self._fetch_with_retry(cover_url, max_retries=3)
                except OSError:
                    return
                if data[:800].lower().find(b"<html") != -1:
                    return
                cover_path.write_bytes(data)
        except OSError:
            return

        GLib.idle_add(self._finish_cover_load, str(cover_path))

    def _finish_cover_load(self, cover_path: str) -> bool:
        # usa Texture para WebP (mais confiável que set_filename no GTK4)
        for pic in (self.result_cover_picture, self.result_banner_picture):
            if pic is None:
                continue
            try:
                from gi.repository import Gdk
                texture = Gdk.Texture.new_from_filename(cover_path)
                pic.set_paintable(texture)
            except Exception:
                try:
                    pic.set_filename(cover_path)
                except Exception:
                    pass
        return False

    def _on_settings_clicked(self, *_args) -> None:
        if self.wallpaper_dialog is not None:
            self._close_wallpaper_dialog()
        if self.settings_menu is not None:
            self._close_settings_menu()
            return

        self.settings_menu = self._build_settings_menu()
        self.home_overlay.add_overlay(self.settings_menu)
        self._animate_settings_button(80)
        if self.settings_revealer is not None:
            self.settings_revealer.set_reveal_child(True)

    def _on_config_clicked(self, *_args) -> None:
        if self.settings_menu is not None:
            self._close_settings_menu(remove_now=True)
        self._show_screen("config")

    def _on_account_or_config_clicked(self, *_args) -> None:
        if self.settings_menu is not None:
            self._close_settings_menu(remove_now=True)
        if self._has_saved_login() and self.stack is not None:
            self._apply_cached_account_view()
            self._ensure_account_details_loaded()
            self._show_account_screen()
            return
        self._show_screen("config")

    def _on_back_home_clicked(self, *_args) -> None:
        self.url_entry.set_text("")
        self._show_screen("home")

    def _on_result_back_clicked(self, *_args) -> None:
        if self.stack is None:
            return
        if self.result_back_target == "account":
            self._show_screen("account")
            selected = self._selected_mdlist()
            if selected is not None:
                self._show_mdlist_manga(selected)
            return
        self._show_screen("home")

    def _on_config_save_clicked(self, *_args) -> None:
        fields = (
            self.username_entry,
            self.password_entry,
            self.client_id_entry,
            self.client_secret_entry,
        )
        if any(entry is None or not entry.get_text().strip() for entry in fields):
            if self.config_status_label is not None:
                self.config_status_label.set_text("Preencha usuario, senha, Client ID e Client Secret.")
            return

        username = self.username_entry.get_text().strip()
        password = self.password_entry.get_text()
        client_id = self.client_id_entry.get_text().strip()
        client_secret = self.client_secret_entry.get_text()

        self.config["mangadex_username"] = username
        self.config["mangadex_password"] = password
        self.config["mangadex_client_id"] = client_id
        self.config["mangadex_client_secret"] = client_secret
        self._save_config()
        if self.config_status_label is not None:
            self.config_status_label.set_text("Fazendo login...")

        threading.Thread(
            target=self._login_mangadex,
            args=(username, password, client_id, client_secret),
            daemon=True,
        ).start()

    def _auto_login_if_configured(self) -> None:
        if not self._has_saved_login():
            return
        username = self.config.get("mangadex_username", "").strip()
        password = self.config.get("mangadex_password", "")
        client_id = self.config.get("mangadex_client_id", "").strip()
        client_secret = self.config.get("mangadex_client_secret", "")

        self.status_label.set_text("Entrando no MangaDex...")
        self.auto_login_in_progress = True
        threading.Thread(
            target=self._auto_login_mangadex,
            args=(username, password, client_id, client_secret),
            daemon=True,
        ).start()

    def _has_saved_login(self) -> bool:
        return all(
            (
                self.config.get("mangadex_username", "").strip(),
                self.config.get("mangadex_password", ""),
                self.config.get("mangadex_client_id", "").strip(),
                self.config.get("mangadex_client_secret", ""),
            )
        )

    def _on_logout_clicked(self, *_args) -> None:
        for key in (
            "mangadex_username",
            "mangadex_password",
            "mangadex_client_id",
            "mangadex_client_secret",
        ):
            self.config.pop(key, None)
        self._save_config()
        self.mangadex_client.access_token = None
        self.account_profile = None
        self.account_mdlists = None
        self.account_selected_mdlist_id = None
        self.session_avatar_path = None
        self.session_banner_path = None
        self._save_account_cache()
        self._clear_account_view()
        self._update_settings_avatar_icon()
        self._update_settings_account_button()
        self._show_screen("config")

    def _clear_account_view(self) -> None:
        if self.account_username_label is not None:
            self.account_username_label.set_text(self._t("not_logged"))
        if self.account_user_id_label is not None:
            self.account_user_id_label.set_text(self._t("login_required"))
        if self.account_avatar_picture is not None:
            self.account_avatar_picture.set_paintable(None)
        if self.account_avatar_fallback is not None:
            self.account_avatar_fallback.set_visible(True)
        if self.account_banner_picture is not None:
            self.account_banner_picture.set_paintable(None)
        if self.account_mdlists_box is not None:
            while child := self.account_mdlists_box.get_first_child():
                self.account_mdlists_box.remove(child)
            self.account_mdlists_box.append(self._build_account_status_row(self._t("login_required")))
        self._close_mdlist_manga_panel()

    def _login_mangadex(
        self,
        username: str,
        password: str,
        client_id: str,
        client_secret: str,
    ) -> None:
        try:
            self.mangadex_client.login(username, password, client_id, client_secret)
            profile = self.mangadex_client.get_me()
            mdlists = self.mangadex_client.get_user_mdlists(profile.id)
        except MangaDexApiError as error:
            GLib.idle_add(self._finish_login_error, str(error))
            return
        GLib.idle_add(self._finish_login_success, profile, mdlists)

    def _auto_login_mangadex(
        self,
        username: str,
        password: str,
        client_id: str,
        client_secret: str,
    ) -> None:
        try:
            self.mangadex_client.login(username, password, client_id, client_secret)
            profile = self.mangadex_client.get_me()
        except MangaDexApiError as error:
            GLib.idle_add(self._finish_login_error, str(error))
            return
        GLib.idle_add(self._finish_auto_login_success, profile)

    def _finish_auto_login_success(self, profile: UserProfile) -> bool:
        self.account_profile = profile
        self._update_account_profile(profile, refresh_media=False)
        self._refresh_missing_account_media(profile)
        self._save_account_cache()
        self._clear_home_status()
        self.auto_login_in_progress = False
        # pré-carrega MDLists em fundo para abrir instantâneo
        if not self.account_details_loading:
            self.account_details_loading = True
            threading.Thread(target=self._load_account_mdlists, args=(profile.id,), daemon=True).start()
        return False

    def _finish_login_success(self, profile: UserProfile, mdlists: list[UserMdList]) -> bool:
        if self.config_status_label is not None:
            self.config_status_label.set_text(self._t("login_done"))
        self.account_profile = profile
        self.account_mdlists = mdlists
        self._save_account_cache()
        self._update_settings_account_button()
        self._show_account(profile, mdlists)
        self.auto_login_in_progress = False
        return False

    def _finish_login_error(self, message: str) -> bool:
        self.auto_login_in_progress = False
        if self.config_status_label is not None:
            self.config_status_label.set_text(message)
        return False

    def _show_account(self, profile: UserProfile, mdlists: list[UserMdList]) -> None:
        self._update_account_profile(profile)
        self._update_account_mdlists(mdlists)
        if not self.auto_login_in_progress:
            self._show_screen("account")

    def _update_account_profile(self, profile: UserProfile, refresh_media: bool = True) -> None:
        if self.account_username_label is not None:
            self.account_username_label.set_text(profile.username)
        if self.account_user_id_label is not None:
            self.account_user_id_label.set_text(f"ID: {profile.id}")
        if profile.avatar_url and refresh_media:
            self._load_profile_media(profile.avatar_url, "avatar")
        if profile.banner_url and refresh_media:
            self._load_profile_media(profile.banner_url, "banner")

    def _update_account_mdlists(self, mdlists: list[UserMdList]) -> None:
        if self.account_mdlists_box is not None:
            while child := self.account_mdlists_box.get_first_child():
                self.account_mdlists_box.remove(child)

            if not mdlists:
                self.account_mdlists_box.append(
                    self._build_account_status_row(self._t("no_mdlists"))
                )
            for mdlist in mdlists:
                detail = self._mdlist_detail_text(mdlist)
                self.account_mdlists_box.append(
                    self._build_account_mdlist_row(mdlist, detail)
                )

            if self.account_manga_panel is not None and self.account_manga_panel.get_visible():
                selected = self._selected_mdlist()
                if selected is not None:
                    self._show_mdlist_manga(selected)

    def _show_account_screen(self) -> None:
        self._show_screen("account")

    def _apply_cached_account_view(self) -> None:
        if self.account_profile is not None:
            self._update_account_profile(self.account_profile, refresh_media=False)
        if self.account_mdlists is not None:
            self._update_account_mdlists(self.account_mdlists)
        self._apply_cached_account_media()

    def _refresh_missing_account_media(self, profile: UserProfile) -> None:
        avatar_path = self.session_avatar_path
        if profile.avatar_url and not (avatar_path and Path(avatar_path).exists()):
            self._load_profile_media(profile.avatar_url, "avatar")

        banner_path = self.session_banner_path
        if profile.banner_url and not (banner_path and Path(banner_path).exists()):
            self._load_profile_media(profile.banner_url, "banner")

    def _on_refresh_account_profile_clicked(self, *_args) -> None:
        if self.account_profile_refreshing:
            return
        self.account_profile_refreshing = True
        threading.Thread(target=self._refresh_account_profile, daemon=True).start()

    def _refresh_account_profile(self) -> None:
        try:
            profile = self.mangadex_client.get_me()
        except MangaDexApiError as error:
            GLib.idle_add(self._finish_account_profile_refresh_error, str(error))
            return
        GLib.idle_add(self._finish_account_profile_refresh, profile)

    def _finish_account_profile_refresh(self, profile: UserProfile) -> bool:
        self.account_profile_refreshing = False
        self.account_profile = profile
        self._update_account_profile(profile, refresh_media=False)
        if profile.avatar_url:
            self._load_profile_media(profile.avatar_url, "avatar", force=True)
        if profile.banner_url:
            self._load_profile_media(profile.banner_url, "banner", force=True)
        self._save_account_cache()
        return False

    def _finish_account_profile_refresh_error(self, message: str) -> bool:
        self.account_profile_refreshing = False
        if self.account_user_id_label is not None:
            self.account_user_id_label.set_text(self._t("profile_refresh_error", message=message))
        return False

    def _ensure_account_details_loaded(self) -> None:
        if self.account_mdlists is not None or self.account_details_loading:
            return
        if self.account_profile is None:
            if self.account_user_id_label is not None:
                self.account_user_id_label.set_text(self._t("login_loading"))
            return
        self.account_details_loading = True
        if self.account_mdlists_box is not None:
            while child := self.account_mdlists_box.get_first_child():
                self.account_mdlists_box.remove(child)
            self.account_mdlists_box.append(self._build_account_status_row(self._t("loading_mdlists")))
        threading.Thread(target=self._load_account_mdlists, args=(self.account_profile.id,), daemon=True).start()

    def _load_account_mdlists(self, user_id: str) -> None:
        try:
            mdlists = self.mangadex_client.get_my_mdlists_with_manga()
        except MangaDexApiError as error:
            GLib.idle_add(self._finish_account_mdlists_error, str(error))
            return
        GLib.idle_add(self._finish_account_mdlists_load, mdlists)

    def _finish_account_mdlists_load(self, mdlists: list[UserMdList]) -> bool:
        self.account_mdlists = mdlists
        self.account_details_loading = False
        self._update_account_mdlists(mdlists)
        self._save_account_cache()
        return False

    def _finish_account_mdlists_error(self, message: str) -> bool:
        self.account_details_loading = False
        if self.account_mdlists_box is not None:
            while child := self.account_mdlists_box.get_first_child():
                self.account_mdlists_box.remove(child)
            self.account_mdlists_box.append(self._build_account_status_row(message))
        return False

    def _build_account_status_row(self, text: str) -> Gtk.Widget:
        label = Gtk.Label(label=text)
        label.add_css_class("account-mdlist-row")
        label.set_halign(Gtk.Align.FILL)
        label.set_xalign(0.0)
        return label

    def _mdlist_detail_text(self, mdlist: UserMdList) -> str:
        return f"{mdlist.source} - {mdlist.visibility} - {self._t('manga_count', count=len(mdlist.manga))}"

    def _build_account_mdlist_row(self, mdlist: UserMdList, visibility: str) -> Gtk.Widget:
        button = Gtk.Button()
        button.add_css_class("account-mdlist-button")
        button.set_focus_on_click(False)
        button.connect("clicked", self._on_mdlist_clicked, mdlist.id)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.add_css_class("account-mdlist-row")
        title = Gtk.Label(label=mdlist.name)
        title.add_css_class("account-mdlist-title")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)
        title.set_xalign(0.0)

        badge = Gtk.Label(label=visibility)
        badge.add_css_class("account-mdlist-badge")
        badge.set_halign(Gtk.Align.END)

        row.append(title)
        row.append(badge)
        button.set_child(row)
        return button

    def _on_mdlist_clicked(self, _button: Gtk.Button, mdlist_id: str) -> None:
        self.account_selected_mdlist_id = mdlist_id
        selected = self._selected_mdlist()
        if selected is not None:
            self._show_mdlist_manga(selected)

    def _on_mdlist_back_clicked(self, _button: Gtk.Button) -> None:
        self._close_mdlist_manga_panel()

    def _close_mdlist_manga_panel(self) -> None:
        self.account_selected_mdlist_id = None
        if self.account_manga_panel is not None:
            self.account_manga_panel.set_visible(False)
        if self.account_lists_header is not None:
            self.account_lists_header.set_visible(True)
        if self.account_mdlists_scroller is not None:
            self.account_mdlists_scroller.set_visible(True)
            adjustment = self.account_mdlists_scroller.get_vadjustment()
            if adjustment is not None:
                adjustment.set_value(adjustment.get_lower())

    def _on_account_key_pressed(self, _controller, keyval, _keycode, _state) -> bool:
        if keyval == Gdk.KEY_Escape and self.account_manga_panel is not None:
            if self.account_manga_panel.get_visible():
                self._close_mdlist_manga_panel()
                return True
        return False

    def _on_window_key_pressed(self, _controller, keyval, _keycode, _state) -> bool:
        if keyval != Gdk.KEY_Escape:
            return False
        if self.stack is None:
            return False
        visible = self.stack.get_visible_child_name()
        if visible == "account":
            if self.account_manga_panel is not None and self.account_manga_panel.get_visible():
                self._close_mdlist_manga_panel()
                return True
            return False
        if visible == "loading" and self.loading_back_button is not None and self.loading_back_button.get_visible():
            self._show_screen("home")
            return True
        return False

    def _selected_mdlist(self) -> UserMdList | None:
        if not self.account_mdlists:
            return None
        if self.account_selected_mdlist_id is None:
            return None
        for mdlist in self.account_mdlists:
            if mdlist.id == self.account_selected_mdlist_id:
                return mdlist
        return self.account_mdlists[0]

    def _show_mdlist_manga(self, mdlist: UserMdList) -> None:
        if self.account_manga_grid is None:
            return
        if self.account_manga_title_label is not None:
            self.account_manga_title_label.set_text(self._t("list_manga_named", name=mdlist.name))
        if self.account_lists_header is not None:
            self.account_lists_header.set_visible(False)
        if self.account_mdlists_scroller is not None:
            self.account_mdlists_scroller.set_visible(False)
        if self.account_manga_panel is not None:
            self.account_manga_panel.set_visible(True)
        while child := self.account_manga_grid.get_first_child():
            self.account_manga_grid.remove(child)
        for manga in mdlist.manga:
            self.account_manga_grid.append(self._build_manga_card(manga))

    def _build_manga_card(self, manga: MangaDetails) -> Gtk.Widget:
        button = Gtk.Button()
        button.add_css_class("account-manga-card-button")
        button.set_focus_on_click(False)
        button.connect("clicked", self._on_account_manga_clicked, manga.id)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("account-manga-card")
        card.set_size_request(82, 168)

        picture = Gtk.Picture()
        picture.add_css_class("account-manga-cover")
        picture.set_content_fit(Gtk.ContentFit.COVER)
        picture.set_can_shrink(True)
        picture.set_size_request(70, 116)

        title = Gtk.Label(label=manga.title or manga.id)
        title.add_css_class("account-manga-title")
        title.set_wrap(True)
        title.set_max_width_chars(11)
        title.set_justify(Gtk.Justification.CENTER)
        title.set_xalign(0.5)

        card.append(picture)
        card.append(title)
        if manga.cover_url:
            self._load_manga_cover(manga.cover_url, picture)
        button.set_child(card)
        return button

    def _on_account_manga_clicked(self, _button: Gtk.Button, manga_id: str) -> None:
        # MDList é sempre MangaDex, força source
        self.current_source = "mangadex"
        self.config["source"] = "mangadex"
        self._save_config()
        if self.source_switch:
            self.source_switch.set_active(False)
            self.source_switch.set_label("MangaDex")
            self.url_entry.set_placeholder_text("https://mangadex.org/title/...")
        self.result_back_target = "account"
        self._show_manga_loading(self._t("selected_manga_loading"))
        threading.Thread(target=self._load_manga_details, args=(manga_id,), daemon=True).start()

    def _load_manga_details(self, manga_id: str) -> None:
        try:
            manga = self.mangadex_client.get_manga(manga_id)
        except MangaDexApiError as error:
            GLib.idle_add(self._finish_mangadex_error, str(error))
            return
        GLib.idle_add(self._finish_mangadex_load, manga)

    def _load_manga_cover(self, cover_url: str, picture: Gtk.Picture) -> None:
        cached = self._cached_cover_path(cover_url)
        if cached.exists():
            try:
                head = cached.read_bytes()[:200]
                if b"<html" in head.lower() or b"<!doctype" in head.lower():
                    cached.unlink()
                else:
                    picture.set_filename(str(cached))
                    return
            except OSError:
                pass
        threading.Thread(target=self._download_manga_cover, args=(cover_url, picture), daemon=True).start()

    def _download_manga_cover(self, cover_url: str, picture: Gtk.Picture) -> None:
        cover_path = self._cached_cover_path(cover_url)
        try:
            COVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            # limpa cache HTML inválido
            if cover_path.exists():
                try:
                    head = cover_path.read_bytes()[:200]
                    if b"<html" in head.lower() or b"<!doctype" in head.lower():
                        cover_path.unlink()
                except OSError:
                    pass
            if cover_path.exists():
                GLib.idle_add(self._finish_manga_cover_load, str(cover_path), picture)
                return
            try:
                data = self._fetch_with_retry(cover_url, max_retries=3)
            except OSError:
                return
            if data[:800].lower().find(b"<html") != -1:
                return
            cover_path.write_bytes(data)
        except OSError:
            return
        GLib.idle_add(self._finish_manga_cover_load, str(cover_path), picture)

    def _finish_manga_cover_load(self, cover_path: str, picture: Gtk.Picture) -> bool:
        try:
            from gi.repository import Gdk
            texture = Gdk.Texture.new_from_filename(cover_path)
            picture.set_paintable(texture)
        except Exception:
            try:
                picture.set_filename(cover_path)
            except Exception:
                pass
        return False

    def _cached_cover_path(self, cover_url: str) -> Path:
        extension = Path(urllib.parse.urlparse(cover_url).path).suffix or ".jpg"
        file_name = hashlib.sha256(cover_url.encode("utf-8")).hexdigest()[:16] + extension
        return COVER_CACHE_DIR / file_name

    def _on_refresh_mdlists_clicked(self, *_args) -> None:
        selected = self._selected_mdlist()
        if selected is None:
            self.account_mdlists = None
            self._ensure_account_details_loaded()
            return

        self.account_details_loading = True
        if self.account_manga_grid is not None:
            while child := self.account_manga_grid.get_first_child():
                self.account_manga_grid.remove(child)
            self.account_manga_grid.append(self._build_manga_status_card(self._t("looking_for_new_manga")))
        threading.Thread(target=self._refresh_selected_mdlist, args=(selected.id,), daemon=True).start()

    def _refresh_selected_mdlist(self, mdlist_id: str) -> None:
        try:
            details = self.mangadex_client.get_mdlist(mdlist_id)
        except MangaDexApiError as error:
            GLib.idle_add(self._finish_account_mdlists_error, str(error))
            return
        GLib.idle_add(self._finish_selected_mdlist_refresh, details)

    def _finish_selected_mdlist_refresh(self, details: MdListDetails) -> bool:
        if self.account_mdlists is None:
            self.account_mdlists = []
        updated: list[UserMdList] = []
        for mdlist in self.account_mdlists:
            if mdlist.id == details.id:
                updated.append(
                    UserMdList(
                        id=mdlist.id,
                        name=mdlist.name,
                        visibility=mdlist.visibility,
                        manga=details.manga,
                        source=mdlist.source,
                    )
                )
            else:
                updated.append(mdlist)
        self.account_mdlists = updated
        self.account_details_loading = False
        self._update_account_mdlists(updated)
        selected = self._selected_mdlist()
        if selected is not None:
            self._show_mdlist_manga(selected)
        self._save_account_cache()
        return False

    def _build_manga_status_card(self, text: str) -> Gtk.Widget:
        label = Gtk.Label(label=text)
        label.add_css_class("account-manga-status")
        label.set_size_request(220, 80)
        return label

    def _load_profile_media(self, url: str, media_type: str, force: bool = False) -> None:
        threading.Thread(
            target=self._download_profile_media,
            args=(url, media_type, force),
            daemon=True,
        ).start()

    def _download_profile_media(self, url: str, media_type: str, force: bool = False) -> None:
        try:
            PROFILE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            extension = Path(urllib.parse.urlparse(url).path).suffix or ".jpg"
            file_name = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16] + extension
            media_path = PROFILE_CACHE_DIR / file_name
            if force or not media_path.exists():
                try:
                    data = self._fetch_with_retry(url, max_retries=3)
                except OSError:
                    return
                media_path.write_bytes(data)
        except OSError:
            return

        GLib.idle_add(self._finish_profile_media_load, str(media_path), media_type)

    def _set_account_avatar_file(self, media_path: str) -> None:
        if self.account_avatar_picture is None:
            return

        texture = self._avatar_texture(media_path, ACCOUNT_AVATAR_TEXTURE_SIZE)
        if texture is None:
            return

        self.account_avatar_picture.set_paintable(texture)

    def _update_settings_avatar_icon(self) -> None:
        if self.settings_icon_picture is None:
            return

        self.settings_icon_picture.set_filename(None)
        avatar_path = self.session_avatar_path
        if avatar_path and Path(avatar_path).exists():
            texture = self._avatar_texture(avatar_path, SETTINGS_AVATAR_SIZE * 3)
            if texture is not None:
                self.settings_icon_picture.set_paintable(texture)
                return

        self.settings_icon_picture.set_paintable(self._settings_gear_texture())

    def _settings_gear_texture(self) -> Gdk.Texture | None:
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(ASSET_DIR / "settings-gear.svg"),
                SETTINGS_AVATAR_SIZE * 3,
                SETTINGS_AVATAR_SIZE * 3,
                True,
            )
        except GLib.Error:
            return None
        return Gdk.Texture.new_for_pixbuf(pixbuf)

    def _avatar_texture(self, media_path: str, target_size: int) -> Gdk.Texture | None:
        try:
            source = GdkPixbuf.Pixbuf.new_from_file(media_path)
        except GLib.Error:
            return None

        source_width = source.get_width()
        source_height = source.get_height()
        if source_width <= 0 or source_height <= 0:
            return None

        crop_size = min(source_width, source_height)
        crop_x = max(0, (source_width - crop_size) // 2)
        crop_y = max(0, (source_height - crop_size) // 2)
        cropped = GdkPixbuf.Pixbuf.new_subpixbuf(
            source,
            crop_x,
            crop_y,
            crop_size,
            crop_size,
        )
        pixbuf = cropped.scale_simple(
            target_size,
            target_size,
            GdkPixbuf.InterpType.HYPER,
        )
        if pixbuf is None:
            return None

        return Gdk.Texture.new_for_pixbuf(pixbuf)

    def _set_account_banner_file(self, media_path: str) -> None:
        if self.account_banner_picture is None:
            return

        try:
            source = GdkPixbuf.Pixbuf.new_from_file(media_path)
        except GLib.Error:
            return

        source_width = source.get_width()
        source_height = source.get_height()
        if source_width <= 0 or source_height <= 0:
            return

        target_width = ACCOUNT_BANNER_WIDTH
        target_height = ACCOUNT_BANNER_HEIGHT
        scale = max(target_width / source_width, target_height / source_height)
        scaled_width = max(1, int(source_width * scale))
        scaled_height = max(1, int(source_height * scale))

        scaled = source.scale_simple(
            scaled_width,
            scaled_height,
            GdkPixbuf.InterpType.BILINEAR,
        )
        if scaled is None:
            return

        crop_x = max(0, (scaled_width - target_width) // 2)
        crop_y = max(0, (scaled_height - target_height) // 2)
        cropped = GdkPixbuf.Pixbuf.new_subpixbuf(
            scaled,
            crop_x,
            crop_y,
            min(target_width, scaled_width - crop_x),
            min(target_height, scaled_height - crop_y),
        )
        self.account_banner_picture.set_paintable(Gdk.Texture.new_for_pixbuf(cropped))

    def _finish_profile_media_load(self, media_path: str, media_type: str) -> bool:
        if media_type == "avatar" and self.account_avatar_picture is not None:
            self._set_account_avatar_file(media_path)
            if self.account_avatar_fallback is not None:
                self.account_avatar_fallback.set_visible(False)
            self.session_avatar_path = media_path
            self._update_settings_avatar_icon()
        if media_type == "banner" and self.account_banner_picture is not None:
            self._set_account_banner_file(media_path)
            self.session_banner_path = media_path
        return False

    def _load_account_cache(self) -> None:
        if not ACCOUNT_CACHE_PATH.exists():
            return
        try:
            data = json.loads(ACCOUNT_CACHE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        profile_data = data.get("profile")
        if isinstance(profile_data, dict):
            self.account_profile = UserProfile(
                id=profile_data.get("id", ""),
                username=profile_data.get("username", "MangaDex user"),
                avatar_url=profile_data.get("avatar_url"),
                banner_url=profile_data.get("banner_url"),
            )

        mdlists_data = data.get("mdlists")
        if isinstance(mdlists_data, list):
            self.account_mdlists = [
                UserMdList(
                    id=item.get("id", ""),
                    name=item.get("name", "MDList"),
                    visibility=item.get("visibility", ""),
                    source=item.get("source", "mine"),
                    manga=[
                        MangaDetails(
                            id=manga.get("id", ""),
                            title=manga.get("title", ""),
                            cover_url=manga.get("cover_url"),
                            description="",
                        )
                        for manga in item.get("manga", [])
                        if isinstance(manga, dict)
                    ],
                )
                for item in mdlists_data
                if isinstance(item, dict)
            ]

    def _apply_cached_account_media(self) -> None:
        avatar_path = self.session_avatar_path
        if avatar_path and Path(avatar_path).exists() and self.account_avatar_picture is not None:
            self._set_account_avatar_file(avatar_path)
            if self.account_avatar_fallback is not None:
                self.account_avatar_fallback.set_visible(False)
        self._update_settings_avatar_icon()

        banner_path = self.session_banner_path
        if banner_path and Path(banner_path).exists() and self.account_banner_picture is not None:
            self._set_account_banner_file(banner_path)

    def _save_account_cache(self) -> None:
        profile = self.account_profile
        data = {
            "profile": None
            if profile is None
            else {
                "id": profile.id,
                "username": profile.username,
                "avatar_url": profile.avatar_url,
                "banner_url": profile.banner_url,
            },
            "mdlists": [
                {
                    "id": mdlist.id,
                    "name": mdlist.name,
                    "visibility": mdlist.visibility,
                    "source": mdlist.source,
                    "manga": [
                        {
                            "id": manga.id,
                            "title": manga.title,
                            "cover_url": manga.cover_url,
                        }
                        for manga in mdlist.manga
                    ],
                }
                for mdlist in (self.account_mdlists or [])
            ],
        }
        try:
            ACCOUNT_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            ACCOUNT_CACHE_PATH.write_text(
                json.dumps(data, indent=2, ensure_ascii=True),
                encoding="utf-8",
            )
            ACCOUNT_CACHE_PATH.chmod(0o600)
        except OSError:
            pass

    def _on_language_clicked(self, *_args) -> None:
        self._set_ui_language("en" if self.ui_language == "pt-BR" else "pt-BR")
        self._set_home_status(self._t("language_status"), clear_after_ms=3000)

    def _on_wallpaper_clicked(self, *_args) -> None:
        if self.settings_menu is not None:
            self._close_settings_menu(remove_now=True)
        self.wallpaper_dialog = self._build_wallpaper_dialog()
        self.home_overlay.add_overlay(self.wallpaper_dialog)
        self.wallpaper_dialog.grab_focus()

    def _close_settings_menu(self, remove_now: bool = False) -> None:
        menu = self.settings_menu
        if menu is None:
            return

        self._animate_settings_button(28)
        if self.settings_revealer is not None:
            self.settings_revealer.set_reveal_child(False)

        if remove_now:
            self.home_overlay.remove_overlay(menu)
            self.settings_menu = None
            self.settings_revealer = None
            return

        def remove_menu() -> bool:
            if self.settings_menu is menu:
                self.home_overlay.remove_overlay(menu)
                self.settings_menu = None
                self.settings_revealer = None
            return False

        GLib.timeout_add(190, remove_menu)

    def _animate_settings_button(self, target_margin_end: int) -> None:
        if self.settings_button is None:
            return

        if self.settings_animation_id is not None:
            GLib.source_remove(self.settings_animation_id)
            self.settings_animation_id = None

        start_margin = self.settings_button.get_margin_end()
        start_time = time.monotonic()
        duration = 0.18

        def tick() -> bool:
            if self.settings_button is None:
                self.settings_animation_id = None
                return False

            progress = min((time.monotonic() - start_time) / duration, 1.0)
            eased = 1 - (1 - progress) * (1 - progress)
            margin = round(start_margin + (target_margin_end - start_margin) * eased)
            self.settings_button.set_margin_end(margin)

            if progress >= 1.0:
                self.settings_button.set_margin_end(target_margin_end)
                self.settings_animation_id = None
                return False
            return True

        self.settings_animation_id = GLib.timeout_add(12, tick)

    def _on_wallpaper_backdrop_clicked(self, gesture: Gtk.GestureClick, *_args) -> None:
        _, x, y = gesture.get_point()
        widget = gesture.get_widget()
        picked = widget.pick(x, y, Gtk.PickFlags.DEFAULT)
        if picked is widget:
            self._close_wallpaper_dialog()

    def _on_wallpaper_key_pressed(self, _controller, keyval, _keycode, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self._close_wallpaper_dialog()
            return True
        return False

    def _on_save_wallpaper_clicked(self, *_args) -> None:
        if self.wallpaper_entry is None:
            return
        url = self.wallpaper_entry.get_text().strip()
        self.wallpaper_entry.remove_css_class("invalid")
        if not url.startswith(("http://", "https://")):
            self.wallpaper_entry.add_css_class("invalid")
            self._set_home_status("Use um link http ou https para o wallpaper.", clear_after_ms=3000)
            return

        self._set_home_status(self._t("wallpaper_downloading"))
        threading.Thread(target=self._download_wallpaper, args=(url,), daemon=True).start()

    def _on_reset_wallpaper_clicked(self, *_args) -> None:
        self.config.pop("wallpaper_url", None)
        self.config.pop("wallpaper_path", None)
        self._save_config()
        self._set_wallpaper(FALLBACK_WALLPAPER)
        self._set_home_status(self._t("wallpaper_reset"), clear_after_ms=3000)
        self._close_wallpaper_dialog()

    def _close_wallpaper_dialog(self) -> None:
        if self.wallpaper_dialog is not None:
            self.home_overlay.remove_overlay(self.wallpaper_dialog)
            self.wallpaper_dialog = None
            self.wallpaper_entry = None

    def _restore_custom_wallpaper(self) -> None:
        url = self.config.get("wallpaper_url")
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            threading.Thread(target=self._download_wallpaper, args=(url,), daemon=True).start()

    def _download_wallpaper(self, url: str) -> None:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "MangaDex-dl GTK"})
            with urllib.request.urlopen(request, timeout=20) as response:
                content_type = response.headers.get_content_type()
                data = response.read()
        except (OSError, urllib.error.URLError) as error:
            GLib.idle_add(self._finish_wallpaper_error, self._t("wallpaper_download_error", error=error))
            return

        extension = self._extension_for_url(url, content_type)
        if extension is None:
            GLib.idle_add(self._finish_wallpaper_error, "Formato de imagem nao suportado.")
            return

        CUSTOM_WALLPAPER_DIR.mkdir(parents=True, exist_ok=True)
        file_name = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16] + extension
        wallpaper_path = CUSTOM_WALLPAPER_DIR / file_name
        wallpaper_path.write_bytes(data)
        GLib.idle_add(self._finish_wallpaper_success, url, str(wallpaper_path))

    def _finish_wallpaper_success(self, url: str, wallpaper_path: str) -> bool:
        self.config["wallpaper_url"] = url
        self.config.pop("wallpaper_path", None)
        self._save_config()
        self._set_wallpaper(Path(wallpaper_path))
        if self.wallpaper_dialog is not None:
            self._set_home_status(self._t("wallpaper_saved"), clear_after_ms=3000)
        self._close_wallpaper_dialog()
        return False

    def _finish_wallpaper_error(self, message: str) -> bool:
        if self.wallpaper_entry is not None:
            self.wallpaper_entry.add_css_class("invalid")
        self._set_home_status(message, clear_after_ms=3000)
        return False

    def _set_home_status(self, message: str, clear_after_ms: int | None = None) -> None:
        if self.status_clear_id is not None:
            GLib.source_remove(self.status_clear_id)
            self.status_clear_id = None

        self.status_label.set_text(message)
        self.status_label.set_visible(bool(message))
        if clear_after_ms is None:
            return

        def clear_status() -> bool:
            self.status_label.set_text("")
            self.status_label.set_visible(False)
            self.status_clear_id = None
            return False

        self.status_clear_id = GLib.timeout_add(clear_after_ms, clear_status)

    def _clear_home_status(self) -> None:
        if self.status_clear_id is not None:
            GLib.source_remove(self.status_clear_id)
            self.status_clear_id = None
        self.status_label.set_text("")
        self.status_label.set_visible(False)

    def _set_wallpaper(self, path: Path) -> None:
        if self.background_picture is None:
            return

        self._stop_gif_animation()
        self.current_wallpaper_path = path
        if path.suffix.lower() == ".gif":
            self._start_gif_wallpaper(path)
            return

        self.background_picture.set_paintable(None)
        self.background_picture.set_filename(str(path))

    def _start_gif_wallpaper(self, path: Path) -> None:
        if self.background_picture is None:
            return

        try:
            animation = GdkPixbuf.PixbufAnimation.new_from_file(str(path))
        except GLib.Error as error:
            self.status_label.set_text(f"GIF invalido, usando wallpaper padrao: {error.message}")
            self.background_picture.set_filename(str(FALLBACK_WALLPAPER))
            return

        if animation.is_static_image():
            texture = Gdk.Texture.new_for_pixbuf(animation.get_static_image())
            self.background_picture.set_paintable(texture)
            return

        self.gif_animation_iter = animation.get_iter(None)
        self._show_current_gif_frame()
        self._queue_next_gif_frame()

    def _show_current_gif_frame(self) -> None:
        if self.background_picture is None or self.gif_animation_iter is None:
            return

        pixbuf = self.gif_animation_iter.get_pixbuf()
        texture = Gdk.Texture.new_for_pixbuf(pixbuf)
        self.background_picture.set_paintable(texture)

    def _queue_next_gif_frame(self) -> None:
        if self.gif_animation_iter is None:
            return

        delay = self.gif_animation_iter.get_delay_time()
        if delay < 0:
            delay = 100
        delay = max(delay, 20)

        def tick() -> bool:
            if self.gif_animation_iter is None:
                self.gif_animation_id = None
                return False

            self.gif_animation_iter.advance(None)
            self._show_current_gif_frame()
            self.gif_animation_id = None
            self._queue_next_gif_frame()
            return False

        self.gif_animation_id = GLib.timeout_add(delay, tick)

    def _stop_gif_animation(self) -> None:
        if self.gif_animation_id is not None:
            GLib.source_remove(self.gif_animation_id)
            self.gif_animation_id = None
        self.gif_animation_iter = None

    def _current_wallpaper_path(self) -> Path:
        url = self.config.get("wallpaper_url")
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            ext = self._extension_for_url(url, "")
            if ext is None:
                ext = Path(urllib.parse.urlparse(url).path).suffix or ".jpg"
            file_name = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16] + ext
            cached = CUSTOM_WALLPAPER_DIR / file_name
            if cached.exists():
                return cached
        return FALLBACK_WALLPAPER

    def _load_config(self) -> dict[str, str]:
        path = CONFIG_PATH if CONFIG_PATH.exists() else LEGACY_CONFIG_PATH
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _prepare_volatile_cache(self) -> None:
        # Limpeza por TTL (7 dias) ao invés de apagar tudo no startup/exit
        self._clear_expired_cache()
        # Não registrar atexit que apaga tudo; cache volátil persiste entre sessões
        changed = False
        for key in ("cached_avatar_path", "cached_banner_path", "wallpaper_path"):
            if key in self.config:
                self.config.pop(key, None)
                changed = True
        if changed:
            self._save_config()

    def _clear_expired_cache(self) -> None:
        now = time.time()
        ttl = 7 * 24 * 3600
        for path in (PROFILE_CACHE_DIR, READER_CACHE_DIR, CUSTOM_WALLPAPER_DIR):
            if not path.exists():
                continue
            for item in path.rglob("*"):
                try:
                    if item.is_file() and (now - item.stat().st_mtime) > ttl:
                        item.unlink()
                except OSError:
                    pass

    def _clear_volatile_cache(self) -> None:
        # Mantido para compatibilidade/manual - faz limpeza total
        for path in (PROFILE_CACHE_DIR, READER_CACHE_DIR, CUSTOM_WALLPAPER_DIR):
            try:
                if path.exists():
                    shutil.rmtree(path)
            except OSError:
                pass

    def _save_config(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(self.config, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        try:
            CONFIG_PATH.chmod(0o600)
        except OSError:
            pass

    def _extension_for_url(self, url: str, content_type: str) -> str | None:
        extension = IMAGE_EXTENSIONS.get(content_type)
        if extension is not None:
            return extension

        path = urllib.parse.urlparse(url).path.lower()
        for candidate in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]:
            if path.endswith(candidate):
                return candidate
        return None


class MangaDexApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID)

    def do_activate(self) -> None:
        window = self.props.active_window
        if window is None:
            window = MangaDexWindow(self)
        window.present()


def main() -> int:
    app = MangaDexApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
