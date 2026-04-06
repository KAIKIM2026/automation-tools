import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
import math
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

BASE_DIR = os.path.dirname(
    sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)
)
FFMPEG_PATH = os.path.join(BASE_DIR, "ffmpeg-8.1-essentials_build", "bin", "ffmpeg.exe")


def enable_dpi_awareness():
    if os.name != "nt":
        return
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def hide_console_window():
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        console_window = kernel32.GetConsoleWindow()
        if console_window:
            user32.ShowWindow(console_window, 0)
    except Exception:
        pass

def select_folder():
    path = filedialog.askdirectory()
    if path:
        folder_var.set(path)


def select_bg_color():
    _, hex_color = colorchooser.askcolor(color=bg_color_var.get(), parent=root_win)
    if hex_color:
        bg_color_var.set(hex_color)
        if "bg_preview" in globals():
            bg_preview.redraw(hex_color)
        update_shadow_example()


def hex_to_rgb(value):
    value = value.strip().lstrip("#")
    if len(value) != 6:
        return (242, 242, 242)
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def mix_colors(base_rgb, target_rgb, amount):
    mixed = []
    for base, target in zip(base_rgb, target_rgb):
        value = round(base + (target - base) * amount)
        mixed.append(max(0, min(255, value)))
    return tuple(mixed)


