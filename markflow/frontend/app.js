/* ============================================================
   MarkFlow — Frontend State Machine & API Client
   ============================================================ */

(function () {
  "use strict";

  var API_URL = "http://localhost:8000/generate";
  var TIMEOUT_MS = 120000;

  var states = {
    IDLE: "idle",
    LOADING: "loading",
    SUCCESS: "success",
    ERROR: "error",
  };

  var currentState = states.IDLE;
  var pdfBlobUrl = null;

  // DOM References
  var contentInput = document.getElementById("content-input");
  var stylePromptInput = document.getElementById("style-prompt-input");
  var cssToggle = document.getElementById("css-toggle");
  var cssPanel = document.getElementById("css-panel");
  var generateBtn = document.getElementById("generate-btn");
  var loadingState = document.getElementById("loading-state");
  var errorState = document.getElementById("error-state");
  var errorMessage = document.getElementById("error-message");
  var successState = document.getElementById("success-state");
  var pdfPreview = document.getElementById("pdf-preview");
  var downloadBtn = document.getElementById("download-btn");
  var resetBtn = document.getElementById("reset-btn");
  var idleState = document.getElementById("idle-state");
  var charCount = document.getElementById("char-count");

  // --- Character Count ---
  function updateCharCount() {
    if (charCount && contentInput) {
      var len = contentInput.value.length;
      charCount.textContent = len.toLocaleString();
    }
  }

  if (contentInput && charCount) {
    contentInput.addEventListener("input", updateCharCount);
    updateCharCount();
  }

  // --- State Machine ---
  function setState(newState, data) {
    if (currentState === states.SUCCESS && newState !== states.SUCCESS) {
      revokeBlobUrl();
    }

    // Hide all states
    if (idleState) idleState.classList.add("hidden");
    loadingState.classList.add("hidden");
    errorState.classList.add("hidden");
    successState.classList.add("hidden");

    var btnTextEl = generateBtn.querySelector(".btn__text");

    switch (newState) {
      case states.IDLE:
        generateBtn.disabled = false;
        if (btnTextEl) btnTextEl.textContent = "Generate PDF";
        else generateBtn.textContent = "Generate PDF";
        if (idleState) idleState.classList.remove("hidden");
        break;
      case states.LOADING:
        generateBtn.disabled = true;
        if (btnTextEl) btnTextEl.textContent = "Generating…";
        else generateBtn.textContent = "Generating…";
        loadingState.classList.remove("hidden");
        break;
      case states.ERROR:
        generateBtn.disabled = false;
        if (btnTextEl) btnTextEl.textContent = "Generate PDF";
        else generateBtn.textContent = "Generate PDF";
        errorMessage.textContent = data.message || "Something went wrong.";
        errorState.classList.remove("hidden");
        break;
      case states.SUCCESS:
        generateBtn.disabled = false;
        if (btnTextEl) btnTextEl.textContent = "Generate PDF";
        else generateBtn.textContent = "Generate PDF";
        setPreview(data.blobUrl);
        successState.classList.remove("hidden");
        break;
    }

    currentState = newState;
  }

  function setPreview(blobUrl) {
    pdfBlobUrl = blobUrl;
    pdfPreview.data = blobUrl;
    downloadBtn.href = blobUrl;
  }

  function revokeBlobUrl() {
    if (pdfBlobUrl) {
      URL.revokeObjectURL(pdfBlobUrl);
      pdfBlobUrl = null;
    }
    pdfPreview.data = "";
    downloadBtn.href = "#";
  }

  // --- Generate PDF ---
  async function generatePDF() {
    var content = contentInput.value;
    var stylePrompt = stylePromptInput ? stylePromptInput.value : "";

    if (!content.trim()) {
      setState(states.ERROR, { message: "Please enter some content to convert." });
      return;
    }

    setState(states.LOADING);

    var requestBody = {
      content: content,
      style_prompt: stylePrompt.trim(),
    };

    var controller = new AbortController();
    var timeoutId = setTimeout(function () {
      controller.abort();
    }, TIMEOUT_MS);

    try {
      var response = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        var errorData;
        try {
          errorData = await response.json();
        } catch (_) {
          errorData = {};
        }
        var detail = (errorData.detail && errorData.detail.detail) || "";
        var errorMsg =
          (errorData.detail && errorData.detail.error) ||
          errorData.error ||
          "Request failed (HTTP " + response.status + ")";

        if (response.status === 504) {
          errorMsg = "Server took too long to generate your PDF. Try shorter content.";
        } else if (response.status === 500 && /timed out/i.test(detail)) {
          errorMsg = "PDF rendering timed out — your document may be too complex. Try shorter content.";
        }
        throw new Error(errorMsg);
      }

      var blob = await response.blob();
      var blobUrl = URL.createObjectURL(blob);
      setState(states.SUCCESS, { blobUrl: blobUrl });
    } catch (error) {
      clearTimeout(timeoutId);

      if (error.name === "AbortError") {
        setState(states.ERROR, {
          message: "Request timed out. The server is taking too long. Try shorter content.",
        });
      } else {
        setState(states.ERROR, {
          message:
            error.message ||
            "Something went wrong. Please check your input and try again.",
        });
      }
    }
  }

  // --- CSS Panel Toggle ---
  function toggleCssPanel() {
    var arrow = cssToggle.querySelector(".css-toggle-arrow");
    if (cssPanel.classList.contains("collapsed")) {
      cssPanel.classList.remove("collapsed");
      arrow.textContent = "▾";
    } else {
      cssPanel.classList.add("collapsed");
      arrow.textContent = "▸";
    }
  }

  // --- Reset ---
  function resetApp() {
    setState(states.IDLE);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // --- Style Preset Chips ---
  var presetChips = document.querySelectorAll(".preset-chip");
  var activePreset = null;

  presetChips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      var prompt = chip.getAttribute("data-prompt");

      // Toggle off if clicking active preset
      if (activePreset === chip) {
        chip.classList.remove("preset-chip--active");
        stylePromptInput.value = "";
        activePreset = null;
        return;
      }

      // Deactivate previous
      if (activePreset) {
        activePreset.classList.remove("preset-chip--active");
      }

      // Activate this one
      chip.classList.add("preset-chip--active");
      stylePromptInput.value = prompt;
      activePreset = chip;
    });
  });

  // Clear active preset when user types custom text
  if (stylePromptInput) {
    stylePromptInput.addEventListener("input", function () {
      var matchesPreset = false;
      presetChips.forEach(function (chip) {
        if (chip.getAttribute("data-prompt") === stylePromptInput.value) {
          matchesPreset = true;
        }
      });

      if (!matchesPreset && activePreset) {
        activePreset.classList.remove("preset-chip--active");
        activePreset = null;
      }
    });
  }

  // --- Event Listeners ---
  generateBtn.addEventListener("click", generatePDF);
  cssToggle.addEventListener("click", toggleCssPanel);
  resetBtn.addEventListener("click", resetApp);

  document.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      if (!generateBtn.disabled) {
        generatePDF();
      }
    }
  });
})();
