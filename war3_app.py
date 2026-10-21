"""Composition root: connect the desktop view to the application and backend."""
from war3_ui_services import DesktopServices
import sys


def desktop_services():
    from war3_backend import ELEPHANT_HOTKEY_SPECS, GlobalHotkeyManager, Win10ReadLogger
    from war3_artifact_plan import ArtifactPlanSettings
    from war3_save_codes import SaveExtractionError, extract_text, validate_prefix
    from war3_services import save_extraction, archive_fields
    from war3_services.batch_edit import BatchEditModel, BatchEditService
    from war3_services.extension_definitions import prepare_extension_definitions
    services = dict(hotkeys=ELEPHANT_HOTKEY_SPECS, hotkey_manager=GlobalHotkeyManager,
                    logger_factory=Win10ReadLogger, artifact_settings=ArtifactPlanSettings,
                    SaveExtractionError=SaveExtractionError,extract_text=extract_text,validate_prefix=validate_prefix,
                    BatchEditModel=BatchEditModel,BatchEditService=BatchEditService,
                    prepare_extension_definitions=prepare_extension_definitions)
    for module,names in ((save_extraction,('default_save_roots','documents_directory','export_codes',
            'log_extraction_failure','read_code_file','read_live_codes','scan_code_directory')),
            (archive_fields,('display_rows','export_archive_result','find_archive_files','read_archive_file','read_current_heroes'))):
        services.update({name:getattr(module,name) for name in names})
    return DesktopServices(**services)


def run_gui(initial_pid=None, initial_hotkeys_enabled=False):
    from war3_application import TrainerApplication
    from war3_gui import run_gui as build_view
    return build_view(initial_pid, initial_hotkeys_enabled,
                      application_factory=TrainerApplication, services=desktop_services())


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) == 2 and arguments[0] == '--runtime-self-test':
        from war3_runtime_check import run
        return run(arguments[1])
    from war3_cli import main as run_cli_entry
    return run_cli_entry(arguments, launch_gui=run_gui)
