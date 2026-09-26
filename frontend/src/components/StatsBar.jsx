import React, { useEffect, useState } from 'react';
import { getDensity, getCongestion } from '../api/client';

export default function StatsBar() {
    const [stats, setStats] = useState([]);
    const [loading, setLoading] = useState(true);

    const fetchStats = async () => {
        try {
            const [densityData, congestionData] = await Promise.all([
                getDensity(15),
                getCongestion(15)
            ]);

            const combined = {};
            
            congestionData.forEach(c => {
                combined[c.camera_id] = {
                    camera_id: c.camera_id,
                    recent_count: c.recent_count,
                    rolling_avg: c.rolling_avg,
                    congested: c.congested,
                    event_count: 0
                };
            });

            densityData.forEach(d => {
                if (!combined[d.camera_id]) {
                    combined[d.camera_id] = { camera_id: d.camera_id, congested: false, rolling_avg: 0, recent_count: 0 };
                }
                combined[d.camera_id].event_count = d.event_count;
            });

            setStats(Object.values(combined));
        } catch (err) {
            console.error("Error fetching stats:", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchStats();
        const interval = setInterval(fetchStats, 30000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="bg-gray-700 rounded-lg p-4 shadow-md">
            <h2 className="text-lg font-semibold text-gray-100 mb-3 border-b border-gray-600 pb-2">Traffic Stats (15m)</h2>
            {loading && stats.length === 0 ? (
                <div className="text-gray-400 text-sm">Loading stats...</div>
            ) : stats.length === 0 ? (
                <div className="text-gray-400 text-sm italic">No data available</div>
            ) : (
                <div className="grid grid-cols-1 gap-3">
                    {stats.map(stat => (
                        <div key={stat.camera_id} className="bg-gray-800 rounded p-3 border border-gray-600 flex flex-col gap-1">
                            <div className="flex justify-between items-center">
                                <span className="font-semibold text-gray-200 text-sm">{stat.camera_id}</span>
                                <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase ${stat.congested ? 'bg-red-900/50 text-red-400' : 'bg-green-900/50 text-green-400'}`}>
                                    {stat.congested ? 'Congested' : 'Normal'}
                                </span>
                            </div>
                            <div className="grid grid-cols-2 text-xs mt-1">
                                <div>
                                    <span className="text-gray-500">Events:</span>
                                    <span className="ml-1 text-gray-300">{stat.event_count || 0}</span>
                                </div>
                                <div>
                                    <span className="text-gray-500">Avg:</span>
                                    <span className="ml-1 text-gray-300">
                                        {stat.rolling_avg != null 
                                            ? stat.rolling_avg.toFixed(1) 
                                            : '-'}
                                    </span>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
