CREATE TABLE `pace_snapshots` (
	`id` integer PRIMARY KEY NOT NULL,
	`schema_version` integer NOT NULL,
	`generated_at` text NOT NULL,
	`uploaded_at` text NOT NULL,
	`snapshot_json` text NOT NULL
);
