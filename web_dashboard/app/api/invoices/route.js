import { NextResponse } from "next/server";
import { getInvoices, deepFlatten } from "@/lib/cosmos";

export async function GET() {
    try {
        const rawInvoices = await getInvoices(200);
        const invoices = rawInvoices.map(item => {
            const flattened = deepFlatten(item);
            const inv = flattened.invoice || {};
            return {
                ...flattened,
                ...inv,
                // Ensure common fields are at top level with expected names
                vendor_name: inv.vendor_name || (inv.vendor && inv.vendor.name) || "Unknown Vendor",
                invoice_number: inv.invoice_number || inv.invoice_id || flattened.id,
                total: inv.invoice_total || inv.total || inv.net_amount || inv.total_amount || 0,
                invoice_date: inv.invoice_date || inv.date || flattened.confirmed_at
            };
        });
        return NextResponse.json(invoices);
    } catch (e) {
        return NextResponse.json({ error: e.message }, { status: 500 });
    }
}
