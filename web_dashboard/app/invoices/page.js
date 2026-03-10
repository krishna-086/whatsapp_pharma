"use client";
import { useEffect, useState } from "react";

export default function InventoryPage() {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState("");
    const [modal, setModal] = useState(null); // null | { mode: 'add' | 'edit', item }
    const [toast, setToast] = useState(null);
    const [deleteConfirm, setDeleteConfirm] = useState(null);

    const loadItems = () => {
        setLoading(true);
        fetch("/api/inventory")
            .then((r) => r.json())
            .then(setItems)
            .catch(console.error)
            .finally(() => setLoading(false));
    };

    useEffect(() => { loadItems(); }, []);

    const showToast = (msg, type = "success") => {
        setToast({ msg, type });
        setTimeout(() => setToast(null), 3000);
    };

    const handleSave = async (doc) => {
        try {
            const res = await fetch("/api/inventory", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(doc),
            });
            if (!res.ok) throw new Error("Save failed");
            setModal(null);
            showToast(modal.mode === "add" ? "Item added!" : "Item updated!");
            loadItems();
        } catch (e) {
            showToast(e.message, "error");
        }
    };

    const handleDelete = async (id) => {
        try {
            const res = await fetch(`/api/inventory?id=${id}`, { method: "DELETE" });
            if (!res.ok) throw new Error("Delete failed");
            setDeleteConfirm(null);
            showToast("Item deleted!");
            loadItems();
        } catch (e) {
            showToast(e.message, "error");
        }
    };

    const filtered = items.filter((i) =>
        (i.name || "").toLowerCase().includes(search.toLowerCase())
    );

    const getStockBadge = (qty) => {
        if (qty <= 0) return <span className="badge badge-danger">Out of stock</span>;
        if (qty < 10) return <span className="badge badge-warning">Low stock</span>;
        return <span className="badge badge-success">In stock</span>;
    };

    return (
        <>
            <div className="page-header">
                <h1>Inventory ({items.length})</h1>
                <div className="toolbar">
                    <div className="search-bar">
                        <span className="icon">🔍</span>
                        <input
                            placeholder="Search medicines..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </div>
                    <button
                        className="btn btn-primary"
                        onClick={() =>
                            setModal({
                                mode: "add",
                                item: { id: "", name: "", quantity: 0, mrp: 0, batch_no: "", expiry_date: "", category: "" },
                            })
                        }
                    >
                        + Add Item
                    </button>
                </div>
            </div>

            <div className="card">
                {loading ? (
                    <div className="loading"><div className="spinner" /></div>
                ) : filtered.length === 0 ? (
                    <div className="empty-state">
                        <span className="icon">📦</span>
                        <p>No items found</p>
                    </div>
                ) : (
                    <div className="data-table-container">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Qty</th>
                                    <th>MRP (₹)</th>
                                    <th>Batch</th>
                                    <th>Expiry</th>
                                    <th>Status</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.map((item) => (
                                    <tr key={item.id}>
                                        <td style={{ fontWeight: 600 }}>{item.name}</td>
                                        <td>{item.quantity ?? 0}</td>
                                        <td>₹{(item.mrp || 0).toFixed(2)}</td>
                                        <td style={{ color: "var(--text-secondary)" }}>
                                            {item.batch_no || "—"}
                                        </td>
                                        <td style={{ color: "var(--text-secondary)" }}>
                                            {item.expiry_date || "—"}
                                        </td>
                                        <td>{getStockBadge(item.quantity || 0)}</td>
                                        <td>
                                            <div style={{ display: "flex", gap: 8 }}>
                                                <button
                                                    className="btn btn-outline btn-sm"
                                                    onClick={() =>
                                                        setModal({ mode: "edit", item: { ...item } })
                                                    }
                                                >
                                                    ✏️ Edit
                                                </button>
                                                <button
                                                    className="btn btn-outline btn-sm"
                                                    style={{ color: "var(--danger)" }}
                                                    onClick={() => setDeleteConfirm(item)}
                                                >
                                                    🗑
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* ─── Add / Edit Modal ─── */}
            {modal && (
                <ItemModal
                    mode={modal.mode}
                    item={modal.item}
                    onClose={() => setModal(null)}
                    onSave={handleSave}
                />
            )}

            {/* ─── Delete Confirmation ─── */}
            {deleteConfirm && (
                <div className="modal-backdrop" onClick={() => setDeleteConfirm(null)}>
                    <div className="modal" onClick={(e) => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2>Delete Item</h2>
                            <button className="modal-close" onClick={() => setDeleteConfirm(null)}>×</button>
                        </div>
                        <div className="modal-body">
                            <p>Are you sure you want to delete <strong>{deleteConfirm.name}</strong>?</p>
                            <p style={{ color: "var(--text-muted)", marginTop: 8, fontSize: 13 }}>
                                This action cannot be undone.
                            </p>
                        </div>
                        <div className="modal-footer">
                            <button className="btn btn-outline" onClick={() => setDeleteConfirm(null)}>Cancel</button>
                            <button className="btn btn-danger" onClick={() => handleDelete(deleteConfirm.id)}>Delete</button>
                        </div>
                    </div>
                </div>
            )}

            {/* ─── Toast ─── */}
            {toast && (
                <div className={`toast toast-${toast.type}`}>{toast.msg}</div>
            )}
        </>
    );
}

function ItemModal({ mode, item, onClose, onSave }) {
    const [form, setForm] = useState({ ...item });

    const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));

    const handleSubmit = (e) => {
        e.preventDefault();
        const doc = {
            ...form,
            quantity: Number(form.quantity) || 0,
            mrp: Number(form.mrp) || 0,
        };
        if (mode === "add" && !doc.id) {
            doc.id = doc.name.toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "").slice(0, 64);
        }
        onSave(doc);
    };

    return (
        <div className="modal-backdrop" onClick={onClose}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
                <form onSubmit={handleSubmit}>
                    <div className="modal-header">
                        <h2>{mode === "add" ? "Add New Item" : "Edit Item"}</h2>
                        <button type="button" className="modal-close" onClick={onClose}>×</button>
                    </div>
                    <div className="modal-body">
                        <div className="form-group">
                            <label className="form-label">Medicine Name *</label>
                            <input
                                className="form-input"
                                required
                                value={form.name || ""}
                                onChange={(e) => set("name", e.target.value)}
                                placeholder="e.g. Paracetamol 500mg"
                            />
                        </div>
                        <div className="form-row">
                            <div className="form-group">
                                <label className="form-label">Quantity *</label>
                                <input
                                    className="form-input"
                                    type="number"
                                    min="0"
                                    required
                                    value={form.quantity ?? ""}
                                    onChange={(e) => set("quantity", e.target.value)}
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">MRP (₹)</label>
                                <input
                                    className="form-input"
                                    type="number"
                                    step="0.01"
                                    min="0"
                                    value={form.mrp ?? ""}
                                    onChange={(e) => set("mrp", e.target.value)}
                                />
                            </div>
                        </div>
                        <div className="form-row">
                            <div className="form-group">
                                <label className="form-label">Batch No</label>
                                <input
                                    className="form-input"
                                    value={form.batch_no || ""}
                                    onChange={(e) => set("batch_no", e.target.value)}
                                    placeholder="e.g. B-2026-01"
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Expiry Date</label>
                                <input
                                    className="form-input"
                                    value={form.expiry_date || ""}
                                    onChange={(e) => set("expiry_date", e.target.value)}
                                    placeholder="e.g. 03-2027"
                                />
                            </div>
                        </div>
                        <div className="form-group">
                            <label className="form-label">Category</label>
                            <input
                                className="form-input"
                                value={form.category || ""}
                                onChange={(e) => set("category", e.target.value)}
                                placeholder="e.g. Allopathy, Homeopathy"
                            />
                        </div>
                    </div>
                    <div className="modal-footer">
                        <button type="button" className="btn btn-outline" onClick={onClose}>Cancel</button>
                        <button type="submit" className="btn btn-primary">
                            {mode === "add" ? "Add Item" : "Save Changes"}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
root@656de9f93ae3:/home/site/wwwroot/app# cat invoices/page.js
"use client";
import { useEffect, useState } from "react";

export default function InvoicesPage() {
    const [invoices, setInvoices] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState("");
    const [selected, setSelected] = useState(null);

    useEffect(() => {
        fetch("/api/invoices")
            .then((r) => r.json())
            .then(setInvoices)
            .catch(console.error)
            .finally(() => setLoading(false));
    }, []);

    const filtered = invoices.filter((inv) => {
        if (!search) return true;
        const term = search.toLowerCase();
        return (
            (inv.vendor_name || "").toLowerCase().includes(term) ||
            (inv.invoice_number || "").toLowerCase().includes(term) ||
            (inv.id || "").toLowerCase().includes(term)
        );
    });

    const formatDate = (iso) => {
        if (!iso) return "—";
        try {
            const d = new Date(iso);
            return d.toLocaleDateString("en-IN", {
                day: "2-digit",
                month: "short",
                year: "numeric",
            });
        } catch {
            return iso;
        }
    };

    const getItems = (inv) => {
        return inv.items || [];
    };

    const getTotal = (inv) => {
        return Number(inv.total) || 0;
    };

    const getVendor = (inv) => {
        return inv.vendor_name || "Unknown Vendor";
    };

    const getInvoiceNo = (inv) => {
        return inv.invoice_number || inv.id?.slice(0, 12) || "—";
    };

    return (
        <>
            <div className="page-header">
                <h1>Invoices ({invoices.length})</h1>
                <div className="toolbar">
                    <div className="search-bar">
                        <span className="icon">🔍</span>
                        <input
                            placeholder="Search invoices..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </div>
                </div>
            </div>

            {loading ? (
                <div className="loading"><div className="spinner" /></div>
            ) : filtered.length === 0 ? (
                <div className="card">
                    <div className="empty-state">
                        <span className="icon">🧾</span>
                        <p>No invoices found</p>
                    </div>
                </div>
            ) : (
                <div className="invoice-grid">
                    {filtered.map((inv) => (
                        <div
                            key={inv.id}
                            className="invoice-card"
                            onClick={() => setSelected(inv)}
                        >
                            <div className="invoice-card-header">
                                <div>
                                    <div className="invoice-vendor">{getVendor(inv)}</div>
                                    <div className="invoice-meta">
                                        <span>Invoice #{getInvoiceNo(inv)}</span>
                                        <span>{formatDate(inv.created_at || inv.invoice_date)}</span>
                                    </div>
                                </div>
                                <div className="invoice-total">
                                    ₹{getTotal(inv).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                                </div>
                            </div>
                            <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
                                {getItems(inv).length} line items
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* ─── Invoice Detail Modal ─── */}
            {selected && (
                <div className="modal-backdrop" onClick={() => setSelected(null)}>
                    <div
                        className="modal"
                        style={{ maxWidth: 640 }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="modal-header">
                            <h2>Invoice Details</h2>
                            <button className="modal-close" onClick={() => setSelected(null)}>×</button>
                        </div>
                        <div className="modal-body">
                            <div style={{ marginBottom: 16 }}>
                                <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 4 }}>Vendor</div>
                                <div style={{ fontWeight: 700, fontSize: 16 }}>{getVendor(selected)}</div>
                            </div>
                            <div className="form-row" style={{ marginBottom: 20 }}>
                                <div>
                                    <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 4 }}>Invoice #</div>
                                    <div style={{ fontWeight: 600 }}>{getInvoiceNo(selected)}</div>
                                </div>
                                <div>
                                    <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 4 }}>Date</div>
                                    <div style={{ fontWeight: 600 }}>{formatDate(selected.created_at || selected.invoice_date)}</div>
                                </div>
                            </div>

                            <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>Line Items</h3>
                            <div className="data-table-container">
                                <table className="data-table" style={{ fontSize: 13 }}>
                                    <thead>
                                        <tr>
                                            <th>Item</th>
                                            <th>Qty</th>
                                            <th>Price</th>
                                            <th>Batch</th>
                                            <th>Expiry</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {getItems(selected).map((it, idx) => {
                                            const name = it.description || it.name || "—";
                                            const qty = it.quantity || "—";
                                            const price = it.unit_price || it.mrp || "—";
                                            const batch = it.batch_no || it.batch_number || it.batch || "—";
                                            const expiry = it.expiry_date || it.expiry || "—";
                                            return (
                                                <tr key={idx}>
                                                    <td>{name}</td>
                                                    <td>{qty}</td>
                                                    <td>₹{price}</td>
                                                    <td>{batch}</td>
                                                    <td>{expiry}</td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>

                            <div style={{ textAlign: "right", marginTop: 16 }}>
                                <span style={{ fontSize: 13, color: "var(--text-muted)" }}>Total: </span>
                                <span style={{ fontSize: 20, fontWeight: 800, color: "var(--primary)" }}>
                                    ₹{getTotal(selected).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
