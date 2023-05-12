# File: __init__.py
# Created Date: Saturday February 25th 2023
# Author: Steven Atkinson (steven@atkinson.mn)

"""
GUI for training

Usage:
>>> from nam.train.gui import run
>>> run()
"""

# Hack to recover graceful shutdowns in Windows.
# This has to happen ASAP
# See:
# https://github.com/sdatkinson/neural-amp-modeler/issues/105
# https://stackoverflow.com/a/44822794
def _ensure_graceful_shutdowns():
    import os

    if os.name == "nt":  # OS is Windows
        os.environ["FOR_DISABLE_CONSOLE_CTRL_HANDLER"] = "1"


_ensure_graceful_shutdowns()

import re
import tkinter as tk
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from tkinter import filedialog
from typing import Callable, Optional, Sequence

try:
    from nam import __version__
    from nam.train import core

    _install_is_valid = True
except ImportError:
    _install_is_valid = False
_BUTTON_WIDTH = 20
_BUTTON_HEIGHT = 2
_TEXT_WIDTH = 70

_DEFAULT_NUM_EPOCHS = 100
_DEFAULT_DELAY = None


@dataclass
class _AdvancedOptions(object):
    architecture: core.Architecture
    num_epochs: int
    delay: Optional[int]


class _PathType(Enum):
    FILE = "file"
    DIRECTORY = "directory"
    MULTIFILE = "multifile"


class _PathButton(object):
    """
    Button and the path
    """

    def __init__(
        self,
        frame: tk.Frame,
        button_text,
        info_str: str,
        path_type: _PathType,
        hooks: Optional[Sequence[Callable[[], None]]] = None,
    ):
        self._info_str = info_str
        self._path: Optional[Path] = None
        self._path_type = path_type
        self._button = tk.Button(
            frame,
            text=button_text,
            width=_BUTTON_WIDTH,
            height=_BUTTON_HEIGHT,
            fg="black",
            command=self._set_val,
        )
        self._button.pack(side=tk.LEFT)
        self._label = tk.Label(
            frame,
            width=_TEXT_WIDTH,
            height=_BUTTON_HEIGHT,
            fg="black",
            bg=None,
            anchor="w",
        )
        self._label.pack(side=tk.RIGHT)
        self._hooks = hooks
        self._set_text()

    @property
    def val(self) -> Optional[Path]:
        return self._path

    def _set_text(self):
        if self._path is None:
            self._label["fg"] = "red"
            self._label["text"] = f"{self._info_str} is not set!"
        else:
            val = self.val
            val = val[0] if isinstance(val, tuple) and len(val) == 1 else val
            self._label["fg"] = "black"
            self._label["text"] = f"{self._info_str} set to {val}"

    def _set_val(self):
        res = {
            _PathType.FILE: filedialog.askopenfilename,
            _PathType.DIRECTORY: filedialog.askdirectory,
            _PathType.MULTIFILE: filedialog.askopenfilenames,
        }[self._path_type]()
        if res != "":
            self._path = res
        self._set_text()

        if self._hooks is not None:
            for h in self._hooks:
                h()


