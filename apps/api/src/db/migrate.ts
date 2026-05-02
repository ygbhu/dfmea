import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { Pool } from 'pg';
import { getDatabaseUrl } from './env';

const migrationsDir = resolve(__dirname, 'migrations');

export async function runMigrations(databaseUrl = getDatabaseUrl()): Promise<void> {
  const pool = new Pool({ connectionString: databaseUrl });
  const client = await pool.connect();

  try {
    await client.query(`
      CREATE TABLE IF NOT EXISTS schema_migrations (
        migration_id text PRIMARY KEY,
        applied_at timestamptz NOT NULL DEFAULT now()
      );
    `);

    if (!existsSync(migrationsDir)) {
      throw new Error(`Migrations directory does not exist: ${migrationsDir}`);
    }

    const files = readdirSync(migrationsDir)
      .filter((file) => file.endsWith('.sql'))
      .sort();

    for (const file of files) {
      const migrationId = file;
      const applied = await client.query('SELECT 1 FROM schema_migrations WHERE migration_id = $1', [
        migrationId,
      ]);

      if (applied.rowCount) {
        continue;
      }

      const sql = readFileSync(resolve(migrationsDir, file), 'utf8');
      await client.query('BEGIN');
      try {
        await client.query(sql);
        await client.query('INSERT INTO schema_migrations (migration_id) VALUES ($1)', [migrationId]);
        await client.query('COMMIT');
        console.log(`Applied migration ${migrationId}`);
      } catch (error) {
        await client.query('ROLLBACK');
        throw error;
      }
    }
  } finally {
    client.release();
    await pool.end();
  }
}

if (require.main === module) {
  void runMigrations().catch((error: unknown) => {
    console.error(error);
    process.exit(1);
  });
}
