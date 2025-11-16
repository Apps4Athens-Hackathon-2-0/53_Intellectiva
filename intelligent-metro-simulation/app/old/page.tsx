'use client';
import React, { useState, useEffect, useRef, useMemo } from "react";
import { Play, Pause, RotateCcw, Zap, Clock } from "lucide-react";

interface Station {
  id: string;
  name: string;
  nameEn: string;
  lat: number;
  lon: number;
  distanceFromStart: number;
  influxRate: number;
}

interface Trip {
  trainId: string;
  departureTime: number;
  direction: "eastbound" | "westbound";
  stationIds: string[];
}

interface Schedule {
  trips: Trip[];
}

interface SimulationConfig {
  stations: Station[];
  officialSchedule: Schedule;
  optimizedSchedule: Schedule;
  trainCapacity: number;
  avgSpeed: number;
  dwellTime: number;
  energyConsumptionRate: number;
  kwhPrice: number;
}

interface Train {
  id: string;
  position: number;
  stationIndex: number;
  direction: "eastbound" | "westbound";
  passengers: number;
  nextStationArrival: number;
  status: "moving" | "stopped";
  energyConsumed: number;
  departureTime: number;
  lastStopTime: number;
}

interface Metrics {
  avgWaitingTime: number;
  totalRunningTime: number;
  kwhPrice: number;
  totalEnergyConsumption: number;
  totalEnergyCost: number;
  avgTrainLoad: number;
  trainLoadVariance: number;
  passengersServed: number;
  totalPassengerMinutes: number;
}

