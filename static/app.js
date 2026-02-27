const allowBtn = document.getElementById("allow-btn");
const resultEl = document.getElementById("result");
const sendBtn = document.getElementById("send-btn");
const statusEl = document.getElementById("status");
const userIdInput = document.getElementById("user-id");

let collectedData = null;

function getChatIdFromUrl() {
  const parts = window.location.pathname.split("/");
  return parts[2] || null;
}

// Auto-fill chat ID into input
window.addEventListener("DOMContentLoaded", () => {
  const chatId = getChatIdFromUrl();
  if (chatId) {
    userIdInput.value = chatId;
  }
});



// Collect only after clicking Allow
document.addEventListener("DOMContentLoaded", () => {

  collectedData = {
    user_agent: navigator.userAgent,
    language: navigator.language,
    screen_resolution: `${window.screen.width}x${window.screen.height}`,
    consent_given: true,
    cpu_cores: navigator.hardwareConcurrency ?? "Unavailable",
    ram_gb: navigator.deviceMemory ?? "Unavailable",
  };

  resultEl.textContent = JSON.stringify(collectedData, null, 2);

  sendBtn.disabled = false;

});

// Manual send only
document.addEventListener("DOMContentLoaded", async () => {

  if (!collectedData) {
    statusEl.textContent = "Collect data first.";
    return;
  }

  const chatId = getChatIdFromUrl();
  if (!chatId) {
    statusEl.textContent = "Chat ID missing.";
    return;
  }

  statusEl.textContent = "Sending...";

  try {
    const res = await fetch(`/num/${chatId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectedData),
    });

    const data = await res.json();

    if (!res.ok) {
      statusEl.textContent = data.error || "Failed.";
      return;
    }

    statusEl.textContent = "Sent successfully.";
  } catch (err) {
    statusEl.textContent = "Network error.";
  }

});