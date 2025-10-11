from typing import Any


def track(name: str, value: Any) -> None:
    """
    Tracks a custom metric for display in the PyForge Metrics panel.
    """

    print(
        f"PyForge tracking is only available in a live session. Metric: {name}={value}"
    )


def metric(name: str, type: str = "value", unit: str = ""):
    """
    A decorator to define a function as a persistent custom metric.
    """

    def decorator(func):

        func._is_pf_metric = True
        func._pf_metric_name = name
        func._pf_metric_type = type
        func._pf_metric_unit = unit
        return func

    return decorator


def override(target: str):
    """
    A decorator to override a core agent function. ADVANCED and DANGEROUS.
    The decorated function's first argument must be `original_func`.
    """

    def decorator(func):
        func._is_pf_override = True
        func._pf_override_target = target
        return func

    return decorator
