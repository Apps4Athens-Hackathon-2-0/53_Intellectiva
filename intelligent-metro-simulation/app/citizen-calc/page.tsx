"use client";

import { useState, useMemo } from "react";
import { Users, TrendingUp, ArrowDownRight, ArrowUpRight, Info } from "lucide-react";

// Simplified satisfaction model based on wait time and load factor
interface ScheduleMetrics {
    avgWaitTimeMin: number;
    avgLoadFactor: number;
    daysPerYear?: number;
}

interface SatisfactionParams {
    waitTimeWeight: number;
    loadFactorWeight: number;
}

interface SatisfactionBreakdown {
    waitTimeScore: number;
    loadFactorScore: number;
    overallScore: number;
    satisfiedPassengers?: number;
}

function computeSatisfactionScore(
    metrics: ScheduleMetrics,
    params: SatisfactionParams,
    avgDailyPassengers: number
): SatisfactionBreakdown {
    // Wait time: ideal ≤5 min, poor ≥15 min
    const waitTimeScore = Math.max(0, 100 - (metrics.avgWaitTimeMin / 15) * 100);

    // Load factor: ideal 60-70%, poor >90% or <30%
    const loadFactorScore = metrics.avgLoadFactor <= 70
        ? Math.min(100, (metrics.avgLoadFactor / 70) * 100)
        : Math.max(0, 100 - ((metrics.avgLoadFactor - 70) / 30) * 100);

    // Overall weighted score
    const overallScore = (
        waitTimeScore * (params.waitTimeWeight / 100) +
        loadFactorScore * (params.loadFactorWeight / 100)
    );

    // Estimate satisfied passengers
    const satisfactionRate = overallScore >= 60 ? (overallScore - 20) / 80 : overallScore / 120;
    const satisfiedPassengers = avgDailyPassengers * satisfactionRate;

    return {
        waitTimeScore,
        loadFactorScore,
        overallScore,
        satisfiedPassengers,
    };
}