const ATHENS_LINE3_CONFIG: SimulationConfig = {
  stations: [
    { id: "s01", name: "Δημοτικό Θέατρο", nameEn: "Dimotiko Theatro", lat: 37.942905, lon: 23.647350, distanceFromStart: 0.0, influxRate: 0.8 },
    { id: "s02", name: "Πειραιάς", nameEn: "Piraeus", lat: 37.948100, lon: 23.642265, distanceFromStart: 1.5, influxRate: 1.2 },
    { id: "s03", name: "Μανιάτικα", nameEn: "Maniatika", lat: 37.959545, lon: 23.639780, distanceFromStart: 3.0, influxRate: 0.5 },
    { id: "s04", name: "Νίκαια", nameEn: "Nikaia", lat: 37.965745, lon: 23.647550, distanceFromStart: 4.5, influxRate: 0.7 },
    { id: "s05", name: "Κορυδαλλός", nameEn: "Korydallos", lat: 37.977050, lon: 23.650405, distanceFromStart: 6.0, influxRate: 0.9 },
    { id: "s06", name: "Αγία Βαρβάρα", nameEn: "Agia Varvara", lat: 37.989710, lon: 23.659320, distanceFromStart: 7.5, influxRate: 0.6 },
    { id: "s07", name: "Αγία Μαρίνα", nameEn: "Agia Marina", lat: 37.996860, lon: 23.667130, distanceFromStart: 9.0, influxRate: 0.8 },
    { id: "s08", name: "Αιγάλεω", nameEn: "Egaleo", lat: 37.991420, lon: 23.681690, distanceFromStart: 10.5, influxRate: 1.0 },
    { id: "s09", name: "Ελαιώνας", nameEn: "Eleonas", lat: 37.987725, lon: 23.693375, distanceFromStart: 12.8, influxRate: -0.3 },
    { id: "s10", name: "Κεραμεικός", nameEn: "Kerameikos", lat: 37.978715, lon: 23.710940, distanceFromStart: 15.0, influxRate: 1.5 },
    { id: "s11", name: "Μοναστηράκι", nameEn: "Monastiraki", lat: 37.976615, lon: 23.725905, distanceFromStart: 16.5, influxRate: 2.0 },
    { id: "s12", name: "Σύνταγμα", nameEn: "Syntagma", lat: 37.974790, lon: 23.735535, distanceFromStart: 18.0, influxRate: 1.8 },
    { id: "s13", name: "Ευαγγελισμός", nameEn: "Evangelismos", lat: 37.975900, lon: 23.746560, distanceFromStart: 19.5, influxRate: -0.5 },
    { id: "s14", name: "Μέγαρο Μουσικής", nameEn: "Megaro Moussikis", lat: 37.979370, lon: 23.753515, distanceFromStart: 20.3, influxRate: -0.4 },
    { id: "s15", name: "Αμπελόκηποι", nameEn: "Ambelokipi", lat: 37.986945, lon: 23.757600, distanceFromStart: 21.8, influxRate: 0.9 },
    { id: "s16", name: "Πανόρμου", nameEn: "Panormou", lat: 37.993030, lon: 23.763530, distanceFromStart: 23.3, influxRate: 0.7 },
    { id: "s17", name: "Κατεχάκη", nameEn: "Katehaki", lat: 37.993445, lon: 23.776965, distanceFromStart: 24.8, influxRate: 0.6 },
    { id: "s18", name: "Εθνική Άμυνα", nameEn: "Ethniki Amyna", lat: 37.999475, lon: 23.784810, distanceFromStart: 26.3, influxRate: -0.2 },
    { id: "s19", name: "Χολαργός", nameEn: "Holargos", lat: 38.004710, lon: 23.794355, distanceFromStart: 27.8, influxRate: 0.5 },
    { id: "s20", name: "Νομισματοκοπείο", nameEn: "Nomismatokopio", lat: 38.009425, lon: 23.805970, distanceFromStart: 29.3, influxRate: 0.4 },
    { id: "s21", name: "Αγία Παρασκευή", nameEn: "Agia Paraskevi", lat: 38.017380, lon: 23.812765, distanceFromStart: 30.0, influxRate: 0.8 },
    { id: "s22", name: "Χαλάνδρι", nameEn: "Halandri", lat: 38.021755, lon: 23.821185, distanceFromStart: 31.5, influxRate: 1.1 },
    { id: "s23", name: "Δουκίσσης Πλακεντίας", nameEn: "Doukissis Plakentias", lat: 38.023965, lon: 23.832545, distanceFromStart: 33.0, influxRate: -0.6 },
    { id: "s24", name: "Παλλήνη", nameEn: "Pallini", lat: 38.005100, lon: 23.869825, distanceFromStart: 37.5, influxRate: 0.3 },
    { id: "s25", name: "Παιανία - Κάντζα", nameEn: "Paiania-Kantza", lat: 37.984485, lon: 23.870020, distanceFromStart: 39.0, influxRate: 0.4 },
    { id: "s26", name: "Κορωπί", nameEn: "Koropi", lat: 37.912860, lon: 23.895860, distanceFromStart: 43.5, influxRate: 0.5 },
    { id: "s27", name: "Αεροδρόμιο", nameEn: "Airport", lat: 37.936890, lon: 23.944700, distanceFromStart: 47.3, influxRate: -1.5 },
  ],
  trainCapacity: 600,
  avgSpeed: 40,
  dwellTime: 0.5,
  energyConsumptionRate: 4.2,
  kwhPrice: 0.15,
  officialSchedule: {
    trips: Array.from({ length: 40 }, (_, i) => ({
      trainId: `T${(i + 1).toString().padStart(2, '0')}`,
      departureTime: 330 + (i * 7.5),
      direction: (i % 2 === 0 ? "eastbound" : "westbound") as "eastbound" | "westbound",
      stationIds: i % 2 === 0
        ? ["s01", "s02", "s03", "s04", "s05", "s06", "s07", "s08", "s09", "s10", "s11", "s12", "s13", "s14", "s15", "s16", "s17", "s18", "s19", "s20", "s21", "s22", "s23", "s24", "s25", "s26", "s27"]
        : ["s27", "s26", "s25", "s24", "s23", "s22", "s21", "s20", "s19", "s18", "s17", "s16", "s15", "s14", "s13", "s12", "s11", "s10", "s09", "s08", "s07", "s06", "s05", "s04", "s03", "s02", "s01"]
    }))
  },
  optimizedSchedule: {
    trips: Array.from({ length: 40 }, (_, i) => ({
      trainId: `O${(i + 1).toString().padStart(2, '0')}`,
      departureTime: 330 + (i * 6),
      direction: (i % 2 === 0 ? "eastbound" : "westbound") as "eastbound" | "westbound",
      stationIds: i % 2 === 0
        ? ["s01", "s02", "s03", "s04", "s05", "s06", "s07", "s08", "s09", "s10", "s11", "s12", "s13", "s14", "s15", "s16", "s17", "s18", "s19", "s20", "s21", "s22", "s23", "s24", "s25", "s26", "s27"]
        : ["s27", "s26", "s25", "s24", "s23", "s22", "s21", "s20", "s19", "s18", "s17", "s16", "s15", "s14", "s13", "s12", "s11", "s10", "s09", "s08", "s07", "s06", "s05", "s04", "s03", "s02", "s01"]
    }))
  },
};

