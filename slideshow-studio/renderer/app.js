const folderInput = document.querySelector("#folderInput");
const durationInput = document.querySelector("#durationInput");
const bgColorInput = document.querySelector("#bgColorInput");
const bgColorPicker = document.querySelector("#bgColorPicker");
const shadowToggle = document.querySelector("#shadowToggle");
const shadowControls = document.querySelector("#shadowControls");
const blurInput = document.querySelector("#blurInput");
const distanceInput = document.querySelector("#distanceInput");
const opacityInput = document.querySelector("#opacityInput");
const blurValue = document.querySelector("#blurValue");
const distanceValue = document.querySelector("#distanceValue");
const opacityValue = document.querySelector("#opacityValue");
const previewStage = document.querySelector("#previewStage");
const previewShadow = document.querySelector("#previewShadow");
const statusBadge = document.querySelector("#statusBadge");
const statusMessage = document.querySelector("#statusMessage");
const resultMessage = document.querySelector("#resultMessage");
const progressBar = document.querySelector("#progressBar");
const startButton = document.querySelector("#startButton");
const cancelButton = document.querySelector("#cancelButton");
const pickFolderButton = document.querySelector("#pickFolderButton");

const state = {
  useShadow: true,
  running: false
};

function isHexColor(value) {
  return /^#[0-9a-fA-F]{6}$/.test(value);
}

function setShadowState(enabled) {
  state.useShadow = enabled;
  shadowToggle.classList.toggle("is-active", enabled);
  shadowToggle.setAttribute("aria-pressed", String(enabled));
  shadowToggle.textContent = enabled ? "Enabled" : "Disabled";
  shadowControls.hidden = !enabled;
  updatePreview();
}

function setBusy(running) {
  state.running = running;
  startButton.disabled = running;
  cancelButton.disabled = !running;
  pickFolderButton.disabled = running;
}

function setStatus(tone, message) {
  const badgeText =
    tone === "working" ? "Working" :
    tone === "success" ? "Done" :
    tone === "error" ? "Error" :
    "Ready";

  statusBadge.className = `status-badge ${tone}`;
  statusBadge.textContent = badgeText;
  statusMessage.textContent = message;
}

function setProgress(percent) {
  progressBar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
}

function syncSliderLabels() {
  blurValue.textContent = blurInput.value;
  distanceValue.textContent = distanceInput.value;
  opacityValue.textContent = `${opacityInput.value}%`;
}

function syncColorInputs(source) {
  const value = source.value.trim();
  if (!isHexColor(value)) {
    return;
  }

  bgColorInput.value = value;
  bgColorPicker.value = value.toLowerCase();
  updatePreview();
}

function updatePreview() {
  const bgColor = isHexColor(bgColorInput.value.trim()) ? bgColorInput.value.trim() : "#f2f2f2";
  const blur = Number(blurInput.value);
  const distance = Number(distanceInput.value);
  const opacity = Number(opacityInput.value) / 100;

  previewStage.style.background = bgColor;
  previewShadow.style.opacity = state.useShadow ? String(opacity) : "0";
  previewShadow.style.filter = `blur(${Math.max(1, blur * 2)}px)`;
  previewShadow.style.transform = `translate(${Math.round(distance * 2.4)}px, ${Math.round(distance * 2.9)}px)`;
}

function readPayload() {
  return {
    folder: folderInput.value.trim(),
    duration: Number(durationInput.value),
    bgColor: bgColorInput.value.trim(),
    useShadow: state.useShadow,
    blurAmount: Number(blurInput.value),
    distanceAmount: Number(distanceInput.value),
    shadowOpacity: Number(opacityInput.value)
  };
}

async function startSlideshow() {
  resultMessage.textContent = "";
  setBusy(true);
  setStatus("working", "Preparing images... (0%)");
  setProgress(0);

  try {
    await window.slideshowApi.startSlideshow(readPayload());
  } catch (error) {
    setBusy(false);
    setStatus("error", error.message || "Failed to start slideshow.");
    resultMessage.textContent = error.details || "";
  }
}

pickFolderButton.addEventListener("click", async () => {
  const selected = await window.slideshowApi.pickFolder();
  if (selected) {
    folderInput.value = selected;
  }
});

shadowToggle.addEventListener("click", () => {
  setShadowState(!state.useShadow);
});

bgColorInput.addEventListener("input", () => syncColorInputs(bgColorInput));
bgColorPicker.addEventListener("input", () => syncColorInputs(bgColorPicker));

startButton.addEventListener("click", startSlideshow);
cancelButton.addEventListener("click", async () => {
  await window.slideshowApi.cancelSlideshow();
});

[blurInput, distanceInput, opacityInput].forEach((input) => {
  input.addEventListener("input", () => {
    syncSliderLabels();
    updatePreview();
  });
});

window.slideshowApi.onProgress((data) => {
  setStatus("working", data.message);
  setProgress(data.percent);
});

window.slideshowApi.onDone((data) => {
  setBusy(false);
  setStatus("success", "Done!");
  setProgress(100);
  resultMessage.textContent = `Video saved to:\n${data.outputPath}`;
});

window.slideshowApi.onError((data) => {
  setBusy(false);
  if (data.cancelled) {
    setStatus("idle", "Cancelled.");
    setProgress(0);
    resultMessage.textContent = "";
    return;
  }

  setStatus("error", data.message);
  resultMessage.textContent = data.details || "";
});

async function init() {
  syncSliderLabels();
  setShadowState(true);
  syncColorInputs(bgColorInput);
  setStatus("idle", "Ready to export.");
  setProgress(0);

  const config = await window.slideshowApi.getConfig();
  if (config.busy) {
    setBusy(true);
    setStatus("working", "Another slideshow job is already running.");
    return;
  }

  setBusy(false);
}

init().catch((error) => {
  setBusy(false);
  setStatus("error", error.message || "Failed to initialize app.");
});
