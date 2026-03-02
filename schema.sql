CREATE TABLE IF NOT EXISTS Players (
    id_discord BIGINT PRIMARY KEY,
    name TEXT,
    zanzibar INTEGER DEFAULT 100,
    is_farming BOOLEAN DEFAULT FALSE,
    start_farm_time TIMESTAMP,
    last_daily TIMESTAMP,
    has_droid BOOLEAN DEFAULT FALSE,
    daily_cooldown_hours INTEGER DEFAULT 24,
    daily_min INTEGER DEFAULT 50,
    daily_max INTEGER DEFAULT 100,
    prod_multiplier FLOAT DEFAULT 1.0,
    has_trader_1 BOOLEAN DEFAULT FALSE,
    has_trader_2 BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS Tokens (
    token_name TEXT PRIMARY KEY,
    current_value FLOAT DEFAULT 100.0,
    total_farmers INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS Inventory (
    player_id BIGINT,
    token_name TEXT,
    amount FLOAT DEFAULT 0.0,
    PRIMARY KEY (player_id, token_name),
    FOREIGN KEY (player_id) REFERENCES Players(id_discord)
);
