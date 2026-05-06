from .packer import Contextpacker

__all__ = ["Contextpacker", "launch_gui"]
__version__ = "0.2.0"


def launch_gui(max_tokens: int = 8192) -> None:
    """Launch the interactive contextpacker GUI.

    Requires ``tkinter`` (included with most Python distributions).

    Parameters
    ----------
    max_tokens:
        Default token budget pre-filled in every tab.
    """
    try:
        from .gui import launch_gui as _launch
    except ImportError as exc:
        raise ImportError(
            "contextpacker GUI requires tkinter. "
            "Install it via your system package manager "
            "(e.g. 'apt install python3-tk' on Debian/Ubuntu)."
        ) from exc
    _launch(max_tokens=max_tokens)
