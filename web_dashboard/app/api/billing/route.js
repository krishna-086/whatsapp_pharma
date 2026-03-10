import { NextResponse } from "next/server";
import {
    getInventory,
    upsertInventoryItem,
    createTransaction,
} from "@/lib/cosmos";

export async function POST(request) {
    try {
        const body = await request.json();
        const { items, customerName, paymentMethod } = body;

        if (!items || !items.length) {
            return NextResponse.json({ error: "No items provided" }, { status: 400 });
        }

        // Fetch current inventory to validate & deduct
        const inventory = await getInventory();
        const inventoryMap = {};
        for (const inv of inventory) {
            inventoryMap[inv.id] = inv;
        }

        const saleItems = [];
        const errors = [];

        for (const item of items) {
            const inv = inventoryMap[item.id];
            if (!inv) {
                errors.push(`${item.name || item.id} not found in inventory`);
                continue;
            }
            if ((inv.quantity || 0) < (item.quantity || 1)) {
                errors.push(`${inv.name}: insufficient stock (have ${inv.quantity})`);
                continue;
            }

            const qty = item.quantity || 1;
            const mrp = inv.mrp || 0;
            const amount = Math.round(qty * mrp * 100) / 100;

            // Deduct stock
            inv.quantity = (inv.quantity || 0) - qty;
            await upsertInventoryItem(inv);

            saleItems.push({
                name: inv.name,
                quantity: qty,
                mrp,
                amount,
            });
        }

        if (saleItems.length === 0) {
            return NextResponse.json({ error: errors.join("; ") }, { status: 400 });
        }

        const total = saleItems.reduce((s, i) => s + i.amount, 0);

        // Record transaction
        const txn = await createTransaction({
            type: "sale",
            sender: "dashboard",
            customer_name: customerName || "",
            payment_method: paymentMethod || "cash",
            items: saleItems,
            total: Math.round(total * 100) / 100,
        });

        return NextResponse.json({
            success: true,
            transaction: txn,
            errors: errors.length ? errors : undefined,
        });
    } catch (e) {
        return NextResponse.json({ error: e.message }, { status: 500 });
    }
}
