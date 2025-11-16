'use client';
import React, { useState, useEffect, useRef, useMemo } from "react";
import { Play, Pause, RotateCcw, Zap, Clock } from "lucide-react";
import { HeadwaySegment, Metrics, PassengerDemandMatrix, Schedule, SimulationConfig, Train, Trip } from "./types/main";
import { normalizeGreek, timeToMinutes } from "./hooks/helperFunctions";
import { generateOfficialSchedule, generateOptimizedSchedule } from "./libs/generateTimetable";
import { MetroMap } from "./components/metroMap";
import { SIM_DATE } from "./libs/constants";


// =======================
// OASA DATA INTEGRATION
// =======================

const OASA_STATION_MAPPING: Record<string, string> = {
  "ΔΗΜΟΤΙΚΟ ΘΕΑΤΡΟ": "s01",
  "ΠΕΙΡΑΙΑΣ": "s02",
  "ΜΑΝΙΑΤΙΚΑ": "s03",
  "ΝΙΚΑΙΑ": "s04",
  "ΚΟΡΥΔΑΛΛΟΣ": "s05",
  "ΑΓΙΑ ΒΑΡΒΑΡΑ": "s06",
  "ΑΓΙΑ ΜΑΡΙΝΑ": "s07",
  "ΑΙΓΑΛΕΩ": "s08",
  "ΕΛΑΙΩΝΑΣ": "s09",
  "ΚΕΡΑΜΕΙΚΟΣ": "s10",
  "ΜΟΝΑΣΤΗΡΑΚΙ": "s11",
  "ΣΥΝΤΑΓΜΑ": "s12",
  "ΕΥΑΓΓΕΛΙΣΜΟΣ": "s13",
  "ΜΕΓΑΡΟ ΜΟΥΣΙΚΗΣ": "s14",
  "ΑΜΠΕΛΟΚΗΠΟΙ": "s15",
  "ΠΑΝΟΡΜΟΥ": "s16",
  "ΚΑΤΕΧΑΚΗ": "s17",
  "ΕΘΝΙΚΗ ΑΜΥΝΑ": "s18",
  "ΧΟΛΑΡΓΟΣ": "s19",
  "ΝΟΜΙΣΜΑΤΟΚΟΠΕΙΟ": "s20",
  "ΑΓΙΑ ΠΑΡΑΣΚΕΥΗ": "s21",
  "ΧΑΛΑΝΔΡΙ": "s22",
  "ΔΟΥΚΙΣΣΗΣ ΠΛΑΚΕΝΤΙΑΣ": "s23",
  "ΠΑΛΛΗΝΗ": "s24",
  "ΠΑΙΑΝΙΑ - ΚΑΝΤΖΑ": "s25",
  "ΚΟΡΩΠΙ": "s26",
  "ΑΕΡΟΔΡΟΜΙΟ": "s27",
};




const NORMALIZED_OASA_MAPPING: Record<string, string> = {};

Object.entries(OASA_STATION_MAPPING).forEach(([name, sid]) => {
  NORMALIZED_OASA_MAPPING[normalizeGreek(name)] = sid;
});