class _GUI(object):
    def __init__(self):
        self._root = tk.Tk()
        self._root.title(f"NAM Trainer - v{__version__}")

        # Buttons for paths:
        self._frame_input_path = tk.Frame(self._root)
        self._frame_input_path.pack()
        self._path_button_input = _PathButton(
            self._frame_input_path,
            "Input Audio",
            "Input audio",
            _PathType.FILE,
            hooks=[self._check_button_states],
        )

        self._frame_output_path = tk.Frame(self._root)
        self._frame_output_path.pack()
        self._path_button_output = _PathButton(
            self._frame_output_path,
            "Output Audio",
            "Output audio",
            _PathType.MULTIFILE,
            hooks=[self._check_button_states],
        )

        self._frame_train_destination = tk.Frame(self._root)
        self._frame_train_destination.pack()
        self._path_button_train_destination = _PathButton(
            self._frame_train_destination,
            "Train Destination",
            "Train destination",
            _PathType.DIRECTORY,
            hooks=[self._check_button_states],
        )

        # This should probably be to the right somewhere
        self._get_additional_options_frame()

        # Advanced options for training
        default_architecture = core.Architecture.STANDARD
        self.advanced_options = _AdvancedOptions(
            default_architecture, _DEFAULT_NUM_EPOCHS, _DEFAULT_DELAY
        )
        # Window to edit them:
        self._frame_advanced_options = tk.Frame(self._root)
        self._frame_advanced_options.pack()
        self._button_advanced_options = tk.Button(
            self._frame_advanced_options,
            text="Advanced options...",
            width=_BUTTON_WIDTH,
            height=_BUTTON_HEIGHT,
            fg="black",
            command=self._open_advanced_options,
        )
        self._button_advanced_options.pack()

        # Train button
        self._frame_train = tk.Frame(self._root)
        self._frame_train.pack()
        self._button_train = tk.Button(
            self._frame_train,
            text="Train",
            width=_BUTTON_WIDTH,
            height=_BUTTON_HEIGHT,
            fg="black",
            command=self._train,
        )
        self._button_train.pack()

        self._check_button_states()

    def _get_additional_options_frame(self):
        # Checkboxes
        self._frame_silent = tk.Frame(self._root)
        self._frame_silent.pack(side=tk.LEFT)

        # Silent run (bypass popups)
        self._silent = tk.BooleanVar()
        self._chkbox_silent = tk.Checkbutton(
            self._frame_silent,
            text="Silent run",
            variable=self._silent,
        )
        self._chkbox_silent.grid(row=1, column=1, sticky="W")

        # Auto save the end plot
        self._save_plot = tk.BooleanVar()
        self._save_plot.set(True)  # default this to true
        self._chkbox_save_plot = tk.Checkbutton(
            self._frame_silent,
            text="Save plot automatically",
            variable=self._save_plot,
        )
        self._chkbox_save_plot.grid(row=2, column=1, sticky="W")

    def mainloop(self):
        self._root.mainloop()

    def _open_advanced_options(self):
        """
        Open advanced options
        """
        ao = _AdvancedOptionsGUI(self)
        # I should probably disable the main GUI...
        ao.mainloop()
        # ...and then re-enable it once it gets closed.

    def _train(self):
        # Advanced options:
        num_epochs = self.advanced_options.num_epochs
        architecture = self.advanced_options.architecture
        delay = self.advanced_options.delay
        file_list = self._path_button_output.val

        # Advanced-er options
        # If you're poking around looking for these, then maybe it's time to learn to
        # use the command-line scripts ;)
        lr = 0.004
        lr_decay = 0.007
        seed = 0

        # Run it
        for file in file_list:
            print(f"Now training {file}")
            modelname = re.sub(r"\.wav$", "", file.split("/")[-1])

            trained_model = core.train(
                self._path_button_input.val,
                file,
                self._path_button_train_destination.val,
                epochs=num_epochs,
                delay=delay,
                architecture=architecture,
                lr=lr,
                lr_decay=lr_decay,
                seed=seed,
                silent=self._silent.get(),
                save_plot=self._save_plot.get(),
                modelname=modelname,
            )
            print("Model training complete!")
            print("Exporting...")
            outdir = self._path_button_train_destination.val
            print(f"Exporting trained model to {outdir}...")
            trained_model.net.export(outdir, modelname=modelname)
            print("Done!")

    def _check_button_states(self):
        """
        Determine if any buttons should be disabled
        """
        # Train button is diabled unless all paths are set
        if any(
            pb.val is None
            for pb in (
                self._path_button_input,
                self._path_button_output,
                self._path_button_train_destination,
            )
        ):
            self._button_train["state"] = tk.DISABLED
            return
        self._button_train["state"] = tk.NORMAL


_ADVANCED_OPTIONS_LEFT_WIDTH = 12
_ADVANCED_OPTIONS_RIGHT_WIDTH = 12


class _LabeledOptionMenu(object):
    """
    Label (left) and radio buttons (right)
    """

    def __init__(
        self, frame: tk.Frame, label: str, choices: Enum, default: Optional[Enum] = None
    ):
        """
        :param command: Called to propagate option selection. Is provided with the
            value corresponding to the radio button selected.
        """
        self._frame = frame
        self._choices = choices
        height = _BUTTON_HEIGHT
        bg = None
        fg = "black"
        self._label = tk.Label(
            frame,
            width=_ADVANCED_OPTIONS_LEFT_WIDTH,
            height=height,
            fg=fg,
            bg=bg,
            anchor="w",
            text=label,
        )
        self._label.pack(side=tk.LEFT)

        frame_menu = tk.Frame(frame)
        frame_menu.pack(side=tk.RIGHT)

        self._selected_value = None
        default = (list(choices)[0] if default is None else default).value
        self._menu = tk.OptionMenu(
            frame_menu,
            tk.StringVar(master=frame, value=default, name=label),
            # default,
            *[choice.value for choice in choices],  #  if choice.value!=default],
            command=self._set,
        )
        self._menu.config(width=_ADVANCED_OPTIONS_RIGHT_WIDTH)
        self._menu.pack(side=tk.RIGHT)
        # Initialize
        self._set(default)

    def get(self) -> Enum:
        return self._selected_value

    def _set(self, val: str):
        """
        Set the value selected
        """
        self._selected_value = self._choices(val)