class MetroSimulator {
  private config: SimulationConfig;
  private trains: Map<string, Train> = new Map();
  private currentTime: number = 0;
  private totalWaitTime: number = 0;
  private passengersServed: number = 0;
  private stationWaitingPassengers: Map<string, number> = new Map();
  private startTime: number = 330;
  private lastUpdateTime: number = 0;

  constructor(config: SimulationConfig, schedule: Schedule) {
    this.config = config;
    this.initializeTrains(schedule);
    this.config.stations.forEach(s => this.stationWaitingPassengers.set(s.id, 0));
  }

  private initializeTrains(schedule: Schedule) {
    schedule.trips.forEach((trip) => {
      const isEastbound = trip.direction === "eastbound";
      const startStation = isEastbound ? this.config.stations[0] : this.config.stations[this.config.stations.length - 1];

      this.trains.set(trip.trainId, {
        id: trip.trainId,
        position: startStation.distanceFromStart,
        stationIndex: isEastbound ? 0 : this.config.stations.length - 1,
        direction: trip.direction,
        passengers: 0,
        nextStationArrival: trip.departureTime,
        status: "stopped",
        energyConsumed: 0,
        departureTime: trip.departureTime,
        lastStopTime: trip.departureTime,
      });
    });
  }

  getStationWaitingPassengers(): Map<string, number> {
    return this.stationWaitingPassengers;
  }

  reset() {
    this.totalWaitTime = 0;
    this.passengersServed = 0;
    this.trains.forEach(train => {
      const isEastbound = train.direction === "eastbound";
      const startStation = isEastbound ? this.config.stations[0] : this.config.stations[this.config.stations.length - 1];
      train.position = startStation.distanceFromStart;
      train.stationIndex = isEastbound ? 0 : this.config.stations.length - 1;
      train.passengers = 0;
      train.nextStationArrival = train.departureTime;
      train.status = "stopped";
      train.energyConsumed = 0;
      train.lastStopTime = train.departureTime;
    });
    this.stationWaitingPassengers.clear();
    this.config.stations.forEach(s => this.stationWaitingPassengers.set(s.id, 0));
  }

  update(currentTime: number): { trains: Train[]; metrics: Metrics } {
    const deltaTime = this.lastUpdateTime === 0 ? 0 : currentTime - this.lastUpdateTime;
    this.lastUpdateTime = currentTime;
    this.currentTime = currentTime;

    if (currentTime < this.startTime) {
      this.reset();
      return { trains: Array.from(this.trains.values()), metrics: this.calculateMetrics() };
    }

    this.config.stations.forEach(station => {
      const currentWaiting = this.stationWaitingPassengers.get(station.id) || 0;
      const influx = station.influxRate * (deltaTime / 5);
      const newWaiting = Math.max(0, currentWaiting + influx);

      this.stationWaitingPassengers.set(station.id, newWaiting);
    });


    this.trains.forEach((train) => this.updateTrain(train));

    return { trains: Array.from(this.trains.values()), metrics: this.calculateMetrics() };
  }

