import { useEffect, useRef } from "react";
import { SimulationConfig, Train } from "../types/main";

// =======================
// METRO MAP COMPONENT
// =======================

const HIGHLIGHTED_STATIONS = ['Dimotiko Theatro', 'Doukissis Plakentias', 'Airport']

export const MetroMap: React.FC<{
    config: SimulationConfig;
    trains: Train[];
    label: string;
    isOptimized?: boolean;
    waitingPassengers: Map<string, number>;
}> = ({ config, trains, label, isOptimized, waitingPassengers }) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        const w = rect.width;
        const h = rect.height;

        ctx.fillStyle = "#000000";
        ctx.fillRect(0, 0, w, h);

        const lats = config.stations.map((s) => s.lat);
        const lons = config.stations.map((s) => s.lon);
        const minLat = Math.min(...lats);
        const maxLat = Math.max(...lats);
        const minLon = Math.min(...lons);
        const maxLon = Math.max(...lons);

        const padding = 70;
        const scaleX = (w - 2 * padding) / (maxLon - minLon || 1);
        const scaleY = (h - 2 * padding) / (maxLat - minLat || 1);

        const project = (lat: number, lon: number) => ({
            x: padding + (lon - minLon) * scaleX,
            y: h - (padding + (lat - minLat) * scaleY),
        });

        // Line path
        ctx.strokeStyle = isOptimized ? "#00aaff" : "#0088cc";
        ctx.lineWidth = 3;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.beginPath();
        config.stations.forEach((station, i) => {
            const pos = project(station.lat, station.lon);
            if (i === 0) ctx.moveTo(pos.x, pos.y);
            else ctx.lineTo(pos.x, pos.y);
        });
        ctx.stroke();

        // Stations
        config.stations.forEach((station, i) => {
            const pos = project(station.lat, station.lon);
            const waitingPaxRaw = waitingPassengers.get(station.id) || 0;
            const waitingPax = Math.max(0, Math.round(waitingPaxRaw));

            if (waitingPax > 0 && !HIGHLIGHTED_STATIONS.includes(station.nameEn)) {
                const indicatorSize = Math.min(24, 10 + Math.sqrt(waitingPax) * 0.7);
                ctx.beginPath();
                ctx.arc(pos.x, pos.y, indicatorSize, 0, 2 * Math.PI);
                ctx.fillStyle = "rgba(255, 165, 0, 0.25)";
                ctx.fill();
                ctx.strokeStyle = "#ffaa00";
                ctx.lineWidth = 2;
                ctx.stroke();

                ctx.fillStyle = "#ffaa00";
                ctx.font = "bold 10px 'Courier New', monospace";
                ctx.textAlign = "center";
                ctx.fillText(waitingPax.toString(), pos.x, pos.y - indicatorSize - 6);
            }

            ctx.beginPath();
            ctx.arc(pos.x, pos.y, 5, 0, 2 * Math.PI);
            ctx.fillStyle = "#000000";
            ctx.fill();
            ctx.strokeStyle = isOptimized ? "#00aaff" : "#0088cc";
            ctx.lineWidth = 2;
            ctx.stroke();

            if (HIGHLIGHTED_STATIONS.includes(station.nameEn)) {
                ctx.fillStyle = "#999999";
                ctx.font = "10px 'Courier New', monospace";
                ctx.textAlign = i % 2 === 0 ? "right" : "left";
                const offset = i % 2 === 0 ? -10 : 10;
                ctx.fillText(station.nameEn, pos.x + offset, pos.y + 3);
            }

        });


        // Trains
        trains.forEach((train) => {
            if (train.stationIndex < 0 || train.stationIndex >= config.stations.length)
                return;

            let targetLat = 0,
                targetLon = 0;
            let foundPosition = false;

            for (let i = 0; i < config.stations.length - 1; i++) {
                const s1 = config.stations[i];
                const s2 = config.stations[i + 1];
                if (
                    train.position >=
                    Math.min(s1.distanceFromStart, s2.distanceFromStart) &&
                    train.position <=
                    Math.max(s1.distanceFromStart, s2.distanceFromStart)
                ) {
                    const ratio =
                        Math.abs(train.position - s1.distanceFromStart) /
                        Math.abs(s2.distanceFromStart - s1.distanceFromStart || 1);
                    targetLat = s1.lat + (s2.lat - s1.lat) * ratio;
                    targetLon = s1.lon + (s2.lon - s1.lon) * ratio;
                    foundPosition = true;
                    break;
                }
            }

            if (!foundPosition) {
                const station = config.stations[train.stationIndex];
                targetLat = station.lat;
                targetLon = station.lon;
            }

            const pos = project(targetLat, targetLon);
            const loadFactor = train.passengers / config.trainCapacity;

            let trainColor = "#44ff44";
            if (loadFactor > 0.85) trainColor = "#ff4444";
            else if (loadFactor < 0.3) trainColor = "#4488ff";

            ctx.beginPath();
            ctx.arc(pos.x, pos.y, 9, 0, 2 * Math.PI);
            ctx.fillStyle = trainColor;
            ctx.fill();
            ctx.strokeStyle = "#ffffff";
            ctx.lineWidth = 2;
            ctx.stroke();

            if (train.passengers > 0) {
                ctx.fillStyle = "#ffffff";
                ctx.font = "bold 10px 'Courier New', monospace";
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText(Math.round(train.passengers).toString(), pos.x, pos.y);
            }
        });
    }, [config, trains, isOptimized, waitingPassengers]);

    return (
        <div className="relative w-full h-full bg-black border border-white/20">
            <div className="absolute top-2 left-2 text-white text-xs font-mono bg-black/90 px-2 py-1 border border-white/30">
                {label}
            </div>
            <canvas ref={canvasRef} className="w-full h-full" />
        </div>
    );
};