export default function Line3SatisfactionCalculator() {
    // Daily passengers - Line 3 specific (132k from 2022 extension data)
    const [avgDailyPassengers, setAvgDailyPassengers] = useState(132000);

    // Weights (default 15% wait time, 10% load factor, totaling 25%)
    const [waitTimeWeight, setWaitTimeWeight] = useState(15);
    const [loadFactorWeight, setLoadFactorWeight] = useState(10);

    // Official schedule metrics
    const [offAvgWait, setOffAvgWait] = useState(6.5);
    const [offLoad, setOffLoad] = useState(85);

    // Optimized schedule metrics
    const [optAvgWait, setOptAvgWait] = useState(5.0);
    const [optLoad, setOptLoad] = useState(68);

    const DAYS_PER_YEAR = 365;

    const params: SatisfactionParams = useMemo(
        () => ({
            waitTimeWeight,
            loadFactorWeight,
        }),
        [waitTimeWeight, loadFactorWeight]
    );

    const officialMetrics: ScheduleMetrics = useMemo(
        () => ({
            avgWaitTimeMin: offAvgWait,
            avgLoadFactor: offLoad,
            daysPerYear: DAYS_PER_YEAR,
        }),
        [offAvgWait, offLoad]
    );

    const optimizedMetrics: ScheduleMetrics = useMemo(
        () => ({
            avgWaitTimeMin: optAvgWait,
            avgLoadFactor: optLoad,
            daysPerYear: DAYS_PER_YEAR,
        }),
        [optAvgWait, optLoad]
    );

    const satOfficial = useMemo(
        () => computeSatisfactionScore(officialMetrics, params, avgDailyPassengers),
        [officialMetrics, params, avgDailyPassengers]
    );

    const satOptimized = useMemo(
        () => computeSatisfactionScore(optimizedMetrics, params, avgDailyPassengers),
        [optimizedMetrics, params, avgDailyPassengers]
    );

    const scoreDelta = satOptimized.overallScore - satOfficial.overallScore;
    const passDelta = (satOptimized.satisfiedPassengers ?? 0) - (satOfficial.satisfiedPassengers ?? 0);
    const annualPassDelta = passDelta * DAYS_PER_YEAR;

    const formatMoney = (v: number) =>
        new Intl.NumberFormat("de-GR", {
            maximumFractionDigits: 1,
        }).format(v);

    const formatMoneyCompact = (v: number) =>
        new Intl.NumberFormat("de-GR", {
            notation: "compact",
            maximumFractionDigits: 1,
        }).format(v);

    const formatPercent = (v: number) => `${v.toFixed(2)}%`;

    return (
        <main className="min-h-screen bg-black text-white flex flex-col">
            {/* Top bar */}
            <div className="border-b border-white/20 bg-black px-6 py-3 flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <div className="text-sm font-mono">
                        <span className="text-white/60">Athens Metro Line 3:</span>{" "}
                        <span className="text-white">Citizen Satisfaction Analyzer</span>
                    </div>
                    <div className="text-[10px] font-mono text-white/40 bg-white/5 px-2 py-1 border border-white/20 uppercase tracking-wide flex items-center gap-1">
                        <Users className="w-3 h-3" />
                        <span>Passenger Experience Impact</span>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <div className="text-xs font-mono text-white/60 bg-white/5 px-3 py-1 border border-white/20 flex items-center gap-2">
                        <Info className="w-3 h-3" />
                        <span>Inputs are per average day · Annual = × {DAYS_PER_YEAR}</span>
                    </div>
                </div>
            </div>

            {/* Body */}
            <div className="flex-1 flex flex-col p-6 gap-6 overflow-y-auto">
                {/* Summary row */}
                <section className="grid gap-4 md:grid-cols-3">
                    <SummaryCard
                        title="Satisfaction Score – Official"
                        value={formatMoney(satOfficial.overallScore)}
                        subtitle={formatMoneyCompact(satOfficial.satisfiedPassengers ?? 0) + " satisfied/day"}
                    />
                    <SummaryCard
                        title="Satisfaction Score – Optimized"
                        value={formatMoney(satOptimized.overallScore)}
                        subtitle={formatMoneyCompact(satOptimized.satisfiedPassengers ?? 0) + " satisfied/day"}
                    />
                    <SummaryCard
                        title="Improvement"
                        value={`+${formatMoney(scoreDelta)} pts`}
                        subtitle={`+${formatPercent((scoreDelta / satOfficial.overallScore) * 100)}`}
                        positive={scoreDelta > 0}
                        highlight
                    />
                </section>

                {/* Main layout: inputs left, breakdown right */}
                <section className="grid gap-6 lg:grid-cols-2">
                    {/* Left: Inputs */}
                    <div className="space-y-6">
                        {/* Daily passengers */}
                        <div className="border border-white/20 bg-black p-4 rounded-2xl space-y-4">
                            <div className="flex items-center justify-between border-b border-white/10 pb-2">
                                <div className="text-xs font-mono text-white/60">
                                    PASSENGER VOLUME · LINE 3
                                </div>
                                <div className="text-[10px] font-mono text-white/40">
                                    Daily ridership
                                </div>
                            </div>

                            <NumberInput
                                label="Average daily passengers"
                                value={avgDailyPassengers}
                                onChange={setAvgDailyPassengers}
                                step={1000}
                            />

                            <p className="text-[9px] text-white/40 leading-tight">
                                Line 3 Piraeus extension serves ~132k passengers/day. Total Athens Metro: ~800k/day (2024). Ridership increased 8% in 2024 vs 2023.
                            </p>
                        </div>

                        {/* Satisfaction Weights */}
                        <div className="border border-white/20 bg-black p-4 rounded-2xl space-y-3">
                            <div className="flex items-center justify-between border-b border-white/10 pb-2">
                                <div className="text-xs font-mono text-white/60">
                                    SATISFACTION WEIGHTS
                                </div>
                                <a
                                    href="https://www.stasy.gr/wp-content/uploads/2025/09/Oik_katastaseis2024_FINAL.pdf#page=23"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-[10px] font-mono text-blue-400 hover:text-blue-300 underline underline-offset-2 flex items-center gap-1"
                                >
                                    STASY Records 2024
                                    <svg className="w-3 h-3 opacity-70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                            d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                    </svg>
                                </a>
                            </div>

                            <div className="grid grid-cols-2 gap-2 text-[10px] font-mono">
                                <NumberInput
                                    label="Wait Time Weight (%)"
                                    value={waitTimeWeight}
                                    onChange={setWaitTimeWeight}
                                    step={1}
                                />
                                <NumberInput
                                    label="Load Factor Weight (%)"
                                    value={loadFactorWeight}
                                    onChange={setLoadFactorWeight}
                                    step={1}
                                />
                            </div>

                            <p className="text-[9px] text-white/40 leading-tight">
                                Wait time: ideal ≤5min (100pts), poor ≥15min (0pts). Load factor: ideal 60-70% (100pts), poor &gt;90% or &lt;30% (0pts).
                            </p>
                        </div>

                        {/* Schedule Inputs */}
                        <div className="border border-white/20 bg-black p-4 rounded-2xl space-y-4">
                            <div className="flex items-center justify-between border-b border-white/10 pb-2">
                                <div className="text-xs font-mono text-white/60">
                                    SCHEDULE INPUT · PER AVERAGE DAY
                                </div>
                                <div className="text-[10px] font-mono text-white/40">
                                    Wait Time & Load · Line 3
                                </div>
                            </div>

                            <div className="grid gap-4 md:grid-cols-2">
                                <div className="space-y-3">
                                    <div className="text-[11px] font-mono text-white/70">
                                        OFFICIAL SCHEDULE
                                    </div>
                                    <NumberInput
                                        label="Avg wait time (min)"
                                        value={offAvgWait}
                                        onChange={setOffAvgWait}
                                        step={0.5}
                                    />
                                    <NumberInput
                                        label="Load factor (%)"
                                        value={offLoad}
                                        onChange={setOffLoad}
                                        step={1}
                                    />
                                </div>
                                <div className="space-y-3 border border-blue-500/30 bg-blue-500/5 p-3 rounded-xl">
                                    <div className="text-[11px] font-mono text-blue-300">
                                        AI-OPTIMIZED SCHEDULE
                                    </div>
                                    <NumberInput
                                        label="Avg wait time (min)"
                                        value={optAvgWait}
                                        onChange={setOptAvgWait}
                                        step={0.5}
                                    />
                                    <NumberInput
                                        label="Load factor (%)"
                                        value={optLoad}
                                        onChange={setOptLoad}
                                        step={1}
                                    />
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Right: Breakdown table & impact */}
                    <div className="space-y-6">
                        <div className="border border-white/20 bg-black p-4 rounded-2xl space-y-3">
                            <div className="flex items-center justify-between border-b border-white/10 pb-2">
                                <div className="text-xs font-mono text-white/60">
                                    SATISFACTION BREAKDOWN
                                </div>
                                <div className="text-[10px] font-mono text-white/40">
                                    All scores on 0-100 scale
                                </div>
                            </div>

                            <div className="overflow-x-auto">
                                <table className="min-w-full text-xs font-mono">
                                    <thead className="bg-white/5 text-white/60">
                                        <tr>
                                            <th className="px-3 py-2 text-left">Component</th>
                                            <th className="px-3 py-2 text-right">Official</th>
                                            <th className="px-3 py-2 text-right">Optimized</th>
                                            <th className="px-3 py-2 text-right">Δ Change</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <BreakdownRow
                                            label="Wait Time"
                                            official={satOfficial.waitTimeScore}
                                            optimized={satOptimized.waitTimeScore}
                                            format={formatMoney}
                                        />
                                        <BreakdownRow
                                            label="Load Factor"
                                            official={satOfficial.loadFactorScore}
                                            optimized={satOptimized.loadFactorScore}
                                            format={formatMoney}
                                        />
                                        <tr className="border-t border-white/10 bg-white/5 font-semibold">
                                            <td className="px-3 py-2">Overall Score</td>
                                            <td className="px-3 py-2 text-right">
                                                {formatMoney(satOfficial.overallScore)}
                                            </td>
                                            <td className="px-3 py-2 text-right">
                                                {formatMoney(satOptimized.overallScore)}
                                            </td>
                                            <td
                                                className={`px-3 py-2 text-right ${scoreDelta > 0
                                                    ? "text-blue-400"
                                                    : scoreDelta < 0
                                                        ? "text-red-400"
                                                        : "text-white/60"
                                                    }`}
                                            >
                                                {scoreDelta > 0 ? "+" : ""}{formatMoney(scoreDelta)}
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {/* Annual impact card */}
                        <div className="border border-blue-500/40 bg-blue-500/10 p-4 rounded-2xl flex items-center justify-between gap-4">
                            <div className="space-y-1">
                                <div className="text-[10px] uppercase tracking-wide text-blue-300 font-mono flex items-center gap-2">
                                    <TrendingUp className="w-3 h-3" />
                                    Annual Impact (Line 3)
                                </div>
                                <div className="text-lg font-mono text-blue-300 flex items-center gap-2">
                                    {scoreDelta >= 0 ? (
                                        <ArrowUpRight className="w-4 h-4" />
                                    ) : (
                                        <ArrowDownRight className="w-4 h-4 text-red-400" />
                                    )}
                                    <span>+{formatMoneyCompact(annualPassDelta)} satisfied/year</span>
                                </div>
                                <div className="text-[11px] text-blue-200/80 font-mono">
                                    Implementation will {scoreDelta >= 0 ? "improve" : "degrade"} passenger experience
                                    <br />by {formatPercent((scoreDelta / satOfficial.overallScore) * 100)} annually!
                                </div>
                            </div>
                            <div className="text-[11px] text-white/50 font-mono max-w-xs">
                                This metric is calculated based on wait time and train load factor optimization.
                            </div>
                        </div>
                    </div>
                </section>
            </div>
        </main>
    );
}

