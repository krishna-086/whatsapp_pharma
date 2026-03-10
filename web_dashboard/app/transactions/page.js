"use client";
import { useEffect, useState, Fragment } from "react";
import { generateReceiptPDF } from "@/lib/pdf";

export default function TransactionsPage() {
    const [transactions, setTransactions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState("");
    const [typeFilter, setTypeFilter] = useState("all");
    const [expanded, setExpanded] = useState(null);

    useEffect(() => {
        fetch("/api/transactions")
            .then((r) => r.json())
            .then(setTransactions)
            .catch(console.error)
            .finally(() => setLoading(false));
    }, []);

    const filtered = transactions.filter((t) => {
        if (typeFilter !== "all" && t.type !== typeFilter) return false;
        if (search) {
            const term = search.toLowerCase();
            const itemNames = (t.items || []).map((i) => (i.name || "").toLowerCase()).join(" ");
            return (
                itemNames.includes(term) ||
                (t.sender || "").toLowerCase().includes(term) ||
                (t.id || "").toLowerCase().includes(term)
            );
        }
        return true;
    });

    const formatDate = (iso) => {
        if (!iso) return "—";
        const d = new Date(iso);
        return d.toLocaleDateString("en-IN", {
            day: "2-digit",
            month: "short",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    };

    const formatItems = (items) => {
        if (!items || !items.length) return "—";
        const names = items.map((i) => i.name || "Unknown");
        if (names.length <= 2) return names.join(", ");
        return `${names[0]}, ${names[1]} +${names.length - 2} more`;
    };

    return (
        <>
            <div className="page-header">
                <h1>Transactions ({transactions.length})</h1>
                <div className="toolbar">
                    <div className="search-bar">
                        <span className="icon">🔍</span>
                        <input
                            placeholder="Search transactions..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </div>
                    <select
                        className="form-select"
                        style={{ width: 140 }}
                        value={typeFilter}
                        onChange={(e) => setTypeFilter(e.target.value)}
                    >
                        <option value="all">All Types</option>
                        <option value="sale">Sales</option>
                        <option value="purchase">Purchases</option>
                    </select>
                </div>
            </div>

            <div className="card">
                {loading ? (
                    <div className="loading"><div className="spinner" /></div>
                ) : filtered.length === 0 ? (
                    <div className="empty-state">
                        <span className="icon">💳</span>
                        <p>No transactions found</p>
                    </div>
                ) : (
                    <div className="data-table-container">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th></th>
                                    <th>Date</th>
                                    <th>Type</th>
                                    <th>Items</th>
                                    <th>Total</th>
                                    <th>Source</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.map((txn) => (
                                    <Fragment key={txn.id}>
                                        <tr
                                            onClick={() =>
                                                setExpanded(expanded === txn.id ? null : txn.id)
                                            }
                                            style={{ cursor: "pointer" }}
                                        >
                                            <td style={{ width: 24, color: "var(--text-muted)" }}>
                                                {expanded === txn.id ? "▼" : "▶"}
                                            </td>
                                            <td style={{ whiteSpace: "nowrap" }}>
                                                {formatDate(txn.created_at)}
                                            </td>
                                            <td>
                                                <span
                                                    className={`badge ${txn.type === "sale" ? "badge-success" : "badge-primary"
                                                        }`}
                                                >
                                                    {txn.type || "sale"}
                                                </span>
                                            </td>
                                            <td>{formatItems(txn.items)}</td>
                                            <td style={{ fontWeight: 700 }}>
                                                ₹{(txn.total || 0).toFixed(2)}
                                            </td>
                                            <td style={{ color: "var(--text-muted)", fontSize: 13 }}>
                                                {(txn.sender || "").replace("whatsapp:", "").replace("dashboard", "🖥 Dashboard")}
                                            </td>
                                        </tr>
                                        {expanded === txn.id && (
                                            <tr key={`${txn.id}-detail`}>
                                                <td colSpan={6} style={{ padding: 0 }}>
                                                    <div className="txn-items">
                                                        <table>
                                                            <tbody>
                                                                {(txn.items || []).map((it, idx) => (
                                                                    <tr key={idx}>
                                                                        <td style={{ fontWeight: 500 }}>{it.name}</td>
                                                                        <td>Qty: {it.quantity}</td>
                                                                        <td>MRP: ₹{it.mrp || it.unit_price || 0}</td>
                                                                        <td style={{ fontWeight: 600 }}>
                                                                            ₹{(it.amount || 0).toFixed(2)}
                                                                        </td>
                                                                    </tr>
                                                                ))}
                                                            </tbody>
                                                        </table>
                                                        <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '10px 15px', borderTop: '1px solid #f1f5f9' }}>
                                                            <button
                                                                className="btn btn-outline btn-sm"
                                                                onClick={(e) => {
                                                                    e.stopPropagation();
                                                                    generateReceiptPDF(txn);
                                                                }}
                                                                style={{ display: 'flex', alignItems: 'center', gap: '5px' }}
                                                            >
                                                                📄 Download PDF Receipt
                                                            </button>
                                                        </div>
                                                    </div>
                                                </td>
                                            </tr>
                                        )}
                                    </Fragment>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </>
    );
}
