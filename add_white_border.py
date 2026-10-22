
import os
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageOps

SETTINGS_FILE = Path.home() / ".white_border_settings.json"

DEFAULT_PERCENTAGE = 10.0
MIN_PERCENTAGE = 0.5
MAX_PERCENTAGE = 100.0


def load_settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as file:
            settings = json.load(file)
            if isinstance(settings, dict):
                return settings
    except (OSError, ValueError):
        pass
    return {}


def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as file:
            json.dump(settings, file, indent=4)
    except OSError:
        pass


def valid_percentage(value):
    try:
        number = float(value)
        return (
            MIN_PERCENTAGE <= number <= MAX_PERCENTAGE
            and abs(number * 2 - round(number * 2)) < 1e-8
        )
    except (TypeError, ValueError):
        return False


class WhiteBorderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("White Border Utility")
        self.root.resizable(False, False)

        self.settings = load_settings()

        last_folder = self.settings.get(
            "last_folder", str(Path.home())
        )
        if not Path(last_folder).is_dir():
            last_folder = str(Path.home())
        self.last_folder = last_folder

        percentage = self.settings.get(
            "last_percentage", DEFAULT_PERCENTAGE
        )
        if not valid_percentage(percentage):
            percentage = DEFAULT_PERCENTAGE

        self.percentage_var = tk.StringVar(
            value=f"{float(percentage):.1f}"
        )
        self.source_var = tk.StringVar()
        self.output_var = tk.StringVar()

        self.source_path = None
        self.auto_output = True
        self.last_auto_output = ""
        self.busy = False

        self.build_ui()
        self.root.bind("<Return>", lambda event: self.add_border())

        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth()
             - self.root.winfo_width()) // 2
        y = (self.root.winfo_screenheight()
             - self.root.winfo_height()) // 2
        self.root.geometry(f"+{x}+{y}")

    def build_ui(self):
        main = ttk.Frame(self.root, padding=18)
        main.grid(row=0, column=0, sticky="nsew")

        ttk.Label(
            main, text="Source image:"
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.source_entry = ttk.Entry(
            main, textvariable=self.source_var, width=58,
            state="readonly"
        )
        self.source_entry.grid(
            row=1, column=0, sticky="ew", padx=(0, 8)
        )

        ttk.Button(
            main, text="Browse...", command=self.browse_source
        ).grid(row=1, column=1, sticky="ew")

        ttk.Label(
            main, text="Output file name (including folder):"
        ).grid(
            row=2, column=0, columnspan=2,
            sticky="w", pady=(16, 5)
        )

        self.output_entry = ttk.Entry(
            main, textvariable=self.output_var, width=72
        )
        self.output_entry.grid(
            row=3, column=0, columnspan=2, sticky="ew"
        )
        self.output_entry.bind(
            "<KeyRelease>", self.output_edited
        )
        self.output_entry.bind(
            "<FocusOut>", self.output_edited
        )

        ttk.Label(
            main,
            text="Border width (% of shortest original image side):"
        ).grid(
            row=4, column=0, columnspan=2,
            sticky="w", pady=(16, 5)
        )

        percentage_frame = ttk.Frame(main)
        percentage_frame.grid(
            row=5, column=0, columnspan=2, sticky="w"
        )

        # Border percentage slider
        self.percentage_slider = tk.Scale(
            percentage_frame,
            from_=MIN_PERCENTAGE,
            to=MAX_PERCENTAGE,
            resolution=0.5,
            orient=tk.HORIZONTAL,
            variable=self.percentage_var,
            command=self.percentage_changed,
            showvalue=False,
            length=350,
        )
        self.percentage_slider.grid(row=0, column=0, sticky="w")    

        self.percentage_display = tk.StringVar(
            value=f"{float(self.percentage_var.get()):.1f}%"
        )

        ttk.Label(
            percentage_frame,
            textvariable=self.percentage_display
        ).grid(row=0, column=1, padx=(5, 0))

        ttk.Separator(
            main, orient="horizontal"
        ).grid(
            row=6, column=0, columnspan=2,
            sticky="ew", pady=18
        )

        self.add_button = ttk.Button(
            main, text="Add Border",
            command=self.add_border
        )
        self.add_button.grid(
            row=7, column=0, columnspan=2,
            sticky="ew", ipady=5
        )

        self.status_var = tk.StringVar(
            value="Select a JPG photograph to begin."
        )
        self.status_label = ttk.Label(
            main,
            textvariable=self.status_var,
            wraplength=500,
            justify="left"
        )
        self.status_label.grid(
            row=8, column=0, columnspan=2,
            sticky="w", pady=(14, 8)
        )

        # Bottom row buttons
        self.folder_button = ttk.Button(
            main,
            text="Open Output Folder",
            command=self.open_output_folder,
            state="disabled",
        )
        self.folder_button.grid(
            row=9, column=0, sticky="w"
        )

        self.close_button = ttk.Button(
            main,
            text="Close",
            command=self.root.destroy,
        )
        self.close_button.grid(
            row=9, column=1, sticky="e"
        )

        main.columnconfigure(0, weight=1)

    def output_edited(self, event=None):
        if self.output_var.get() != self.last_auto_output:
            self.auto_output = False

    def make_suggested_output(self):
        if not self.source_path:
            return ""

        if not valid_percentage(self.percentage_var.get()):
            return ""

        percentage = float(self.percentage_var.get())
        percentage_text = f"{percentage:.1f}".replace(".", "p")
        filename = (
            f"{self.source_path.stem}_bordered_"
            f"{percentage_text}.jpg"
        )
        return str(self.source_path.parent / filename)

    def refresh_suggested_output(self):
        if self.auto_output:
            suggested = self.make_suggested_output()
            self.last_auto_output = suggested
            self.output_var.set(suggested)

    def percentage_changed(self, value=None):
        try:
            percentage = float(value)
            self.percentage_display.set(f"{percentage:.1f}%")
            self.refresh_suggested_output()
        except (TypeError, ValueError):
            pass

    def browse_source(self):
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="Select a JPG photograph",
            initialdir=self.last_folder,
            filetypes=[
                ("JPEG images", "*.jpg *.jpeg"),
                ("All files", "*.*")
            ]
        )

        if not filename:
            return

        self.source_path = Path(filename)
        self.source_var.set(str(self.source_path))
        self.last_folder = str(self.source_path.parent)

        self.settings["last_folder"] = self.last_folder
        save_settings(self.settings)

        # A new source gets a new suggested output name.
        self.auto_output = True
        self.refresh_suggested_output()

        self.status_var.set(
            f"Selected: {self.source_path.name}"
        )
        self.folder_button.configure(state="disabled")

    def add_border(self):
        if self.busy:
            return

        if not self.source_path or not self.source_path.is_file():
            self.status_var.set(
                "Please select a valid source image first."
            )
            return

        percentage_text = self.percentage_var.get().strip()
        if not valid_percentage(percentage_text):
            self.status_var.set(
                "Enter a percentage from 0.5 to 100.0 "
                "in increments of 0.5."
            )
            self.percentage_slider.focus_set()
            return

        percentage = float(percentage_text)
        output_text = self.output_var.get().strip()

        if not output_text:
            self.status_var.set(
                "Please enter an output filename."
            )
            self.output_entry.focus_set()
            return

        output_path = Path(output_text).expanduser()

        # Ensure the output is a JPG.
        if output_path.suffix.lower() not in (".jpg", ".jpeg"):
            output_path = output_path.with_suffix(".jpg")
            self.output_var.set(str(output_path))

        try:
            source_resolved = self.source_path.resolve()
            output_resolved = output_path.resolve()

            if source_resolved == output_resolved:
                self.status_var.set(
                    "Choose a different output filename "
                    "to preserve the original image."
                )
                return

            if not output_path.parent.is_dir():
                self.status_var.set(
                    "The output folder does not exist. "
                    "Please choose a valid path."
                )
                return

            self.busy = True
            self.add_button.configure(state="disabled")
            self.folder_button.configure(state="disabled")
            self.root.config(cursor="watch")
            self.status_var.set("Adding white border...")
            self.root.update_idletasks()

            # Load image and correct EXIF orientation.
            with Image.open(self.source_path) as original:
                image = ImageOps.exif_transpose(
                    original
                ).convert("RGB")

            width, height = image.size
            shortest_side = min(width, height)
            border = round(shortest_side * percentage / 100.0)

            # Expand equally on all four sides.
            bordered = ImageOps.expand(
                image, border=border, fill="white"
            )

            # Save as high-quality JPEG.
            bordered.save(
                output_path,
                format="JPEG",
                quality=95,
                optimize=True
            )

            self.settings["last_percentage"] = percentage
            self.settings["last_folder"] = self.last_folder
            save_settings(self.settings)

            self.last_output_path = output_path
            self.status_var.set(
                "White border added successfully!\n"
                f"Percentage: {percentage:.1f}%\n"
                f"Border per edge: {border} pixels\n"
                f"Original size: {width} x {height}\n"
                f"New size: {bordered.width} x "
                f"{bordered.height}\n"
                f"Saved to: {output_path}"
            )
            self.folder_button.configure(state="normal")

        except Exception as error:
            self.status_var.set(
                f"Unable to process the image:\n{error}"
            )

        finally:
            self.busy = False
            self.add_button.configure(state="normal")
            self.root.config(cursor="")

    def open_output_folder(self):
        output_path = getattr(self, "last_output_path", None)
        if not output_path:
            return

        try:
            os.startfile(str(output_path.parent))
        except OSError as error:
            self.status_var.set(
                f"Unable to open output folder: {error}"
            )


def main():
    root = tk.Tk()
    WhiteBorderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