class _LabeledText(object):
    """
    Label (left) and text input (right)
    """

    def __init__(self, frame: tk.Frame, label: str, default=None, type=None):
        """
        :param command: Called to propagate option selection. Is provided with the
            value corresponding to the radio button selected.
        :param type: If provided, casts value to given type
        """
        self._frame = frame
        label_height = 2
        text_height = 1
        self._label = tk.Label(
            frame,
            width=_ADVANCED_OPTIONS_LEFT_WIDTH,
            height=label_height,
            fg="black",
            bg=None,
            anchor="w",
            text=label,
        )
        self._label.pack(side=tk.LEFT)

        self._text = tk.Text(
            frame,
            width=_ADVANCED_OPTIONS_RIGHT_WIDTH,
            height=text_height,
            fg="black",
            bg=None,
        )
        self._text.pack(side=tk.RIGHT)

        self._type = type

        if default is not None:
            self._text.insert("1.0", str(default))

    def get(self):
        try:
            val = self._text.get("1.0", tk.END)  # Line 1, character zero (wat)
            if self._type is not None:
                val = self._type(val)
            return val
        except tk.TclError:
            return None


class _AdvancedOptionsGUI(object):
    """
    A window to hold advanced options (Architecture and number of epochs)
    """

    def __init__(self, parent: _GUI):
        self._parent = parent
        self._root = tk.Tk()
        self._root.title("Advanced Options")

        # Architecture: radio buttons
        self._frame_architecture = tk.Frame(self._root)
        self._frame_architecture.pack()
        self._architecture = _LabeledOptionMenu(
            self._frame_architecture,
            "Architecture",
            core.Architecture,
            default=self._parent.advanced_options.architecture,
        )

        # Number of epochs: text box
        self._frame_epochs = tk.Frame(self._root)
        self._frame_epochs.pack()

        def non_negative_int(val):
            val = int(val)
            if val < 0:
                val = 0
            return val

        self._epochs = _LabeledText(
            self._frame_epochs,
            "Epochs",
            default=str(self._parent.advanced_options.num_epochs),
            type=non_negative_int,
        )

        # Delay: text box
        self._frame_delay = tk.Frame(self._root)
        self._frame_delay.pack()

        def int_or_null(val):
            val = val.rstrip()
            return val if val == "null" else int(val)

        def int_or_null_inv(val):
            return "null" if val is None else str(val)

        self._delay = _LabeledText(
            self._frame_delay,
            "Delay",
            default=int_or_null_inv(self._parent.advanced_options.delay),
            type=int_or_null,
        )

        # "Ok": apply and destory
        self._frame_ok = tk.Frame(self._root)
        self._frame_ok.pack()
        self._button_ok = tk.Button(
            self._frame_ok,
            text="Ok",
            width=_BUTTON_WIDTH,
            height=_BUTTON_HEIGHT,
            fg="black",
            command=self._apply_and_destroy,
        )
        self._button_ok.pack()

    def mainloop(self):
        self._root.mainloop()

    def _apply_and_destroy(self):
        """
        Set values to parent and destroy this object
        """
        self._parent.advanced_options.architecture = self._architecture.get()
        epochs = self._epochs.get()
        if epochs is not None:
            self._parent.advanced_options.num_epochs = epochs
        delay = self._delay.get()
        # Value None is returned as "null" to disambiguate from non-set.
        if delay is not None:
            self._parent.advanced_options.delay = None if delay == "null" else delay
        self._root.destroy()


def _install_error():
    window = tk.Tk()
    window.title("ERROR")
    label = tk.Label(
        window,
        width=45,
        height=2,
        text="The NAM training software has not been installed correctly.",
    )
    label.pack()
    button = tk.Button(window, width=10, height=2, text="Quit", command=window.destroy)
    button.pack()
    window.mainloop()


def run():
    if _install_is_valid:
        _gui = _GUI()
        _gui.mainloop()
    else:
        _install_error()


if __name__ == "__main__":
    run()