  private updateTrain(train: Train) {
    if (this.currentTime < train.departureTime) {
      train.status = "stopped";
      return;
    }

    if (train.status === "stopped") {
      const dwellElapsed = (this.currentTime - train.lastStopTime) / 60;
      if (dwellElapsed >= this.config.dwellTime) {
        this.handlePassengerExchange(train);
        train.status = "moving";
        train.nextStationArrival = this.currentTime;
      }
    }

    if (train.status === "moving") {
      const timeSinceLastStation = (this.currentTime - train.nextStationArrival) / 60;
      const distanceTraveled = timeSinceLastStation * this.config.avgSpeed;

      const currentStation = this.config.stations[train.stationIndex];
      const nextStationIndex = train.direction === "eastbound" ? train.stationIndex + 1 : train.stationIndex - 1;

      if (nextStationIndex >= 0 && nextStationIndex < this.config.stations.length) {
        const nextStation = this.config.stations[nextStationIndex];
        const distanceToNext = Math.abs(nextStation.distanceFromStart - currentStation.distanceFromStart);

        if (distanceTraveled >= distanceToNext) {
          train.stationIndex = nextStationIndex;
          train.position = nextStation.distanceFromStart;
          train.status = "stopped";
          train.lastStopTime = this.currentTime;
        } else {
          train.position = train.direction === "eastbound"
            ? currentStation.distanceFromStart + distanceTraveled
            : currentStation.distanceFromStart - distanceTraveled;
        }
      }
    } else {
      train.position = this.config.stations[train.stationIndex]?.distanceFromStart || train.position;
    }

    const totalElapsed = Math.max(0, (this.currentTime - train.departureTime) / 60);
    train.energyConsumed = totalElapsed * this.config.avgSpeed * this.config.energyConsumptionRate;
  }

  private handlePassengerExchange(train: Train) {
    const currentStation = this.config.stations[train.stationIndex];
    if (!currentStation) return;

    const influxRate = currentStation.influxRate;

    if (influxRate < 0) {
      const alighting = Math.min(Math.round(Math.abs(influxRate) * 30), train.passengers);
      train.passengers = Math.max(0, train.passengers - alighting);
    } else {
      const waiting = this.stationWaitingPassengers.get(currentStation.id) || 0;
      const availableCapacity = this.config.trainCapacity - train.passengers;
      const boarding = Math.min(waiting, availableCapacity, Math.round(influxRate * 30));

      if (boarding > 0) {
        train.passengers += boarding;
        this.stationWaitingPassengers.set(currentStation.id, Math.max(0, waiting - boarding));
        this.passengersServed += boarding;
        this.totalWaitTime += boarding * 2;
      }
    }
  }

  private calculateMetrics(): Metrics {
    const trains = Array.from(this.trains.values());
    const activeTrains = trains.filter(t => this.currentTime >= t.departureTime);
    const loads = activeTrains.map((t) => t.passengers);
    const avgLoad = loads.length > 0 ? loads.reduce((a, b) => a + b, 0) / loads.length : 0;
    const variance = loads.length > 0 && avgLoad > 0
      ? Math.pow(Math.sqrt(loads.reduce((sum, load) => sum + Math.pow(load - avgLoad, 2), 0) / loads.length) / avgLoad, 2)
      : 0;
    const totalEnergy = activeTrains.reduce((sum, t) => sum + t.energyConsumed, 0);
    const totalRunningHours = activeTrains.reduce((sum, t) => {
      return sum + Math.max(0, (this.currentTime - t.departureTime) / 60);
    }, 0);

    return {
      avgWaitingTime: this.passengersServed > 0 ? this.totalWaitTime / this.passengersServed : 0,
      totalRunningTime: totalRunningHours,
      kwhPrice: this.config.kwhPrice,
      totalEnergyConsumption: totalEnergy,
      totalEnergyCost: totalEnergy * this.config.kwhPrice,
      avgTrainLoad: avgLoad,
      trainLoadVariance: Math.min(variance, 1),
      passengersServed: this.passengersServed,
      totalPassengerMinutes: this.totalWaitTime,
    };
  }
}

