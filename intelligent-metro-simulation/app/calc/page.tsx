"use client";

import { useState, useMemo } from "react";
import {
    Zap,
    DollarSign,
    ArrowDownRight,
    ArrowUpRight,
    Info,
} from "lucide-react";
import {
    computeScheduleCost,
    ScheduleStats,
    CostParameters,
} from "../libs/costModel";

export default function Line3CostCalculatorPage() {
    // ---- Default schedule stats (per average day) ----
    const [officialKm, setOfficialKm] = useState(18_000); // Placeholder – needs real Line 3 data
    const [officialHours, setOfficialHours] = useState(950); // Placeholder – needs real Line 3 data

    const [optimizedKm, setOptimizedKm] = useState(16_800);
    const [optimizedHours, setOptimizedHours] = useState(910);

    // ---- Default cost parameters (€/km, €/hour, etc.) ----
    // Based on STASY 2024 financial report estimates
    const [energyPerKm, setEnergyPerKm] = useState(0.50);         // €/train-km
    const [maintenancePerKm, setMaintenancePerKm] = useState(0.20); // €/train-km
    const [staffPerHour, setStaffPerHour] = useState(45);         // €/train-hour

    const DAYS_PER_YEAR = 365;

    const officialStats: ScheduleStats = useMemo(
        () => ({
            trainKm: officialKm,
            trainHours: officialHours,
            daysPerYear: DAYS_PER_YEAR,
        }),
        [officialKm, officialHours]
    );

    const optimizedStats: ScheduleStats = useMemo(
        () => ({
            trainKm: optimizedKm,
            trainHours: optimizedHours,
            daysPerYear: DAYS_PER_YEAR,
        }),
        [optimizedKm, optimizedHours]
    );

    const params: CostParameters = useMemo(
        () => ({
            energyPerTrainKm: energyPerKm,
            maintenancePerTrainKm: maintenancePerKm,
            staffPerTrainHour: staffPerHour,
        }),
        [energyPerKm, maintenancePerKm, staffPerHour]
    );

    const costOfficial = useMemo(
        () => computeScheduleCost(officialStats, params),
        [officialStats, params]
    );
    const costOptimized = useMemo(
        () => computeScheduleCost(optimizedStats, params),
        [optimizedStats, params]
    );

    // ---- Fix #2: explicit baselineCost ----
    const baselineCost =
        costOfficial.annualizedTotalCost ?? costOfficial.totalCost ?? 1;

    const saving =
        (costOfficial.annualizedTotalCost ?? costOfficial.totalCost) -
        (costOptimized.annualizedTotalCost ?? costOptimized.totalCost);

    const savingPercent = saving / baselineCost;

    const formatMoney = (v: number) =>
        new Intl.NumberFormat("de-GR", {
            style: "currency",
            currency: "EUR",
            maximumFractionDigits: 0,
        }).format(v);

    const formatMoneyCompact = (v: number) =>
        new Intl.NumberFormat("de-GR", {
            style: "currency",
            currency: "EUR",
            notation: "compact",
            maximumFractionDigits: 1,
        }).format(v);

    const formatPercent = (v: number) => `${(v * 100).toFixed(2)}%`;

    const dailyOfficial = costOfficial.totalCost;
    const dailyOptimized = costOptimized.totalCost;

    return (
        <main className="min-h-screen bg-black text-white flex flex-col">
            {/* Top bar - similar style to sim UI */}
            <div className="border-b border-white/20 bg-black px-6 py-3 flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <div className="text-sm font-mono">
                        <span className="text-white/60">Athens Metro Line 3:</span>{" "}
                        <span className="text-white">Operating Cost Analyzer</span>
                    </div>
                    <div className="text-[10px] font-mono text-white/40 bg-white/5 px-2 py-1 border border-white/20 uppercase tracking-wide flex items-center gap-1">
                        <DollarSign className="w-3 h-3" />
                        <span>Schedule Cost Comparison</span>
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
                        title="Annual Cost – Official"
                        value={formatMoney(
                            costOfficial.annualizedTotalCost ?? costOfficial.totalCost
                        )}
                        subtitle={formatMoneyCompact(dailyOfficial) + " / day"}
                    />
                    <SummaryCard
                        title="Annual Cost – Optimized"
                        value={formatMoney(
                            costOptimized.annualizedTotalCost ?? costOptimized.totalCost
                        )}
                        subtitle={formatMoneyCompact(dailyOptimized) + " / day"}
                    />
                    <SummaryCard
                        title="Annual Saving"
                        value={formatMoney(saving)}
                        subtitle={formatPercent(savingPercent)}
                        positive={saving > 0}
                        highlight
                    />
                </section>

                {/* Main layout: inputs left, breakdown right */}
                <section className="grid gap-6 lg:grid-cols-2">
                    {/* Left: Schedules + Cost Parameters */}
                    <div className="space-y-6">
                        {/* Schedules */}
                        <div className="border border-white/20 bg-black p-4  rounded-2xl    space-y-4">
                            <div className="flex items-center justify-between border-b border-white/10 pb-2">
                                <div className="text-xs font-mono text-white/60">
                                    SCHEDULE INPUT · PER AVERAGE DAY
                                </div>
                                <div className="text-[10px] font-mono text-white/40">
                                    Train-km & Train-hours · Line 3
                                </div>
                            </div>

                            <div className="grid gap-4 md:grid-cols-2">
                                <div className="space-y-3">
                                    <div className="text-[11px] font-mono text-white/70">
                                        OFFICIAL SCHEDULE
                                    </div>
                                    <NumberInput
                                        label="Train-km per day"
                                        value={officialKm}
                                        onChange={setOfficialKm}
                                        step={100}
                                    />
                                    <NumberInput
                                        label="Train-hours per day"
                                        value={officialHours}
                                        onChange={setOfficialHours}
                                        step={10}
                                    />
                                </div>
                                <div className="space-y-3 border border-green-500/30 bg-green-500/5 p-3 rounded-xl">
                                    <div className="text-[11px] font-mono text-green-300">
                                        AI-OPTIMIZED SCHEDULE
                                    </div>
                                    <NumberInput
                                        label="Train-km per day"
                                        value={optimizedKm}
                                        onChange={setOptimizedKm}
                                        step={100}
                                    />
                                    <NumberInput
                                        label="Train-hours per day"
                                        value={optimizedHours}
                                        onChange={setOptimizedHours}
                                        step={10}
                                    />
                                </div>
                            </div>
                        </div>

                        {/* ---------- COMPACT COST PARAMETERS ---------- */}
                        <div className="border border-white/20 bg-black p-4 rounded-2xl space-y-3">
                            <div className="flex items-center justify-between border-b border-white/10 pb-2">
                                <div className="text-xs font-mono text-white/60">
                                    COST PARAMETERS · LINE 3
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

                            {/* 3 inputs on a single line – tiny labels, compact fields */}
                            <div className="grid grid-cols-3 gap-2 text-[10px] font-mono">
                                <NumberInput
                                    label="Energy €/km"
                                    value={energyPerKm}
                                    onChange={setEnergyPerKm}
                                    step={0.05}
                                />
                                <NumberInput
                                    label="Maint. €/km"
                                    value={maintenancePerKm}
                                    onChange={setMaintenancePerKm}
                                    step={0.05}
                                />
                                <NumberInput
                                    label="Staff €/h"
                                    value={staffPerHour}
                                    onChange={setStaffPerHour}
                                    step={1}
                                />
                            </div>

                            <p className="text-[9px] text-white/40 leading-tight">
                                Energy & maint. → allocated from STASY totals by train-km share; staff → operating personnel / train-hour.
                            </p>
                        </div>
                    </div>

                    {/* Right: Breakdown table & deltas */}
                    <div className="space-y-6">
                        <div className="border border-white/20 bg-black p-4 rounded-2xl space-y-3">
                            <div className="flex items-center justify-between border-b border-white/10 pb-2">
                                <div className="text-xs font-mono text-white/60">
                                    DAILY COST BREAKDOWN
                                </div>
                                <div className="text-[10px] font-mono text-white/40">
                                    All values below are per average day
                                </div>
                            </div>

                            <div className="overflow-x-auto">
                                <table className="min-w-full text-xs font-mono">
                                    <thead className="bg-white/5 text-white/60">
                                        <tr>
                                            <th className="px-3 py-2 text-left">Component</th>
                                            <th className="px-3 py-2 text-right">Official</th>
                                            <th className="px-3 py-2 text-right">Optimized</th>
                                            <th className="px-3 py-2 text-right">Δ Saving</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <BreakdownRow
                                            label="Energy"
                                            official={costOfficial.energyCost}
                                            optimized={costOptimized.energyCost}
                                            format={formatMoney}
                                        />
                                        <BreakdownRow
                                            label="Maintenance"
                                            official={costOfficial.maintenanceCost}
                                            optimized={costOptimized.maintenanceCost}
                                            format={formatMoney}
                                        />
                                        <BreakdownRow
                                            label="Staff"
                                            official={costOfficial.staffCost}
                                            optimized={costOptimized.staffCost}
                                            format={formatMoney}
                                        />

                                        <BreakdownRow
                                            label="Other costs"
                                            official={costOfficial.fixedCost}
                                            optimized={costOptimized.fixedCost}
                                            format={formatMoney}
                                        />
                                        <tr className="border-t border-white/10 bg-white/5 font-semibold">
                                            <td className="px-3 py-2">Total</td>
                                            <td className="px-3 py-2 text-right">
                                                {formatMoney(costOfficial.totalCost)}
                                            </td>
                                            <td className="px-3 py-2 text-right">
                                                {formatMoney(costOptimized.totalCost)}
                                            </td>
                                            <td
                                                className={`px-3 py-2 text-right ${costOfficial.totalCost - costOptimized.totalCost > 0
                                                    ? "text-green-400"
                                                    : "text-red-400"
                                                    }`}
                                            >
                                                {formatMoney(
                                                    costOfficial.totalCost - costOptimized.totalCost
                                                )}
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {/* Annual delta card */}
                        <div className="border border-green-500/40 bg-green-500/10 p-4 rounded-2xl flex items-center justify-between gap-4">
                            <div className="space-y-1">
                                <div className="text-[10px] uppercase tracking-wide text-green-300 font-mono flex items-center gap-2">
                                    <Zap className="w-3 h-3" />
                                    Annual Impact (Line 3)
                                </div>
                                <div className="text-lg font-mono text-green-300 flex items-center gap-2">
                                    {saving >= 0 ? (
                                        <ArrowDownRight className="w-4 h-4" />
                                    ) : (
                                        <ArrowUpRight className="w-4 h-4 text-red-400" />
                                    )}
                                    <span>{formatMoney(saving)} / year</span>
                                </div>
                                <div className="text-[11px] text-green-200/80 font-mono">
                                    Implementation will {saving >= 0 ? "reduce" : "increase"} costs
                                    <br />by {formatPercent(savingPercent)} annually!
                                </div>
                            </div>
                            <div className="text-[11px] text-white/50 font-mono max-w-xs">
                                This metric is calculated by making the assumption that the costs
                                are equally distributed between train units.
                            </div>
                        </div>
                    </div>
                </section>
            </div >
        </main >
    );
}

/* ---------- Small UI components, styled like your sim ---------- */

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
                ? "border-green-400/60 shadow-[0_0_30px_rgba(74,222,128,0.25)]"
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
                    className={`mt-2 text-xs font-mono ${positive ? "text-green-400" : "text-white/50"
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
                className="mt-1 w-full rounded-lg border border-white/30 bg-black/80 px-3 py-2 text-xs font-mono text-white focus:outline-none focus:ring-2 focus:ring-green-400 focus:border-green-400"
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
    const diff = official - optimized;
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
                        ? "text-green-400"
                        : "text-red-400"
                    }`}
            >
                {format(diff)}
            </td>
        </tr>
    );
}
