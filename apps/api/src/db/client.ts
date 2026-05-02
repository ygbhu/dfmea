import { drizzle, type NodePgDatabase } from 'drizzle-orm/node-postgres';
import { Pool } from 'pg';
import { getDatabaseUrl } from './env';
import * as schema from './schema';

export type AppDatabase = NodePgDatabase<typeof schema>;

export interface DatabaseClient {
  db: AppDatabase;
  pool: Pool;
  close(): Promise<void>;
}

export function createDatabaseClient(databaseUrl = getDatabaseUrl()): DatabaseClient {
  const pool = new Pool({
    connectionString: databaseUrl,
  });

  return {
    db: drizzle(pool, { schema }),
    pool,
    close: () => pool.end(),
  };
}