/* UI Components */

interface SummaryCardProps {
    title: string;
    value: string;
    subtitle?: string;
    positive?: boolean;
    highlight?: boolean;
}

function SummaryCard({
    title,
    value,
    subtitle,
    positive,
    highlight,
}: SummaryCardProps) {
    return (
        <div
            className={`rounded-2xl border bg-black p-4 flex flex-col justify-between ${highlight
                ? "border-blue-400/60 shadow-[0_0_30px_rgba(96,165,250,0.25)]"
                : "border-white/20"
                }`}
        >
            <div>
                <p className="text-[11px] uppercase tracking-wide text-white/50 font-mono">
                    {title}
                </p>
                <p className="mt-2 text-2xl font-mono">{value}</p>
            </div>
            {subtitle && (
                <p
                    className={`mt-2 text-xs font-mono ${positive ? "text-blue-400" : "text-white/50"
                        }`}
                >
                    {subtitle}
                </p>
            )}
        </div>
    );
}

interface NumberInputProps {
    label: string;
    value: number;
    onChange: (v: number) => void;
    step?: number;
}

function NumberInput({ label, value, onChange, step = 1 }: NumberInputProps) {
    return (
        <label className="text-xs text-white/80 font-mono space-y-1">
            <span>{label}</span>
            <input
                type="number"
                step={step}
                value={value}
                onChange={(e) => onChange(Number(e.target.value) || 0)}
                className="mt-1 w-full rounded-lg border border-white/30 bg-black/80 px-3 py-2 text-xs font-mono text-white focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-blue-400"
            />
        </label>
    );
}

interface BreakdownRowProps {
    label: string;
    official: number;
    optimized: number;
    format: (v: number) => string;
}

function BreakdownRow({
    label,
    official,
    optimized,
    format,
}: BreakdownRowProps) {
    const diff = optimized - official;
    const positive = diff > 0;
    return (
        <tr className="border-t border-white/10">
            <td className="px-3 py-2">{label}</td>
            <td className="px-3 py-2 text-right">{format(official)}</td>
            <td className="px-3 py-2 text-right">{format(optimized)}</td>
            <td
                className={`px-3 py-2 text-right ${diff === 0
                    ? "text-white/60"
                    : positive
                        ? "text-blue-400"
                        : "text-red-400"
                    }`}
            >
                {diff > 0 ? "+" : ""}{format(diff)}
            </td>
        </tr>
    );
}