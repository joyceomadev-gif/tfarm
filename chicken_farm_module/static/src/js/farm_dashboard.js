/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";
import { Component, useState, useRef, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";

export class TaghiniFarmMonitorDashboard extends Component {
    static template = "chicken_farm_module.FarmMonitorDashboard";

    setup() {
        this.action = useService("action");

        // 6 Core Charts Refs
        this.chartRefMortality = useRef("chartCanvasMortality");
        this.chartRefYield = useRef("chartCanvasYield");
        this.chartRefVolume = useRef("chartCanvasVolume");
        this.chartRefFeed = useRef("chartCanvasFeed");
        this.chartRefWeight = useRef("chartCanvasWeight");
        this.chartRefDefect = useRef("chartCanvasDefect");

        this.state = useState({
            loading: true,
            activeTab: "flocks", // 'flocks' | 'abattoir' | 'breeder'
            selectedFarmId: 0,
            datePreset: "all",  // 'all' | '30d' | 'month' | 'quarter' | 'custom'
            dateFrom: "",
            dateTo: "",
            statusFilter: "all",
            stageFilter: "all",
            alertFilter: "all",
            farms: [],
            kpis: {
                mortality_rate: 0.0,
                abattoir_yield_pct: 0.0,
                production_volume_kg: 0.0,
                birds_processed: 0,
                feed_consumed_bags: 0,
                weight_variance_g: 0.0,
                total_defects: 0,
                active_flocks: 0,
                total_live_birds: 0,
                critical_alerts: 0,
                vet_escalations: 0,
                feed_deficit_pens: 0,
                out_of_spec_bags: 0,
            },
            mortality_chart: { labels: [], rates: [], counts: [], placed: [] },
            yield_chart: { labels: [], yields: [], output_kg: [], input_kg: [] },
            volume_chart: { labels: [], volumes_kg: [], birds: [], categories: [], category_weights: [] },
            feed_chart: { labels: [], actual_bags: [], expected_bags: [], actual_kg: [] },
            weight_chart: { labels: [], variance_g: [], actual_g: [], expected_g: [] },
            defect_chart: { labels: [], counts: [], farm_labels: [], farm_counts: [] },
            stage_chart: { labels: [], counts: [] },
            farm_breakdown: [],
            pen_operations: [],
            abattoir_batches: [],
            breeder_batches: [],
            breeder_kpis: {
                active_females: 0,
                active_males: 0,
                total_active_birds: 0,
                males_per_100_females: 0.0,
                today_hatching_eggs: 0,
                today_total_eggs: 0,
                today_hen_day_pct: 0.0,
                latest_hatchability_pct: 0.0,
                cum_chicks_per_hen: 0.0,
                active_danger_count: 0,
            },
            breeder_flocks: [],
            hatchery_dispatches: [],
            breeder_egg_summary: {},
            alerts: [],
        });

        this.charts = [];

        onWillStart(async () => {
            // Ensure Chart.js is loaded
            try {
                await loadBundle("web.chartjs_lib");
            } catch (e) {
                console.warn("Chart.js bundle load fallback:", e);
            }
            await this.fetchDashboardData();
        });

        onMounted(() => {
            this.renderChartsDebounced();
        });

        onWillUnmount(() => {
            this.destroyCharts();
        });
    }

    destroyCharts() {
        if (this.charts && this.charts.length) {
            this.charts.forEach((c) => {
                if (c && typeof c.destroy === "function") {
                    c.destroy();
                }
            });
            this.charts = [];
        }
    }

    renderChartsDebounced() {
        this.destroyCharts();
        setTimeout(() => {
            this.renderCharts();
        }, 80);
    }

    async fetchDashboardData() {
        this.state.loading = true;
        try {
            const res = await rpc("/taghini/farm/dashboard/data", {
                farm_id: Number(this.state.selectedFarmId) || 0,
                date_preset: this.state.datePreset,
                date_from: this.state.dateFrom,
                date_to: this.state.dateTo,
                status: this.state.statusFilter,
                stage: this.state.stageFilter,
                alert_level: this.state.alertFilter,
                tab: this.state.activeTab,
            });

            if (res) {
                this.state.farms = res.farms || [];
                this.state.dateFrom = res.date_from || this.state.dateFrom;
                this.state.dateTo = res.date_to || this.state.dateTo;
                this.state.kpis = res.kpis || this.state.kpis;
                this.state.mortality_chart = res.mortality_chart || { labels: [], rates: [], counts: [], placed: [] };
                this.state.yield_chart = res.yield_chart || { labels: [], yields: [], output_kg: [], input_kg: [] };
                this.state.volume_chart = res.volume_chart || { labels: [], volumes_kg: [], birds: [], categories: [], category_weights: [] };
                this.state.feed_chart = res.feed_chart || { labels: [], actual_bags: [], expected_bags: [], actual_kg: [] };
                this.state.weight_chart = res.weight_chart || { labels: [], variance_g: [], actual_g: [], expected_g: [] };
                this.state.defect_chart = res.defect_chart || { labels: [], counts: [], farm_labels: [], farm_counts: [] };
                this.state.stage_chart = res.stage_chart || { labels: [], counts: [] };
                this.state.farm_breakdown = res.farm_breakdown || [];
                this.state.pen_operations = res.pen_operations || [];
                this.state.abattoir_batches = res.abattoir_batches || [];
                this.state.breeder_batches = res.breeder_batches || [];
                this.state.breeder_kpis = res.breeder_kpis || this.state.breeder_kpis;
                this.state.breeder_flocks = res.breeder_flocks || [];
                this.state.hatchery_dispatches = res.hatchery_dispatches || [];
                this.state.breeder_egg_summary = res.breeder_egg_summary || {};
                this.state.alerts = res.alerts || [];
            }
        } catch (error) {
            console.error("Failed to load Farm Monitor dashboard data:", error);
        } finally {
            this.state.loading = false;
        }
    }

    async setTab(tabName) {
        if (this.state.activeTab === tabName) return;
        this.state.activeTab = tabName;
        await this.fetchDashboardData();
        this.renderChartsDebounced();
    }

    async setDatePreset(preset) {
        this.state.datePreset = preset;
        await this.fetchDashboardData();
        this.renderChartsDebounced();
    }

    async onDateFromChange(ev) {
        this.state.dateFrom = ev.target.value;
        this.state.datePreset = "custom";
        await this.fetchDashboardData();
        this.renderChartsDebounced();
    }

    async onDateToChange(ev) {
        this.state.dateTo = ev.target.value;
        this.state.datePreset = "custom";
        await this.fetchDashboardData();
        this.renderChartsDebounced();
    }

    async onFarmSelected(ev) {
        this.state.selectedFarmId = Number(ev.target.value) || 0;
        await this.fetchDashboardData();
        this.renderChartsDebounced();
    }

    async onStatusSelected(ev) {
        this.state.statusFilter = ev.target.value;
        await this.fetchDashboardData();
        this.renderChartsDebounced();
    }

    async onStageSelected(ev) {
        this.state.stageFilter = ev.target.value;
        await this.fetchDashboardData();
        this.renderChartsDebounced();
    }

    async onAlertSelected(ev) {
        this.state.alertFilter = ev.target.value;
        await this.fetchDashboardData();
        this.renderChartsDebounced();
    }

    async resetFilters() {
        this.state.selectedFarmId = 0;
        this.state.datePreset = "all";
        this.state.statusFilter = "all";
        this.state.stageFilter = "all";
        this.state.alertFilter = "all";
        await this.fetchDashboardData();
        this.renderChartsDebounced();
    }

    async selectFarmRow(farmId) {
        this.state.selectedFarmId = farmId;
        await this.fetchDashboardData();
        this.renderChartsDebounced();
    }

    async refresh() {
        await this.fetchDashboardData();
        this.renderChartsDebounced();
    }

    formatNumber(val) {
        if (val === null || val === undefined || isNaN(val)) return "0";
        return Number(val).toLocaleString();
    }

    formatDecimal(val, dec = 1) {
        if (val === null || val === undefined || isNaN(val)) return "0.0";
        return Number(val).toFixed(dec);
    }

    openFlock(flockId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "taghini.flock",
            res_id: flockId,
            views: [[false, "form"]],
        });
    }

    openAbattoir(batchId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "taghini.abattoir.batch",
            res_id: batchId,
            views: [[false, "form"]],
        });
    }

    openBreeder(batchId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "taghini.breeder.batch",
            res_id: batchId,
            views: [[false, "form"]],
        });
    }

    openBreederFlock(flockId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "taghini.breeder.flock",
            res_id: flockId,
            views: [[false, "form"]],
        });
    }

    openHatchery(dispatchId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "taghini.breeder.hatchery.dispatch",
            res_id: dispatchId,
            views: [[false, "form"]],
        });
    }

    renderCharts() {
        const ChartClass = window.Chart;
        if (!ChartClass) return;

        // -----------------------------------------------------------
        // 1. Mortality Rate per Each Farm (%)
        // -----------------------------------------------------------
        if (this.chartRefMortality && this.chartRefMortality.el) {
            const ctx = this.chartRefMortality.el;
            const labels = this.state.mortality_chart.labels || [];
            const rates = this.state.mortality_chart.rates || [];
            const counts = this.state.mortality_chart.counts || [];

            // Color code: < 1.5% optimal (emerald), 1.5 - 3% warning (amber), > 3% critical (rose)
            const bgColors = rates.map((r) => {
                if (r > 3.0) return "#ef4444";
                if (r > 1.5) return "#f59e0b";
                return "#10b981";
            });

            const cMort = new ChartClass(ctx, {
                type: "bar",
                data: {
                    labels: labels.length ? labels : ["No Data"],
                    datasets: [
                        {
                            label: "Mortality Rate (%)",
                            data: rates.length ? rates : [0],
                            backgroundColor: bgColors.length ? bgColors : ["#cbd5e1"],
                            borderRadius: 4,
                            maxBarThickness: 45,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => {
                                    const idx = ctx.dataIndex;
                                    const cnt = counts[idx] || 0;
                                    return ` Mortality: ${ctx.parsed.y}% (${cnt} birds dead)`;
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: { font: { size: 11, weight: "600" }, color: "#475569" },
                        },
                        y: {
                            beginAtZero: true,
                            grid: { color: "#f1f5f9" },
                            ticks: {
                                callback: (v) => `${v}%`,
                                font: { size: 10 },
                                color: "#94a3b8",
                            },
                        },
                    },
                },
            });
            this.charts.push(cMort);
        }

        // -----------------------------------------------------------
        // 2. Abattoir Yield % per Each Farm
        // -----------------------------------------------------------
        if (this.chartRefYield && this.chartRefYield.el) {
            const ctx = this.chartRefYield.el;
            const labels = this.state.yield_chart.labels || [];
            const yields = this.state.yield_chart.yields || [];
            const outputKg = this.state.yield_chart.output_kg || [];

            // Color code: >= 74% Cyan/Teal, 70-73% Blue, < 70% Orange
            const bgColors = yields.map((y) => {
                if (y >= 74.0) return "#06b6d4";
                if (y >= 70.0) return "#3b82f6";
                return "#f97316";
            });

            const cYield = new ChartClass(ctx, {
                type: "bar",
                data: {
                    labels: labels.length ? labels : ["No Data"],
                    datasets: [
                        {
                            label: "Abattoir Yield %",
                            data: yields.length ? yields : [0],
                            backgroundColor: bgColors.length ? bgColors : ["#cbd5e1"],
                            borderRadius: 4,
                            maxBarThickness: 45,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => {
                                    const idx = ctx.dataIndex;
                                    const kg = outputKg[idx] || 0;
                                    return ` Yield: ${ctx.parsed.y}% (${kg.toLocaleString()} kg carcass)`;
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: { font: { size: 11, weight: "600" }, color: "#475569" },
                        },
                        y: {
                            beginAtZero: true,
                            grid: { color: "#f1f5f9" },
                            ticks: {
                                callback: (v) => `${v}%`,
                                font: { size: 10 },
                                color: "#94a3b8",
                            },
                        },
                    },
                },
            });
            this.charts.push(cYield);
        }

        // -----------------------------------------------------------
        // 3. Abattoir Production Volume (Kg & Processed Birds)
        // -----------------------------------------------------------
        if (this.chartRefVolume && this.chartRefVolume.el) {
            const ctx = this.chartRefVolume.el;
            const labels = this.state.volume_chart.labels || [];
            const volumes = this.state.volume_chart.volumes_kg || [];
            const birds = this.state.volume_chart.birds || [];

            const cVol = new ChartClass(ctx, {
                type: "bar",
                data: {
                    labels: labels.length ? labels : ["No Data"],
                    datasets: [
                        {
                            label: "Output Weight (Kg)",
                            data: volumes.length ? volumes : [0],
                            backgroundColor: "#8b5cf6",
                            hoverBackgroundColor: "#7c3aed",
                            borderRadius: 4,
                            maxBarThickness: 45,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => {
                                    const idx = ctx.dataIndex;
                                    const bCount = birds[idx] || 0;
                                    return ` Production: ${ctx.parsed.y.toLocaleString()} Kg (${bCount.toLocaleString()} birds)`;
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: { font: { size: 11, weight: "600" }, color: "#475569" },
                        },
                        y: {
                            beginAtZero: true,
                            grid: { color: "#f1f5f9" },
                            ticks: {
                                callback: (v) => `${v} kg`,
                                font: { size: 10 },
                                color: "#94a3b8",
                            },
                        },
                    },
                },
            });
            this.charts.push(cVol);
        }

        // -----------------------------------------------------------
        // 4. Farm Feed Consumption (Actual vs Expected Bags)
        // -----------------------------------------------------------
        if (this.chartRefFeed && this.chartRefFeed.el) {
            const ctx = this.chartRefFeed.el;
            const labels = this.state.feed_chart.labels || [];
            const actualBags = this.state.feed_chart.actual_bags || [];
            const expBags = this.state.feed_chart.expected_bags || [];

            const cFeed = new ChartClass(ctx, {
                type: "bar",
                data: {
                    labels: labels.length ? labels : ["No Data"],
                    datasets: [
                        {
                            label: "Actual Feed (Bags)",
                            data: actualBags.length ? actualBags : [0],
                            backgroundColor: "#14b8a6",
                            borderRadius: 3,
                            maxBarThickness: 28,
                        },
                        {
                            label: "Expected Feed (Bags)",
                            data: expBags.length ? expBags : [0],
                            backgroundColor: "#cbd5e1",
                            borderRadius: 3,
                            maxBarThickness: 28,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: "top",
                            align: "end",
                            labels: {
                                boxWidth: 10,
                                boxHeight: 10,
                                font: { size: 10, weight: "500" },
                                color: "#475569",
                                padding: 6,
                            },
                        },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y.toLocaleString()} Bags`,
                            },
                        },
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: { font: { size: 11, weight: "600" }, color: "#475569" },
                        },
                        y: {
                            beginAtZero: true,
                            grid: { color: "#f1f5f9" },
                            ticks: {
                                font: { size: 10 },
                                color: "#94a3b8",
                                precision: 0,
                            },
                        },
                    },
                },
            });
            this.charts.push(cFeed);
        }

        // -----------------------------------------------------------
        // 5. Weight Variance (g vs Standard Curve)
        // -----------------------------------------------------------
        if (this.chartRefWeight && this.chartRefWeight.el) {
            const ctx = this.chartRefWeight.el;
            const labels = this.state.weight_chart.labels || [];
            const variances = this.state.weight_chart.variance_g || [];
            const actualWeights = this.state.weight_chart.actual_g || [];
            const expWeights = this.state.weight_chart.expected_g || [];

            // Color: green for >= 0, red for < 0
            const bgColors = variances.map((v) => (v >= 0 ? "#10b981" : "#f43f5e"));

            const cWeight = new ChartClass(ctx, {
                type: "bar",
                data: {
                    labels: labels.length ? labels : ["No Data"],
                    datasets: [
                        {
                            label: "Weight Variance (g)",
                            data: variances.length ? variances : [0],
                            backgroundColor: bgColors.length ? bgColors : ["#cbd5e1"],
                            borderRadius: 4,
                            maxBarThickness: 45,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => {
                                    const idx = ctx.dataIndex;
                                    const act = actualWeights[idx] || 0;
                                    const exp = expWeights[idx] || 0;
                                    const prefix = ctx.parsed.y >= 0 ? "+" : "";
                                    return ` Var: ${prefix}${ctx.parsed.y}g (Actual: ${act}g | Target: ${exp}g)`;
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: { font: { size: 11, weight: "600" }, color: "#475569" },
                        },
                        y: {
                            grid: {
                                color: (ctx) => (ctx.tick.value === 0 ? "#334155" : "#f1f5f9"),
                                lineWidth: (ctx) => (ctx.tick.value === 0 ? 1.5 : 1),
                            },
                            ticks: {
                                callback: (v) => `${v > 0 ? "+" : ""}${v}g`,
                                font: { size: 10 },
                                color: "#94a3b8",
                            },
                        },
                    },
                },
            });
            this.charts.push(cWeight);
        }

        // -----------------------------------------------------------
        // 6. Abattoir Defect Breakdown
        // -----------------------------------------------------------
        if (this.chartRefDefect && this.chartRefDefect.el) {
            const ctx = this.chartRefDefect.el;
            const labels = this.state.defect_chart.labels || [
                "Dead on Arrival (DOA)",
                "Reception Defects",
                "Processing Rejects",
                "Bagging Out-of-Spec",
            ];
            const counts = this.state.defect_chart.counts || [0, 0, 0, 0];
            const hasData = counts.some((v) => v > 0);

            const defectColors = [
                "#ef4444", // DOA: Red
                "#f97316", // Reception defects: Orange
                "#eab308", // Processing defects: Amber/Yellow
                "#6366f1", // Bagging out-of-spec: Indigo
            ];

            const cDefect = new ChartClass(ctx, {
                type: "doughnut",
                data: {
                    labels: labels,
                    datasets: [
                        {
                            data: hasData ? counts : [1],
                            backgroundColor: hasData ? defectColors : ["#e2e8f0"],
                            borderColor: "#ffffff",
                            borderWidth: 2,
                            hoverOffset: 4,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: "66%",
                    plugins: {
                        legend: {
                            position: "bottom",
                            labels: {
                                boxWidth: 10,
                                boxHeight: 10,
                                font: { size: 10, weight: "500" },
                                color: "#475569",
                                padding: 8,
                            },
                        },
                        tooltip: {
                            callbacks: {
                                label: (item) => {
                                    if (!hasData) return " No defects recorded";
                                    return ` ${item.label}: ${item.parsed} defects`;
                                },
                            },
                        },
                    },
                },
            });
            this.charts.push(cDefect);
        }
    }
}

registry.category("actions").add("taghini_farm_monitor", TaghiniFarmMonitorDashboard);
