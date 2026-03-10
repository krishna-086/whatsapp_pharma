"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
    { href: "/", label: "Overview", icon: "📊" },
    { href: "/inventory", label: "Inventory", icon: "📦" },
    { href: "/transactions", label: "Transactions", icon: "💳" },
    { href: "/invoices", label: "Invoices", icon: "🧾" },
    { href: "/billing", label: "New Bill", icon: "🛒" },
];

export default function Sidebar({ isOpen, onClose }) {
    const pathname = usePathname();

    return (
        <>
            <aside className={`sidebar${isOpen ? " open" : ""}`}>
                <button className="sidebar-close" onClick={onClose}>✕</button>
                <div className="sidebar-brand">
                    <div className="sidebar-brand-icon">💊</div>
                    <div>
                        <h1>PharmAgent</h1>
                        <span>Dashboard</span>
                    </div>
                </div>

                <nav className="sidebar-nav">
                    {links.map(({ href, label, icon }) => (
                        <Link
                            key={href}
                            href={href}
                            className={`sidebar-link${pathname === href ? " active" : ""}`}
                            onClick={onClose}
                        >
                            <span className="icon">{icon}</span>
                            {label}
                        </Link>
                    ))}
                </nav>

                <div className="sidebar-footer">
                    WhatsApp PharmaBot © 2026
                </div>
            </aside>
            <div className="sidebar-overlay" onClick={onClose}></div>
        </>
    );
}
