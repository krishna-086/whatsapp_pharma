"use client";
import { useEffect, useState, useRef } from "react";
import { generateReceiptPDF } from "@/lib/pdf";

export default function BillingPage() {
    const [inventory, setInventory] = useState([]);
    const [billItems, setBillItems] = useState([]);
    const [customerName, setCustomerName] = useState("");
    const [paymentMethod, setPaymentMethod] = useState("cash");
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [toast, setToast] = useState(null);
    const [result, setResult] = useState(null);

    useEffect(() => {
        fetch("/api/inventory")
            .then((r) => r.json())
            .then(setInventory)
            .catch(console.error)
            .finally(() => setLoading(false));
    }, []);

    const showToast = (msg, type = "success") => {
        setToast({ msg, type });
        setTimeout(() => setToast(null), 3500);
    };

    const addBillItem = () => {
        setBillItems([...billItems, { id: "", name: "", quantity: 1, mrp: 0 }]);
    };

    const updateBillItem = (index, field, value) => {
        const updated = [...billItems];
        updated[index] = { ...updated[index], [field]: value };

        // If selecting an item from inventory, auto-fill price
        if (field === "id" && value) {
            const inv = inventory.find((i) => i.id === value);
            if (inv) {
                updated[index].name = inv.name;
                updated[index].mrp = inv.mrp || 0;
                updated[index].maxQty = inv.quantity || 0;
            }
        }
        setBillItems(updated);
    };

    const removeBillItem = (index) => {
        setBillItems(billItems.filter((_, i) => i !== index));
    };

    const grandTotal = billItems.reduce(
        (s, it) => s + (Number(it.quantity) || 0) * (Number(it.mrp) || 0),
        0
    );

    const handleSubmit = async () => {
        if (!billItems.length) return showToast("Add at least one item.", "error");

        const invalidItems = billItems.filter((it) => !it.id);
        if (invalidItems.length) return showToast("Select a medicine for each item.", "error");

        setSubmitting(true);
        try {
            const res = await fetch("/api/billing", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    items: billItems.map((it) => ({
                        id: it.id,
                        name: it.name,
                        quantity: Number(it.quantity) || 1,
                    })),
                    customerName,
                    paymentMethod,
                }),
            });

            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "Billing failed");

            setResult(data);
            showToast("Sale recorded successfully!");
            setBillItems([]);
            setCustomerName("");

            // Refresh inventory
            const freshInv = await fetch("/api/inventory").then((r) => r.json());
            setInventory(freshInv);
        } catch (e) {
            showToast(e.message, "error");
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) {
        return <div className="loading"><div className="spinner" /></div>;
    }

    return (
        <>
            <div className="page-header">
                <h1>New Bill</h1>
                {result && (
                    <button className="btn btn-outline" onClick={() => setResult(null)}>
                        + New Bill
                    </button>
                )}
            </div>

            {result ? (
                <ReceiptView result={result} />
            ) : (
                <div className="billing-layout">
                    {/* Left — Item selection */}
                    <div>
                        <div className="card">
                            <div className="card-header">
                                <span className="card-title">Bill Items</span>
                                <button className="btn btn-primary btn-sm" onClick={addBillItem}>
                                    + Add Item
                                </button>
                            </div>
                            <div className="card-body">
                                {billItems.length === 0 ? (
                                    <div className="empty-state" style={{ padding: 30 }}>
                                        <span className="icon">🛒</span>
                                        <p>Click "Add Item" to start creating a bill</p>
                                    </div>
                                ) : (
                                    billItems.map((item, idx) => (
                                        <BillItemRow
                                            key={idx}
                                            item={item}
                                            inventory={inventory}
                                            onChange={(field, val) => updateBillItem(idx, field, val)}
                                            onRemove={() => removeBillItem(idx)}
                                        />
                                    ))
                                )}
                            </div>
                        </div>

                        <div className="card" style={{ marginTop: 20 }}>
                            <div className="card-body">
                                <div className="form-row">
                                    <div className="form-group">
                                        <label className="form-label">Customer Name (optional)</label>
                                        <input
                                            className="form-input"
                                            value={customerName}
                                            onChange={(e) => setCustomerName(e.target.value)}
                                            placeholder="Walk-in customer"
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label className="form-label">Payment Method</label>
                                        <select
                                            className="form-select"
                                            value={paymentMethod}
                                            onChange={(e) => setPaymentMethod(e.target.value)}
                                        >
                                            <option value="cash">Cash</option>
                                            <option value="upi">UPI</option>
                                            <option value="card">Card</option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Right — Summary */}
                    <div className="billing-summary">
                        <div className="card">
                            <div className="card-header">
                                <span className="card-title">Bill Summary</span>
                            </div>
                            <div className="card-body">
                                {billItems.length === 0 ? (
                                    <p style={{ color: "var(--text-muted)", fontSize: 14 }}>
                                        No items added yet.
                                    </p>
                                ) : (
                                    <>
                                        {billItems.map((it, idx) => (
                                            <div className="billing-summary-item" key={idx}>
                                                <span className="name">{it.name || "Select item..."}</span>
                                                <span className="qty">x{it.quantity}</span>
                                                <span className="amount">
                                                    ₹{((Number(it.quantity) || 0) * (Number(it.mrp) || 0)).toFixed(2)}
                                                </span>
                                            </div>
                                        ))}
                                        <div className="billing-total">
                                            <span>Grand Total</span>
                                            <span>₹{grandTotal.toFixed(2)}</span>
                                        </div>
                                    </>
                                )}
                                <button
                                    className="btn btn-primary"
                                    style={{ width: "100%", marginTop: 16, justifyContent: "center" }}
                                    disabled={submitting || billItems.length === 0}
                                    onClick={handleSubmit}
                                >
                                    {submitting ? "Processing..." : "💳 Complete Sale"}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {toast && <div className={`toast toast-${toast.type}`}>{toast.msg}</div>}
        </>
    );
}

