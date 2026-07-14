PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  minecraft_uuid TEXT UNIQUE,
  minecraft_name TEXT,
  discord_id TEXT UNIQUE,
  google_id TEXT UNIQUE,
  display_name TEXT,
  role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('owner', 'admin', 'user', 'guest')),
  minecraft_verified_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auth_links (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  provider TEXT NOT NULL CHECK (provider IN ('discord', 'google')),
  provider_subject TEXT NOT NULL,
  minecraft_uuid TEXT,
  minecraft_name TEXT,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'verified', 'expired', 'revoked')),
  expires_at TEXT NOT NULL,
  verified_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admins (
  discord_id TEXT PRIMARY KEY,
  role TEXT NOT NULL CHECK (role IN ('owner', 'admin')),
  added_by_discord_id TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS points (
  minecraft_uuid TEXT PRIMARY KEY,
  balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
  daily_minesweeper_points INTEGER NOT NULL DEFAULT 0 CHECK (daily_minesweeper_points >= 0),
  daily_points_date TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (minecraft_uuid) REFERENCES users(minecraft_uuid)
);

CREATE TABLE IF NOT EXISTS point_transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  minecraft_uuid TEXT NOT NULL,
  amount INTEGER NOT NULL,
  kind TEXT NOT NULL CHECK (
    kind IN (
      'minecraft_activity',
      'minesweeper',
      'discord_first_verify',
      'admin_adjustment',
      'trial_penalty'
    )
  ),
  source_id TEXT,
  reason TEXT,
  actor_discord_id TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (minecraft_uuid) REFERENCES users(minecraft_uuid)
);

CREATE TABLE IF NOT EXISTS incidents (
  incident_id TEXT PRIMARY KEY,
  type TEXT NOT NULL CHECK (type IN ('PVP', 'ITEM', 'ENV', 'REPLAY', 'CHEST', 'ADMIN', 'TRIAL')),
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'reviewing', 'trial', 'closed')),
  summary TEXT NOT NULL,
  visibility TEXT NOT NULL DEFAULT 'admin_only' CHECK (visibility IN ('public_summary', 'admin_only')),
  auto_punishment_allowed INTEGER NOT NULL DEFAULT 0 CHECK (auto_punishment_allowed IN (0, 1)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  closed_at TEXT
);

