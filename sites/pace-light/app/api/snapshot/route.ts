import { getDb } from "../../../db";
import { paceSnapshots } from "../../../db/schema";
export const dynamic = "force-dynamic";
const MAX_SNAPSHOT_BYTES = 512_000;

export async function POST(request: Request) {
  if (Number(request.headers.get("content-length") ?? 0) > MAX_SNAPSHOT_BYTES) return Response.json({ error: "Snapshot exceeds 500 KiB." }, { status: 413 });
  let value: unknown;
  try { value = await request.json(); } catch { return Response.json({ error: "Snapshot must be valid JSON." }, { status: 400 }); }
  const error = validateSnapshot(value); if (error) return Response.json({ error }, { status: 400 });
  const snapshot = value as PaceSnapshot, uploadedAt = new Date().toISOString();
  await getDb().insert(paceSnapshots).values({ id: 1, schemaVersion: snapshot.schema_version, generatedAt: snapshot.generated_at, uploadedAt, snapshotJson: JSON.stringify(snapshot) }).onConflictDoUpdate({ target: paceSnapshots.id, set: { schemaVersion: snapshot.schema_version, generatedAt: snapshot.generated_at, uploadedAt, snapshotJson: JSON.stringify(snapshot) } });
  return Response.json({ accepted: true, generated_at: snapshot.generated_at });
}
type PaceSnapshot = { schema_version:number; generated_at:string; as_of_date:string; recent_activities:unknown[]; active_plan:unknown|null };
function validateSnapshot(value: unknown): string | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return "Snapshot must be an object.";
  const item=value as Record<string,unknown>;
  if(item.schema_version!==1)return "Unsupported snapshot schema.";
  if(typeof item.generated_at!=="string"||Number.isNaN(Date.parse(item.generated_at)))return "generated_at must be an ISO timestamp.";
  if(typeof item.as_of_date!=="string"||!/^\d{4}-\d{2}-\d{2}$/.test(item.as_of_date))return "as_of_date must use YYYY-MM-DD.";
  if(!Array.isArray(item.recent_activities)||item.recent_activities.length>84)return "recent_activities must contain at most 84 items.";
  if(!(item.active_plan===null||(typeof item.active_plan==="object"&&!Array.isArray(item.active_plan))))return "active_plan must be an object or null.";
  const forbidden=JSON.stringify(value).match(/provider_activity_id|raw_payload|latitude|longitude|polyline|gps|api_key|token/i);return forbidden?`Forbidden private field: ${forbidden[0]}.`:null;
}