function BillItemRow({ item, inventory, onChange, onRemove }) {
    const [query, setQuery] = useState(item.name || "");
    const [showList, setShowList] = useState(false);
    const ref = useRef(null);

    const suggestions = inventory.filter((inv) =>
        (inv.name || "").toLowerCase().includes(query.toLowerCase()) && inv.quantity > 0
    ).slice(0, 8);

    useEffect(() => {
        const handler = (e) => {
            if (ref.current && !ref.current.contains(e.target)) setShowList(false);
        };
        document.addEventListener("mousedown", handler);
        return () => document.removeEventListener("mousedown", handler);
    }, []);

    const selectItem = (inv) => {
        setQuery(inv.name);
        onChange("id", inv.id);
        setShowList(false);
    };

    return (
        <div className="billing-item-row">
            <div className="autocomplete-container" ref={ref}>
                <input
                    className="form-input"
                    placeholder="Search medicine..."
                    value={query}
                    onChange={(e) => {
                        setQuery(e.target.value);
                        setShowList(true);
                        if (!e.target.value) onChange("id", "");
                    }}
                    onFocus={() => setShowList(true)}
                />
                {showList && suggestions.length > 0 && (
                    <div className="autocomplete-list">
                        {suggestions.map((inv) => (
                            <div
                                key={inv.id}
                                className="autocomplete-item"
                                onClick={() => selectItem(inv)}
                            >
                                <span>{inv.name}</span>
                                <span className="sub">
                                    ₹{inv.mrp || 0} · {inv.quantity} in stock
                                </span>
                            </div>
                        ))}
                    </div>
                )}
            </div>
            <input
                className="form-input"
                type="number"
                min="1"
                max={item.maxQty || 9999}
                value={item.quantity}
                onChange={(e) => onChange("quantity", e.target.value)}
                placeholder="Qty"
            />
            <div style={{ fontSize: 14, fontWeight: 600, paddingTop: 4 }}>
                ₹{((Number(item.quantity) || 0) * (Number(item.mrp) || 0)).toFixed(2)}
            </div>
            <button
                className="btn btn-icon btn-outline"
                style={{ color: "var(--danger)" }}
                onClick={onRemove}
                title="Remove"
            >
                ×
            </button>
        </div>
    );
}

function ReceiptView({ result }) {
    const txn = result.transaction;
    return (
        <div className="card" style={{ maxWidth: 540 }}>
            <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span className="card-title">✅ Sale Complete</span>
                    <span className="badge badge-success">Recorded</span>
                </div>
                <button
                    className="btn btn-primary btn-sm"
                    onClick={() => generateReceiptPDF(txn)}
                    style={{ display: 'flex', alignItems: 'center', gap: '5px' }}
                >
                    📥 Download Receipt
                </button>
            </div>
            <div className="card-body">
                <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 16 }}>
                    Transaction ID: {txn?.id || "—"}<br />
                    {txn?.created_at ? new Date(txn.created_at).toLocaleString("en-IN") : ""}
                </div>

                <div className="data-table-container">
                    <table className="data-table" style={{ fontSize: 13 }}>
                        <thead>
                            <tr>
                                <th>Item</th>
                                <th>Qty</th>
                                <th>MRP</th>
                                <th>Amount</th>
                            </tr>
                        </thead>
                        <tbody>
                            {(txn?.items || []).map((it, idx) => (
                                <tr key={idx}>
                                    <td style={{ fontWeight: 500 }}>{it.name}</td>
                                    <td>{it.quantity}</td>
                                    <td>₹{it.mrp}</td>
                                    <td style={{ fontWeight: 600 }}>₹{(it.amount || 0).toFixed(2)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                <div className="billing-total">
                    <span>Total</span>
                    <span>₹{(txn?.total || 0).toFixed(2)}</span>
                </div>

                {result.errors && (
                    <div style={{ marginTop: 12, fontSize: 13, color: "var(--warning)" }}>
                        ⚠ {result.errors.join(", ")}
                    </div>
                )}
            </div>
        </div>
    );
}