const MetroMap: React.FC<{ config: SimulationConfig; trains: Train[]; label: string; isOptimized?: boolean; waitingPassengers: Map<string, number> }> = ({ config, trains, label, isOptimized, waitingPassengers }) => {
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

    const project = (lat: number, lon: number) => ({ x: padding + (lon - minLon) * scaleX, y: h - (padding + (lat - minLat) * scaleY) });

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

    config.stations.forEach((station, i) => {
      const pos = project(station.lat, station.lon);
      const waitingPaxRaw = waitingPassengers.get(station.id) || 0;
      const waitingPax = Math.max(0, Math.round(waitingPaxRaw));

      if (waitingPax > 0) {
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

      ctx.fillStyle = "#999999";
      ctx.font = "10px 'Courier New', monospace";
      ctx.textAlign = i % 2 === 0 ? "right" : "left";
      const offset = i % 2 === 0 ? -10 : 10;
      ctx.fillText(station.nameEn, pos.x + offset, pos.y + 3);
    });

    trains.forEach((train) => {
      if (train.stationIndex < 0 || train.stationIndex >= config.stations.length) return;

      let targetLat = 0, targetLon = 0;
      let foundPosition = false;

      for (let i = 0; i < config.stations.length - 1; i++) {
        const s1 = config.stations[i];
        const s2 = config.stations[i + 1];
        if (train.position >= Math.min(s1.distanceFromStart, s2.distanceFromStart) &&
          train.position <= Math.max(s1.distanceFromStart, s2.distanceFromStart)) {
          const ratio = Math.abs(train.position - s1.distanceFromStart) / Math.abs(s2.distanceFromStart - s1.distanceFromStart || 1);
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
      <div className="absolute top-2 left-2 text-white text-xs font-mono bg-black/90 px-2 py-1 border border-white/30">{label}</div>
      <canvas ref={canvasRef} className="w-full h-full" />
    </div>
  );
};

const CapacityBar: React.FC<{ trains: Train[]; capacity: number; label: string; isPlaying: boolean }> = ({ trains, capacity, label, isPlaying }) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const animationRef = useRef<number | null>(null);

  useEffect(() => {
    if (!isPlaying || !scrollRef.current) return;

    let lastTime = performance.now();
    const speed = 19.5; // pixels per second

    const scroll = (now: number) => {
      const dt = (now - lastTime) / 1000; // seconds since last frame
      lastTime = now;

      const el = scrollRef.current;
      if (el) {
        el.scrollTop += speed * dt;
        if (el.scrollTop >= el.scrollHeight - el.clientHeight) {
          el.scrollTop = 0;
        }
      }
      animationRef.current = requestAnimationFrame(scroll);
    };

    animationRef.current = requestAnimationFrame(scroll);

    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, [isPlaying]);


  return (
    <div className="space-y-1">
      <div className="text-xs text-white/60 font-mono mb-2">{label}</div>
      <div ref={scrollRef} className="overflow-y-auto space-y-1 pr-2" style={{ height: '160px', scrollBehavior: isPlaying ? 'auto' : 'smooth' }}>
        {trains.map((train) => {
          const loadFactor = train.passengers / capacity;
          let color = "#44ff44";
          if (loadFactor > 0.85) color = "#ff4444";
          else if (loadFactor < 0.3) color = "#4488ff";

          return (
            <div key={train.id} className="flex items-center gap-2">
              <div className="text-[10px] font-mono text-white/40 w-8 flex items-center gap-1">
                <span>{train.id}</span>
                <span className="text-[8px]">{train.direction === "eastbound" ? "→" : "←"}</span>
              </div>
              <div className="flex-1 h-4 bg-white/10 border border-white/20 relative">
                <div className="h-full transition-all duration-300" style={{ width: `${(loadFactor * 100).toFixed(1)}%`, backgroundColor: color }} />
                <div className="absolute inset-0 flex items-center justify-center text-[9px] font-mono text-white font-bold">{Math.round(train.passengers)}/{capacity}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default function Home() {
  const START_TIME = 330;
  const END_TIME = 1770;
  const DAY_LENGTH = 1440;

  const [currentTime, setCurrentTime] = useState(START_TIME);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(60);
  const [showComparison, setShowComparison] = useState(false);
  const [currentDay, setCurrentDay] = useState(1);

  const officialSim = useMemo(() => new MetroSimulator(ATHENS_LINE3_CONFIG, ATHENS_LINE3_CONFIG.officialSchedule), []);
  const optimizedSim = useMemo(() => new MetroSimulator(ATHENS_LINE3_CONFIG, ATHENS_LINE3_CONFIG.optimizedSchedule), []);

  const officialState = officialSim.update(currentTime);
  const optimizedState = optimizedSim.update(currentTime);
  const officialWaiting = officialSim.getStationWaitingPassengers();
  const optimizedWaiting = optimizedSim.getStationWaitingPassengers();

  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setCurrentTime((prev) => {
        const next = prev + 0.5;
        if (next >= START_TIME + DAY_LENGTH) {
          setCurrentDay(d => d + 1);
          officialSim.reset();
          optimizedSim.reset();
          return START_TIME;
        }
        return next;
      });
    }, 1000 / speed);
    return () => clearInterval(interval);
  }, [isPlaying, speed, officialSim, optimizedSim]);

  const formatTime = (minutes: number) => {
    const h = Math.floor(minutes / 60);
    const m = Math.floor(minutes % 60);
    return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}`;
  };

  const calculateImprovement = (official: number, optimized: number) => {
    if (official === 0) return 0;
    return ((official - optimized) / official) * 100;
  };

  const handleReset = () => {
    setCurrentTime(START_TIME);
    setIsPlaying(false);
    setCurrentDay(1);
    officialSim.reset();
    optimizedSim.reset();
  };

  return (
    <main className="min-h-screen bg-black text-white flex flex-col">
      <div className="border-b border-white/20 bg-black px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="text-sm font-mono">
            <span className="text-white/60">Athens Metro Line 3:</span> <span className="text-white">AI Schedule Optimization</span>
          </div>
          <div className="text-xs font-mono text-white/40 bg-white/5 px-2 py-1 border border-white/20">
            Day {currentDay}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-xs font-mono text-white/60 bg-white/5 px-3 py-1 border border-white/20">
            <Clock className="inline w-3 h-3 mr-1" />{formatTime(currentTime)}
          </div>
          {!showComparison ? (
            <button onClick={() => { setShowComparison(true); handleReset(); }} className="text-xs font-mono px-4 py-1 bg-white text-black hover:bg-white/90 transition-colors flex items-center gap-2">
              <Zap className="w-3 h-3" />COMPARE WITH AI
            </button>
          ) : (
            <button onClick={() => { setShowComparison(false); handleReset(); }} className="text-xs font-mono px-4 py-1 border border-white/40 hover:bg-white/10 transition-colors">BACK</button>
          )}
        </div>
      </div>

      <div className="flex-1 flex flex-col p-6 gap-6 overflow-y-auto">
        {!showComparison ? (
          <>
            <div className="flex-1 grid grid-cols-3 gap-6">
              <div className="col-span-2">
                <MetroMap config={ATHENS_LINE3_CONFIG} trains={officialState.trains} label="OFFICIAL SCHEDULE" isOptimized={false} waitingPassengers={officialWaiting} />
              </div>
              <div className="space-y-6">
                <div className="border border-white/20 bg-black p-4 space-y-3">
                  <div className="text-xs font-mono text-white/60 border-b border-white/10 pb-2">CURRENT METRICS</div>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-white/60">Avg Wait Time</span>
                      <span className="font-mono text-lg text-white">{officialState.metrics.avgWaitingTime.toFixed(1)} <span className="text-xs text-white/40">min</span></span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-white/60">Energy Cost</span>
                      <span className="font-mono text-lg text-white">€{officialState.metrics.totalEnergyCost.toFixed(0)}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-white/60">Avg Load</span>
                      <span className="font-mono text-lg text-white">{officialState.metrics.avgTrainLoad.toFixed(0)} <span className="text-xs text-white/40">pax</span></span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-white/60">Load Variance</span>
                      <span className="font-mono text-lg text-white">{officialState.metrics.trainLoadVariance.toFixed(3)}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-white/60">Running Time</span>
                      <span className="font-mono text-lg text-white">{officialState.metrics.totalRunningTime.toFixed(1)} <span className="text-xs text-white/40">hrs</span></span>
                    </div>
                  </div>
                </div>
                <div className="border border-white/20 bg-black p-4">
                  <CapacityBar trains={officialState.trains} capacity={ATHENS_LINE3_CONFIG.trainCapacity} label="TRAIN CAPACITY (40 trains)" isPlaying={isPlaying} />
                </div>
                <div className="border border-white/20 bg-black p-3 text-[10px] space-y-1">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3" style={{ backgroundColor: "#44ff44" }} />
                    <span className="text-white/60">Optimal (30-85%)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3" style={{ backgroundColor: "#4488ff" }} />
                    <span className="text-white/60">Undercrowded (&lt;30%)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3" style={{ backgroundColor: "#ff4444" }} />
                    <span className="text-white/60">Overcrowded (&gt;85%)</span>
                  </div>
                  <div className="border-t border-white/10 mt-2 pt-2">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full" style={{ border: "2px solid #ffaa00", backgroundColor: "rgba(255, 165, 0, 0.25)" }} />
                      <span className="text-white/60">Waiting passengers</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div className="border border-white/20 bg-black p-4">
              <div className="flex items-center gap-4">
                <button onClick={() => setIsPlaying((p) => !p)} className="px-4 py-2 bg-white text-black hover:bg-white/90 transition-colors text-xs font-mono flex items-center gap-2">
                  {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}{isPlaying ? "PAUSE" : "PLAY"}
                </button>
                <button onClick={handleReset} className="px-4 py-2 border border-white/40 hover:bg-white/10 transition-colors text-xs font-mono flex items-center gap-2">
                  <RotateCcw className="w-4 h-4" />RESET
                </button>
                <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} className="bg-black border border-white/40 px-3 py-2 text-xs font-mono text-white">
                  <option value={5}>5x</option>
                  <option value={30}>30x</option>
                  <option value={60}>60x</option>
                  <option value={120}>120x</option>
                </select>
                <div className="flex-1">
                  <input type="range" min={START_TIME} max={END_TIME} step={0.5} value={currentTime} onChange={(e) => { setCurrentTime(Number(e.target.value)); setIsPlaying(false); }} className="w-full" />
                  <div className="flex justify-between text-[10px] text-white/40 font-mono mt-1">
                    <span>{formatTime(START_TIME)}</span>
                    <span>DAY {currentDay}</span>
                    <span>{formatTime(END_TIME)}</span>
                  </div>
                </div>
              </div>
            </div>
          </>
        ) : (
          <>
            <div className="flex-1 grid grid-cols-2 gap-6">
              <div className="flex flex-col gap-4">
                <div className="flex-1">
                  <MetroMap config={ATHENS_LINE3_CONFIG} trains={officialState.trains} label="OFFICIAL SCHEDULE" isOptimized={false} waitingPassengers={officialWaiting} />
                </div>
                <div className="border border-white/20 bg-black p-4">
                  <CapacityBar trains={officialState.trains} capacity={ATHENS_LINE3_CONFIG.trainCapacity} label="CAPACITY - OFFICIAL" isPlaying={isPlaying} />
                </div>
                <div className="border border-white/20 bg-black p-3 space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-white/60">Avg Wait</span>
                    <span className="font-mono text-white">{officialState.metrics.avgWaitingTime.toFixed(1)} min</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/60">Energy Cost</span>
                    <span className="font-mono text-white">€{officialState.metrics.totalEnergyCost.toFixed(0)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/60">Variance</span>
                    <span className="font-mono text-white">{officialState.metrics.trainLoadVariance.toFixed(3)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/60">Avg Load</span>
                    <span className="font-mono text-white">{officialState.metrics.avgTrainLoad.toFixed(0)} pax</span>
                  </div>
                </div>
              </div>
              <div className="flex flex-col gap-4">
                <div className="flex-1">
                  <MetroMap config={ATHENS_LINE3_CONFIG} trains={optimizedState.trains} label="AI-OPTIMIZED SCHEDULE" isOptimized={true} waitingPassengers={optimizedWaiting} />
                </div>
                <div className="border border-white/20 bg-black p-4">
                  <CapacityBar trains={optimizedState.trains} capacity={ATHENS_LINE3_CONFIG.trainCapacity} label="CAPACITY - AI OPTIMIZED" isPlaying={isPlaying} />
                </div>
                <div className="border border-green-500/30 bg-green-500/10 p-3 space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-white/70">Avg Wait</span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-white">{optimizedState.metrics.avgWaitingTime.toFixed(1)} min</span>
                      <span className={`font-mono text-[10px] ${calculateImprovement(officialState.metrics.avgWaitingTime, optimizedState.metrics.avgWaitingTime) > 0 ? "text-green-400" : "text-red-400"}`}>
                        {calculateImprovement(officialState.metrics.avgWaitingTime, optimizedState.metrics.avgWaitingTime) > 0 ? "↓" : "↑"}{Math.abs(calculateImprovement(officialState.metrics.avgWaitingTime, optimizedState.metrics.avgWaitingTime)).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/70">Energy Cost</span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-white">€{optimizedState.metrics.totalEnergyCost.toFixed(0)}</span>
                      <span className={`font-mono text-[10px] ${calculateImprovement(officialState.metrics.totalEnergyCost, optimizedState.metrics.totalEnergyCost) > 0 ? "text-green-400" : "text-red-400"}`}>
                        {calculateImprovement(officialState.metrics.totalEnergyCost, optimizedState.metrics.totalEnergyCost) > 0 ? "↓" : "↑"}{Math.abs(calculateImprovement(officialState.metrics.totalEnergyCost, optimizedState.metrics.totalEnergyCost)).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/70">Variance</span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-white">{optimizedState.metrics.trainLoadVariance.toFixed(3)}</span>
                      <span className={`font-mono text-[10px] ${calculateImprovement(officialState.metrics.trainLoadVariance, optimizedState.metrics.trainLoadVariance) > 0 ? "text-green-400" : "text-red-400"}`}>
                        {calculateImprovement(officialState.metrics.trainLoadVariance, optimizedState.metrics.trainLoadVariance) > 0 ? "↓" : "↑"}{Math.abs(calculateImprovement(officialState.metrics.trainLoadVariance, optimizedState.metrics.trainLoadVariance)).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/70">Avg Load</span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-white">{optimizedState.metrics.avgTrainLoad.toFixed(0)} pax</span>
                      <span className={`font-mono text-[10px] ${Math.abs(calculateImprovement(optimizedState.metrics.avgTrainLoad, officialState.metrics.avgTrainLoad)) < 5 ? "text-white/40" : "text-green-400"}`}>
                        {officialState.metrics.avgTrainLoad > optimizedState.metrics.avgTrainLoad ? "↓" : "↑"}{Math.abs(calculateImprovement(optimizedState.metrics.avgTrainLoad, officialState.metrics.avgTrainLoad)).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div className="border border-white/20 bg-black p-4">
              <div className="flex items-center gap-4">
                <button onClick={() => setIsPlaying((p) => !p)} className="px-4 py-2 bg-white text-black hover:bg-white/90 transition-colors text-xs font-mono flex items-center gap-2">
                  {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}{isPlaying ? "PAUSE" : "PLAY"}
                </button>
                <button onClick={handleReset} className="px-4 py-2 border border-white/40 hover:bg-white/10 transition-colors text-xs font-mono flex items-center gap-2">
                  <RotateCcw className="w-4 h-4" />RESET
                </button>
                <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} className="bg-black border border-white/40 px-3 py-2 text-xs font-mono text-white">
                  <option value={5}>5x</option>
                  <option value={30}>30x</option>
                  <option value={60}>60x</option>
                  <option value={120}>120x</option>
                </select>
                <div className="flex-1">
                  <input type="range" min={START_TIME} max={END_TIME} step={0.5} value={currentTime} onChange={(e) => { setCurrentTime(Number(e.target.value)); setIsPlaying(false); }} className="w-full" />
                  <div className="flex justify-between text-[10px] text-white/40 font-mono mt-1">
                    <span>{formatTime(START_TIME)}</span>
                    <span>DAY {currentDay}</span>
                    <span>{formatTime(END_TIME)}</span>
                  </div>
                </div>
                <div className="border border-green-500/50 bg-green-500/10 px-4 py-2">
                  <div className="text-[10px] text-green-400/80 mb-1">KEY IMPROVEMENT</div>
                  <div className="text-sm font-mono text-green-400">↓ {Math.abs(calculateImprovement(officialState.metrics.avgWaitingTime, optimizedState.metrics.avgWaitingTime)).toFixed(1)}% Wait Time</div>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </main>
  );
}