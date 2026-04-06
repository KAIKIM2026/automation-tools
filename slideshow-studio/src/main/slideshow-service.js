const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const { app } = require("electron");

let activeJob = null;

function hasActiveJob() {
  return activeJob !== null;
}

function createError(message) {
  return new Error(message);
}

function getResourceRoot(projectRoot) {
  if (app.isPackaged) {
    return process.resourcesPath;
  }

  return projectRoot;
}

function getFfmpegPath(projectRoot) {
  const resourceRoot = getResourceRoot(projectRoot);
  const candidates = [
    path.join(resourceRoot, "ffmpeg", "ffmpeg.exe"),
    path.join(resourceRoot, "ffmpeg-8.1-essentials_build", "bin", "ffmpeg.exe")
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  throw createError("ffmpeg.exe was not found.");
}

function getBundledBackendExecutable(projectRoot) {
  const resourceRoot = getResourceRoot(projectRoot);
  const candidates = [
    path.join(resourceRoot, "backend", "slideshow_backend.exe"),
    path.join(resourceRoot, "dist-python", "slideshow_backend.exe")
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  return "";
}

function getPythonExecutable() {
  const candidates = [
    process.env.SLIDESHOW_PYTHON,
    path.join(process.env.USERPROFILE || "", "AppData", "Local", "Programs", "Python", "Python314", "python.exe")
  ].filter(Boolean);

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  throw createError("Python executable was not found. Set SLIDESHOW_PYTHON or install Python 3.14 in the default location.");
}

function getBackendLaunch(projectRoot) {
  const bundledExecutable = getBundledBackendExecutable(projectRoot);
  if (bundledExecutable) {
    return {
      command: bundledExecutable,
      args: []
    };
  }

  return {
    command: getPythonExecutable(),
    args: [path.join(projectRoot, "slideshow-studio", "src", "python", "slideshow_backend.py")]
  };
}

function startSlideshowJob(payload, hooks) {
  if (activeJob) {
    throw createError("A slideshow job is already running.");
  }

  const backendLaunch = getBackendLaunch(hooks.projectRoot);
  const ffmpegPath = getFfmpegPath(hooks.projectRoot);
  const args = [
    ...backendLaunch.args,
    "--folder",
    String(payload.folder || ""),
    "--duration",
    String(payload.duration ?? ""),
    "--bg-color",
    String(payload.bgColor || ""),
    "--blur",
    String(payload.blurAmount ?? 5),
    "--distance",
    String(payload.distanceAmount ?? 6),
    "--shadow-opacity",
    String(payload.shadowOpacity ?? 35)
  ];

  if (payload.useShadow) {
    args.push("--use-shadow");
  }

  const proc = spawn(backendLaunch.command, args, {
    cwd: hooks.projectRoot,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      SLIDESHOW_PROJECT_ROOT: getResourceRoot(hooks.projectRoot),
      SLIDESHOW_FFMPEG_PATH: ffmpegPath
    }
  });

  activeJob = {
    proc,
    cancelled: false
  };

  return new Promise((resolve, reject) => {
    let stdoutBuffer = "";
    let stderrText = "";
    let settled = false;
    let donePayload = null;
    let errorPayload = null;

    const finish = (handler, value) => {
      if (settled) {
        return;
      }
      settled = true;
      activeJob = null;
      handler(value);
    };

    proc.stdout.on("data", (chunk) => {
      stdoutBuffer += chunk.toString("utf8");

      let newlineIndex = stdoutBuffer.indexOf("\n");
      while (newlineIndex >= 0) {
        const line = stdoutBuffer.slice(0, newlineIndex).trim();
        stdoutBuffer = stdoutBuffer.slice(newlineIndex + 1);

        if (line) {
          try {
            const event = JSON.parse(line);
            if (event.type === "progress") {
              hooks.sendProgress(event);
            } else if (event.type === "done") {
              donePayload = event;
              hooks.sendDone(event);
            } else if (event.type === "error") {
              errorPayload = event;
              hooks.sendError({
                ...event,
                cancelled: activeJob ? activeJob.cancelled : false
              });
            }
          } catch (_error) {
            stderrText += `${line}\n`;
          }
        }

        newlineIndex = stdoutBuffer.indexOf("\n");
      }
    });

    proc.stderr.on("data", (chunk) => {
      stderrText += chunk.toString("utf8");
    });

    proc.on("error", (error) => {
      finish(reject, error);
    });

    proc.on("close", (code) => {
      if (code === 0 && donePayload) {
        finish(resolve, donePayload);
        return;
      }

      if (activeJob && activeJob.cancelled) {
        finish(reject, createError("The job was cancelled."));
        return;
      }

      const message = errorPayload?.message || stderrText.trim() || "Python backend failed.";
      finish(reject, createError(message));
    });
  });
}

function cancelSlideshowJob() {
  if (!activeJob) {
    return;
  }

  activeJob.cancelled = true;
  if (activeJob.proc && !activeJob.proc.killed) {
    activeJob.proc.kill();
  }
}

module.exports = {
  cancelSlideshowJob,
  hasActiveJob,
  startSlideshowJob
};
