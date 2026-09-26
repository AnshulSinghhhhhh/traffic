import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, Polyline, Tooltip } from 'react-leaflet';
import { getCameras, getDensity } from '../api/client';

const center = [12.985, 77.615];

export default function MapView({ trajectoryPoints }) {
    const [cameras, setCameras] = useState([]);
    const [densityMap, setDensityMap] = useState({});

    const fetchMapData = async () => {
        try {
            const [camsData, densityData] = await Promise.all([
                getCameras(),
                getDensity()
            ]);
            setCameras(camsData);
            
            const density = {};
            densityData.forEach(d => { density[d.camera_id] = d.event_count; });
            setDensityMap(density);
        } catch (error) {
            console.error("Failed to fetch map data:", error);
        }
    };

    useEffect(() => {
        fetchMapData();
        const interval = setInterval(fetchMapData, 30000);
        return () => clearInterval(interval);
    }, []);

    const getMarkerColor = (count) => {
        if (!count || count === 0) return 'gray';
        if (count <= 5) return 'green';
        if (count <= 15) return 'orange';
        return 'red';
    };

    return (
        <div className="h-full w-full bg-gray-900 z-0">
            <MapContainer center={center} zoom={13} style={{ height: '100%', width: '100%' }}>
                <TileLayer
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    attribution='&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'
                />
                {cameras.map(cam => {
                    const count = densityMap[cam.camera_id] || 0;
                    return (
                        <CircleMarker
                            key={`cam-${cam.camera_id}`}
                            center={[cam.lat, cam.lng]}
                            radius={8 + Math.min(count, 10)}
                            pathOptions={{
                                color: getMarkerColor(count),
                                fillColor: getMarkerColor(count),
                                fillOpacity: 0.7
                            }}
                        >
                            <Popup>
                                <div className="text-gray-900">
                                    <strong>{cam.name}</strong><br />
                                    Road: {cam.road_name || 'Unknown'}<br />
                                    Events (15m): {count}
                                </div>
                            </Popup>
                        </CircleMarker>
                    );
                })}

                {trajectoryPoints && trajectoryPoints.length > 0 && (
                    <>
                        <Polyline
                            positions={trajectoryPoints.filter(p => p.lat && p.lng).map(p => [p.lat, p.lng])}
                            pathOptions={{ color: '#3b82f6', weight: 3 }}
                        />
                        {trajectoryPoints.filter(p => p.lat && p.lng).map((p, index) => (
                            <CircleMarker
                                key={`traj-${index}`}
                                center={[p.lat, p.lng]}
                                radius={6}
                                pathOptions={{ color: '#ffffff', fillColor: '#3b82f6', fillOpacity: 1, weight: 2 }}
                            >
                                <Tooltip permanent direction="top" offset={[0, -10]}>
                                    {index + 1}
                                </Tooltip>
                            </CircleMarker>
                        ))}
                    </>
                )}
            </MapContainer>
        </div>
    );
}
