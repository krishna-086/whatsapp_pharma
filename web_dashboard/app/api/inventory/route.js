import { NextResponse } from "next/server";
import {
    getInventory,
    upsertInventoryItem,
    deleteInventoryItem,
    deepFlatten,
} from "@/lib/cosmos";

export async function GET() {
    try {
        const rawItems = await getInventory();
        const items = deepFlatten(rawItems);
        return NextResponse.json(items);
    } catch (e) {
        return NextResponse.json({ error: e.message }, { status: 500 });
    }
}

export async function POST(request) {
    try {
        const body = await request.json();
        const result = await upsertInventoryItem(body);
        return NextResponse.json(result);
    } catch (e) {
        return NextResponse.json({ error: e.message }, { status: 500 });
    }
}

export async function DELETE(request) {
    try {
        const { searchParams } = new URL(request.url);
        const id = searchParams.get("id");
        if (!id) return NextResponse.json({ error: "id required" }, { status: 400 });
        await deleteInventoryItem(id);
        return NextResponse.json({ success: true });
    } catch (e) {
        return NextResponse.json({ error: e.message }, { status: 500 });
    }
}
