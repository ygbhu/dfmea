from __future__ import annotations

import sqlite3


SCHEMA_TABLES = ("projects", "nodes", "fm_links")


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS projects (
      id       TEXT PRIMARY KEY,
      name     TEXT NOT NULL,
      data     TEXT NOT NULL DEFAULT '{}',
      created  TEXT NOT NULL,
      updated  TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS nodes (
      rowid      INTEGER PRIMARY KEY AUTOINCREMENT,
      id         TEXT UNIQUE,
      type       TEXT NOT NULL,
      parent_id  INTEGER NOT NULL DEFAULT 0,
      project_id TEXT NOT NULL REFERENCES projects(id),
      name       TEXT,
      data       TEXT NOT NULL DEFAULT '{}',
      created    TEXT NOT NULL,
      updated    TEXT NOT NULL
    )
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_cascade_delete_node
    AFTER DELETE ON nodes
    BEGIN
      DELETE FROM nodes WHERE parent_id = OLD.rowid;
    END
    """,
    """
    CREATE TABLE IF NOT EXISTS fm_links (
      from_rowid  INTEGER NOT NULL REFERENCES nodes(rowid) ON DELETE CASCADE,
      to_fm_rowid INTEGER NOT NULL REFERENCES nodes(rowid) ON DELETE CASCADE,
      PRIMARY KEY (from_rowid, to_fm_rowid)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_node_type ON nodes(type, project_id)",
    "CREATE INDEX IF NOT EXISTS idx_node_parent ON nodes(parent_id)",
    "CREATE INDEX IF NOT EXISTS idx_node_id ON nodes(id) WHERE id IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_fm_links_to ON fm_links(to_fm_rowid)",
)


def bootstrap_schema(conn: sqlite3.Connection) -> None:
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)
