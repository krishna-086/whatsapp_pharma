import { CosmosClient } from "@azure/cosmos";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

// Manual .env.local parsing to avoid 'dotenv' dependency
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const envPath = path.resolve(__dirname, ".env.local");

const env = {};
if (fs.existsSync(envPath)) {
    const content = fs.readFileSync(envPath, "utf8");
    content.split("\n").forEach(line => {
        const parts = line.split("=");
        if (parts.length >= 2) {
            const key = parts[0].trim();
            const val = parts.slice(1).join("=").trim();
            env[key] = val;
        }
    });
}

const endpoint = env.COSMOS_ENDPOINT || process.env.COSMOS_ENDPOINT;
const key = env.COSMOS_KEY || process.env.COSMOS_KEY;
const databaseId = env.COSMOS_DB || process.env.COSMOS_DB || "pharmagent";

async function check() {
    if (!endpoint || !key) {
        console.error("Missing COSMOS_ENDPOINT or COSMOS_KEY in .env.local or environment");
        return;
    }

    const client = new CosmosClient({ endpoint, key });
    const database = client.database(databaseId);
    const containers = ["invoices", "inventory", "transactions"];

    for (const cName of containers) {
        console.log(`\n--- Container: ${cName} ---`);
        try {
            const container = database.container(cName);
            const { resources } = await container.items.query("SELECT TOP 1 * FROM c").fetchAll();
            if (resources.length > 0) {
                console.log(JSON.stringify(resources[0], null, 2));
            } else {
                console.log("Empty container.");
            }
        } catch (e) {
            console.error(`Error reading ${cName}: ${e.message}`);
        }
    }
}

check();
