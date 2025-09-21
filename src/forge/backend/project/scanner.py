from pathlib import Path


def detect_python_project_layout(workspace_path: str) -> dict:
    """
    Analyzes a workspace and generates a comprehensive, in-memory LSP settings
    payload for BasedPyright. This configuration is designed for a "high signal,
    low noise" development experience.
    """
    print(f"[Scanner] Analyzing workspace for LSP settings: {workspace_path}")
    workspace = Path(workspace_path)

    analysis_settings = {
        "typeCheckingMode": "basic",
        "diagnosticMode": "openFilesOnly",
        "useLibraryCodeForTypes": True,
        "diagnosticSeverityOverrides": {
            "reportMissingImports": "error",
            "reportUndefinedVariable": "error",
            "reportUnboundVariable": "error",
            "reportInvalidStringEscapeSequence": "error",
            "reportCallInDefaultInitializer": "error",
            "reportUnusedImport": "warning",
            "reportUnusedVariable": "warning",
            "reportNotAccessed": "warning",
            "reportDuplicateImport": "warning",
            "reportConstantRedefinition": "warning",
            "reportUnreachable": "warning",
            "reportShadowedImport": "warning",
            "reportShadowedClass": "warning",
            "reportShadowedFunction": "warning",
            "reportRedundantCast": "warning",
            "reportAttributeAccessOnNone": "hint",
            "reportOptionalMemberAccess": "hint",
            "reportUnnecessaryComparison": "hint",
            "reportAssertAlwaysTrue": "hint",
            "reportUnusedExpression": "hint",
            "reportUnknownVariableType": "hint",
            "reportUnknownParameterType": "hint",
            "reportUnknownArgumentType": "hint",
            "reportUnknownLambdaType": "hint",
            "reportUnknownMemberType": "hint",
            "reportMissingTypeStubs": "none",
            "reportGeneralTypeIssues": "none",
            "reportMissingModuleSource": "none",
            "reportIncompatibleMethodOverride": "none",
            "reportIncompatibleVariableOverride": "none",
            "reportUnknownBaseClass": "none",
            "reportUnknownDecoratorType": "none",
            "reportFunctionMemberAccess": "none",
        },
    }

    extra_paths = []

    venv_path = workspace / ".venv"
    if venv_path.is_dir():
        print("[Scanner] Detected virtual environment: .venv")
        analysis_settings["venvPath"] = str(workspace)
        analysis_settings["venv"] = ".venv"

    src_path = workspace / "src"
    if src_path.is_dir():
        is_package = any(
            (item.is_dir() and (item / "__init__.py").exists())
            for item in src_path.iterdir()
        )
        if is_package:
            print("[Scanner] Detected 'src' layout, adding to extraPaths.")
            extra_paths.append("src")

    if extra_paths:
        analysis_settings["extraPaths"] = extra_paths

    final_settings_payload = {
        "python": {"analysis": analysis_settings},
        "basedpyright": {"analysis": analysis_settings},
    }

    print(
        f"[Scanner] Final LSP settings payload generated with comprehensive diagnostics."
    )
    return final_settings_payload
