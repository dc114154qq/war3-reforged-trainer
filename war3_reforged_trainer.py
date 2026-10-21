"""Executable entry and compatibility import for existing scripts."""
from __future__ import annotations
import sys

if __name__ == "__main__":
    from war3_app import main
    raise SystemExit(main())
else:
    # Keep historic imports and monkeypatches bound to the real backend module.
    # Production backend modules import war3_backend directly and stay headless.
    import war3_backend as _backend
    from war3_app import main, run_gui
    from war3_cli import build_arg_parser, run_cli
    from war3_ui_i18n import detect_ui_language, translate_ui_text

    def apply_ui_theme(root: object, style: object, dark: bool) -> dict[str, str]:
        from war3_gui import apply_ui_theme as apply_theme
        return apply_theme(root, style, dark)

    _backend.main = main
    _backend.run_gui = run_gui
    _backend.build_arg_parser = build_arg_parser
    _backend.run_cli = run_cli
    _backend.apply_ui_theme = apply_ui_theme
    _backend.detect_ui_language = detect_ui_language
    _backend.translate_ui_text = translate_ui_text
    sys.modules[__name__] = _backend
