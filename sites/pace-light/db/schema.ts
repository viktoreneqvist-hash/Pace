import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";
export const paceSnapshots = sqliteTable("pace_snapshots", { id: integer("id").primaryKey(), schemaVersion: integer("schema_version").notNull(), generatedAt: text("generated_at").notNull(), uploadedAt: text("uploaded_at").notNull(), snapshotJson: text("snapshot_json").notNull() });