CREATE TABLE IF NOT EXISTS incident_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  incident_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  actor_uuid TEXT,
  target_uuid TEXT,
  world TEXT,
  x REAL,
  y REAL,
  z REAL,
  yaw REAL,
  pitch REAL,
  payload_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (incident_id) REFERENCES incidents(incident_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS death_items (
  item_id TEXT PRIMARY KEY,
  incident_id TEXT NOT NULL,
  death_id TEXT NOT NULL,
  owner_uuid TEXT NOT NULL,
  material TEXT NOT NULL,
  original_amount INTEGER NOT NULL CHECK (original_amount > 0),
  remaining_amount INTEGER NOT NULL CHECK (remaining_amount >= 0),
  returned_amount INTEGER NOT NULL DEFAULT 0 CHECK (returned_amount >= 0),
  tag_removed_amount INTEGER NOT NULL DEFAULT 0 CHECK (tag_removed_amount >= 0),
  status TEXT NOT NULL DEFAULT 'unrecovered' CHECK (
    status IN (
      'unrecovered',
      'picked_by_other',
      'stored',
      'partially_returned',
      'fully_returned',
      'tag_removed',
      'suspected_lost'
    )
  ),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (incident_id) REFERENCES incidents(incident_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS item_movements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id TEXT NOT NULL,
  incident_id TEXT NOT NULL,
  movement_type TEXT NOT NULL CHECK (
    movement_type IN ('drop', 'pickup', 'chest_in', 'chest_out', 'player_transfer', 'owner_return', 'lost_suspected')
  ),
  from_uuid TEXT,
  to_uuid TEXT,
  container_location TEXT,
  amount INTEGER NOT NULL CHECK (amount > 0),
  tag_removed INTEGER NOT NULL DEFAULT 0 CHECK (tag_removed IN (0, 1)),
  payload_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (item_id) REFERENCES death_items(item_id) ON DELETE CASCADE,
  FOREIGN KEY (incident_id) REFERENCES incidents(incident_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS secret_containers (
  container_id TEXT PRIMARY KEY,
  world TEXT NOT NULL,
  x INTEGER NOT NULL,
  y INTEGER NOT NULL,
  z INTEGER NOT NULL,
  container_type TEXT NOT NULL,
  first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_opened_at TEXT,
  last_opened_by_uuid TEXT,
  last_opened_by_name TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(world, x, y, z)
);

CREATE TABLE IF NOT EXISTS secret_container_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  container_id TEXT NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('open', 'close')),
  actor_uuid TEXT NOT NULL,
  actor_name TEXT NOT NULL,
  world TEXT NOT NULL,
  x INTEGER NOT NULL,
  y INTEGER NOT NULL,
  z INTEGER NOT NULL,
  container_type TEXT NOT NULL,
  contents_json TEXT NOT NULL DEFAULT '[]',
  payload_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (container_id) REFERENCES secret_containers(container_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS legal_reports (
  report_id TEXT PRIMARY KEY,
  report_type TEXT NOT NULL CHECK (report_type IN ('complaint', 'prosecution')),
  reporter_discord_id TEXT NOT NULL,
  reporter_name TEXT NOT NULL,
  target_name TEXT NOT NULL,
  summary TEXT NOT NULL,
  world TEXT,
  x INTEGER,
  y INTEGER,
  z INTEGER,
  radius INTEGER NOT NULL DEFAULT 15 CHECK (radius >= 0),
  related_secret_events_json TEXT NOT NULL DEFAULT '[]',
  related_count INTEGER NOT NULL DEFAULT 0 CHECK (related_count >= 0),
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'reviewing', 'trial', 'closed')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS replays (
  replay_id TEXT PRIMARY KEY,
  incident_id TEXT NOT NULL,
  subject_uuid TEXT,
  window_before_seconds INTEGER NOT NULL DEFAULT 30,
  window_after_seconds INTEGER NOT NULL DEFAULT 60,
  storage_path TEXT,
  payload_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (incident_id) REFERENCES incidents(incident_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS trials (
  trial_id TEXT PRIMARY KEY,
  incident_id TEXT NOT NULL,
  accused_name TEXT NOT NULL,
  victim_name TEXT NOT NULL,
  witnesses_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
  verdict TEXT,
  punishment_type TEXT CHECK (
    punishment_type IS NULL OR punishment_type IN (
      'warning',
      'point_deduction',
      'item_return_order',
      'temporary_access_restriction',
      'ip_ban_candidate',
      'permanent_ban_candidate',
      'combined',
      'manual_judgement'
    )
  ),
  restitution TEXT,
  memo TEXT,
  discord_channel_id TEXT,
  discord_thread_url TEXT,
  decided_by_discord_id TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  closed_at TEXT,
  FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
);

CREATE TABLE IF NOT EXISTS trial_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trial_id TEXT NOT NULL,
  discord_message_id TEXT,
  author_discord_id TEXT,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (trial_id) REFERENCES trials(trial_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_type TEXT NOT NULL CHECK (actor_type IN ('bot', 'plugin', 'admin', 'system')),
  actor_id TEXT,
  action TEXT NOT NULL,
  target_type TEXT,
  target_id TEXT,
  payload_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS server_status (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  is_online INTEGER NOT NULL DEFAULT 0 CHECK (is_online IN (0, 1)),
  stable_state TEXT NOT NULL DEFAULT 'unknown' CHECK (stable_state IN ('online', 'offline', 'unknown')),
  stable_since TEXT,
  player_count INTEGER NOT NULL DEFAULT 0,
  max_players INTEGER NOT NULL DEFAULT 20,
  tps REAL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS registration_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  last_name TEXT NOT NULL,
  first_name TEXT NOT NULL,
  full_name TEXT NOT NULL,
  minecraft_name TEXT NOT NULL,
  minecraft_uuid TEXT,
  discord_name TEXT NOT NULL,
  discord_id TEXT,
  google_email TEXT,
  google_sub TEXT,
  password_hash TEXT,
  password_alg TEXT,
  ip_hash TEXT,
  ip_prefix_hash TEXT,
  user_agent_hash TEXT,
  device_token_hash TEXT,
  validation_result TEXT NOT NULL DEFAULT '{}',
  warning_count INTEGER NOT NULL DEFAULT 0 CHECK (warning_count >= 0),
  status TEXT NOT NULL DEFAULT 'PENDING' CHECK (
    status IN ('PENDING', 'APPROVED', 'REJECTED', 'WARNING', 'SUSPENDED_6H', 'BANNED')
  ),
  auto_approved INTEGER NOT NULL DEFAULT 0 CHECK (auto_approved IN (0, 1)),
  suspension_until TEXT,
  ban_reason TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_registration_attempts_minecraft_name
  ON registration_attempts(minecraft_name);

CREATE INDEX IF NOT EXISTS idx_registration_attempts_ip_hash
  ON registration_attempts(ip_hash);

CREATE INDEX IF NOT EXISTS idx_registration_attempts_device_token_hash
  ON registration_attempts(device_token_hash);

CREATE INDEX IF NOT EXISTS idx_registration_attempts_status
  ON registration_attempts(status);

CREATE TABLE IF NOT EXISTS registration_bans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  discord_id TEXT,
  minecraft_uuid TEXT,
  minecraft_name TEXT,
  google_sub TEXT,
  google_email TEXT,
  ip_hash TEXT,
  device_token_hash TEXT,
  reason TEXT NOT NULL,
  evidence_json TEXT NOT NULL DEFAULT '{}',
  banned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  banned_by TEXT,
  is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_registration_bans_active
  ON registration_bans(is_active);

CREATE INDEX IF NOT EXISTS idx_registration_bans_identity
  ON registration_bans(discord_id, minecraft_uuid, google_sub, ip_hash, device_token_hash);

CREATE TABLE IF NOT EXISTS admin_accounts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider TEXT NOT NULL CHECK (provider IN ('discord', 'google', 'minecraft')),
  provider_subject TEXT NOT NULL,
  discord_id TEXT,
  google_sub TEXT,
  google_email TEXT,
  minecraft_uuid TEXT,
  minecraft_name TEXT,
  display_name TEXT,
  role TEXT NOT NULL CHECK (role IN ('owner', 'admin')),
  added_by TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(provider, provider_subject)
);

CREATE INDEX IF NOT EXISTS idx_admin_accounts_provider
  ON admin_accounts(provider, provider_subject);

CREATE TABLE IF NOT EXISTS linked_accounts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  discord_id TEXT,
  minecraft_uuid TEXT,
  google_sub TEXT,
  google_email TEXT,
  linked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  verified_at TEXT,
  status TEXT NOT NULL DEFAULT 'linked' CHECK (status IN ('linked', 'verified', 'revoked', 'blocked')),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_linked_accounts_discord_id
  ON linked_accounts(discord_id);

CREATE INDEX IF NOT EXISTS idx_linked_accounts_minecraft_uuid
  ON linked_accounts(minecraft_uuid);

CREATE INDEX IF NOT EXISTS idx_linked_accounts_google_sub
  ON linked_accounts(google_sub);

CREATE TABLE IF NOT EXISTS registration_security_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_type TEXT NOT NULL,
  severity TEXT NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH')),
  ip_hash TEXT,
  ip_prefix_hash TEXT,
  user_agent_hash TEXT,
  device_token_hash TEXT,
  discord_id TEXT,
  minecraft_uuid TEXT,
  google_sub TEXT,
  minecraft_name TEXT,
  discord_name TEXT,
  message TEXT NOT NULL,
  evidence_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_registration_security_events_type
  ON registration_security_events(event_type);

CREATE INDEX IF NOT EXISTS idx_registration_security_events_ip_hash
  ON registration_security_events(ip_hash);

CREATE INDEX IF NOT EXISTS idx_registration_security_events_device_token_hash
  ON registration_security_events(device_token_hash);

INSERT OR IGNORE INTO server_status (id) VALUES (1);

CREATE INDEX IF NOT EXISTS idx_incidents_type_created ON incidents(type, created_at);
CREATE INDEX IF NOT EXISTS idx_incident_events_incident ON incident_events(incident_id);
CREATE INDEX IF NOT EXISTS idx_point_transactions_uuid ON point_transactions(minecraft_uuid, created_at);
CREATE INDEX IF NOT EXISTS idx_item_movements_item ON item_movements(item_id, created_at);
CREATE INDEX IF NOT EXISTS idx_secret_container_events_container ON secret_container_events(container_id, created_at);
CREATE INDEX IF NOT EXISTS idx_secret_container_events_actor ON secret_container_events(actor_uuid, created_at);
CREATE INDEX IF NOT EXISTS idx_secret_container_events_actor_name ON secret_container_events(actor_name, created_at);
CREATE INDEX IF NOT EXISTS idx_secret_container_events_location ON secret_container_events(world, x, y, z, created_at);
CREATE INDEX IF NOT EXISTS idx_legal_reports_type_created ON legal_reports(report_type, created_at);
CREATE INDEX IF NOT EXISTS idx_legal_reports_target ON legal_reports(target_name, created_at);
CREATE INDEX IF NOT EXISTS idx_replays_incident ON replays(incident_id, created_at);
CREATE INDEX IF NOT EXISTS idx_replays_subject ON replays(subject_uuid, created_at);
CREATE INDEX IF NOT EXISTS idx_trials_incident ON trials(incident_id);
