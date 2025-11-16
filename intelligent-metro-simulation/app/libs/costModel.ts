// costModel.ts

// High-level stats of a schedule for Line 3
export interface ScheduleStats {
    /** Total train-kilometres operated in the period (e.g. per day) */
    trainKm: number;

    /** Total train-hours (rolling stock in service time) in the period */
    trainHours: number;

    /**
     * Number of calendar days this schedule represents.
     * Example: if stats are "per weekday", daysPerYear could be 260.
     * If stats are "per average day", daysPerYear could be 365.
     */
    daysPerYear?: number;
}

// Unit cost parameters for Line 3
export interface CostParameters {
    /** Energy cost per train-km (€/train-km) */
    energyPerTrainKm: number;

    /** Maintenance + repairs + consumables per train-km (€/train-km) */
    maintenancePerTrainKm: number;

    /** Staff cost per train-hour (€/train-hour) – mainly drivers & ops */
    staffPerTrainHour: number;



    /**
     * Fixed cost per year for Line 3 (overhead, depots, etc.).
     * You can set this to 0 if you only care about variable costs.
     */
    fixedCostPerYear?: number;
}

export interface CostBreakdown {
    /** Variable energy cost for the period */
    energyCost: number;
    /** Variable maintenance cost for the period */
    maintenanceCost: number;
    /** Variable staff cost for the period */
    staffCost: number;

    /** Fixed cost allocated to this period */
    fixedCost: number;
    /** Total cost for the period */
    totalCost: number;

    /** Optional annualized total, if daysPerYear was provided */
    annualizedTotalCost?: number;
}

/**
 * Compute the operating cost of a given Line 3 schedule.
 *
 * You feed it:
 *  - stats for the schedule (trainKm & trainHours)
 *  - calibrated cost parameters (€/train-km, €/train-hour, etc.)
 *
 * It returns a detailed breakdown + total cost.
 */
export function computeScheduleCost(
    stats: ScheduleStats,
    params: CostParameters
): CostBreakdown {
    const {
        trainKm,
        trainHours,
        daysPerYear,
    } = stats;

    const {
        energyPerTrainKm,
        maintenancePerTrainKm,
        staffPerTrainHour,
        fixedCostPerYear = 0,
    } = params;

    // Variable costs
    const energyCost = trainKm * energyPerTrainKm;
    const maintenanceCost = trainKm * maintenancePerTrainKm;
    const staffCost = trainHours * staffPerTrainHour;

    // If the stats describe a single "typical" day,
    // allocate fixed annual cost proportionally.
    let fixedCost = 0;
    let annualizedTotalCost: number | undefined = undefined;

    if (daysPerYear && daysPerYear > 0) {
        // cost share of the fixed annual cost that corresponds to this period
        fixedCost = fixedCostPerYear / daysPerYear;

        const totalPerDay =
            energyCost +
            maintenanceCost +
            staffCost +
            fixedCost;

        annualizedTotalCost = totalPerDay * daysPerYear;
    }

    const totalCost =
        energyCost +
        maintenanceCost +
        staffCost +
        fixedCost;

    return {
        energyCost,
        maintenanceCost,
        staffCost,
        fixedCost,
        totalCost,
        annualizedTotalCost,
    };
}
