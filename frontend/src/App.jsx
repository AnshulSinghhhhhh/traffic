import React, { useState } from 'react';
import MapView from './components/MapView';
import VehicleSearch from './components/VehicleSearch';
import AlertPanel from './components/AlertPanel';
import StatsBar from './components/StatsBar';

export default function App() {
    const [trajectoryPoints, setTrajectoryPoints] = useState([]);

    return (
        <div className="flex flex-col h-screen bg-gray-900 text-gray-100 font-sans">
            <header className="bg-gray-800 p-4 border-b border-gray-700 flex-shrink-0">
                <h1 className="text-2xl font-bold text-white tracking-wide">IDAHR</h1>
                <p className="text-sm text-gray-400">Multi-Camera ANPR Tracking</p>
            </header>
            <div className="flex flex-1 overflow-hidden">
                <aside className="w-96 flex flex-col overflow-y-auto bg-gray-800 border-r border-gray-700">
                    <div className="p-4 flex flex-col gap-6">
                        <AlertPanel />
                        <VehicleSearch trajectoryPoints={trajectoryPoints} setTrajectoryPoints={setTrajectoryPoints} />
                        <StatsBar />
                    </div>
                </aside>
                <main className="flex-1 relative">
                    <MapView trajectoryPoints={trajectoryPoints} />
                </main>
            </div>
        </div>
    );
}
