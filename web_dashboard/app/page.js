"use client";
import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export default function OverviewPage() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/stats")
      .then((r) => r.json())
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
      </div>
    );
  }

  if (!stats) return <p>Failed to load dashboard stats.</p>;

  const cards = [
    {
      label: "Total Items",
      value: stats.totalItems,
      sub: "medicines in stock",
      icon: "📦",
      bg: "var(--primary-bg)",
      color: "var(--primary)",
    },
    {
      label: "Low Stock",
      value: stats.lowStockCount,
      sub: "items below 10 units",
      icon: "⚠️",
      bg: "var(--warning-bg)",
      color: "var(--warning)",
    },
    {
      label: "Today's Sales",
      value: stats.todaySalesCount,
      sub: `₹${stats.todayRevenue.toLocaleString("en-IN")} revenue`,
      icon: "💳",
      bg: "var(--success-bg)",
      color: "var(--success)",
    },
    {
      label: "Stock Value",
      value: `₹${stats.totalStockValue.toLocaleString("en-IN")}`,
      sub: "total inventory value",
      icon: "💰",
      bg: "var(--primary-bg)",
      color: "var(--primary)",
    },
  ];

  return (
    <>
      <div className="stats-grid">
        {cards.map((c) => (
          <div className="stat-card" key={c.label}>
            <div className="stat-card-header">
              <span className="stat-card-label">{c.label}</span>
              <div
                className="stat-card-icon"
                style={{ background: c.bg, color: c.color }}
              >
                {c.icon}
              </div>
            </div>
            <div className="stat-card-value">{c.value}</div>
            <div className="stat-card-sub">{c.sub}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">Revenue — Last 7 Days</span>
          <span className="badge badge-primary">
            Total: ₹{stats.totalRevenue.toLocaleString("en-IN")}
          </span>
        </div>
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={stats.revenueByDay}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="day" tick={{ fontSize: 12, fill: "#64748b" }} />
              <YAxis tick={{ fontSize: 12, fill: "#64748b" }} />
              <Tooltip
                contentStyle={{
                  background: "#fff",
                  border: "1px solid #e2e8f0",
                  borderRadius: 8,
                  fontSize: 13,
                }}
              />
              <Bar
                dataKey="revenue"
                fill="#2563eb"
                radius={[6, 6, 0, 0]}
                name="Revenue ₹"
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </>
  );
}
