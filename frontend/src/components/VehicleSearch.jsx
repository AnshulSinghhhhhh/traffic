import React, { useState } from 'react';
import { getVehicle, getTrajectory } from '../api/client';

export default function VehicleSearch({ trajectoryPoints, setTrajectoryPoints }) {
    const [plate, setPlate] = useState('');
    const [vehicle, setVehicle] = useState(null);
    const [timeline, setTimeline] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleSearch = async (e) => {
        e.preventDefault();
        if (!plate.trim()) return;
        
        setLoading(true);
        setError(null);
        setVehicle(null);
        setTimeline([]);
        setTrajectoryPoints([]);

        try {
            const [vehData, trajData] = await Promise.all([
                getVehicle(plate),
                getTrajectory(plate)
            ]);
            setVehicle(vehData);
            setTimeline(trajData);
            setTrajectoryPoints(trajData);
        } catch (err) {
            setError(err.message || 'Vehicle not found or API error.');
        } finally {
            setLoading(false);
        }
    };

    const handleClear = () => {
        setPlate('');
        setVehicle(null);
        setTimeline([]);
        setTrajectoryPoints([]);
        setError(null);
    };

    return (
        <div className="bg-gray-700 rounded-lg p-4 shadow-md">
            <h2 className="text-lg font-semibold text-gray-100 mb-3 border-b border-gray-600 pb-2">Vehicle Search</h2>
            <form onSubmit={handleSearch} className="flex gap-2 mb-4">
                <input
                    type="text"
                    value={plate}
                    onChange={(e) => setPlate(e.target.value.toUpperCase())}
                    placeholder="Enter plate (e.g. KA01AB1234)"
                    className="flex-1 bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-gray-100 focus:outline-none focus:border-blue-500 uppercase"
                />
                <button type="submit" disabled={loading} className="bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded text-sm transition-colors">
                    {loading ? '...' : 'Search'}
                </button>
                {(vehicle || error || trajectoryPoints.length > 0) && (
                    <button type="button" onClick={handleClear} className="bg-gray-600 hover:bg-gray-500 text-white px-3 py-1.5 rounded text-sm transition-colors">
                        Clear
                    </button>
                )}
            </form>

            {error && (
                <div className="text-red-400 text-sm bg-red-900/30 p-2 rounded border border-red-800 mb-4">
                    {error}
                </div>
            )}

            {vehicle && (
                <div className="mb-4 text-sm bg-gray-800 p-3 rounded">
                    <div className="font-bold text-blue-400 text-base mb-1">{vehicle.plate}</div>
                    <div className="grid grid-cols-2 gap-y-1 text-gray-300">
                        <div><span className="text-gray-500">First:</span> {vehicle.first_seen ? new Date(vehicle.first_seen).toLocaleString() : '-'}</div>
                        <div><span className="text-gray-500">Last:</span> {vehicle.last_seen ? new Date(vehicle.last_seen).toLocaleString() : '-'}</div>
                        <div><span className="text-gray-500">Cams:</span> {vehicle.camera_count}</div>
                        <div>
                            <span className="text-gray-500">Status:</span>
                            {vehicle.has_alerts ? (
                                <span className="ml-1 text-red-400 font-medium">⚠ Alert</span>
                            ) : (
                                <span className="ml-1 text-green-400 font-medium">Clear</span>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {timeline.length > 0 && (
                <div>
                    <h3 className="text-sm font-semibold text-gray-300 mb-2">Sighting Timeline ({timeline.length} hops)</h3>
                    <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                        {timeline.map((point, idx) => (
                            <div key={idx} className="bg-gray-800 rounded p-2 text-xs flex justify-between items-center border-l-2 border-blue-500">
                                <div>
                                    <div className="font-semibold text-gray-200">{point.camera_id}</div>
                                    <div className="text-gray-400">{new Date(point.timestamp).toLocaleString()}</div>
                                </div>
                                <div className="bg-gray-700 w-5 h-5 flex items-center justify-center rounded-full text-[10px] text-gray-300">
                                    {idx + 1}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
