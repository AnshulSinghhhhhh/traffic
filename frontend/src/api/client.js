const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function apiFetch(path, options = {}) {
    const url = `${BASE}${path}`;
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };

    const response = await fetch(url, { ...options, headers });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `API Error: ${response.status} ${response.statusText}`);
    }
    return response.json();
}

export function getCameras() { return apiFetch('/cameras'); }
export function getTrajectory(plate) { return apiFetch(`/trajectory/${plate}`); }
export function getVehicle(plate) { return apiFetch(`/vehicle/${plate}`); }
export function getDensity(window = 15) { return apiFetch(`/traffic/density?window=${window}`); }
export function getCongestion(window = 15) { return apiFetch(`/traffic/congestion?window=${window}`); }
export function getAlerts(status = 'unresolved') { return apiFetch(`/alerts?alert_status=${status}`); }
export function resolveAlert(alertId) { return apiFetch(`/alerts/${alertId}/resolve`, { method: 'PATCH' }); }
export function addToBlacklist(plate, reason) {
    return apiFetch('/blacklist', {
        method: 'POST',
        body: JSON.stringify({ plate, reason })
    });
}
