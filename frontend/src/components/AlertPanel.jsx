import React, { useState, useEffect } from 'react';
import { getAlerts, resolveAlert, addToBlacklist } from '../api/client';

export default function AlertPanel() {
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [blPlate, setBlPlate] = useState('');
    const [blReason, setBlReason] = useState('');
    const [blStatus, setBlStatus] = useState(null);

    const fetchAlerts = async () => {
        try {
            const data = await getAlerts('unresolved');
            setAlerts(data);
        } catch (err) {
            console.error("Failed to load alerts:", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchAlerts();
        const interval = setInterval(fetchAlerts, 10000);
        return () => clearInterval(interval);
    }, []);

    const handleResolve = async (alertId) => {
        try {
            await resolveAlert(alertId);
            fetchAlerts();
        } catch (err) {
            console.error("Error resolving alert", err);
        }
    };

    const handleBlacklist = async (e) => {
        e.preventDefault();
        if (!blPlate.trim()) return;
        try {
            await addToBlacklist(blPlate, blReason || 'Suspicious activity');
            setBlStatus({ type: 'success', msg: 'Added to blacklist' });
            setBlPlate('');
            setBlReason('');
            setTimeout(() => setBlStatus(null), 3000);
        } catch (err) {
            setBlStatus({ type: 'error', msg: err.message || 'Failed to blacklist' });
        }
    };

    return (
        <div className="bg-gray-700 rounded-lg shadow-md flex flex-col h-auto max-h-96">
            <div className="p-4 border-b border-gray-600 flex justify-between items-center shrink-0">
                <h2 className="text-lg font-semibold text-gray-100 flex items-center gap-2">
                    Alerts
                    {alerts.length > 0 && (
                        <span className="bg-red-500 text-white text-xs px-2 py-0.5 rounded-full font-bold">
                            {alerts.length}
                        </span>
                    )}
                </h2>
            </div>
            
            <div className="p-4 overflow-y-auto flex-1 space-y-3">
                {loading && alerts.length === 0 ? (
                    <div className="text-gray-400 text-sm">Loading alerts...</div>
                ) : alerts.length === 0 ? (
                    <div className="text-gray-400 text-sm italic">No unresolved alerts</div>
                ) : (
                    alerts.map(alert => (
                        <div key={alert.alert_id} className="bg-gray-800 rounded p-3 border border-red-900/50 flex flex-col gap-2">
                            <div className="flex justify-between items-start">
                                <div className="flex gap-2 items-center">
                                    <span className="bg-red-500/20 text-red-400 text-xs px-1.5 py-0.5 rounded font-semibold uppercase">
                                        {alert.type || 'Alert'}
                                    </span>
                                    <span className="font-bold text-gray-200 text-sm">{alert.plate}</span>
                                </div>
                                <div className="text-xs text-gray-500">
                                    {alert.created_at ? new Date(alert.created_at).toLocaleTimeString() : ''}
                                </div>
                            </div>
                            <div className="text-xs text-gray-400">
                                {alert.message || `Detected on camera ${alert.camera_id}`}
                            </div>
                            <button 
                                onClick={() => handleResolve(alert.alert_id)}
                                className="self-end mt-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 px-2 py-1 rounded transition-colors border border-gray-600"
                            >
                                Resolve
                            </button>
                        </div>
                    ))
                )}
            </div>

            <div className="p-4 border-t border-gray-600 bg-gray-800 rounded-b-lg shrink-0">
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Quick Blacklist</h3>
                <form onSubmit={handleBlacklist} className="flex flex-col gap-2">
                    <div className="flex gap-2">
                        <input
                            type="text"
                            value={blPlate}
                            onChange={(e) => setBlPlate(e.target.value.toUpperCase())}
                            placeholder="Plate"
                            className="w-1/3 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-100 focus:outline-none focus:border-red-500 uppercase"
                        />
                        <input
                            type="text"
                            value={blReason}
                            onChange={(e) => setBlReason(e.target.value)}
                            placeholder="Reason"
                            className="flex-1 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-100 focus:outline-none focus:border-red-500"
                        />
                    </div>
                    <div className="flex justify-between items-center">
                        <div className="text-xs">
                            {blStatus && (
                                <span className={blStatus.type === 'error' ? 'text-red-400' : 'text-green-400'}>
                                    {blStatus.msg}
                                </span>
                            )}
                        </div>
                        <button type="submit" className="bg-red-600 hover:bg-red-500 text-white px-3 py-1 rounded text-xs transition-colors">
                            Add
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