def update_shadow_example(*_args):
    if "example_canvas" not in globals():
        return

    example_canvas.delete("all")

    bg_rgb = hex_to_rgb(bg_color_var.get())
    example_canvas.configure(bg=rgb_to_hex(bg_rgb))

    blur_amount = int(round(blur_var.get()))
    opacity = max(0.0, min(1.0, shadow_opacity_var.get() / 100))
    distance_amount = int(round(distance_var.get()))
    canvas_w = max(220, int(example_canvas.cget("width")))
    canvas_h = max(170, int(example_canvas.cget("height")))
    box_w = 112
    box_h = 112
    shadow_x = int(round(distance_amount * 1.5))
    shadow_y = int(round(distance_amount * 1.9))
    spread_room = max(18, blur_amount * 4)
    total_w = box_w + shadow_x + spread_room
    total_h = box_h + shadow_y + spread_room
    base_x = max(18, (canvas_w - total_w) // 2)
    base_y = max(18, (canvas_h - total_h) // 2)

    if use_shadow_var.get() and opacity > 0:
        if blur_amount <= 0:
            shadow_rgb = mix_colors(bg_rgb, (0, 0, 0), opacity)
            example_canvas.create_rectangle(
                base_x + shadow_x,
                base_y + shadow_y,
                base_x + shadow_x + box_w,
                base_y + shadow_y + box_h,
                fill=rgb_to_hex(shadow_rgb),
                outline="",
            )
        else:
            max_layers = max(blur_amount * 2, 6)
            for layer in range(max_layers, 0, -1):
                spread = max(1, int(round(layer * 1.6)))
                factor = layer / max_layers
                shadow_rgb = mix_colors(bg_rgb, (0, 0, 0), opacity * factor * 0.22)
                example_canvas.create_rectangle(
                    base_x + shadow_x - spread,
                    base_y + shadow_y - spread,
                    base_x + shadow_x + box_w + spread,
                    base_y + shadow_y + box_h + spread,
                    fill=rgb_to_hex(shadow_rgb),
                    outline="",
                )

    example_canvas.create_rectangle(
        base_x,
        base_y,
        base_x + box_w,
        base_y + box_h,
        fill="#ffffff",
        outline="#dddddd",
    )

    example_canvas.create_rectangle(
        base_x,
        base_y,
        base_x + box_w,
        base_y + box_h,
        outline="#f7f7f7",
    )


def set_status(message, tone="idle"):
    status_var.set(message)
    if "status_badge" in globals():
        tone_map = {
            "idle": (PALETTE["accent_soft"], PALETTE["accent_hover"]),
            "working": ("#eaf8ef", "#4f8b62"),
            "success": ("#eef9ea", "#4f8b62"),
            "error": ("#fff1eb", "#c66a4b"),
        }
        badge_bg, badge_fg = tone_map.get(tone, tone_map["idle"])
        status_badge.configure(bg=badge_bg, fg=badge_fg)

    if "status_label" in globals():
        text_map = {
            "idle": PALETTE["muted"],
            "working": "#5f7f8f",
            "success": "#4f8b62",
            "error": "#c66a4b",
        }
        status_label.configure(fg=text_map.get(tone, PALETTE["muted"]))

    if "status_badge_text_var" in globals():
        badge_text = {
            "idle": "Ready",
            "working": "Working",
            "success": "Done",
            "error": "Error",
        }
        status_badge_text_var.set(badge_text.get(tone, "Ready"))


def set_progress(value):
    pct = max(0, min(100, value))
    if "progress_bar" in globals():
        progress_bar.set_value(pct)


def set_action_button_enabled(enabled):
    if "btn" not in globals():
        return

    btn.set_enabled(enabled)


def update_shadow_controls(*_args):
    if "shadow_controls_frame" not in globals():
        return

    if use_shadow_var.get():
        if not shadow_controls_frame.winfo_ismapped():
            shadow_controls_frame.pack(fill="x", padx=18, pady=(14, 16))
    else:
        if shadow_controls_frame.winfo_ismapped():
            shadow_controls_frame.pack_forget()

    update_shadow_example()


def build_filter_graph(bg_color, blur_amount, distance_amount, opacity_percent):
    shadow_x = max(0, int(round(distance_amount * 2.2)))
    shadow_y = max(0, int(round(distance_amount * 2.8)))
    alpha = max(0.0, min(1.0, opacity_percent / 100))
    blur = max(0, int(blur_amount))
    shadow_pad = max(max(1, blur) * 3, max(shadow_x, shadow_y) * 3)

    if blur <= 0:
        return (
            f"color=c={bg_color}:s=1080x1920:rate=24[bg];"
            "[0:v]scale=1000:1840:force_original_aspect_ratio=decrease,"
            "format=rgba,pad=1000:1840:(ow-iw)/2:(oh-ih)/2:color=black@0,setsar=1,"
            "fps=24,split=2[img_main][shadow_src];"
            f"[shadow_src]colorchannelmixer="
            f"rr=0:rg=0:rb=0:ra=0:"
            f"gr=0:gg=0:gb=0:ga=0:"
            f"br=0:bg=0:bb=0:ba=0:"
            f"ar=0:ag=0:ab=0:aa={alpha}[shadow];"
            f"[bg][shadow]overlay=(W-w)/2+{shadow_x}:(H-h)/2+{shadow_y}:format=auto:shortest=1[bg_shadow];"
            "[bg_shadow][img_main]overlay=(W-w)/2:(H-h)/2:format=auto:shortest=1,setsar=1[v]"
        )

    return (
        f"color=c={bg_color}:s=1080x1920:rate=24[bg];"
        "[0:v]scale=1000:1840:force_original_aspect_ratio=decrease,"
        "pad=1000:1840:(ow-iw)/2:(oh-ih)/2:color=black@0,setsar=1,"
        "format=rgba,fps=24,split=2[img_main][shadow_src];"
        f"[img_main]pad=iw+{shadow_pad * 2}:ih+{shadow_pad * 2}:{shadow_pad}:{shadow_pad}:color=black@0[img_canvas];"
        f"[shadow_src]pad=iw+{shadow_pad * 2}:ih+{shadow_pad * 2}:{shadow_pad}:{shadow_pad}:color=black@0,"
        "colorchannelmixer="
        f"rr=0:rg=0:rb=0:ra=0:"
        f"gr=0:gg=0:gb=0:ga=0:"
        f"br=0:bg=0:bb=0:ba=0:"
        f"ar=0:ag=0:ab=0:aa={alpha},"
        f"boxblur=luma_radius={blur}:luma_power=1:chroma_radius={max(1, blur // 2)}:"
        f"chroma_power=1:alpha_radius={blur}:alpha_power=1[shadow];"
        f"[bg][shadow]overlay=(W-w)/2+{shadow_x}:(H-h)/2+{shadow_y}:format=auto:shortest=1[bg_shadow];"
        "[bg_shadow][img_canvas]overlay=(W-w)/2:(H-h)/2:format=auto:shortest=1,setsar=1[v]"
    )


def build_single_image_filter(bg_color, blur_amount, distance_amount, opacity_percent):
    shadow_x = max(0, int(round(distance_amount * 2.2)))
    shadow_y = max(0, int(round(distance_amount * 2.8)))
    alpha = max(0.0, min(1.0, opacity_percent / 100))
    blur = max(0, int(blur_amount))
    shadow_pad = max(max(1, blur) * 3, max(shadow_x, shadow_y) * 3)

    if blur <= 0:
        return (
            f"color=c={bg_color}:s=1080x1920[bg];"
            "[0:v]scale=1000:1840:force_original_aspect_ratio=decrease,"
            "format=rgba,pad=1000:1840:(ow-iw)/2:(oh-ih)/2:color=black@0,setsar=1,"
            "split=2[img_main][shadow_src];"
            f"[shadow_src]colorchannelmixer="
            f"rr=0:rg=0:rb=0:ra=0:"
            f"gr=0:gg=0:gb=0:ga=0:"
            f"br=0:bg=0:bb=0:ba=0:"
            f"ar=0:ag=0:ab=0:aa={alpha}[shadow];"
            f"[bg][shadow]overlay=(W-w)/2+{shadow_x}:(H-h)/2+{shadow_y}:format=auto[bg_shadow];"
            "[bg_shadow][img_main]overlay=(W-w)/2:(H-h)/2:format=auto,format=rgb24[v]"
        )

    return (
        f"color=c={bg_color}:s=1080x1920[bg];"
        "[0:v]scale=1000:1840:force_original_aspect_ratio=decrease,"
        "pad=1000:1840:(ow-iw)/2:(oh-ih)/2:color=black@0,setsar=1,"
        "format=rgba,split=2[img_main][shadow_src];"
        f"[img_main]pad=iw+{shadow_pad * 2}:ih+{shadow_pad * 2}:{shadow_pad}:{shadow_pad}:color=black@0[img_canvas];"
        f"[shadow_src]pad=iw+{shadow_pad * 2}:ih+{shadow_pad * 2}:{shadow_pad}:{shadow_pad}:color=black@0,"
        "colorchannelmixer="
        f"rr=0:rg=0:rb=0:ra=0:"
        f"gr=0:gg=0:gb=0:ga=0:"
        f"br=0:bg=0:bb=0:ba=0:"
        f"ar=0:ag=0:ab=0:aa={alpha},"
        f"boxblur=luma_radius={blur}:luma_power=1:chroma_radius={max(1, blur // 2)}:"
        f"chroma_power=1:alpha_radius={blur}:alpha_power=1[shadow];"
        f"[bg][shadow]overlay=(W-w)/2+{shadow_x}:(H-h)/2+{shadow_y}:format=auto[bg_shadow];"
        "[bg_shadow][img_canvas]overlay=(W-w)/2:(H-h)/2:format=auto,format=rgb24[v]"
    )


def run():
    folder = folder_var.get()
    duration_text = duration_var.get()
    bg_color = bg_color_var.get().strip()
    distance_amount = int(round(distance_var.get()))
    blur_amount = int(round(blur_var.get()))
    shadow_opacity = int(round(shadow_opacity_var.get()))
    use_shadow = bool(use_shadow_var.get())

    if not folder:
        messagebox.showerror("Error", "Please select a photo folder.")
        return

    try:
        duration = float(duration_text)
    except ValueError:
        messagebox.showerror("Error", "Please enter the photo duration as a number.")
        return

    if duration <= 0:
        messagebox.showerror("Error", "Photo duration must be greater than 0.")
        return

    if not 0 <= shadow_opacity <= 100:
        messagebox.showerror("Error", "Shadow opacity must be between 0 and 100.")
        return

    if not re.fullmatch(r"#[0-9a-fA-F]{6}", bg_color):
        messagebox.showerror(
            "Error",
            "Background color must use #RRGGBB format.\nExample: #FFFFFF",
        )
        return

    exts = (".jpg", ".jpeg", ".png")
    images = []
    for root, _, files in os.walk(folder):
        for file_name in files:
            if file_name.lower().endswith(exts):
                full_path = os.path.join(root, file_name)
                images.append((full_path, os.path.getmtime(full_path)))

    if not images:
        messagebox.showerror("Error", "No image files were found.")
        return

    images.sort(key=lambda item: item[1])
    image_paths = [item[0] for item in images]

    folder_name = os.path.basename(folder.rstrip("/\\"))
    output = os.path.join(folder, f"{folder_name}_slideshow.mp4")

    total_frames = int(len(image_paths) * duration * 24)

    set_status("Preparing images... (0%)", "working")
    set_progress(0)
    set_action_button_enabled(False)
    root_win.update()

    def do_ffmpeg():
        temp_dir = tempfile.mkdtemp(prefix="slideshow_frames_", dir=folder)
        list_path = os.path.join(folder, f"_filelist_{uuid.uuid4().hex}.txt")
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_path,
            "-filter_threads",
            "1",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-tune",
            "stillimage",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "fps=24,setsar=1",
            "-r",
            "24",
            "-progress",
            "pipe:2",
            output,
        ]

        try:
            proc = None
            rendered_paths = []
            image_filter = build_single_image_filter(
                bg_color,
                blur_amount if use_shadow else 0,
                distance_amount if use_shadow else 0,
                shadow_opacity if use_shadow else 0,
            )

            for index, image_path in enumerate(image_paths, start=1):
                rendered_path = os.path.join(temp_dir, f"frame_{index:05d}.png")
                render_cmd = [
                    FFMPEG_PATH,
                    "-y",
                    "-i",
                    image_path,
                    "-filter_complex",
                    image_filter,
                    "-map",
                    "[v]",
                    "-frames:v",
                    "1",
                    rendered_path,
                ]
                render_proc = subprocess.run(
                    render_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if render_proc.returncode != 0:
                    raise RuntimeError(
                        f"Failed to preprocess image:\n{image_path}\n\n{render_proc.stderr.strip()}"
                    )
                rendered_paths.append(rendered_path)
                prep_pct = int(index / len(image_paths) * 35)
                set_status(f"Preparing images... ({prep_pct}%)", "working")
                set_progress(prep_pct)
                root_win.update_idletasks()

            with open(list_path, "w", encoding="utf-8") as file_list:
                for rendered_path in rendered_paths:
                    file_list.write(f"file '{rendered_path}'\n")
                    file_list.write(f"duration {duration}\n")
                file_list.write(f"file '{rendered_paths[-1]}'\n")

            set_status("Creating video... (35%)", "working")
            set_progress(35)
            root_win.update_idletasks()

            proc = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

            log_path = os.path.join(BASE_DIR, "ffmpeg_log.txt")
            stderr_lines = []
            with open(log_path, "w", encoding="utf-8") as log_f:
                log_f.write(f"CMD: {' '.join(cmd)}\n\n")
                log_f.write(f"IMAGES ({len(image_paths)}):\n")
                for p in image_paths:
                    log_f.write(f"  {p}\n")
                log_f.write("\nFFMPEG OUTPUT:\n")
                for line in proc.stderr:
                    stderr_lines.append(line)
                    log_f.write(line)
                    log_f.flush()
                    match = re.search(r"frame=\s*(\d+)", line)
                    if match and total_frames > 0:
                        frame = int(match.group(1))
                        pct = min(35 + int(frame / total_frames * 64), 99)
                        set_status(f"Creating video... ({pct}%)", "working")
                        set_progress(pct)
                        root_win.update_idletasks()

            proc.wait()
            if proc.stderr:
                proc.stderr.close()

            if proc.returncode == 0:
                set_progress(100)
                set_status("Done!", "success")
                messagebox.showinfo("Done!", f"Video saved to:\n{output}")
                return

            error_detail = "".join(stderr_lines[-20:]).strip()
            set_status("Error", "error")
            messagebox.showerror("Error", f"Failed to create the video.\n\nLog: {log_path}\n\n{error_detail}")
        except Exception as exc:
            set_status("Error", "error")
            messagebox.showerror("Error", str(exc))
        finally:
            if os.path.exists(list_path):
                try:
                    os.remove(list_path)
                except OSError:
                    pass
            shutil.rmtree(temp_dir, ignore_errors=True)
            set_action_button_enabled(True)

    threading.Thread(target=do_ffmpeg, daemon=True).start()

enable_dpi_awareness()
hide_console_window()
root_win = tk.Tk()
root_win.title("Slideshow Maker")
root_win.geometry("560x1120")
root_win.resizable(False, False)
root_win.configure(bg="#eef4f8")

GRAD_TOP = (149, 216, 255)   # #95d8ff
GRAD_BOT = (255, 255, 255)   # #ffffff
GRAD_MID = "#caebff"         # frame background colour (gradient midpoint)

PALETTE = {
    "app_bg": GRAD_MID,
    "card_bg": "#fbfdff",
    "card_border": "#d9e5ee",
    "text": "#15232d",
    "muted": "#6f8795",
    "soft_text": "#92a6b3",
    "accent": "#64dbff",
    "accent_hover": "#4dcef5",
    "accent_soft": "#e6f9ff",
    "accent_soft_2": "#f2fcff",
    "track": "#d7e5ee",
    "track_fill": "#b9d9eb",
    "progress_trough": "#dbe8f0",
    "success": "#8edb89",
    "shadow_soft": "#dde7ef",
    "shadow_far": "#edf4f8",
    "card_tint": "#f8fcff",
    "card_tint_2": "#ffffff",
    "scroll_track": "#b8e0f7",
    "scroll_thumb": "#7ec9f0",
    "scroll_thumb_hover": "#5cbde8",
}

style = ttk.Style()
try:
    style.theme_use("clam")
except tk.TclError:
    pass
style.configure(".", background=PALETTE["app_bg"], foreground=PALETTE["text"])
style.configure(
    "Card.TFrame",
    background=PALETTE["card_bg"],
    borderwidth=1,
    relief="solid",
)
style.configure(
    "CardTitle.TLabel",
    background=PALETTE["card_bg"],
    foreground=PALETTE["text"],
    font=("Segoe UI Semibold", 11),
)
style.configure(
    "CardBody.TLabel",
    background=PALETTE["card_bg"],
    foreground=PALETTE["muted"],
    font=("Segoe UI", 9),
)
style.configure(
    "Value.TEntry",
    fieldbackground="#ffffff",
    foreground=PALETTE["text"],
    bordercolor=PALETTE["card_border"],
    lightcolor=PALETTE["card_border"],
    darkcolor=PALETTE["card_border"],
    insertcolor=PALETTE["accent"],
    padding=(10, 8),
    relief="flat",
)
style.map(
    "Value.TEntry",
    bordercolor=[("focus", PALETTE["accent"])],
    lightcolor=[("focus", PALETTE["accent"])],
    darkcolor=[("focus", PALETTE["accent"])],
)
style.configure(
    "Visible.Horizontal.TProgressbar",
    troughcolor=PALETTE["progress_trough"],
    background=PALETTE["accent"],
    bordercolor=PALETTE["progress_trough"],
    lightcolor=PALETTE["accent"],
    darkcolor=PALETTE["accent"],
)
style.configure(
    "Accent.Horizontal.TScale",
    background=PALETTE["card_bg"],
    troughcolor=PALETTE["track"],
    bordercolor=PALETTE["track"],
    lightcolor=PALETTE["track"],
    darkcolor=PALETTE["track"],
)
style.configure(
    "Plain.Vertical.TScrollbar",
    troughcolor=PALETTE["app_bg"],
    background=PALETTE["app_bg"],
    bordercolor=PALETTE["app_bg"],
    arrowcolor=PALETTE["app_bg"],
    darkcolor=PALETTE["app_bg"],
    lightcolor=PALETTE["app_bg"],
)

folder_var = tk.StringVar()
duration_var = tk.StringVar(value="0.5")
bg_color_var = tk.StringVar(value="#f2f2f2")
blur_var = tk.DoubleVar(value=5)
distance_var = tk.DoubleVar(value=6)
shadow_opacity_var = tk.DoubleVar(value=35)
use_shadow_var = tk.BooleanVar(value=True)
status_var = tk.StringVar(value="")

background_canvas = tk.Canvas(
    root_win,
    bg=PALETTE["app_bg"],
    highlightthickness=0,
    bd=0,
    relief="flat",
    width=468,
    height=900,
)
background_canvas.place(x=0, y=0, relwidth=1, relheight=1)
_band = 3
for _y in range(0, 1400, _band):
    _t = min(1.0, _y / 1120)
    _r = int(GRAD_TOP[0] + (GRAD_BOT[0] - GRAD_TOP[0]) * _t)
    _g = int(GRAD_TOP[1] + (GRAD_BOT[1] - GRAD_TOP[1]) * _t)
    _b = int(GRAD_TOP[2] + (GRAD_BOT[2] - GRAD_TOP[2]) * _t)
    background_canvas.create_rectangle(
        0, _y, 700, _y + _band, fill=f"#{_r:02x}{_g:02x}{_b:02x}", outline=""
    )

main_frame = tk.Frame(root_win, bg=PALETTE["app_bg"])
content_shell = tk.Frame(root_win, bg=PALETTE["app_bg"])
content_shell.pack(fill="both", expand=True, padx=18, pady=18)

scrollbar_shell = tk.Frame(content_shell, bg=PALETTE["app_bg"], width=18)
scrollbar_shell.pack(side="right", fill="y", padx=(10, 0))
scrollbar_shell.pack_propagate(False)

scrollbar = tk.Canvas(
    scrollbar_shell,
    bg=PALETTE["app_bg"],
    highlightthickness=0,
    bd=0,
    width=18,
)
scrollbar.pack(fill="y", expand=True)

content_canvas = tk.Canvas(
    content_shell,
    bg=PALETTE["app_bg"],
    highlightthickness=0,
    bd=0,
)
content_canvas.pack(side="left", fill="both", expand=True)

main_frame = tk.Frame(content_canvas, bg=PALETTE["app_bg"])
canvas_window = content_canvas.create_window((0, 0), window=main_frame, anchor="nw")


def sync_scroll_region(_event=None):
    content_canvas.configure(scrollregion=content_canvas.bbox("all"))


def sync_canvas_window(event):
    content_canvas.itemconfigure(canvas_window, width=event.width)


def handle_mousewheel(event):
    delta = event.delta
    if delta == 0:
        return
    content_canvas.yview_scroll(int(-delta / 120), "units")


scroll_state = {"first": 0.0, "last": 1.0, "dragging": False, "hover": False, "anchor_y": 0}


def redraw_scrollbar():
    scrollbar.delete("all")
    width = max(scrollbar.winfo_width(), 18)
    height = max(scrollbar.winfo_height(), 40)

    scrollbar.create_polygon(
        rounded_rect_points(4, 4, width - 4, height - 4, 9),
        smooth=True,
        splinesteps=32,
        fill=PALETTE["scroll_track"],
        outline="",
    )

    first = scroll_state["first"]
    last = scroll_state["last"]
    thumb_top = 6 + (height - 12) * first
    thumb_bottom = 6 + (height - 12) * last
    if thumb_bottom - thumb_top < 44:
        thumb_bottom = min(height - 6, thumb_top + 44)
    thumb_fill = PALETTE["scroll_thumb_hover"] if scroll_state["hover"] or scroll_state["dragging"] else PALETTE["scroll_thumb"]

    scrollbar.create_polygon(
        rounded_rect_points(5, thumb_top, width - 5, thumb_bottom, 8),
        smooth=True,
        splinesteps=32,
        fill=thumb_fill,
        outline="",
        tags="thumb",
    )


def set_scrollbar(first, last):
    scroll_state["first"] = float(first)
    scroll_state["last"] = float(last)
    redraw_scrollbar()


def scroll_to_fraction(fraction):
    fraction = max(0.0, min(1.0, fraction))
    content_canvas.yview_moveto(fraction)


def scrollbar_press(event):
    width = max(scrollbar.winfo_width(), 18)
    height = max(scrollbar.winfo_height(), 40)
    first = scroll_state["first"]
    last = scroll_state["last"]
    thumb_top = 6 + (height - 12) * first
    thumb_bottom = 6 + (height - 12) * last
    if thumb_bottom - thumb_top < 44:
        thumb_bottom = min(height - 6, thumb_top + 44)

    if thumb_top <= event.y <= thumb_bottom:
        scroll_state["dragging"] = True
        scroll_state["anchor_y"] = event.y - thumb_top
    else:
        fraction = (event.y - 6) / max(1, height - 12)
        scroll_to_fraction(fraction)
    redraw_scrollbar()


def scrollbar_drag(event):
    if not scroll_state["dragging"]:
        return
    height = max(scrollbar.winfo_height(), 40)
    thumb_span = max(0.08, scroll_state["last"] - scroll_state["first"])
    usable = max(1, height - 12)
    thumb_top = event.y - scroll_state["anchor_y"]
    fraction = (thumb_top - 6) / usable
    scroll_to_fraction(max(0.0, min(1.0 - thumb_span, fraction)))


def scrollbar_release(_event):
    scroll_state["dragging"] = False
    redraw_scrollbar()


def scrollbar_hover(_event):
    scroll_state["hover"] = True
    redraw_scrollbar()


def scrollbar_leave(_event):
    scroll_state["hover"] = False
    if not scroll_state["dragging"]:
        redraw_scrollbar()


main_frame.bind("<Configure>", sync_scroll_region)
content_canvas.bind("<Configure>", sync_canvas_window)
content_canvas.bind_all("<MouseWheel>", handle_mousewheel)
content_canvas.configure(yscrollcommand=set_scrollbar)
scrollbar.bind("<Configure>", lambda _event: redraw_scrollbar())
scrollbar.bind("<Button-1>", scrollbar_press)
scrollbar.bind("<B1-Motion>", scrollbar_drag)
scrollbar.bind("<ButtonRelease-1>", scrollbar_release)
scrollbar.bind("<Enter>", scrollbar_hover)
scrollbar.bind("<Leave>", scrollbar_leave)


def rounded_rect_points(x1, y1, x2, y2, radius):
    radius = max(0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    return [
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    ]


def make_card(parent):
    shell = tk.Frame(parent, bg=PALETTE["app_bg"])
    shell.pack(fill="x", pady=(0, 38), padx=(6, 22))

    card_canvas = tk.Canvas(
        shell,
        bg=PALETTE["app_bg"],
        highlightthickness=0,
        bd=0,
        relief="flat",
        height=120,
    )
    card_canvas.pack(fill="both", expand=True)

    card = tk.Frame(card_canvas, bg=PALETTE["card_bg"], bd=0)
    card_window = card_canvas.create_window((2, 2), window=card, anchor="nw")

    def redraw(_event=None):
        width = max(card_canvas.winfo_width() - 2, 120)
        content_height = max(card.winfo_reqheight(), 72)
        height = content_height + 42
        card_canvas.configure(height=height)
        card_canvas.delete("panel")

        # Soft drop shadow — SVG spec: dx=7 dy=5 blur=4.3 opacity=0.25
        # Simulated with 10 clean layers, bounded within canvas
        _sn = 10
        _bg_r, _bg_g, _bg_b = 202, 235, 255   # GRAD_MID approx (#caebff)
        _sh_r, _sh_g, _sh_b = 112, 162, 191   # 25% black over GRAD_MID
        _card_x1, _card_y1 = 3, 4
        _card_x2, _card_y2 = width - 24, content_height + 12
        for _si in range(_sn, 0, -1):
            _frac = _si / _sn
            _expand = (_sn - _si) * 2
            _ox = 5   # x offset (≈ SVG dx=7 scaled)
            _oy = 7   # y offset (≈ SVG dy=5 scaled, slightly more for depth)
            _cr = int(_bg_r + (_sh_r - _bg_r) * _frac)
            _cg = int(_bg_g + (_sh_g - _bg_g) * _frac)
            _cb = int(_bg_b + (_sh_b - _bg_b) * _frac)
            _shadow_fill = f"#{_cr:02x}{_cg:02x}{_cb:02x}"
            _sx1 = max(0, _card_x1 + _ox - _expand)
            _sy1 = max(0, _card_y1 + _oy - _expand // 2)
            _sx2 = min(width - 2, _card_x2 + _ox + _expand)  # clamp to canvas
            _sy2 = _card_y2 + _oy + _expand
            _srad = max(24, 30 + _expand)
            card_canvas.create_polygon(
                rounded_rect_points(_sx1, _sy1, _sx2, _sy2, _srad),
                smooth=True,
                splinesteps=36,
                fill=_shadow_fill,
                outline="",
                tags="panel",
            )

        card_canvas.create_polygon(
            rounded_rect_points(3, 4, width - 24, content_height + 12, 30),
            smooth=True,
            splinesteps=36,
            fill=PALETTE["card_bg"],
            outline="",
            tags="panel",
        )
        card_canvas.tag_lower("panel")
        card_canvas.coords(card_window, 16, 16)
        card_canvas.itemconfigure(card_window, width=width - 44)

    card.bind("<Configure>", redraw)
    card_canvas.bind("<Configure>", redraw)
    shell.after(0, redraw)
    return card


def make_section_title(parent, eyebrow, title, body):
    header = tk.Frame(parent, bg=PALETTE["card_bg"])
    header.pack(fill="x", padx=18, pady=(16, 4))

    tk.Label(
        header,
        text=eyebrow,
        bg=PALETTE["card_bg"],
        fg=PALETTE["soft_text"],
        font=("Segoe UI Semibold", 8),
    ).pack(anchor="w")
    title_label = tk.Label(
        header,
        text=title,
        bg=PALETTE["card_bg"],
        fg=PALETTE["text"],
        font=("Segoe UI Semibold", 15),
        justify="left",
        anchor="w",
    )
    title_label.pack(anchor="w", fill="x", pady=(2, 0))
    body_label = tk.Label(
        header,
        text=body,
        bg=PALETTE["card_bg"],
        fg=PALETTE["muted"],
        font=("Segoe UI", 9),
        justify="left",
        anchor="w",
    )
    if body:
        body_label.pack(anchor="w", fill="x", pady=(5, 0))

    def update_wrap(event):
        wrap_length = max(260, event.width - 4)
        title_label.configure(wraplength=wrap_length)
        if body:
            body_label.configure(wraplength=wrap_length)

    header.bind("<Configure>", update_wrap)


def make_field_label(parent, text):
    tk.Label(
        parent,
        text=text,
        bg=PALETTE["card_bg"],
        fg=PALETTE["muted"],
        font=("Segoe UI Semibold", 8),
    ).pack(anchor="w")


def make_accent_button(parent, text, command, width=12):
    button = tk.Button(
        parent,
        text=text,
        command=command,
        bg=PALETTE["accent"],
        fg="white",
        activebackground=PALETTE["accent_hover"],
        activeforeground="white",
        relief="flat",
        bd=0,
        padx=14,
        pady=11,
        font=("Segoe UI Semibold", 9),
        cursor="hand2",
        width=width,
    )
    return button


def make_primary_canvas_button(parent, text, command, width=320, height=54):
    button = tk.Canvas(
        parent,
        width=width,
        height=height,
        bg=PALETTE["card_bg"],
        highlightthickness=0,
        bd=0,
        cursor="hand2",
    )
    state = {"enabled": True}

    def redraw(fill_color=None):
        fill = fill_color or (PALETTE["accent"] if state["enabled"] else "#c7d8e3")
        text_color = "white" if state["enabled"] else "#f8fbfd"
        button.delete("all")
        button.create_polygon(
            rounded_rect_points(1, 1, width - 1, height - 1, 18),
            smooth=True,
            splinesteps=32,
            fill=fill,
            outline="",
        )
        button.create_text(
            width / 2,
            height / 2,
            text=text,
            fill=text_color,
            font=("Segoe UI Semibold", 10),
        )

    def on_enter(_event):
        if state["enabled"]:
            redraw(PALETTE["accent_hover"])

    def on_leave(_event):
        redraw()

    def on_click(_event):
        if state["enabled"]:
            command()

    def set_enabled(enabled):
        state["enabled"] = enabled
        button.configure(cursor="hand2" if enabled else "arrow")
        redraw()

    button.bind("<Enter>", on_enter)
    button.bind("<Leave>", on_leave)
    button.bind("<Button-1>", on_click)
    button.set_enabled = set_enabled
    redraw()
    return button


def make_round_entry(parent, textvariable, width=180, height=44):
    shell = tk.Canvas(
        parent,
        width=width,
        height=height,
        bg=PALETTE["card_bg"],
        highlightthickness=0,
        bd=0,
    )
    entry = tk.Entry(
        shell,
        textvariable=textvariable,
        relief="flat",
        bd=0,
        highlightthickness=0,
        bg="#ffffff",
        fg=PALETTE["text"],
        insertbackground=PALETTE["accent"],
        font=("Segoe UI", 9),
    )
    window_id = shell.create_window(16, height / 2, window=entry, anchor="w")

    def redraw(_event=None):
        current_width = max(width, shell.winfo_width())
        current_height = max(height, shell.winfo_height())
        shell.configure(height=current_height)
        shell.delete("bg")
        shell.create_polygon(
            rounded_rect_points(1, 1, current_width - 1, current_height - 1, 16),
            smooth=True,
            splinesteps=32,
            fill="#ffffff",
            outline=PALETTE["card_border"],
            width=1,
            tags="bg",
        )
        shell.tag_lower("bg")
        shell.coords(window_id, 16, current_height / 2)
        shell.itemconfigure(window_id, width=max(40, current_width - 32), height=current_height - 12)

    shell.bind("<Configure>", redraw)
    shell.after(0, redraw)
    return shell, entry


def make_round_preview(parent, size=32):
    canvas = tk.Canvas(
        parent,
        width=size,
        height=size,
        bg=PALETTE["card_bg"],
        highlightthickness=0,
        bd=0,
    )

    def redraw(color=None):
        fill = color or bg_color_var.get()
        canvas.delete("all")
        canvas.create_polygon(
            rounded_rect_points(1, 1, size - 1, size - 1, 10),
            smooth=True,
            splinesteps=28,
            fill=fill,
            outline=PALETTE["card_border"],
            width=1,
        )

    canvas.redraw = redraw
    redraw()
    return canvas


def make_round_checkbox(parent, text, variable, command=None):
    row = tk.Frame(parent, bg=PALETTE["card_bg"])
    box = tk.Canvas(row, width=22, height=22, bg=PALETTE["card_bg"], highlightthickness=0, bd=0, cursor="hand2")
    box.pack(side="left")
    label = tk.Label(
        row,
        text=text,
        bg=PALETTE["card_bg"],
        fg=PALETTE["text"],
        font=("Segoe UI Semibold", 9),
        cursor="hand2",
    )
    label.pack(side="left", padx=(8, 0))

    def redraw(*_args):
        checked = bool(variable.get())
        box.delete("all")
        box.create_polygon(
            rounded_rect_points(1, 1, 21, 21, 7),
            smooth=True,
            splinesteps=24,
            fill=PALETTE["accent_soft_2"] if checked else "#ffffff",
            outline=PALETTE["card_border"],
            width=1,
        )
        if checked:
            box.create_line(6, 12, 10, 16, 16, 7, fill=PALETTE["accent"], width=2, capstyle=tk.ROUND, joinstyle=tk.ROUND)

    def toggle(_event=None):
        variable.set(not variable.get())
        redraw()
        if command:
            command()

    variable.trace_add("write", redraw)
    box.bind("<Button-1>", toggle)
    label.bind("<Button-1>", toggle)
    row.bind("<Button-1>", toggle)
    redraw()
    return row


def make_round_progress(parent, width=404, height=18):
    bar = tk.Canvas(parent, width=width, height=height, bg=PALETTE["card_bg"], highlightthickness=0, bd=0)
    state = {"value": 0}

    def draw():
        bar.delete("all")
        current_width = max(width, bar.winfo_width())
        ratio = state["value"] / 100
        bar.create_polygon(
            rounded_rect_points(1, 1, current_width - 1, height - 1, 8),
            smooth=True,
            splinesteps=24,
            fill=PALETTE["progress_trough"],
            outline="",
        )
        fill_width = max(12, 1 + (current_width - 2) * ratio) if state["value"] > 0 else 0
        if fill_width:
            bar.create_polygon(
                rounded_rect_points(1, 1, fill_width, height - 1, 8),
                smooth=True,
                splinesteps=24,
                fill=PALETTE["accent_soft"],
                outline="",
            )

    def set_value(value):
        state["value"] = max(0, min(100, value))
        draw()

    bar.bind("<Configure>", lambda _event: draw())
    bar.set_value = set_value
    draw()
    return bar


def make_value_pill(parent, variable, formatter):
    pill = tk.Canvas(
        parent,
        bg=PALETTE["card_bg"],
        width=56,
        height=28,
        highlightthickness=0,
        bd=0,
    )

    def refresh(*_args):
        text = formatter()
        width = max(46, 22 + len(text) * 7)
        pill.configure(width=width)
        pill.delete("all")
        pill.create_polygon(
            rounded_rect_points(1, 1, width - 1, 27, 12),
            smooth=True,
            splinesteps=28,
            fill=PALETTE["accent_soft_2"],
            outline="",
        )
        pill.create_text(
            width / 2,
            14,
            text=text,
            fill=PALETTE["accent_hover"],
            font=("Segoe UI Semibold", 8),
        )

    variable.trace_add("write", refresh)
    refresh()
    return pill


def make_slider_row(parent, label_text, variable, from_, to, length, formatter):
    row = tk.Frame(parent, bg=PALETTE["card_bg"])
    row.pack(fill="x", pady=(0, 10))

    header = tk.Frame(row, bg=PALETTE["card_bg"])
    header.pack(fill="x")
    make_field_label(header, label_text)
    value_pill = make_value_pill(header, variable, formatter)
    value_pill.pack(side="right")

    slider_canvas = tk.Canvas(
        row,
        width=length,
        height=30,
        bg=PALETTE["card_bg"],
        highlightthickness=0,
        bd=0,
    )
    slider_canvas.pack(anchor="w", pady=(4, 0))

    def draw_slider(*_args):
        slider_canvas.delete("all")
        current = max(from_, min(to, variable.get()))
        ratio = 0 if to == from_ else (current - from_) / (to - from_)
        left = 8
        right = length - 8
        center_y = 15
        thumb_x = left + (right - left) * ratio

        slider_canvas.create_polygon(
            rounded_rect_points(left, center_y - 4, right, center_y + 4, 4),
            smooth=True,
            splinesteps=28,
            fill=PALETTE["track"],
            outline="",
        )
        slider_canvas.create_polygon(
            rounded_rect_points(left, center_y - 4, thumb_x, center_y + 4, 4),
            smooth=True,
            splinesteps=28,
            fill=PALETTE["track_fill"],
            outline="",
        )
        slider_canvas.create_oval(
            thumb_x - 10,
            center_y - 10,
            thumb_x + 10,
            center_y + 10,
            fill="#ffffff",
            outline=PALETTE["card_border"],
            width=1,
        )
        slider_canvas.create_oval(
            thumb_x - 5,
            center_y - 5,
            thumb_x + 5,
            center_y + 5,
            fill=PALETTE["accent"],
            outline="",
        )

    def set_from_x(x):
        left = 8
        right = length - 8
        ratio = (x - left) / max(1, right - left)
        snapped = round(from_ + max(0.0, min(1.0, ratio)) * (to - from_))
        variable.set(snapped)

    slider_canvas.bind("<Button-1>", lambda event: set_from_x(event.x))
    slider_canvas.bind("<B1-Motion>", lambda event: set_from_x(event.x))
    variable.trace_add("write", draw_slider)
    draw_slider()

    return row


hero_card = make_card(main_frame)
hero_top = tk.Frame(hero_card, bg=PALETTE["card_bg"])
hero_top.pack(fill="x", padx=18, pady=(16, 4))

status_chip = tk.Frame(hero_top, bg=PALETTE["card_bg"])
status_chip.pack(anchor="w")
status_dot = tk.Canvas(
    status_chip,
    width=10,
    height=10,
    highlightthickness=0,
    bg=PALETTE["card_bg"],
)
status_dot.pack(side="left")
status_dot.create_oval(1, 1, 9, 9, fill=PALETTE["accent"], outline="")
tk.Label(
    status_chip,
    text="SLIDESHOW STUDIO",
    bg=PALETTE["card_bg"],
    fg=PALETTE["soft_text"],
    font=("Segoe UI Semibold", 8),
).pack(side="left", padx=(6, 0))

hero_title_label = tk.Label(
    hero_card,
    text="사진 슬라이드쇼 변환기",
    bg=PALETTE["card_bg"],
    fg=PALETTE["text"],
    font=("Segoe UI Semibold", 18),
    justify="left",
    anchor="w",
)
hero_title_label.pack(anchor="w", fill="x", padx=18, pady=(4, 18))
hero_body_label = tk.Label(
    hero_card,
    text="",
    bg=PALETTE["card_bg"],
    fg=PALETTE["muted"],
    font=("Segoe UI", 9),
    justify="left",
    anchor="w",
)


def update_hero_wrap(event):
    wrap_length = max(260, event.width - 40)
    hero_title_label.configure(wraplength=wrap_length)


hero_card.bind("<Configure>", update_hero_wrap)

input_card = make_card(main_frame)
make_section_title(
    input_card,
    "INPUT",
    "기본 설정",
    "",
)

folder_wrap = tk.Frame(input_card, bg=PALETTE["card_bg"])
folder_wrap.pack(fill="x", padx=18, pady=(6, 0))
make_field_label(folder_wrap, "Photo folder")
folder_row = tk.Frame(folder_wrap, bg=PALETTE["card_bg"])
folder_row.pack(fill="x", pady=(7, 0))
folder_entry_shell, folder_entry = make_round_entry(folder_row, folder_var, width=302, height=46)
folder_entry_shell.pack(side="left", fill="x", expand=True)
browse_btn = make_primary_canvas_button(folder_row, "Browse", select_folder, width=122, height=46)
browse_btn.pack(side="left", padx=(10, 0))

duration_wrap = tk.Frame(input_card, bg=PALETTE["card_bg"])
duration_wrap.pack(fill="x", padx=18, pady=(14, 16))
make_field_label(duration_wrap, "Seconds per photo")
duration_entry_shell, duration_entry = make_round_entry(duration_wrap, duration_var, width=118, height=46)
duration_entry_shell.pack(anchor="w", pady=(7, 0))

visual_card = make_card(main_frame)
make_section_title(
    visual_card,
    "LOOK",
    "배경과 깊이감",
    "",
)

bg_wrap = tk.Frame(visual_card, bg=PALETTE["card_bg"])
bg_wrap.pack(fill="x", padx=18, pady=(6, 0))
make_field_label(bg_wrap, "Background color (HEX)")
bg_frame = tk.Frame(bg_wrap, bg=PALETTE["card_bg"])
bg_frame.pack(fill="x", pady=(7, 0))
bg_entry_shell, bg_entry = make_round_entry(bg_frame, bg_color_var, width=182, height=46)
bg_entry_shell.pack(side="left")
pick_btn = make_primary_canvas_button(bg_frame, "Pick color", select_bg_color, width=114, height=46)
pick_btn.pack(side="left", padx=(10, 0))
bg_preview = make_round_preview(bg_frame, 40)
bg_preview.pack(side="left", padx=(10, 0))

shadow_toggle = make_round_checkbox(visual_card, "Enable shadow", use_shadow_var, update_shadow_controls)
shadow_toggle.pack(anchor="w", padx=18, pady=(14, 0))

shadow_controls_frame = tk.Frame(visual_card, bg=PALETTE["card_bg"])
make_slider_row(
    shadow_controls_frame,
    "Shadow blur",
    blur_var,
    0,
    10,
    388,
    lambda: f"{int(round(blur_var.get()))}",
)
make_slider_row(
    shadow_controls_frame,
    "Shadow distance",
    distance_var,
    0,
    10,
    388,
    lambda: f"{int(round(distance_var.get()))}",
)
make_slider_row(
    shadow_controls_frame,
    "Shadow opacity",
    shadow_opacity_var,
    0,
    100,
    388,
    lambda: f"{int(round(shadow_opacity_var.get()))}%",
)
make_field_label(shadow_controls_frame, "Shadow preview")
example_canvas = tk.Canvas(
    shadow_controls_frame,
    width=256,
    height=196,
    highlightthickness=1,
    highlightbackground=PALETTE["card_border"],
    bg="#f2f2f2",
)
example_canvas.pack(anchor="w", pady=(7, 0))

action_card = make_card(main_frame)
make_section_title(
    action_card,
    "EXPORT",
    "영상 만들기",
    "",
)

action_meta = tk.Frame(action_card, bg=PALETTE["card_bg"])
action_meta.pack(fill="x", padx=18, pady=(0, 6))

meta_left = tk.Frame(action_meta, bg=PALETTE["card_bg"])
meta_left.pack(side="left")
tk.Label(
    meta_left,
    text="Status",
    bg=PALETTE["card_bg"],
    fg=PALETTE["soft_text"],
    font=("Segoe UI Semibold", 8),
).pack(anchor="w")

status_badge_text_var = tk.StringVar(value="Ready")
status_badge = tk.Label(
    meta_left,
    textvariable=status_badge_text_var,
    bg=PALETTE["accent_soft"],
    fg=PALETTE["accent_hover"],
    font=("Segoe UI Semibold", 8),
    padx=10,
    pady=5,
)
status_badge.pack(anchor="w", pady=(5, 0))

meta_right = tk.Frame(action_meta, bg=PALETTE["card_bg"])
meta_right.pack(side="right")
tk.Label(
    meta_right,
    text="Output",
    bg=PALETTE["card_bg"],
    fg=PALETTE["soft_text"],
    font=("Segoe UI Semibold", 8),
).pack(anchor="e")
tk.Label(
    meta_right,
    text="MP4 / H.264",
    bg=PALETTE["card_bg"],
    fg=PALETTE["text"],
    font=("Segoe UI Semibold", 10),
).pack(anchor="e", pady=(5, 0))

bottom_frame = tk.Frame(action_card, bg=PALETTE["card_bg"])
bottom_frame.pack(fill="x", padx=18, pady=(6, 16))

btn = make_primary_canvas_button(bottom_frame, "Make Video", run, width=404, height=48)
btn.pack(anchor="w", pady=(0, 10))

progress_bar = make_round_progress(bottom_frame, width=404, height=16)
progress_bar.pack(anchor="w", pady=(0, 10))

status_label = tk.Label(
    bottom_frame,
    textvariable=status_var,
    bg=PALETTE["card_bg"],
    fg=PALETTE["muted"],
    font=("Segoe UI", 9),
)
status_label.pack(anchor="w")
set_action_button_enabled(True)
set_status("Ready to export.", "idle")

bg_color_var.trace_add("write", update_shadow_example)
bg_color_var.trace_add("write", lambda *_args: "bg_preview" in globals() and bg_preview.redraw(bg_color_var.get()))
blur_var.trace_add("write", update_shadow_example)
shadow_opacity_var.trace_add("write", update_shadow_example)
distance_var.trace_add("write", update_shadow_example)
use_shadow_var.trace_add("write", update_shadow_example)
update_shadow_controls()
update_shadow_example()

root_win.mainloop()
