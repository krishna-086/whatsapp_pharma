import { NextResponse } from "next/server";
import { getDashboardStats } from "@/lib/cosmos";

export async function GET() {
    try {
        const stats = await getDashboardStats();
        return NextResponse.json(stats);
    } catch (e) {
        return NextResponse.json({ error: e.message }, { status: 500 });
    }
}
