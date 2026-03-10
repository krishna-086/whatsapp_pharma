"use client";
import { usePathname } from "next/navigation";

const titles = {
    "/": { title: "Dashboard", subtitle: "Overview & analytics" },
    "/inventory": { title: "Inventory", subtitle: "Manage your medicine stock" },
    "/transactions": { title: "Transactions", subtitle: "Sales & purchase history" },
    "/invoices": { title: "Invoices", subtitle: "Confirmed supplier invoices" },
    "/billing": { title: "New Bill", subtitle: "Create a customer sale" },
};

export default function Header({ onMenuClick }) {
    const pathname = usePathname();
    const { title, subtitle } = titles[pathname] || titles["/"];

    return (
        <header className="header">
            <div style={{ display: "flex", alignItems: "center" }}>
                <button className="menu-toggle" onClick={onMenuClick}>☰</button>
                <div>
                    <div className="header-title">{title}</div>
                    <div className="header-subtitle">{subtitle}</div>
                </div>
            </div>
            <div className="header-right">
                <div className="header-badge">Connected to Cosmos DB</div>
            </div>
        </header>
    );
}
