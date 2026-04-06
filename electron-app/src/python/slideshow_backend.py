import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid


DEFAULT_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PROJECT_ROOT = os.environ.get("SLIDESHOW_PROJECT_ROOT", DEFAULT_PROJECT_ROOT)
FFMPEG_PATH = os.environ.get(
    "SLIDESHOW_FFMPEG_PATH",
    os.path.join(PROJECT_ROOT, "ffmpeg-8.1-essentials_build", "bin", "ffmpeg.exe"),
)


def emit(event_type, **data):
    payload = {"type": event_type, **data}
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


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


def collect_images(folder):
    exts = (".jpg", ".jpeg", ".png")
    images = []
    for root, _, files in os.walk(folder):
        for file_name in files:
            if file_name.lower().endswith(exts):
                full_path = os.path.join(root, file_name)
                images.append((full_path, os.path.getmtime(full_path)))

    images.sort(key=lambda item: item[1])
    return [item[0] for item in images]


def validate_args(args):
    if not args.folder:
        raise ValueError("Photo folder is required.")
    if not os.path.isdir(args.folder):
        raise ValueError("Selected photo folder does not exist.")
    if args.duration <= 0:
        raise ValueError("Duration must be greater than 0.")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", args.bg_color):
        raise ValueError("Background color must use #RRGGBB format.")
    if not 0 <= args.shadow_opacity <= 100:
        raise ValueError("Shadow opacity must be between 0 and 100.")
    if not os.path.exists(FFMPEG_PATH):
        raise ValueError(f"ffmpeg.exe was not found.\nExpected path: {FFMPEG_PATH}")


def run_ffmpeg_render(args):
    validate_args(args)
    image_paths = collect_images(args.folder)
    if not image_paths:
        raise ValueError("No image files were found in the selected folder.")

    folder_name = os.path.basename(args.folder.rstrip("/\\"))
    output_path = os.path.join(args.folder, f"{folder_name}_slideshow.mp4")
    temp_dir = tempfile.mkdtemp(prefix="slideshow_frames_", dir=args.folder)
    list_path = os.path.join(args.folder, f"_filelist_{uuid.uuid4().hex}.txt")
    log_path = os.path.join(PROJECT_ROOT, "ffmpeg_log.txt")
    total_frames = max(1, int(len(image_paths) * args.duration * 24))

    image_filter = build_single_image_filter(
        args.bg_color,
        args.blur if args.use_shadow else 0,
        args.distance if args.use_shadow else 0,
        args.shadow_opacity if args.use_shadow else 0,
    )

    emit("progress", phase="prepare", percent=0, message="Preparing images... (0%)")

    try:
        rendered_paths = []
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
            emit("progress", phase="prepare", percent=prep_pct, message=f"Preparing images... ({prep_pct}%)")

        with open(list_path, "w", encoding="utf-8") as file_list:
            for rendered_path in rendered_paths:
                file_list.write(f"file '{rendered_path}'\n")
                file_list.write(f"duration {args.duration}\n")
            file_list.write(f"file '{rendered_paths[-1]}'\n")

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
            output_path,
        ]

        emit("progress", phase="render", percent=35, message="Creating video... (35%)")

        stderr_lines = []
        with open(log_path, "w", encoding="utf-8") as log_f:
            log_f.write(f"CMD: {' '.join(cmd)}\n\n")
            log_f.write(f"IMAGES ({len(image_paths)}):\n")
            for image_path in image_paths:
                log_f.write(f"  {image_path}\n")
            log_f.write("\nFFMPEG OUTPUT:\n")

            proc = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

            for line in proc.stderr:
                stderr_lines.append(line)
                log_f.write(line)
                log_f.flush()
                match = re.search(r"frame=\s*(\d+)", line)
                if match:
                    frame = int(match.group(1))
                    pct = min(35 + int(frame / total_frames * 64), 99)
                    emit("progress", phase="render", percent=pct, message=f"Creating video... ({pct}%)")

            proc.wait()
            if proc.returncode != 0:
                detail = "".join(stderr_lines[-20:]).strip()
                raise RuntimeError(detail or "Failed to create the video.")

        emit("done", outputPath=output_path, logPath=log_path)
    finally:
        if os.path.exists(list_path):
            try:
                os.remove(list_path)
            except OSError:
                pass
        shutil.rmtree(temp_dir, ignore_errors=True)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", required=True)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--bg-color", required=True)
    parser.add_argument("--blur", type=int, default=5)
    parser.add_argument("--distance", type=int, default=6)
    parser.add_argument("--shadow-opacity", type=int, default=35)
    parser.add_argument("--use-shadow", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        run_ffmpeg_render(args)
        return 0
    except Exception as exc:
        emit("error", message=str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
