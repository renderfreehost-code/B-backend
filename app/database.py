import os
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

def init_db():
    schema = """
    CREATE TABLE IF NOT EXISTS users (
      id SERIAL PRIMARY KEY,
      name TEXT NOT NULL,
      email TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      balance BIGINT NOT NULL DEFAULT 10000,
      is_admin BOOLEAN NOT NULL DEFAULT FALSE,
      referral_code TEXT UNIQUE,
      referred_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
      referral_bonus_earned BIGINT NOT NULL DEFAULT 0,
      email_verified BOOLEAN NOT NULL DEFAULT FALSE,
      reset_token TEXT,
      reset_token_expires_at TIMESTAMPTZ,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code TEXT UNIQUE;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_bonus_earned BIGINT NOT NULL DEFAULT 0;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token TEXT;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expires_at TIMESTAMPTZ;


    CREATE TABLE IF NOT EXISTS email_verifications (
      id BIGSERIAL PRIMARY KEY,
      user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
      email TEXT NOT NULL,
      code TEXT NOT NULL,
      purpose TEXT NOT NULL DEFAULT 'signup',
      expires_at TIMESTAMPTZ NOT NULL,
      used BOOLEAN NOT NULL DEFAULT FALSE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS settings (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS games (
      id SERIAL PRIMARY KEY,
      name TEXT NOT NULL,
      slug TEXT UNIQUE NOT NULL,
      category TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'active',
      min_bet BIGINT NOT NULL DEFAULT 10,
      max_bet BIGINT NOT NULL DEFAULT 10000,
      risk_level TEXT NOT NULL DEFAULT 'medium',
      win_chance INTEGER NOT NULL DEFAULT 45,
      payout_min NUMERIC(8,2) NOT NULL DEFAULT 1.20,
      payout_max NUMERIC(8,2) NOT NULL DEFAULT 3.00,
      result_mode TEXT NOT NULL DEFAULT 'per_user_rng',
      visible BOOLEAN NOT NULL DEFAULT TRUE
    );

    CREATE TABLE IF NOT EXISTS deposit_requests (
      id SERIAL PRIMARY KEY,
      user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
      amount BIGINT NOT NULL,
      note TEXT,
      status TEXT NOT NULL DEFAULT 'processing',
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      reviewed_at TIMESTAMPTZ
    );

    CREATE TABLE IF NOT EXISTS bets (
      id SERIAL PRIMARY KEY,
      user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
      game_id INTEGER REFERENCES games(id) ON DELETE CASCADE,
      amount BIGINT NOT NULL,
      result TEXT NOT NULL,
      payout BIGINT NOT NULL DEFAULT 0,
      multiplier NUMERIC(8,2) NOT NULL DEFAULT 0,
      balance_before BIGINT NOT NULL DEFAULT 0,
      balance_after BIGINT NOT NULL DEFAULT 0,
      rng_roll INTEGER NOT NULL DEFAULT 0,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    ALTER TABLE bets ADD COLUMN IF NOT EXISTS balance_before BIGINT NOT NULL DEFAULT 0;
    ALTER TABLE bets ADD COLUMN IF NOT EXISTS balance_after BIGINT NOT NULL DEFAULT 0;
    ALTER TABLE bets ADD COLUMN IF NOT EXISTS rng_roll INTEGER NOT NULL DEFAULT 0;

    CREATE TABLE IF NOT EXISTS coin_ledger (
      id BIGSERIAL PRIMARY KEY,
      user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
      type TEXT NOT NULL,
      amount BIGINT NOT NULL,
      balance_before BIGINT NOT NULL,
      balance_after BIGINT NOT NULL,
      note TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS referral_rewards (
      id BIGSERIAL PRIMARY KEY,
      referrer_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
      referred_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
      amount BIGINT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE(referrer_user_id, referred_user_id)
    );

    CREATE TABLE IF NOT EXISTS messages (
      id SERIAL PRIMARY KEY,
      user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
      title TEXT NOT NULL,
      body TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_bets_user_created ON bets(user_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_bets_game_created ON bets(game_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_deposit_user_created ON deposit_requests(user_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_deposit_status ON deposit_requests(status);
    CREATE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code);
    CREATE INDEX IF NOT EXISTS idx_ledger_user_created ON coin_ledger(user_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_email_verifications_user ON email_verifications(user_id, purpose, used);
    CREATE INDEX IF NOT EXISTS idx_games_category_visible ON games(category, visible);
    CREATE INDEX IF NOT EXISTS idx_games_status_visible ON games(status, visible);
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(schema)
            conn.commit()

def seed_games():
    games = [
      ("Aviator", "aviator", "Crash"),
      ("Rocket Crash", "rocket-crash", "Crash"),
      ("Space Crash", "space-crash", "Crash"),
      ("JetX", "jetx", "Crash"),
      ("Balloon Crash", "balloon-crash", "Crash"),
      ("Multiplier Rush", "multiplier-rush", "Crash"),
      ("Cash Rocket", "cash-rocket", "Crash"),
      ("Turbo Plane", "turbo-plane", "Crash"),
      ("Crash X", "crash-x", "Crash"),
      ("Galaxy Flight", "galaxy-flight", "Crash"),
      ("Dice", "dice", "Number"),
      ("Mines", "mines", "Number"),
      ("Plinko", "plinko", "Number"),
      ("Limbo", "limbo", "Number"),
      ("Keno", "keno", "Number"),
      ("Coin Flip", "coin-flip", "Number"),
      ("Hi-Lo", "hi-lo", "Number"),
      ("Wheel", "wheel", "Number"),
      ("Lucky Number", "lucky-number", "Number"),
      ("Goal", "goal", "Number"),
      ("Tower", "tower", "Number"),
      ("Hilo Cards", "hilo-cards", "Number"),
      ("Roulette", "roulette", "Casino"),
      ("European Roulette", "european-roulette", "Casino"),
      ("American Roulette", "american-roulette", "Casino"),
      ("Blackjack", "blackjack", "Casino"),
      ("Baccarat", "baccarat", "Casino"),
      ("Dragon Tiger", "dragon-tiger", "Casino"),
      ("Sic Bo", "sic-bo", "Casino"),
      ("Craps", "craps", "Casino"),
      ("Andar Bahar", "andar-bahar", "Casino"),
      ("Teen Patti", "teen-patti", "Casino"),
      ("Casino Hold'em", "casino-holdem", "Casino"),
      ("Poker", "poker", "Cards"),
      ("Texas Poker", "texas-poker", "Cards"),
      ("Omaha Poker", "omaha-poker", "Cards"),
      ("Three Card Poker", "three-card-poker", "Cards"),
      ("Red Dog", "red-dog", "Cards"),
      ("War Card", "war-card", "Cards"),
      ("Rummy", "rummy", "Cards"),
      ("Bridge Mock", "bridge-mock", "Cards"),
      ("Classic Slot", "classic-slot", "Slots"),
      ("Fruit Slot", "fruit-slot", "Slots"),
      ("Treasure Slot", "treasure-slot", "Slots"),
      ("Mega Spin", "mega-spin", "Slots"),
      ("Candy Slot", "candy-slot", "Slots"),
      ("Egypt Slot", "egypt-slot", "Slots"),
      ("Pirate Gold", "pirate-gold", "Slots"),
      ("Book of Demo", "book-of-demo", "Slots"),
      ("Lucky Seven", "lucky-seven", "Slots"),
      ("Jungle Spin", "jungle-spin", "Slots"),
      ("Wild Gems", "wild-gems", "Slots"),
      ("Fire Joker", "fire-joker", "Slots"),
      ("Diamond Rush", "diamond-rush", "Slots"),
      ("Golden Buffalo", "golden-buffalo", "Slots"),
      ("Football", "football", "Sports"),
      ("Cricket", "cricket", "Sports"),
      ("Basketball", "basketball", "Sports"),
      ("Tennis", "tennis", "Sports"),
      ("Volleyball", "volleyball", "Sports"),
      ("Table Tennis", "table-tennis", "Sports"),
      ("Esports", "esports", "Sports"),
      ("Horse Racing Mock", "horse-racing-mock", "Sports"),
      ("Greyhound Mock", "greyhound-mock", "Sports"),
      ("Baseball", "baseball", "Sports"),
      ("Ice Hockey", "ice-hockey", "Sports"),
      ("Boxing", "boxing", "Sports"),
      ("MMA", "mma", "Sports"),
      ("Kabaddi", "kabaddi", "Sports"),
      ("Live Roulette", "live-roulette", "Live Casino"),
      ("Live Blackjack", "live-blackjack", "Live Casino"),
      ("Live Baccarat", "live-baccarat", "Live Casino"),
      ("Live Wheel", "live-wheel", "Live Casino"),
      ("Live Dragon Tiger", "live-dragon-tiger", "Live Casino"),
      ("Live Game Show", "live-game-show", "Live Casino"),
      ("Live Sic Bo", "live-sic-bo", "Live Casino"),
      ("Live Andar Bahar", "live-andar-bahar", "Live Casino"),
      ("Live Teen Patti", "live-teen-patti", "Live Casino"),
      ("Live Poker", "live-poker", "Live Casino"),
      ("Penalty Shootout", "penalty-shootout", "Arcade"),
      ("Penalty Duel", "penalty-duel", "Arcade"),
      ("Scratch Card", "scratch-card", "Arcade"),
      ("Spin Wheel", "spin-wheel", "Arcade"),
      ("Lucky Box", "lucky-box", "Arcade"),
      ("Treasure Box", "treasure-box", "Arcade"),
      ("Fishing Demo", "fishing-demo", "Arcade"),
      ("Race Demo", "race-demo", "Arcade"),
    ]
    with get_conn() as conn:
        with conn.cursor() as cur:
            for name, slug, category in games:
                cur.execute("""
                  INSERT INTO games(name,slug,category)
                  VALUES(%s,%s,%s)
                  ON CONFLICT(slug) DO NOTHING
                """, (name, slug, category))
            cur.execute("""
              INSERT INTO settings(key,value) VALUES
              ('banner_text', 'এটি একটি শিক্ষামূলক ডেমো ওয়েবসাইট। এখানে কোনো বাস্তব টাকা/উত্তোলন নেই।'),
              ('banner_visible', 'true'),
              ('banner_color', '#facc15'),
              ('support_whatsapp', '#'),
              ('support_telegram', '#'),
              ('support_livechat', '#'),
              ('referral_bonus', '1000'),
              ('email_verification_enabled', 'true'),
              ('forgot_password_enabled', 'true'),
              ('registration_enabled', 'true'),
              ('smtp_enabled', 'false'),
              ('site_name', 'Educational Webbing Site'),
              ('site_logo_text', 'E'),
              ('splash_enabled', 'true'),
              ('splash_title', 'Educational Webbing Site'),
              ('splash_subtitle', 'Loading secure lobby...'),
              ('game_loading_enabled', 'true'),
              ('game_loading_title', 'Preparing Game'),
              ('game_loading_message', 'Please wait while the game is loading. Read the instructions before playing.'),
              ('game_instruction_image', '')
              ON CONFLICT(key) DO NOTHING
            """)
            cur.execute("""
              UPDATE users SET referral_code = 'HP' || id || UPPER(SUBSTRING(MD5(email || id::text) FROM 1 FOR 5))
              WHERE referral_code IS NULL
            """)
            conn.commit()
