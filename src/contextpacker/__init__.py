"""contextpacker — token-aware packing and truncation for LLM context windows."""
from .packer import Contextpacker

__all__ = ["Contextpacker", "launch_gui"]
__version__ = "0.2.0"


def launch_gui() -> None:
    """Launch the contextpacker Tkinter GUI.

    Raises
    ------
    ImportError
        If ``tkinter`` is not available in the current Python installation.
    """
    try:
        from .gui import launch  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "The contextpacker GUI requires tkinter, which is not available "
            "in this Python installation. Install the 'python3-tk' system "
            "package (e.g. 'sudo apt install python3-tk' on Debian/Ubuntu)."
        ) from exc
    launch()
