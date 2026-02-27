const modal = document.getElementById("consent-modal");
const openBtn = document.getElementById("open-consent");
const allowBtn = document.getElementById("allow-btn");
const denyBtn = document.getElementById("deny-btn");
const resultEl = document.getElementById("result");
const shareUserIdInput = document.getElementById("share-user-id");
const telegramConfirmInput = document.getElementById("telegram-confirm");
const telegramSendBtn = document.getElementById("telegram-send-btn");
const telegramStatusEl = document.getElementById("telegram-status");
let lastCollectedInfo = null;

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

function getBasicInfo() {
  return {
    device_model: getDeviceModel(),
    user_agent: safeValue(navigator.userAgent),
    language: safeValue(navigator.language),
    screen_resolution: `${window.screen.width}x${window.screen.height}`,
    cpu_cores: navigator.hardwareConcurrency ?? "Unavailable",
    ram_gb: navigator.deviceMemory ?? "Unavailable",
  };
}

async function getPermissionState(name) {
  if (!navigator.permissions || !navigator.permissions.query) {
    return "Unsupported";
  }

  try {
    const result = await navigator.permissions.query({ name });
    return safeValue(result.state, "Unavailable");
  } catch (_err) {
    return "Unavailable";
  }
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

function getCoordinatesIfAllowed() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      resolve("Geolocation not supported");
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        resolve(`lat=${latitude.toFixed(5)}, lon=${longitude.toFixed(5)}`);
      },
      () => {
        resolve("Permission denied / unavailable");
      },
      { enableHighAccuracy: false, timeout: 10000 }
    );
  });
}

async function getIpAndApproxLocation() {
  try {
    const response = await fetch("https://ipwho.is/");
    const data = await response.json();
    if (!response.ok || !data || data.success === false) {
      return {
        ip_address: "Unavailable",
        country: "Unavailable",
        region: "Unavailable",
        city: "Unavailable",
        timezone: "Unavailable",
      };
    }

    return {
      ip_address: safeValue(data.ip),
      country: safeValue(data.country),
      region: safeValue(data.region),
      city: safeValue(data.city),
      timezone: safeValue(data.timezone && data.timezone.id),
    };
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

function formatInfo(info) {
  const ramValue = info.ram_gb === "Unavailable" || info.ram_gb === undefined || info.ram_gb === null
    ? "Unavailable"
    : `${info.ram_gb} GB`;

  return [
    "Visitor Information Captured",
    "==========================",
    "",
    "Device & Browser",
    `- Device Model: ${safeValue(info.device_model)}`,
    `- User Agent: ${safeValue(info.user_agent)}`,
    "",
    "Network Information",
    `- IP Address: ${safeValue(info.ip_address)}`,
    `- Language: ${safeValue(info.language)}`,
    "",
    "Location Details",
    `- Country: ${safeValue(info.country)}`,
    `- Region: ${safeValue(info.region)}`,
    `- City: ${safeValue(info.city)}`,
    `- Timezone: ${safeValue(info.timezone)}`,
    `- Coordinates: ${safeValue(info.coordinates)}`,
    "",
    "Display Information",
    `- Resolution: ${safeValue(info.screen_resolution)}`,
    "",
    "Battery Status",
    `- Level: ${safeValue(info.battery_level)}`,
    `- Charging: ${safeValue(info.battery_charging)}`,
    "",
    "Device Permissions",
    `- Camera: ${safeValue(info.camera_permission)}`,
    `- Location: ${safeValue(info.location_permission)}`,
    "",
    "Hardware & Storage",
    `- CPU Cores: ${safeValue(info.cpu_cores)}`,
    `- RAM: ${ramValue}`,
    `- Storage Used: ${safeValue(info.storage_used_gb)}`,
    `- Storage Total: ${safeValue(info.storage_total_gb)}`,
  ].join("\n");
}

async function collectAndSend() {
  const basic = getBasicInfo();

  const [cameraPermission, locationPermission, battery, storage, coordinates, ipLocation] =
    await Promise.all([
      getPermissionState("camera"),
      getPermissionState("geolocation"),
      getBatteryDetails(),
      getStorageDetails(),
      getCoordinatesIfAllowed(),
      getIpAndApproxLocation(),
    ]);

  const info = {
    ...basic,
    ...battery,
    ...storage,
    ...ipLocation,
    coordinates,
    camera_permission: cameraPermission,
    location_permission: locationPermission,
    consent_given: true,
  };
  lastCollectedInfo = info;

  resultEl.classList.remove("empty");
  resultEl.textContent = formatInfo(info);
  if (telegramSendBtn) {
    telegramSendBtn.disabled = false;
  }
  if (telegramStatusEl) {
    telegramStatusEl.textContent = "Collection complete. Manual Telegram share is available.";
  }

  const res = await fetch("/collect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(info),
  });

  if (!res.ok) {
    let backendMessage = "Backend storage failed.";
    try {
      const data = await res.json();
      if (data && data.error) {
        backendMessage = data.error;
      }
    } catch (_err) {
      // Keep default message if response is not JSON.
    }
    resultEl.textContent += `\n\nWarning: ${backendMessage}`;
  }
}

async function sendToTelegram() {
  if (!lastCollectedInfo) {
    telegramStatusEl.textContent = "Collect data first.";
    return;
  }

  const userId = (shareUserIdInput?.value || "").trim();
  if (!userId) {
    telegramStatusEl.textContent = "Enter your allowed user ID.";
    return;
  }

  if (!telegramConfirmInput?.checked) {
    telegramStatusEl.textContent = "Check the confirmation box before sending.";
    return;
  }

  const secondConfirm = window.confirm(
    "Send the displayed information to Telegram now?"
  );
  if (!secondConfirm) {
    telegramStatusEl.textContent = "Telegram share cancelled.";
    return;
  }

  telegramStatusEl.textContent = "Sending to Telegram...";
  const payload = {
    ...lastCollectedInfo,
    user_id: userId,
    share_confirmed: true,
  };

  const res = await fetch("/share-telegram", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  let responseData = null;
  try {
    responseData = await res.json();
  } catch (_err) {
    // Keep fallback message.
  }

  if (!res.ok) {
    telegramStatusEl.textContent = responseData?.error || "Telegram send failed.";
    return;
  }

  telegramStatusEl.textContent = "Sent to Telegram successfully.";
}

openBtn?.addEventListener("click", () => {
  modal.classList.remove("hidden");
});

denyBtn?.addEventListener("click", () => {
  modal.classList.add("hidden");
  resultEl.classList.remove("empty");
  resultEl.textContent = "Consent denied. No data was collected.";
});

allowBtn?.addEventListener("click", async () => {
  modal.classList.add("hidden");
  await collectAndSend();
});

telegramSendBtn?.addEventListener("click", async () => {
  await sendToTelegram();
});
