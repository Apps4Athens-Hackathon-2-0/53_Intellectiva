// ─────────────────────────────────────────────────────────────────────────────
//  scheduleBuilder.ts
// ─────────────────────────────────────────────────────────────────────────────
import { timeToMinutes } from "../hooks/helperFunctions";
import { HeadwaySegment, Schedule, Trip } from "../types/main";

// ────────────────────── Station IDs ──────────────────────
const LINE3_STATION_IDS_EASTBOUND: string[] = [
    "s01", "s02", "s03", "s04", "s05", "s06", "s07", "s08", "s09",
    "s10", "s11", "s12", "s13", "s14", "s15", "s16", "s17", "s18",
    "s19", "s20", "s21", "s22", "s23", "s24", "s25", "s26", "s27",
];
const LINE3_STATION_IDS_WESTBOUND: string[] = [...LINE3_STATION_IDS_EASTBOUND].reverse();

// ────────────────────── Headway Definitions ──────────────────────
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

const OPTIMIZED_HEADWAYS: HeadwaySegment[] = [
    { from: timeToMinutes("00:00"), to: timeToMinutes("01:00"), headway: 10 },
    { from: timeToMinutes("05:00"), to: timeToMinutes("06:00"), headway: 8.6 },
    { from: timeToMinutes("06:00"), to: timeToMinutes("07:00"), headway: 7.5 },
    { from: timeToMinutes("07:00"), to: timeToMinutes("08:00"), headway: 15 },
    { from: timeToMinutes("08:00"), to: timeToMinutes("09:00"), headway: 10 },
    { from: timeToMinutes("09:00"), to: timeToMinutes("10:00"), headway: 6.7 },
    { from: timeToMinutes("10:00"), to: timeToMinutes("11:00"), headway: 6 },
    { from: timeToMinutes("11:00"), to: timeToMinutes("12:00"), headway: 6.7 },
    { from: timeToMinutes("12:00"), to: timeToMinutes("13:00"), headway: 6.7 },
    { from: timeToMinutes("13:00"), to: timeToMinutes("14:00"), headway: 6.7 },
    { from: timeToMinutes("14:00"), to: timeToMinutes("15:00"), headway: 6 },
    { from: timeToMinutes("15:00"), to: timeToMinutes("16:00"), headway: 4.6 },
    { from: timeToMinutes("16:00"), to: timeToMinutes("17:00"), headway: 4 },
    { from: timeToMinutes("17:00"), to: timeToMinutes("18:00"), headway: 4.3 },
    { from: timeToMinutes("18:00"), to: timeToMinutes("19:00"), headway: 4.3 },
    { from: timeToMinutes("19:00"), to: timeToMinutes("20:00"), headway: 6.7 },
    { from: timeToMinutes("20:00"), to: timeToMinutes("21:00"), headway: 10 },
    { from: timeToMinutes("21:00"), to: timeToMinutes("22:00"), headway: 15 },
    { from: timeToMinutes("22:00"), to: timeToMinutes("23:00"), headway: 15 },
    { from: timeToMinutes("23:00"), to: timeToMinutes("24:00"), headway: 15 },
];

// ────────────────────── Core Trip Builder ──────────────────────
function buildTripsForTimes(
    times: number[],
    idPrefix: string,
    startIndex: number,
    eastStations: string[],
    westStations: string[]
): { trips: Trip[]; nextIndex: number } {
    const trips: Trip[] = [];
    let idx = startIndex;
    for (const t of times) {
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
    return { trips, nextIndex: idx };
}

// ────────────────────── Segment → Schedule ──────────────────────
function buildScheduleFromSegments(
    segments: HeadwaySegment[],
    idPrefix: string
): Schedule {
    let allTrips: Trip[] = [];
    let idx = 1;

    for (const seg of segments) {
        const duration = seg.to - seg.from;
        const steps = Math.floor(duration / seg.headway + 1e-6); // avoid float drift
        const times: number[] = [];
        for (let i = 0; i < steps; i++) {
            times.push(seg.from + i * seg.headway);
        }

        const { trips, nextIndex } = buildTripsForTimes(
            times,
            idPrefix,
            idx,
            LINE3_STATION_IDS_EASTBOUND,
            LINE3_STATION_IDS_WESTBOUND
        );
        allTrips = allTrips.concat(trips);
        idx = nextIndex;
    }
    return { trips: allTrips };
}

// ────────────────────── Public API ──────────────────────
export function generateOfficialSchedule(): Schedule {
    return buildScheduleFromSegments(MON_THU_CORE_HEADWAYS, "T");
}

export function generateOptimizedSchedule(): Schedule {
    return buildScheduleFromSegments(OPTIMIZED_HEADWAYS, "O");
}

// ────────────────────── Bonus: Manual Time List ──────────────────────
type TimeInput = string | number;
function timesListToMinutes(list: TimeInput[]): number[] {
    return list.map((v) => (typeof v === "number" ? v : timeToMinutes(v)));
}

export function buildScheduleFromTimesList(
    times: TimeInput[],
    idPrefix: string,
    startIndex = 1
): Schedule {
    const minutes = timesListToMinutes(times);
    const { trips } = buildTripsForTimes(
        minutes,
        idPrefix,
        startIndex,
        LINE3_STATION_IDS_EASTBOUND,
        LINE3_STATION_IDS_WESTBOUND
    );
    return { trips };
}