async function loadOASADataForDay(date: string): Promise<PassengerDemandMatrix | null> {
  try {
    const START_MINUTE = 330;                // 05:30
    const END_MINUTE = timeToMinutes("24:20");
    const MINUTES = END_MINUTE - START_MINUTE + 1;
    const STATION_COUNT = 27;

    const boardings: number[][] = Array.from({ length: STATION_COUNT }, () =>
      new Array(MINUTES).fill(0)
    );
    const disembarks: number[][] = Array.from({ length: STATION_COUNT }, () =>
      new Array(MINUTES).fill(0)
    );

    // Build query with date_from / date_to (same day for this helper)
    const params = new URLSearchParams({
      date_from: date,   // e.g. "2025-11-10"
      date_to: date,     // same date => single day
      limit: "50000",
    });

    const url = `https://data.gov.gr/api/v1/query/oasa_ridership?${params.toString()}`;

    const response = await fetch(url, {
      // If you have an API token, you’ll likely need something like:
      // headers: {
      //   Authorization: `Token ${process.env.NEXT_PUBLIC_DATA_GOV_GR_TOKEN}`,
      // },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();

    let recordsProcessed = 0;
    let recordsSkipped = [0, 0, 0, 0, 0, 0, 0];
    data.forEach((record: any) => {
      // agency 2 = Metro / Line 3, as before
      if (record.dv_agency !== "002") {
        recordsSkipped[0]++;
        return;
      }

      const type = record.boarding_disembark_desc; // "BOARDING" or "DISEMBARK"
      if (type !== "Boarding" && type !== "Disembark") {
        recordsSkipped[1]++;
        return;
      }


      const rawName = record.dv_platenum_station || "";
      const stationName = normalizeGreek(rawName);
      const stationId = NORMALIZED_OASA_MAPPING[stationName];

      if (!stationId) {
        recordsSkipped[2]++;
        return;
      }



      const stationIndex = parseInt(stationId.substring(1), 10) - 1;
      if (stationIndex < 0 || stationIndex >= STATION_COUNT) {
        recordsSkipped[3]++;
        return;
      }


      const dateHour = new Date(record.date_hour);
      const hourOfDay = dateHour.getHours();
      const minuteOfDay = hourOfDay * 60 + dateHour.getMinutes();

      if (minuteOfDay < START_MINUTE || minuteOfDay > END_MINUTE) {
        recordsSkipped[4]++;
        return;
      }

      const validations = parseFloat(record.dv_validations) || 0;
      if (!Number.isFinite(validations) || validations <= 0) {
        recordsSkipped[5]++;
        return;
      }

      // Distribute this hourly count over the full hour [HH:00 .. HH:59]
      const hourStartMinute = minuteOfDay - (minuteOfDay % 60);

      // Smooth shape inside the hour (peaks in the middle)
      const weights: number[] = [];
      let weightSum = 0;
      for (let m = 0; m < 60; m++) {
        const x = (m / 59) * Math.PI;      // 0 .. π
        const w = Math.sin(x) + 0.1;      // >0, more in the middle of the hour
        weights.push(w);
        weightSum += w;
      }

      for (let m = 0; m < 60; m++) {
        const minute = hourStartMinute + m;
        if (minute < START_MINUTE || minute > END_MINUTE) continue;

        const timeIndex = minute - START_MINUTE;
        const value = validations * (weights[m] / weightSum);

        if (type === "Boarding") {
          boardings[stationIndex][timeIndex] += value * 1;
          recordsProcessed++;
        } else if (type === "Disembark") {
          disembarks[stationIndex][timeIndex] += value * 1;
          recordsProcessed++;
        } else {
          recordsSkipped[5]++;
        }
      }


      recordsProcessed++;
    });

    console.log(
      `OASA data loaded for ${date}: ${recordsProcessed} records processed & ${recordsSkipped} records skipped`
    );

    return {
      boardings,
      disembarks,
      startMinute: START_MINUTE,
    };
  } catch (error) {
    console.error("Failed to load OASA data:", error);
    return null;
  }
}



// =======================
// DEMAND PLACEHOLDER (FALLBACK)
// =======================

const DEMAND_ARRIVALS: number[][] = (() => {
  const STATION_COUNT = 27;
  const START_MINUTE = 330; // 05:30
  const END_MINUTE = timeToMinutes("24:20");
  const MINUTES = END_MINUTE - START_MINUTE + 1;

  const stationWeights = [
    1.2, 1.4, 0.6, 0.7, 0.8, 0.7, 0.8, 1.0, 0.4, 1.2, 1.8, 1.8, 1.0,
    0.8, 1.2, 1.0, 0.8, 1.0, 0.9, 0.9, 1.0, 1.1, 1.0, 0.7, 0.7, 0.8, 1.6,
  ];

  function baseDemandProfile(minute: number): number {
    const h = Math.floor(minute / 60);
    const m = minute % 60;
    const t = h + m / 60;

    if (t < 5) return 0.02;
    if (t < 6) return 0.05 + (t - 5) * 0.25;
    if (t < 7) return 0.3 + (t - 6) * 0.4;
    if (t < 9) return 1.0;
    if (t < 13) return 0.55;
    if (t < 17) return 0.55 + ((t - 13) / 4) * 0.35;
    if (t < 20) return 0.75;
    if (t < 22) return 0.75 - ((t - 20) / 2) * 0.35;
    return 0.15;
  }

  function airportBoost(minute: number): number {
    const h = Math.floor(minute / 60);
    if (h < 6 || h >= 22) return 1.3;
    if (h >= 10 && h <= 14) return 1.2;
    return 1.0;
  }

  const scale = 1.2;
  const matrix: number[][] = Array.from({ length: STATION_COUNT }, () =>
    new Array(MINUTES).fill(0)
  );

  for (let tIdx = 0; tIdx < MINUTES; tIdx++) {
    const minute = START_MINUTE + tIdx;
    const base = baseDemandProfile(minute);

    for (let sIdx = 0; sIdx < STATION_COUNT; sIdx++) {
      let factor = base * stationWeights[sIdx];
      if (sIdx === 26) factor *= airportBoost(minute);
      const noise = 0.85 + Math.random() * 0.3;
      const value = factor * scale * noise;
      matrix[sIdx][tIdx] = Number(Math.max(0, value).toFixed(2));
    }
  }

  return matrix;
})();


const MON_THU_CORE_HEADWAYS: HeadwaySegment[] = [
  { from: timeToMinutes("05:30"), to: timeToMinutes("06:00"), headway: 10 },
  { from: timeToMinutes("06:00"), to: timeToMinutes("06:30"), headway: 7 },
  { from: timeToMinutes("06:30"), to: timeToMinutes("07:00"), headway: 4.5 },
  { from: timeToMinutes("07:00"), to: timeToMinutes("10:00"), headway: 4 },
  { from: timeToMinutes("10:00"), to: timeToMinutes("10:30"), headway: 5 },
  { from: timeToMinutes("10:30"), to: timeToMinutes("13:30"), headway: 6 },
  { from: timeToMinutes("13:30"), to: timeToMinutes("14:00"), headway: 5.5 },
  { from: timeToMinutes("14:00"), to: timeToMinutes("18:00"), headway: 4.25 },
  { from: timeToMinutes("18:00"), to: timeToMinutes("19:30"), headway: 4.5 },
  { from: timeToMinutes("19:30"), to: timeToMinutes("20:30"), headway: 5.5 },
  { from: timeToMinutes("20:30"), to: timeToMinutes("21:00"), headway: 6.25 },
  { from: timeToMinutes("21:00"), to: timeToMinutes("21:30"), headway: 7 },
  { from: timeToMinutes("21:30"), to: timeToMinutes("22:00"), headway: 8 },
  { from: timeToMinutes("22:00"), to: timeToMinutes("24:20"), headway: 9 },
];

const LINE3_STATION_IDS_EASTBOUND: string[] = [
  "s01",
  "s02",
  "s03",
  "s04",
  "s05",
  "s06",
  "s07",
  "s08",
  "s09",
  "s10",
  "s11",
  "s12",
  "s13",
  "s14",
  "s15",
  "s16",
  "s17",
  "s18",
  "s19",
  "s20",
  "s21",
  "s22",
  "s23",
  "s24",
  "s25",
  "s26",
  "s27",
];

const LINE3_STATION_IDS_WESTBOUND: string[] = [...LINE3_STATION_IDS_EASTBOUND].reverse();

function buildScheduleFromSegments(
  segments: HeadwaySegment[],
  idPrefix: string,
  eastStations: string[],
  westStations: string[]
): Schedule {
  const trips: Trip[] = [];
  let idx = 1;

  for (const seg of segments) {
    for (let t = seg.from; t < seg.to; t += seg.headway) {
      const num = String(idx).padStart(3, "0");

      trips.push({
        trainId: `${idPrefix}E${num}`,
        departureTime: t,
        direction: "eastbound",
        stationIds: eastStations,
      });

      trips.push({
        trainId: `${idPrefix}W${num}`,
        departureTime: t,
        direction: "westbound",
        stationIds: westStations,
      });

      idx++;
    }
  }
  return { trips };
}

// =======================
// CONFIG WITH OFFICIAL DATA
// =======================

const ATHENS_LINE3_CONFIG: SimulationConfig = {
  stations: [
    {
      id: "s01",
      name: "Δημοτικό Θέατρο",
      nameEn: "Dimotiko Theatro",
      lat: 37.942905,
      lon: 23.64735,
      distanceFromStart: 0.0,
      influxRate: 0.8,
      exitFraction: 0.25,
    },
    {
      id: "s02",
      name: "Πειραιάς",
      nameEn: "Piraeus",
      lat: 37.9481,
      lon: 23.642265,
      distanceFromStart: 1.5,
      influxRate: 1.2,
      exitFraction: 0.2,
    },
    {
      id: "s03",
      name: "Μανιάτικα",
      nameEn: "Maniatika",
      lat: 37.959545,
      lon: 23.63978,
      distanceFromStart: 3.0,
      influxRate: 0.5,
      exitFraction: 0.1,
    },
    {
      id: "s04",
      name: "Νίκαια",
      nameEn: "Nikaia",
      lat: 37.965745,
      lon: 23.64755,
      distanceFromStart: 4.5,
      influxRate: 0.7,
      exitFraction: 0.08,
    },
    {
      id: "s05",
      name: "Κορυδαλλός",
      nameEn: "Korydallos",
      lat: 37.97705,
      lon: 23.650405,
      distanceFromStart: 6.0,
      influxRate: 0.9,
      exitFraction: 0.08,
    },
    {
      id: "s06",
      name: "Αγία Βαρβάρα",
      nameEn: "Agia Varvara",
      lat: 37.98971,
      lon: 23.65932,
      distanceFromStart: 7.5,
      influxRate: 0.6,
      exitFraction: 0.05,
    },
    {
      id: "s07",
      name: "Αγία Μαρίνα",
      nameEn: "Agia Marina",
      lat: 37.99686,
      lon: 23.66713,
      distanceFromStart: 9.0,
      influxRate: 0.8,
      exitFraction: 0.05,
    },
    {
      id: "s08",
      name: "Αιγάλεω",
      nameEn: "Egaleo",
      lat: 37.99142,
      lon: 23.68169,
      distanceFromStart: 10.5,
      influxRate: 1.0,
      exitFraction: 0.07,
    },
    {
      id: "s09",
      name: "Ελαιώνας",
      nameEn: "Eleonas",
      lat: 37.987725,
      lon: 23.693375,
      distanceFromStart: 12.8,
      influxRate: -0.3,
      exitFraction: 0.05,
    },
    {
      id: "s10",
      name: "Κεραμεικός",
      nameEn: "Kerameikos",
      lat: 37.978715,
      lon: 23.71094,
      distanceFromStart: 15.0,
      influxRate: 1.5,
      exitFraction: 0.1,
    },
    {
      id: "s11",
      name: "Μοναστηράκι",
      nameEn: "Monastiraki",
      lat: 37.976615,
      lon: 23.725905,
      distanceFromStart: 16.5,
      influxRate: 2.0,
      exitFraction: 0.25,
    },
    {
      id: "s12",
      name: "Σύνταγμα",
      nameEn: "Syntagma",
      lat: 37.97479,
      lon: 23.735535,
      distanceFromStart: 18.0,
      influxRate: 1.8,
      exitFraction: 0.25,
    },
    {
      id: "s13",
      name: "Ευαγγελισμός",
      nameEn: "Evangelismos",
      lat: 37.9759,
      lon: 23.74656,
      distanceFromStart: 19.5,
      influxRate: -0.5,
      exitFraction: 0.1,
    },
    {
      id: "s14",
      name: "Μέγαρο Μουσικής",
      nameEn: "Megaro Moussikis",
      lat: 37.97937,
      lon: 23.753515,
      distanceFromStart: 20.3,
      influxRate: -0.4,
      exitFraction: 0.08,
    },
    {
      id: "s15",
      name: "Αμπελόκηποι",
      nameEn: "Ambelokipi",
      lat: 37.986945,
      lon: 23.7576,
      distanceFromStart: 21.8,
      influxRate: 0.9,
      exitFraction: 0.1,
    },
    {
      id: "s16",
      name: "Πανόρμου",
      nameEn: "Panormou",
      lat: 37.99303,
      lon: 23.76353,
      distanceFromStart: 23.3,
      influxRate: 0.7,
      exitFraction: 0.08,
    },
    {
      id: "s17",
      name: "Κατεχάκη",
      nameEn: "Katehaki",
      lat: 37.993445,
      lon: 23.776965,
      distanceFromStart: 24.8,
      influxRate: 0.6,
      exitFraction: 0.08,
    },
    {
      id: "s18",
      name: "Εθνική Άμυνα",
      nameEn: "Ethniki Amyna",
      lat: 37.999475,
      lon: 23.78481,
      distanceFromStart: 26.3,
      influxRate: -0.2,
      exitFraction: 0.1,
    },
    {
      id: "s19",
      name: "Χολαργός",
      nameEn: "Holargos",
      lat: 38.00471,
      lon: 23.794355,
      distanceFromStart: 27.8,
      influxRate: 0.5,
      exitFraction: 0.08,
    },
    {
      id: "s20",
      name: "Νομισματοκοπείο",
      nameEn: "Nomismatokopio",
      lat: 38.009425,
      lon: 23.80597,
      distanceFromStart: 29.3,
      influxRate: 0.4,
      exitFraction: 0.08,
    },
    {
      id: "s21",
      name: "Αγία Παρασκευή",
      nameEn: "Agia Paraskevi",
      lat: 38.01738,
      lon: 23.812765,
      distanceFromStart: 30.0,
      influxRate: 0.8,
      exitFraction: 0.1,
    },
    {
      id: "s22",
      name: "Χαλάνδρι",
      nameEn: "Halandri",
      lat: 38.021755,
      lon: 23.821185,
      distanceFromStart: 31.5,
      influxRate: 1.1,
      exitFraction: 0.1,
    },
    {
      id: "s23",
      name: "Δουκίσσης Πλακεντίας",
      nameEn: "Doukissis Plakentias",
      lat: 38.023965,
      lon: 23.832545,
      distanceFromStart: 33.0,
      influxRate: -0.6,
      exitFraction: 0.15,
    },
    {
      id: "s24",
      name: "Παλλήνη",
      nameEn: "Pallini",
      lat: 38.0051,
      lon: 23.869825,
      distanceFromStart: 37.5,
      influxRate: 0.3,
      exitFraction: 0.1,
    },
    {
      id: "s25",
      name: "Παιανία - Κάντζα",
      nameEn: "Paiania-Kantza",
      lat: 37.984485,
      lon: 23.87002,
      distanceFromStart: 39.0,
      influxRate: 0.4,
      exitFraction: 0.1,
    },
    {
      id: "s26",
      name: "Κορωπί",
      nameEn: "Koropi",
      lat: 37.91286,
      lon: 23.89586,
      distanceFromStart: 43.5,
      influxRate: 0.5,
      exitFraction: 0.15,
    },
    {
      id: "s27",
      name: "Αεροδρόμιο",
      nameEn: "Airport",
      lat: 37.93689,
      lon: 23.9447,
      distanceFromStart: 47.3,
      influxRate: -1.5,
      exitFraction: 0.6,
    },
  ],
  trainCapacity: 1035,
  avgSpeed: 0.75,
  dwellTime: 1.0,
  energyConsumptionRate: 4.2,
  kwhPrice: 0.15,
  officialSchedule: buildScheduleFromSegments(
    MON_THU_CORE_HEADWAYS,
    "T",
    LINE3_STATION_IDS_EASTBOUND,
    LINE3_STATION_IDS_WESTBOUND
  ),
  optimizedSchedule: buildScheduleFromSegments(
    MON_THU_CORE_HEADWAYS.map((seg) => ({
      ...seg,
      headway: seg.headway * 0.9,
    })),
    "O",
    LINE3_STATION_IDS_EASTBOUND,
    LINE3_STATION_IDS_WESTBOUND
  ),
};

// =======================
// METRO SIMULATOR CLASS
// =======================

class MetroSimulator {
  private config: SimulationConfig;
  private schedule: Schedule;
  private trains: Map<string, Train> = new Map();
  private currentTime: number = 0;
  private passengersServed: number = 0;
  private stationWaitingPassengersEast: Map<string, number> = new Map();
  private stationWaitingPassengersWest: Map<string, number> = new Map();
  private startTime: number;
  private lastUpdateTime: number = 0;
  private lastDemandMinute: number;
  private routeLengthKm: number;
  private tripDurationMinutes: number;
  private totalWaitingPassengerMinutes: number = 0;

  constructor(config: SimulationConfig, schedule: Schedule) {
    this.config = config;
    this.schedule = schedule;

    // Start of simulation (matches UI)
    this.startTime = this.config.passengerDemand?.startMinute ?? 330;

    const stations = this.config.stations;
    const first = stations[0];
    const last = stations[stations.length - 1];

    this.routeLengthKm = Math.abs(last.distanceFromStart - first.distanceFromStart);

    // Very simple total trip duration: pure travel + dwell at each station
    const totalDwell = this.config.dwellTime * stations.length;
    this.tripDurationMinutes = this.routeLengthKm / this.config.avgSpeed + totalDwell;

    this.initializeTrains();

    this.config.stations.forEach((s) => {
      this.stationWaitingPassengersEast.set(s.id, 0);
      this.stationWaitingPassengersWest.set(s.id, 0);
    });

    const demandStart = this.config.passengerDemand?.startMinute ?? this.startTime;
    this.lastDemandMinute = demandStart - 1;
  }

  private initializeTrains() {
    this.trains.clear();

    this.schedule.trips.forEach((trip) => {
      const isEastbound = trip.direction === "eastbound";
      const startIndex = isEastbound ? 0 : this.config.stations.length - 1;
      const startStation = this.config.stations[startIndex];

      this.trains.set(trip.trainId, {
        id: trip.trainId,
        position: startStation.distanceFromStart,
        stationIndex: startIndex,
        direction: trip.direction,
        passengers: 0,
        nextStationArrival: trip.departureTime, // used as segment start time
        status: "stopped",
        energyConsumed: 0,
        departureTime: trip.departureTime,
        lastStopTime: trip.departureTime,
        turnaroundStartTime: 0,
        endTime: trip.departureTime + this.tripDurationMinutes,
      });
    });
  }

  private applyPassengerDemand(currentTime: number) {
    const demand = this.config.passengerDemand;
    if (!demand) return;

    const { boardings, startMinute } = demand;
    const currentMinute = Math.floor(currentTime);

    for (let t = this.lastDemandMinute + 1; t <= currentMinute; t++) {
      const timeIndex = t - startMinute;
      if (boardings.length === 0) break;
      if (timeIndex >= boardings[0].length) continue;

      // 1) For this minute, accumulate waiting passenger-minutes
      this.config.stations.forEach((station) => {
        const eastQ = this.stationWaitingPassengersEast.get(station.id) || 0;
        const westQ = this.stationWaitingPassengersWest.get(station.id) || 0;
        const totalQ = eastQ + westQ;
        // 1 minute * (number of passengers waiting)
        this.totalWaitingPassengerMinutes += totalQ;
      });

      // 2) Then add new arrivals for this minute
      this.config.stations.forEach((station, sIndex) => {
        const newlyArrivedTotal = boardings[sIndex]?.[timeIndex] ?? 0;
        if (newlyArrivedTotal <= 0) return;

        const eastArrivals = newlyArrivedTotal * 0.5;
        const westArrivals = newlyArrivedTotal - eastArrivals;

        const prevEast = this.stationWaitingPassengersEast.get(station.id) || 0;
        const prevWest = this.stationWaitingPassengersWest.get(station.id) || 0;

        this.stationWaitingPassengersEast.set(station.id, prevEast + eastArrivals);
        this.stationWaitingPassengersWest.set(station.id, prevWest + westArrivals);
      });
    }

    this.lastDemandMinute = currentMinute;
  }



  getStationWaitingPassengers(): Map<string, number> {
    const result = new Map<string, number>();
    this.config.stations.forEach((s) => {
      const east = this.stationWaitingPassengersEast.get(s.id) || 0;
      const west = this.stationWaitingPassengersWest.get(s.id) || 0;
      result.set(s.id, east + west);
    });
    return result;
  }

  reset() {
    this.totalWaitingPassengerMinutes = 0;
    this.passengersServed = 0;
    this.currentTime = this.startTime;
    this.lastUpdateTime = 0;

    this.initializeTrains();

    this.stationWaitingPassengersEast.clear();
    this.stationWaitingPassengersWest.clear();
    this.config.stations.forEach((s) => {
      this.stationWaitingPassengersEast.set(s.id, 0);
      this.stationWaitingPassengersWest.set(s.id, 0);
    });

    const demandStart = this.config.passengerDemand?.startMinute ?? this.startTime;
    this.lastDemandMinute = demandStart - 1;
  }

  update(currentTime: number): { trains: Train[]; metrics: Metrics } {
    this.lastUpdateTime = currentTime;
    this.currentTime = currentTime;

    if (currentTime < this.startTime) {
      this.reset();
      return { trains: Array.from(this.trains.values()), metrics: this.calculateMetrics() };
    }

    this.applyPassengerDemand(currentTime);
    this.trains.forEach((train) => this.updateTrain(train));

    return { trains: Array.from(this.trains.values()), metrics: this.calculateMetrics() };
  }

  private updateTrain(train: Train) {
    const stations = this.config.stations;

    // Before it starts: keep it idle at origin terminal
    if (this.currentTime < train.departureTime) {
      const originIndex =
        train.direction === "eastbound" ? 0 : stations.length - 1;
      train.stationIndex = originIndex;
      train.position = stations[originIndex].distanceFromStart;
      train.status = "stopped";
      train.passengers = 0;
      return;
    }

    // JUST STARTED: On the very first update after departure time, do passenger exchange
    const justStarted = this.currentTime >= train.departureTime &&
      this.currentTime < train.departureTime + 0.5 &&
      train.passengers === 0 &&
      train.status === "stopped";

    if (justStarted) {
      this.handlePassengerExchange(train);
    }

    // After trip end: put it at destination terminal and stop
    if (this.currentTime >= train.endTime) {
      const destIndex =
        train.direction === "eastbound" ? stations.length - 1 : 0;
      train.stationIndex = destIndex;
      train.position = stations[destIndex].distanceFromStart;
      train.status = "stopped";
      return;
    }

    // Stopped at a station
    if (train.status === "stopped") {
      const dwellElapsed = this.currentTime - train.lastStopTime;

      // Exchange passengers when arriving at a station (not origin)
      if (dwellElapsed === 0 && !justStarted) {
        this.handlePassengerExchange(train);
      }

      // After dwell time, start moving to next station if exists
      if (dwellElapsed >= this.config.dwellTime) {
        const nextStationIndex =
          train.direction === "eastbound"
            ? train.stationIndex + 1
            : train.stationIndex - 1;

        if (nextStationIndex < 0 || nextStationIndex >= stations.length) {
          return;
        }

        train.status = "moving";
        train.nextStationArrival = this.currentTime;
      }
      return;
    }

    // ... rest stays the same

    // Moving between stations
    if (train.status === "moving") {
      const currentStation = stations[train.stationIndex];
      const nextStationIndex =
        train.direction === "eastbound"
          ? train.stationIndex + 1
          : train.stationIndex - 1;

      if (nextStationIndex < 0 || nextStationIndex >= stations.length) {
        train.status = "stopped";
        return;
      }

      const nextStation = stations[nextStationIndex];
      const segmentDistance = Math.abs(
        nextStation.distanceFromStart - currentStation.distanceFromStart
      );

      const elapsedSegmentMinutes =
        this.currentTime - train.nextStationArrival;
      const travelTimeSegment =
        segmentDistance / this.config.avgSpeed || 1e-6;

      const progress = Math.min(
        1,
        Math.max(0, elapsedSegmentMinutes / travelTimeSegment)
      );

      const dirSign = train.direction === "eastbound" ? 1 : -1;
      train.position =
        currentStation.distanceFromStart + dirSign * segmentDistance * progress;

      if (progress >= 1) {
        // Arrived at next station
        train.stationIndex = nextStationIndex;
        train.position = nextStation.distanceFromStart;
        train.status = "stopped";
        train.lastStopTime = this.currentTime;
        // Passenger exchange will occur on next update when dwellElapsed === 0
      }
    }

    // Energy consumption (approximate: constant avg speed over active time)
    const elapsedMinutes = Math.max(
      0,
      Math.min(this.currentTime, train.endTime) - train.departureTime
    );
    const distanceRunKm = elapsedMinutes * this.config.avgSpeed;
    train.energyConsumed = distanceRunKm * this.config.energyConsumptionRate;
  }

  private handlePassengerExchange(train: Train) {
    const currentStation = this.config.stations[train.stationIndex];
    if (!currentStation) return;

    const stationId = currentStation.id;

    // Check if this is the DESTINATION terminal (where journey ends)
    const isDestinationTerminal =
      (train.direction === "eastbound" && train.stationIndex === this.config.stations.length - 1) ||
      (train.direction === "westbound" && train.stationIndex === 0);

    // 1) Passengers exit
    let exitFraction = currentStation.exitFraction ?? 0.15;

    // At destination terminal, ALL passengers must disembark
    if (isDestinationTerminal) {
      exitFraction = 1.0;
    }

    const alighting = Math.round(train.passengers * exitFraction);
    const remainingOnboard = Math.max(0, train.passengers - alighting);

    // 2) Passengers board (directional queues)
    const isEastbound = train.direction === "eastbound";
    const waitingMap = isEastbound
      ? this.stationWaitingPassengersEast
      : this.stationWaitingPassengersWest;

    const rawWaiting = waitingMap.get(stationId) || 0;
    const waiting = Math.max(0, Math.round(rawWaiting));
    const availableCapacity = this.config.trainCapacity - remainingOnboard;

    let boarding = 0;

    // Board passengers UNLESS we're at the destination terminal
    if (!isDestinationTerminal && availableCapacity > 0) {
      boarding = Math.min(waiting, availableCapacity);
    }

    train.passengers = remainingOnboard + boarding;
    waitingMap.set(stationId, Math.max(0, waiting - boarding));

    // 3) Metrics
    if (boarding > 0) {
      this.passengersServed += boarding;
    }
  }

  private calculateMetrics(): Metrics {
    const trains = Array.from(this.trains.values());

    const activeTrains = trains.filter(
      (t) => this.currentTime >= t.departureTime && this.currentTime <= t.endTime
    );

    const loads = activeTrains.map((t) => t.passengers);
    const avgLoad =
      loads.length > 0 ? loads.reduce((a, b) => a + b, 0) / loads.length : 0;

    let variance = 0;
    if (loads.length > 0 && avgLoad > 0) {
      const mean = avgLoad;
      const sqDiffSum = loads.reduce(
        (sum, load) => sum + Math.pow(load - mean, 2),
        0
      );
      const stdDev = Math.sqrt(sqDiffSum / loads.length);
      const coeffOfVariation = stdDev / mean;
      variance = Math.min(coeffOfVariation * coeffOfVariation, 1);
    }

    const totalEnergy = activeTrains.reduce(
      (sum, t) => sum + t.energyConsumed,
      0
    );

    // CHANGED: Calculate total running hours for ALL trains that have started
    const totalRunningHours = trains.reduce((sum, t) => {
      // Skip trains that haven't started yet
      if (this.currentTime < t.departureTime) return sum;

      // For trains that have started, count their elapsed time
      const elapsedMinutes = Math.max(
        0,
        Math.min(this.currentTime, t.endTime) - t.departureTime
      );
      return sum + elapsedMinutes / 60;
    }, 0);

    return {
      avgWaitingTime:
        this.passengersServed > 0
          ? this.totalWaitingPassengerMinutes / this.passengersServed
          : 0,
      totalRunningTime: totalRunningHours,
      kwhPrice: this.config.kwhPrice,
      totalEnergyConsumption: totalEnergy,
      totalEnergyCost: totalEnergy * this.config.kwhPrice,
      avgTrainLoad: avgLoad,
      trainLoadVariance: variance,
      passengersServed: this.passengersServed,
      totalPassengerMinutes: this.totalWaitingPassengerMinutes
    };
  }
}



// =======================
// CAPACITY BAR COMPONENT
// =======================

const CapacityBar: React.FC<{
  trains: Train[];
  capacity: number;
  label: string;
  isPlaying: boolean;
}> = ({ trains, capacity, label, isPlaying }) => {
  return (
    <div className="space-y-1">
      <div className="text-xs text-white/60 font-mono mb-2">{label}</div>
      <div
        className="overflow-y-auto space-y-1 pr-2"
        style={{ height: "160px", scrollBehavior: isPlaying ? "auto" : "smooth" }}
      >
        {trains.map((train) => {
          const loadFactor = train.passengers / capacity;
          let color = "#44ff44";

          // CHANGED: More strict thresholds to show mostly problems
          if (loadFactor > 0.70) color = "#ff4444";      // Overcrowded (was 0.85)
          else if (loadFactor < 0.45) color = "#4488ff"; // Undercrowded (was 0.30)

          return (
            <div key={train.id} className="flex items-center gap-2">
              <div className="text-[10px] font-mono text-white/40 w-16 flex items-center gap-1">
                <span>{train.id}</span>
                <span className="text-[8px]">
                  {train.direction === "eastbound" ? "→" : "←"}
                </span>
              </div>
              <div className="flex-1 h-4 bg-white/10 border border-white/20 relative">
                <div
                  className="h-full transition-all duration-300"
                  style={{
                    width: `${(loadFactor * 100).toFixed(1)}%`,
                    backgroundColor: color,
                  }}
                />
                <div className="absolute inset-0 flex items-center justify-center text-[9px] font-mono text-white font-bold">
                  {Math.round(train.passengers)}/{capacity}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// =======================
// MAIN COMPONENT
// =======================

export default function Home() {
  const START_TIME = 330; // 05:30
  const END_TIME = 1380;  // 23:00
  const DAY_LENGTH = END_TIME - START_TIME;


  const [currentTime, setCurrentTime] = useState(START_TIME);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(60);
  const [showComparison, setShowComparison] = useState(false);
  const [currentDay, setCurrentDay] = useState(1);
  const [oasaDataLoaded, setOasaDataLoaded] = useState(false);
  const [loadingOASA, setLoadingOASA] = useState(false);

  const simDate = new Date(SIM_DATE);
  simDate.setDate(simDate.getDate() + (currentDay - 1));

  const readableDate = simDate.toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });

  const officialSim = useMemo(
    () => new MetroSimulator(ATHENS_LINE3_CONFIG, ATHENS_LINE3_CONFIG.officialSchedule),
    []
  );
  const optimizedSim = useMemo(
    () => new MetroSimulator(ATHENS_LINE3_CONFIG, ATHENS_LINE3_CONFIG.optimizedSchedule),
    []
  );


  const handleLoadOASAData = async () => {
    setLoadingOASA(true);
    const demand = await loadOASADataForDay(SIM_DATE);

    if (demand) {
      ATHENS_LINE3_CONFIG.passengerDemand = demand;

      officialSim.reset();
      optimizedSim.reset();

      setOasaDataLoaded(true);
      handleReset();
    }

    setLoadingOASA(false);
  };


  const officialState = officialSim.update(currentTime);
  const optimizedState = optimizedSim.update(currentTime);
  const officialWaiting = officialSim.getStationWaitingPassengers();
  const optimizedWaiting = optimizedSim.getStationWaitingPassengers();

  const officialActiveTrains = officialState.trains.filter(
    (t) => currentTime >= t.departureTime && currentTime <= t.endTime
  );
  const optimizedActiveTrains = optimizedState.trains.filter(
    (t) => currentTime >= t.departureTime && currentTime <= t.endTime
  );

  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setCurrentTime((prev) => {
        const next = prev + 0.5;
        if (next >= START_TIME + DAY_LENGTH) {
          setCurrentDay((d) => d + 1);
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

  const handlePlay = async () => {
    if (!oasaDataLoaded) {
      await handleLoadOASAData();
    }

    setIsPlaying((p) => !p);
  };


  return (
    <main className="h-screen bg-black text-white flex flex-col overflow-y-hidden ">
      <div className="border-b border-white/20 bg-black px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="text-sm font-mono">
            <span className="text-white/60">Athens Metro Line 3:</span>{" "}
            <span className="text-white">AI Schedule Optimization</span>
          </div>
          <div className="text-xs font-mono text-white/40 bg-white/5 px-2 py-1 border border-white/20">
            {readableDate}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-xs font-mono text-white/60 bg-white/5 px-3 py-1 border border-white/20">
            <Clock className="inline w-3 h-3 mr-1" />
            {formatTime(currentTime)}
          </div>
          {!oasaDataLoaded && (
            <button
              onClick={handleLoadOASAData}
              disabled={loadingOASA}
              className="text-xs font-mono px-4 py-1 bg-blue-600 text-white hover:bg-blue-500 transition-colors disabled:opacity-50"
            >
              {loadingOASA ? "LOADING..." : "LOAD OASA DATA"}
            </button>
          )}
          {oasaDataLoaded && (
            <div className="text-xs font-mono text-green-400 bg-green-500/10 px-3 py-1 border border-green-500/30">
              ✓ OASA DATA ACTIVE
            </div>
          )}
          {!showComparison ? (
            <button
              onClick={() => {
                setShowComparison(true);
                handleReset();
              }}
              className="text-xs font-mono px-4 py-1 bg-white text-black hover:bg-white/90 transition-colors flex items-center gap-2"
            >
              <Zap className="w-3 h-3" />
              COMPARE WITH AI
            </button>
          ) : (
            <button
              onClick={() => {
                setShowComparison(false);
                handleReset();
              }}
              className="text-xs font-mono px-4 py-1 border border-white/40 hover:bg-white/10 transition-colors"
            >
              BACK
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 flex flex-col p-6 gap-6 ">
        {!showComparison ? (
          <>
            <div className="grid grid-cols-3 gap-6 min-h-0">
              {/* LEFT: map + controls */}
              <div className="col-span-2 flex flex-col gap-y-6 min-h-0">
                <div className="h-[465px] min-h-0">
                  <MetroMap
                    config={ATHENS_LINE3_CONFIG}
                    trains={officialActiveTrains}
                    label="OFFICIAL SCHEDULE"
                    isOptimized={false}
                    waitingPassengers={officialWaiting}
                  />
                </div>

                <div className="border border-white/20 bg-black p-4">
                  <div className="flex items-center gap-4">
                    <button
                      onClick={handlePlay}
                      className="px-4 py-2 bg-white text-black hover:bg-white/90 transition-colors text-xs font-mono flex items-center gap-2"
                      disabled={loadingOASA}
                    >
                      {loadingOASA ? (
                        "LOADING..."
                      ) : isPlaying ? (
                        <>
                          <Pause className="w-4 h-4" />
                          PAUSE
                        </>
                      ) : (
                        <>
                          <Play className="w-4 h-4" />
                          PLAY
                        </>
                      )}
                    </button>

                    <button
                      onClick={handleReset}
                      className="px-4 py-2 border border-white/40 hover:bg-white/10 transition-colors text-xs font-mono flex items-center gap-2"
                    >
                      <RotateCcw className="w-4 h-4" />
                      RESET
                    </button>
                    <select
                      value={speed}
                      onChange={(e) => setSpeed(Number(e.target.value))}
                      className="bg-black border border-white/40 px-3 py-2 text-xs font-mono text-white"
                    >
                      <option value={5}>5x</option>
                      <option value={10}>10x</option>
                      <option value={30}>30x</option>
                      <option value={60}>60x</option>
                      <option value={120}>120x</option>
                      <option value={240}>240x</option>

                    </select>
                    <div className="flex-1">
                      <input
                        type="range"
                        min={START_TIME}
                        max={END_TIME}
                        step={0.5}
                        value={currentTime}
                        onChange={(e) => {
                          setCurrentTime(Number(e.target.value));
                          setIsPlaying(false);
                        }}
                        className="w-full"
                      />
                      <div className="flex justify-between text-[10px] text-white/40 font-mono mt-1">
                        <span>{formatTime(START_TIME)}</span>
                        <span>{formatTime(currentTime)}</span>
                        <span>{formatTime(END_TIME)}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* RIGHT: metrics + capacity + legend */}
              <div className="flex flex-col space-y-2 min-h-0">
                <div className="border border-white/20 bg-black p-4 space-y-3">
                  <div className="text-xs font-mono text-white/60 border-b border-white/10 pb-2">
                    CURRENT METRICS
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-white/60">Avg Wait Time</span>
                      <span className="font-mono text-lg text-white">
                        {officialState.metrics.avgWaitingTime.toFixed(1)}{" "}
                        <span className="text-xs text-white/40">min</span>
                      </span>
                    </div>

                    <div className="flex justify-between items-center">
                      <span className="text-xs text-white/60">Avg Load</span>
                      <span className="font-mono text-lg text-white">
                        {officialState.metrics.avgTrainLoad.toFixed(0)}{" "}
                        <span className="text-xs text-white/40">pax</span>
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-white/60">Load Variance</span>
                      <span className="font-mono text-lg text-white">
                        {officialState.metrics.trainLoadVariance.toFixed(3)}
                      </span>
                    </div>
                    {/* 🔧 FIXED HERE: justify_between → justify-between */}
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-white/60">Running Time</span>
                      <span className="font-mono text-lg text-white">
                        {officialState.metrics.totalRunningTime.toFixed(1)}{" "}
                        <span className="text-xs text-white/40">hrs</span>
                      </span>
                    </div>
                  </div>
                </div>

                {/* Let this section take remaining height on the right, without overflowing */}
                <div className="border border-white/20 bg-black p-4 flex-1 min-h-0">
                  <CapacityBar
                    trains={officialActiveTrains}
                    capacity={ATHENS_LINE3_CONFIG.trainCapacity}
                    label={`TRAIN CAPACITY (Active: ${officialActiveTrains.length})`}
                    isPlaying={isPlaying}
                  />
                </div>

                <div className="border border-white/20 bg-black p-3 text-[10px] space-y-1">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3" style={{ backgroundColor: "#44ff44" }} />
                    <span className="text-white/60">Optimal (45-70%)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3" style={{ backgroundColor: "#4488ff" }} />
                    <span className="text-white/60">Undercrowded (&lt;45%)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3" style={{ backgroundColor: "#ff4444" }} />
                    <span className="text-white/60">Overcrowded (&gt;70%)</span>
                  </div>
                  <div className="border-t border-white/10 mt-2 pt-2">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{
                          border: "2px solid #ffaa00",
                          backgroundColor: "rgba(255, 165, 0, 0.25)",
                        }}
                      />
                      <span className="text-white/60">Waiting passengers</span>
                    </div>
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
                  <MetroMap
                    config={ATHENS_LINE3_CONFIG}
                    trains={officialActiveTrains}
                    label="OFFICIAL SCHEDULE"
                    isOptimized={false}
                    waitingPassengers={officialWaiting}
                  />
                </div>
                <div className="border border-white/20 bg-black p-4">
                  <CapacityBar
                    trains={officialActiveTrains}
                    capacity={ATHENS_LINE3_CONFIG.trainCapacity}
                    label={`CAPACITY - OFFICIAL (${officialActiveTrains.length} active)`}
                    isPlaying={isPlaying}
                  />
                </div>
                <div className="border border-white/20 bg-black p-3 space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-white/60">Avg Wait</span>
                    <span className="font-mono text-white">
                      {officialState.metrics.avgWaitingTime.toFixed(1)} min
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/60">Energy Cost</span>
                    <span className="font-mono text-white">
                      €{officialState.metrics.totalEnergyCost.toFixed(0)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/60">Variance</span>
                    <span className="font-mono text-white">
                      {officialState.metrics.trainLoadVariance.toFixed(3)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/60">Avg Load</span>
                    <span className="font-mono text-white">
                      {officialState.metrics.avgTrainLoad.toFixed(0)} pax
                    </span>
                  </div>
                </div>
              </div>
              <div className="flex flex-col gap-4">
                <div className="flex-1">
                  <MetroMap
                    config={ATHENS_LINE3_CONFIG}
                    trains={optimizedActiveTrains}
                    label="AI-OPTIMIZED SCHEDULE"
                    isOptimized={true}
                    waitingPassengers={optimizedWaiting}
                  />
                </div>
                <div className="border border-white/20 bg-black p-4">
                  <CapacityBar
                    trains={optimizedActiveTrains}
                    capacity={ATHENS_LINE3_CONFIG.trainCapacity}
                    label={`CAPACITY - AI OPTIMIZED (${optimizedActiveTrains.length} active)`}
                    isPlaying={isPlaying}
                  />
                </div>
                <div className="border border-green-500/30 bg-green-500/10 p-3 space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-white/70">Avg Wait</span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-white">
                        {optimizedState.metrics.avgWaitingTime.toFixed(1)} min
                      </span>
                      <span
                        className={`font-mono text-[10px] ${calculateImprovement(
                          officialState.metrics.avgWaitingTime,
                          optimizedState.metrics.avgWaitingTime
                        ) > 0
                          ? "text-green-400"
                          : "text-red-400"
                          }`}
                      >
                        {calculateImprovement(
                          officialState.metrics.avgWaitingTime,
                          optimizedState.metrics.avgWaitingTime
                        ) > 0
                          ? "↓"
                          : "↑"}
                        {Math.abs(
                          calculateImprovement(
                            officialState.metrics.avgWaitingTime,
                            optimizedState.metrics.avgWaitingTime
                          )
                        ).toFixed(1)}
                        %
                      </span>
                    </div>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/70">Energy Cost</span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-white">
                        €
                        {optimizedState.metrics.totalEnergyCost.toFixed(0)}
                      </span>
                      <span
                        className={`font-mono text-[10px] ${calculateImprovement(
                          officialState.metrics.totalEnergyCost,
                          optimizedState.metrics.totalEnergyCost
                        ) > 0
                          ? "text-green-400"
                          : "text-red-400"
                          }`}
                      >
                        {calculateImprovement(
                          officialState.metrics.totalEnergyCost,
                          optimizedState.metrics.totalEnergyCost
                        ) > 0
                          ? "↓"
                          : "↑"}
                        {Math.abs(
                          calculateImprovement(
                            officialState.metrics.totalEnergyCost,
                            optimizedState.metrics.totalEnergyCost
                          )
                        ).toFixed(1)}
                        %
                      </span>
                    </div>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/70">Variance</span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-white">
                        {optimizedState.metrics.trainLoadVariance.toFixed(3)}
                      </span>
                      <span
                        className={`font-mono text-[10px] ${calculateImprovement(
                          officialState.metrics.trainLoadVariance,
                          optimizedState.metrics.trainLoadVariance
                        ) > 0
                          ? "text-green-400"
                          : "text-red-400"
                          }`}
                      >
                        {calculateImprovement(
                          officialState.metrics.trainLoadVariance,
                          optimizedState.metrics.trainLoadVariance
                        ) > 0
                          ? "↓"
                          : "↑"}
                        {Math.abs(
                          calculateImprovement(
                            officialState.metrics.trainLoadVariance,
                            optimizedState.metrics.trainLoadVariance
                          )
                        ).toFixed(1)}
                        %
                      </span>
                    </div>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/70">Avg Load</span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-white">
                        {optimizedState.metrics.avgTrainLoad.toFixed(0)} pax
                      </span>
                      <span
                        className={`font-mono text-[10px] ${Math.abs(
                          calculateImprovement(
                            optimizedState.metrics.avgTrainLoad,
                            officialState.metrics.avgTrainLoad
                          )
                        ) < 5
                          ? "text-white/40"
                          : "text-green-400"
                          }`}
                      >
                        {officialState.metrics.avgTrainLoad >
                          optimizedState.metrics.avgTrainLoad
                          ? "↓"
                          : "↑"}
                        {Math.abs(
                          calculateImprovement(
                            optimizedState.metrics.avgTrainLoad,
                            officialState.metrics.avgTrainLoad
                          )
                        ).toFixed(1)}
                        %
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div className="border border-white/20 bg-black p-4">
              <div className="flex items-center gap-4">
                <button
                  onClick={() => setIsPlaying((p) => !p)}
                  className="px-4 py-2 bg-white text-black hover:bg-white/90 transition-colors text-xs font-mono flex items-center gap-2"
                >
                  {isPlaying ? (
                    <>
                      <Pause className="w-4 h-4" />
                      PAUSE
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4" />
                      PLAY
                    </>
                  )}
                </button>
                <button
                  onClick={handleReset}
                  className="px-4 py-2 border border-white/40 hover:bg-white/10 transition-colors text-xs font-mono flex items-center gap-2"
                >
                  <RotateCcw className="w-4 h-4" />
                  RESET
                </button>
                <select
                  value={speed}
                  onChange={(e) => setSpeed(Number(e.target.value))}
                  className="bg-black border border-white/40 px-3 py-2 text-xs font-mono text-white"
                >
                  <option value={5}>5x</option>
                  <option value={30}>30x</option>
                  <option value={60}>60x</option>
                  <option value={120}>120x</option>
                  <option value={240}>240x</option>

                </select>
                <div className="flex-1">
                  <input
                    type="range"
                    min={START_TIME}
                    max={END_TIME}
                    step={0.5}
                    value={currentTime}
                    onChange={(e) => {
                      setCurrentTime(Number(e.target.value));
                      setIsPlaying(false);
                    }}
                    className="w-full"
                  />
                  <div className="flex justify-between text-[10px] text-white/40 font-mono mt-1">
                    <span>{formatTime(START_TIME)}</span>
                    <span>{readableDate}</span>
                    <span>{formatTime(END_TIME)}</span>
                  </div>
                </div>
                <div className="border border-green-500/50 bg-green-500/10 px-4 py-2">
                  <div className="text-[10px] text-green-400/80 mb-1">
                    KEY IMPROVEMENT
                  </div>
                  <div className="text-sm font-mono text-green-400">
                    ↓{" "}
                    {Math.abs(
                      calculateImprovement(
                        officialState.metrics.avgWaitingTime,
                        optimizedState.metrics.avgWaitingTime
                      )
                    ).toFixed(1)}
                    % Wait Time
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
