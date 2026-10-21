"""Service-port lookup for views; concrete implementations are supplied at startup."""
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class DesktopServices:
    """Explicit desktop dependencies. Implementations are composed in war3_app."""
    hotkeys: tuple
    hotkey_manager: Callable[..., Any]
    logger_factory: Callable[..., Any]
    artifact_settings: Callable[..., Any]
    SaveExtractionError: type[Exception]
    extract_text: Callable[..., Any]
    validate_prefix: Callable[..., Any]
    BatchEditModel: Callable[..., Any]
    BatchEditService: Callable[..., Any]
    prepare_extension_definitions: Callable[..., Any]
    default_save_roots: Callable[..., Any]
    documents_directory: Callable[..., Any]
    export_codes: Callable[..., Any]
    log_extraction_failure: Callable[..., Any]
    read_code_file: Callable[..., Any]
    read_live_codes: Callable[..., Any]
    scan_code_directory: Callable[..., Any]
    display_rows: Callable[..., Any]
    export_archive_result: Callable[..., Any]
    find_archive_files: Callable[..., Any]
    read_archive_file: Callable[..., Any]
    read_current_heroes: Callable[..., Any]


def get_ui_services(widget, services=None) -> DesktopServices:
    if services is not None:
        return services
    current = widget
    while current is not None:
        supplied = getattr(current, 'application_services', None)
        if supplied is not None:
            return supplied
        current = getattr(current, 'master', None)
    raise RuntimeError('Application service ports were not supplied to this view')
