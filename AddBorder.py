
import os
import json
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageOps, ImageTk
from setuptools_scm import get_version

SETTINGS_FILE = Path.home() / ".addborder_settings.json"
LEGACY_SETTINGS_FILE = Path.home() / ".white_border_settings.json"

DEFAULT_PERCENTAGE = 10.0
DEFAULT_BORDER_COLOR = "#ffffff"
DEFAULT_SHADOW_COLOR = "#000000"
DEFAULT_SHADOW_OFFSET = 5
DEFAULT_SHADOW_BLUR = 8
DEFAULT_SHADOW_OPACITY = 50
MAX_SHADOW_BLUR = 100
MIN_PERCENTAGE = 0.5
MAX_PERCENTAGE = 60.0


def get_app_version():
    if getattr(sys, "frozen", False):
        version_file = Path(sys._MEIPASS) / "version.txt"
        try:
            return version_file.read_text(encoding="utf-8").strip()
        except OSError:
            return "unknown"

    project_dir = Path(__file__).resolve().parent
    try:
        return get_version(root=str(project_dir))
    except (LookupError, OSError):
        return "unknown"

def icon_asset_path(filename):
    bundle_dir = Path(
        getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    )
    return bundle_dir / "graphics" / filename


def load_settings():
    for settings_file in (SETTINGS_FILE, LEGACY_SETTINGS_FILE):
        try:
            with open(settings_file, "r", encoding="utf-8") as file:
                settings = json.load(file)
                if isinstance(settings, dict):
                    return settings
        except (OSError, ValueError):
            continue
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


def normalize_color(value):
    if not isinstance(value, str):
        return None

    try:
        rgb = ImageColor.getrgb(value)
    except (TypeError, ValueError):
        return None

    if len(rgb) != 3:
        return None

    return "#{:02x}{:02x}{:02x}".format(*rgb)


def setting_integer(settings, key, default, minimum, maximum):
    value = settings.get(key, default)
    if isinstance(value, bool):
        return default
    try:
        value = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return min(maximum, max(minimum, value))


def render_bordered_image(
    image,
    border,
    border_color,
    shadow_enabled=False,
    shadow_offset_x=0,
    shadow_offset_y=0,
    shadow_blur=0,
    shadow_color=DEFAULT_SHADOW_COLOR,
    shadow_opacity=100,
):
    border = max(0, int(border))
    image = image.convert("RGB")
    width, height = image.size
    canvas_size = (width + 2 * border, height + 2 * border)
    canvas = Image.new("RGB", canvas_size, border_color)

    if shadow_enabled and border > 0 and shadow_opacity > 0:
        offset_x = min(border, max(-border, int(shadow_offset_x)))
        offset_y = min(border, max(-border, int(shadow_offset_y)))
        mask = Image.new("L", canvas_size, 0)
        shadow_left = border + offset_x
        shadow_top = border + offset_y
        ImageDraw.Draw(mask).rectangle(
            (
                shadow_left,
                shadow_top,
                shadow_left + width - 1,
                shadow_top + height - 1,
            ),
            fill=255,
        )
        if shadow_blur > 0:
            mask = mask.filter(ImageFilter.GaussianBlur(shadow_blur))
        mask = mask.point(
            lambda alpha: round(alpha * shadow_opacity / 100)
        )

        shadow_rgb = ImageColor.getrgb(shadow_color)
        shadow = Image.new("RGBA", canvas_size, (*shadow_rgb, 255))
        shadow.putalpha(mask)
        canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow).convert(
            "RGB"
        )

    canvas.paste(image, (border, border))
    return canvas


class AddBorderApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Add Border - {get_app_version()}")
        self._icon_images = tuple(
            ImageTk.PhotoImage(file=str(icon_asset_path(filename)))
            for filename in (
                "addBorderIcon32.png",
                "addBorderIcon64.png",
                "addBorderIcon72.png",
            )
        )
        self.root.iconphoto(True, *self._icon_images)
        # Allow the window and its contents to resize with the user.
        self.root.resizable(True, True)
        self.root.minsize(620, 780)

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

        border_color = normalize_color(
            self.settings.get("last_border_color", DEFAULT_BORDER_COLOR)
        )
        self.border_color = border_color or DEFAULT_BORDER_COLOR
        shadow_color = normalize_color(
            self.settings.get("last_shadow_color", DEFAULT_SHADOW_COLOR)
        )
        self.shadow_color = shadow_color or DEFAULT_SHADOW_COLOR

        self.percentage_var = tk.StringVar(
            value=f"{float(percentage):.1f}"
        )
        self.shadow_enabled_var = tk.BooleanVar(
            value=self.settings.get("last_shadow_enabled") is True
        )
        self.shadow_x_var = tk.IntVar(
            value=setting_integer(
                self.settings, "last_shadow_x", DEFAULT_SHADOW_OFFSET,
                -10000, 10000
            )
        )
        self.shadow_y_var = tk.IntVar(
            value=setting_integer(
                self.settings, "last_shadow_y", DEFAULT_SHADOW_OFFSET,
                -10000, 10000
            )
        )
        self.shadow_blur_var = tk.IntVar(
            value=setting_integer(
                self.settings, "last_shadow_blur", DEFAULT_SHADOW_BLUR,
                0, MAX_SHADOW_BLUR
            )
        )
        self.shadow_opacity_var = tk.IntVar(
            value=setting_integer(
                self.settings, "last_shadow_opacity",
                DEFAULT_SHADOW_OPACITY, 0, 100
            )
        )
        self.source_var = tk.StringVar()
        self.output_var = tk.StringVar()

        self.source_path = None
        self.preview_source = None
        self.preview_photo = None
        self.auto_output = True
        self.last_auto_output = ""
        self.busy = False
        self.last_output_path = None
        self.shadow_settings_expanded = False

        self.build_ui()
        self.root.bind("<Return>", lambda event: self.add_border())

        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth()
             - self.root.winfo_width()) // 2
        y = (self.root.winfo_screenheight()
             - self.root.winfo_height()) // 2
        self.root.geometry(f"+{x}+{y}")

    def build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = ttk.Frame(self.root, padding=18)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(10, weight=1)  # Give the preview the extra height.

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
            row=5, column=0, columnspan=2, sticky="ew"
        )
        percentage_frame.columnconfigure(0, weight=1)

        # Border percentage slider and live percentage display
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
        self.percentage_slider.grid(row=0, column=0, sticky="ew")

        self.percentage_display = tk.StringVar(
            value=f"{float(self.percentage_var.get()):.1f}%"
        )

        ttk.Label(
            percentage_frame,
            textvariable=self.percentage_display
        ).grid(row=0, column=1, padx=(8, 0))

        ttk.Label(main, text="Border colour:").grid(
            row=6, column=0, columnspan=2,
            sticky="w", pady=(12, 5)
        )

        color_frame = ttk.Frame(main)
        color_frame.grid(row=7, column=0, columnspan=2, sticky="w")
        self.color_swatch = tk.Label(
            color_frame,
            width=5,
            relief="solid",
            borderwidth=1,
            background=self.border_color
        )
        self.color_swatch.grid(row=0, column=0, padx=(0, 8))
        ttk.Button(
            color_frame,
            text="Choose colour...",
            command=self.choose_border_color
        ).grid(row=0, column=1)

        self.build_shadow_accordion(main, row=8)

        ttk.Label(main, text="Live preview:").grid(
            row=9, column=0, columnspan=2,
            sticky="w", pady=(12, 5)
        )

        self.preview_frame = ttk.Frame(
            main, height=260, relief="sunken", borderwidth=1
        )
        self.preview_frame.grid(
            row=10, column=0, columnspan=2, sticky="nsew"
        )
        self.preview_frame.grid_propagate(False)
        self.preview_frame.columnconfigure(0, weight=1)
        self.preview_frame.rowconfigure(0, weight=1)

        self.preview_label = ttk.Label(
            self.preview_frame,
            text="Select an image to preview it",
            anchor="center",
            justify="center"
        )
        self.preview_label.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.preview_frame.bind("<Configure>", self.preview_resized)

        ttk.Separator(
            main, orient="horizontal"
        ).grid(
            row=11, column=0, columnspan=2,
            sticky="ew", pady=18
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
            row=12, column=0, columnspan=2,
            sticky="ew", pady=(14, 8)
        )
        self.root.bind("<Configure>", self.window_resized, add="+")

        actions = ttk.Frame(main)
        actions.grid(
            row=13, column=0, columnspan=2, sticky="ew"
        )
        for column in range(3):
            actions.columnconfigure(column, weight=1, uniform="actions")

        self.add_button = ttk.Button(
            actions, text="Add Border",
            command=self.add_border, width=20
        )
        self.add_button.grid(
            row=0, column=0
        )

        self.folder_button = ttk.Button(
            actions,
            text="Open Output Folder",
            command=self.open_output_folder,
            state="disabled",
            width=20
        )
        self.folder_button.grid(
            row=0, column=1
        )

        self.close_button = ttk.Button(
            actions, text="Close", command=self.root.destroy, width=20
        )
        self.close_button.grid(
            row=0, column=2
        )

        # Source/output entries and the preview stretch with the window.
        main.columnconfigure(0, weight=1)

    def build_shadow_accordion(self, parent, row):
        accordion = ttk.Frame(parent)
        accordion.grid(row=row, column=0, columnspan=2, sticky="ew")
        accordion.columnconfigure(1, weight=1)

        ttk.Checkbutton(
            accordion,
            text="Enable Drop Shadow",
            variable=self.shadow_enabled_var,
            command=self.shadow_enabled_changed,
        ).grid(row=0, column=0, sticky="w")
        self.shadow_accordion_button = ttk.Button(
            accordion,
            text="Drop shadow settings  >",
            command=self.toggle_shadow_settings,
            state=(
                tk.NORMAL if self.shadow_enabled_var.get() else tk.DISABLED
            ),
        )
        self.shadow_accordion_button.grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )

        self.shadow_settings_frame = ttk.LabelFrame(
            accordion, text="Drop shadow"
        )
        self.shadow_settings_frame.grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0)
        )
        self.shadow_settings_frame.columnconfigure(1, weight=1)

        self.shadow_x_slider = tk.Scale(
            self.shadow_settings_frame,
            from_=-10000,
            to=10000,
            resolution=1,
            orient=tk.HORIZONTAL,
            variable=self.shadow_x_var,
            command=self.shadow_setting_changed,
            label="X offset (pixels)",
            showvalue=True,
        )
        self.shadow_x_slider.grid(
            row=0, column=0, columnspan=2, sticky="ew", padx=8
        )

        self.shadow_y_slider = tk.Scale(
            self.shadow_settings_frame,
            from_=-10000,
            to=10000,
            resolution=1,
            orient=tk.HORIZONTAL,
            variable=self.shadow_y_var,
            command=self.shadow_setting_changed,
            label="Y offset (pixels)",
            showvalue=True,
        )
        self.shadow_y_slider.grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=8
        )

        self.shadow_blur_slider = tk.Scale(
            self.shadow_settings_frame,
            from_=0,
            to=MAX_SHADOW_BLUR,
            resolution=1,
            orient=tk.HORIZONTAL,
            variable=self.shadow_blur_var,
            command=self.shadow_setting_changed,
            label="Blur (pixels)",
            showvalue=True,
        )
        self.shadow_blur_slider.grid(
            row=2, column=0, columnspan=2, sticky="ew", padx=8
        )

        shadow_color_frame = ttk.Frame(self.shadow_settings_frame)
        shadow_color_frame.grid(
            row=3, column=0, columnspan=2, sticky="w", padx=8, pady=4
        )
        ttk.Label(shadow_color_frame, text="Shadow colour:").grid(
            row=0, column=0, padx=(0, 8)
        )
        self.shadow_color_swatch = tk.Label(
            shadow_color_frame,
            width=5,
            relief="solid",
            borderwidth=1,
            background=self.shadow_color,
        )
        self.shadow_color_swatch.grid(row=0, column=1, padx=(0, 8))
        ttk.Button(
            shadow_color_frame,
            text="Choose colour...",
            command=self.choose_shadow_color,
        ).grid(row=0, column=2)

        self.shadow_opacity_slider = tk.Scale(
            self.shadow_settings_frame,
            from_=0,
            to=100,
            resolution=1,
            orient=tk.HORIZONTAL,
            variable=self.shadow_opacity_var,
            command=self.shadow_setting_changed,
            label="Opacity (%)",
            showvalue=True,
        )
        self.shadow_opacity_slider.grid(
            row=4, column=0, columnspan=2, sticky="ew", padx=8
        )

        if self.preview_source is None:
            self.shadow_x_slider.configure(state=tk.DISABLED)
            self.shadow_y_slider.configure(state=tk.DISABLED)

        if not self.shadow_settings_expanded:
            self.shadow_settings_frame.grid_remove()

    def toggle_shadow_settings(self):
        if not self.shadow_enabled_var.get():
            return

        self.shadow_settings_expanded = not self.shadow_settings_expanded
        if self.shadow_settings_expanded:
            self.shadow_settings_frame.grid()
            label = "Drop shadow settings  v"
        else:
            self.shadow_settings_frame.grid_remove()
            label = "Drop shadow settings  >"
        self.shadow_accordion_button.configure(text=label)

    def window_resized(self, event=None):
        # Keep long status messages readable as the window width changes.
        if event is not None and event.widget is self.root:
            width = max(300, self.root.winfo_width() - 60)
            if hasattr(self, "status_label"):
                self.status_label.configure(wraplength=width)

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
        shadow_suffix = "_ds" if self.shadow_enabled_var.get() else ""
        filename = (
            f"{self.source_path.stem}_bordered_"
            f"{percentage_text}{shadow_suffix}.jpg"
        )
        return str(self.source_path.parent / filename)

    def refresh_suggested_output(self):
        if self.auto_output:
            suggested = self.make_suggested_output()
            self.last_auto_output = suggested
            self.output_var.set(suggested)

    def percentage_changed(self, value=None):
        try:
            percentage = float(
                value if value is not None else self.percentage_var.get()
            )
            self.percentage_display.set(f"{percentage:.1f}%")
            self.refresh_suggested_output()
            self.update_shadow_offset_limits()
            self.update_preview()
        except (TypeError, ValueError):
            pass

    def shadow_offset_bound(self):
        if self.preview_source is None or not valid_percentage(
            self.percentage_var.get()
        ):
            return 0
        width, height = self.preview_source.size
        percentage = float(self.percentage_var.get())
        return round(min(width, height) * percentage / 100.0)

    def update_shadow_offset_limits(self):
        if not hasattr(self, "shadow_x_slider"):
            return
        if self.preview_source is None:
            self.shadow_x_slider.configure(state=tk.DISABLED)
            self.shadow_y_slider.configure(state=tk.DISABLED)
            return

        border = self.shadow_offset_bound()
        previous_x = self.shadow_x_var.get()
        previous_y = self.shadow_y_var.get()
        self.shadow_x_slider.configure(
            from_=-border, to=border, state=tk.NORMAL
        )
        self.shadow_y_slider.configure(
            from_=-border, to=border, state=tk.NORMAL
        )

        x_offset = min(border, max(-border, previous_x))
        y_offset = min(border, max(-border, previous_y))
        self.shadow_x_var.set(x_offset)
        self.shadow_y_var.set(y_offset)
        if x_offset != previous_x or y_offset != previous_y:
            self.save_shadow_settings()

    def save_shadow_settings(self):
        self.settings["last_shadow_enabled"] = (
            self.shadow_enabled_var.get()
        )
        self.settings["last_shadow_x"] = self.shadow_x_var.get()
        self.settings["last_shadow_y"] = self.shadow_y_var.get()
        self.settings["last_shadow_blur"] = self.shadow_blur_var.get()
        self.settings["last_shadow_color"] = self.shadow_color
        self.settings["last_shadow_opacity"] = (
            self.shadow_opacity_var.get()
        )
        save_settings(self.settings)

    def shadow_setting_changed(self, value=None):
        self.save_shadow_settings()
        self.update_preview()

    def shadow_enabled_changed(self):
        self.shadow_settings_expanded = self.shadow_enabled_var.get()
        if self.shadow_settings_expanded:
            self.shadow_settings_frame.grid()
            label = "Drop shadow settings  v"
        else:
            self.shadow_settings_frame.grid_remove()
            label = "Drop shadow settings  >"
        self.shadow_accordion_button.configure(
            text=label,
            state=(
                tk.NORMAL if self.shadow_enabled_var.get() else tk.DISABLED
            ),
        )
        self.save_shadow_settings()
        self.refresh_suggested_output()
        self.update_preview()

    def choose_shadow_color(self):
        _, selected_color = colorchooser.askcolor(
            color=self.shadow_color,
            parent=self.root,
            title="Select shadow colour",
        )
        if selected_color is None:
            return

        shadow_color = normalize_color(selected_color)
        if shadow_color is None:
            self.status_var.set("Unable to use the selected shadow colour.")
            return

        self.shadow_color = shadow_color
        self.shadow_color_swatch.configure(background=shadow_color)
        self.save_shadow_settings()
        self.update_preview()

    def choose_border_color(self):
        _, selected_color = colorchooser.askcolor(
            color=self.border_color,
            parent=self.root,
            title="Select border colour"
        )
        if selected_color is None:
            return

        border_color = normalize_color(selected_color)
        if border_color is None:
            self.status_var.set("Unable to use the selected border colour.")
            return

        self.border_color = border_color
        self.color_swatch.configure(background=border_color)
        self.settings["last_border_color"] = border_color
        save_settings(self.settings)
        self.update_preview()

    def preview_resized(self, event=None):
        """Refresh the preview when the available preview area changes size."""
        if self.preview_source is not None:
            self.update_preview()

    def update_preview(self):
        """Render a fitted preview using the preview area's current dimensions."""
        if self.preview_source is None:
            return

        try:
            percentage = float(self.percentage_var.get())
            source = self.preview_source
            width, height = source.size
            border_original = min(width, height) * percentage / 100.0

            # Leave a little room inside the preview frame for its padding.
            available_width = max(80, self.preview_frame.winfo_width() - 14)
            available_height = max(80, self.preview_frame.winfo_height() - 14)

            # Fit the complete bordered image without making a huge copy of
            # the original photograph while the user drags the slider.
            scale = min(
                available_width / (width + 2 * border_original),
                available_height / (height + 2 * border_original)
            )
            image_width = max(1, round(width * scale))
            image_height = max(1, round(height * scale))
            border_pixels = max(0, round(border_original * scale))

            resampling = getattr(Image, "Resampling", Image).LANCZOS
            thumbnail = source.resize(
                (image_width, image_height), resampling
            )
            preview_image = render_bordered_image(
                thumbnail,
                border_pixels,
                self.border_color,
                shadow_enabled=self.shadow_enabled_var.get(),
                shadow_offset_x=round(self.shadow_x_var.get() * scale),
                shadow_offset_y=round(self.shadow_y_var.get() * scale),
                shadow_blur=round(self.shadow_blur_var.get() * scale),
                shadow_color=self.shadow_color,
                shadow_opacity=self.shadow_opacity_var.get(),
            )
            self.preview_photo = ImageTk.PhotoImage(preview_image)
            self.preview_label.configure(image=self.preview_photo, text="")
        except (TypeError, ValueError, tk.TclError) as error:
            self.preview_label.configure(
                image="", text=f"Unable to preview image:\n{error}"
            )

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

        try:
            with Image.open(self.source_path) as original:
                self.preview_source = ImageOps.exif_transpose(
                    original
                ).convert("RGB")
            self.update_shadow_offset_limits()
            self.update_preview()
        except Exception as error:
            self.preview_source = None
            self.preview_photo = None
            self.update_shadow_offset_limits()
            self.preview_label.configure(
                image="", text=f"Unable to preview image:\n{error}"
            )

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
            self.status_var.set("Adding border...")
            self.root.update_idletasks()

            # Load image and correct EXIF orientation.
            with Image.open(self.source_path) as original:
                image = ImageOps.exif_transpose(
                    original
                ).convert("RGB")

            width, height = image.size
            shortest_side = min(width, height)
            border = round(shortest_side * percentage / 100.0)

            bordered = render_bordered_image(
                image,
                border,
                self.border_color,
                shadow_enabled=self.shadow_enabled_var.get(),
                shadow_offset_x=self.shadow_x_var.get(),
                shadow_offset_y=self.shadow_y_var.get(),
                shadow_blur=self.shadow_blur_var.get(),
                shadow_color=self.shadow_color,
                shadow_opacity=self.shadow_opacity_var.get(),
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
            self.save_shadow_settings()

            self.last_output_path = output_path
            shadow_status = (
                f"Drop shadow: {self.shadow_color}, "
                f"offset ({self.shadow_x_var.get()}, "
                f"{self.shadow_y_var.get()}) px, "
                f"blur {self.shadow_blur_var.get()} px, "
                f"opacity {self.shadow_opacity_var.get()}%\n"
                if self.shadow_enabled_var.get()
                else "Drop shadow: disabled\n"
            )
            self.status_var.set(
                "Border added successfully!\n"
                f"Border colour: {self.border_color}\n"
                f"{shadow_status}"
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
    AddBorderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
