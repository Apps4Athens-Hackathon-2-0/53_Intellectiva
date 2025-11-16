// =======================
// TYPES & INTERFACES
// =======================


export interface Trip {
    trainId: string;
    departureTime: number;
    direction: "eastbound" | "westbound";
    stationIds: string[];
}

export interface Schedule {
    trips: Trip[];
}

export interface PassengerDemandMatrix {
    boardings: number[][];     // [stationIndex][minuteIndex]
    disembarks: number[][];    // [stationIndex][minuteIndex]
    startMinute: number;       // e.g. 330 (05:30)
}


export interface Station {
    id: string;
    name: string;
    nameEn: string;
    lat: number;
    lon: number;
    distanceFromStart: number;
    influxRate: number;
    exitFraction?: number;
}

export interface SimulationConfig {
    stations: Station[];
    officialSchedule: Schedule;
    optimizedSchedule: Schedule;
    trainCapacity: number;
    avgSpeed: number;             // km/min
    dwellTime: number;            // min
    energyConsumptionRate: number; // kWh per train-km
    kwhPrice: number;
    passengerDemand?: PassengerDemandMatrix;
}

export interface Train {
    id: string;
    position: number;   // km along the line
    stationIndex: number;
    direction: "eastbound" | "westbound";
    passengers: number;
    nextStationArrival: number;   // used as "segment start time"
    status: "moving" | "stopped" | "turnaround";
    energyConsumed: number;
    departureTime: number;
    lastStopTime: number;
    turnaroundStartTime: number;  // unused in simple model, kept for type compatibility
    endTime: number;              // when the trip is considered finished
}

export interface Metrics {
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

export type HeadwaySegment = {
    from: number;
    to: number;
    headway: number;
};
