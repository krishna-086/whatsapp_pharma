import { NextResponse } from "next/server";
import { getTransactions, deepFlatten } from "@/lib/cosmos";

export async function GET() {
    try {
        const txns = await getTransactions(200);
        return NextResponse.json(deepFlatten(txns));
    } catch (e) {
        return NextResponse.json({ error: e.message }, { status: 500 });
    }
}
