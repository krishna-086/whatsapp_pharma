import { CosmosClient } from "@azure/cosmos";

const endpoint = process.env.COSMOS_ENDPOINT;
const key = process.env.COSMOS_KEY;
const databaseId = process.env.COSMOS_DB || "pharmagent";

let client;
let database;

function getDatabase() {
  if (!database) {
    client = new CosmosClient({ endpoint, key });
    database = client.database(databaseId);
  }
  return database;
}

function getContainer(containerName) {
  return getDatabase().container(containerName);
}

// Deeply flattens Document Intelligence objects { value, confidence } recursively
export function deepFlatten(obj) {
  if (obj === null || obj === undefined) return obj;
  if (typeof obj !== 'object') return obj;

  // If it's a { value, confidence } object, extract and flatten the value
  if ('value' in obj && Object.keys(obj).length <= 3 && ('confidence' in obj || 'source' in obj)) {
    return deepFlatten(obj.value);
  }

  if (Array.isArray(obj)) {
    return obj.map(deepFlatten);
  }

  const newObj = {};
  for (const key in obj) {
    newObj[key] = deepFlatten(obj[key]);
  }
  return newObj;
}

// ─── Inventory ───────────────────────────────────────────────
export async function getInventory() {
  const { resources } = await getContainer("inventory").items
    .query("SELECT * FROM c ORDER BY c.name")
    .fetchAll();
  return resources;
}

export async function getInventoryItem(id) {
  try {
    const { resource } = await getContainer("inventory").item(id, id).read();
    return resource;
  } catch {
    return null;
  }
}

export async function upsertInventoryItem(doc) {
  doc.updated_at = new Date().toISOString();
  if (!doc.name_lower && doc.name) {
    doc.name_lower = doc.name.toLowerCase();
  }
  const { resource } = await getContainer("inventory").items.upsert(doc);
  return resource;
}

export async function deleteInventoryItem(id) {
  await getContainer("inventory").item(id, id).delete();
}

// ─── Transactions ────────────────────────────────────────────
export async function getTransactions(limit = 100) {
  const { resources } = await getContainer("transactions").items
    .query({
      query: "SELECT * FROM c ORDER BY c.created_at DESC OFFSET 0 LIMIT @lim",
      parameters: [{ name: "@lim", value: limit }],
    })
    .fetchAll();
  return resources;
}

export async function createTransaction(doc) {
  doc.created_at = new Date().toISOString();
  if (!doc.id) doc.id = crypto.randomUUID();
  const { resource } = await getContainer("transactions").items.upsert(doc);
  return resource;
}

// ─── Invoices ──────────────────────────────���─────────────────
export async function getInvoices(limit = 100) {
  const { resources } = await getContainer("invoices").items
    .query({
      query: "SELECT * FROM c ORDER BY c.created_at DESC OFFSET 0 LIMIT @lim",
      parameters: [{ name: "@lim", value: limit }],
    })
    .fetchAll();
  return resources;
}

// ─── Stats helpers ───────────────────────────────────────────
export async function getDashboardStats() {
  const [inventory, transactions] = await Promise.all([
    getInventory(),
    getTransactions(500),
  ]);

  const totalItems = inventory.length;
  const lowStockCount = inventory.filter((i) => (deepFlatten(i.quantity) || 0) < 10).length;
  const totalStockValue = inventory.reduce(
    (sum, i) => sum + (Number(deepFlatten(i.quantity)) || 0) * (Number(deepFlatten(i.mrp)) || Number(deepFlatten(i.unit_price)) || 0),
    0
  );

  const today = new Date().toISOString().slice(0, 10);
  const todaySales = transactions.filter(
    (t) => t.type === "sale" && (t.created_at || "").slice(0, 10) === today
  );
  const todayRevenue = todaySales.reduce((s, t) => s + (Number(deepFlatten(t.total)) || 0), 0);
  const totalRevenue = transactions
    .filter((t) => t.type === "sale")
    .reduce((s, t) => s + (Number(deepFlatten(t.total)) || 0), 0);

  // Last 7 days revenue for chart
  const revenueByDay = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const dateStr = d.toISOString().slice(0, 10);
    const dayLabel = d.toLocaleDateString("en-IN", { weekday: "short" });
    const dayRevenue = transactions
      .filter(
        (t) => t.type === "sale" && (t.created_at || "").slice(0, 10) === dateStr
      )
      .reduce((s, t) => s + (Number(deepFlatten(t.total)) || 0), 0);
    revenueByDay.push({ day: dayLabel, revenue: Math.round(dayRevenue * 100) / 100 });
  }

  return {
    totalItems,
    lowStockCount,
    totalStockValue: Math.round(totalStockValue * 100) / 100,
    todaySalesCount: todaySales.length,
    todayRevenue: Math.round(todayRevenue * 100) / 100,
    totalRevenue: Math.round(totalRevenue * 100) / 100,
    revenueByDay,
  };
}
