import os, random, secrets, string, smtplib
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from .database import init_db, seed_games, get_conn
from .auth import hash_password, verify_password, create_token, current_user, admin_user
from .game_engines import ENGINE_VERSION, calculate_demo_game_result

app = FastAPI(title="Awareness Simulator API")

origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def make_referral_code(user_id: int, email: str) -> str:
    safe = "".join(ch for ch in email.split("@")[0].upper() if ch.isalnum())[:4] or "USER"
    return f"HP{user_id}{safe}{secrets.token_hex(2).upper()}"

def demo_rng_roll_1_100() -> int:
    # Cryptographic random source for demo simulator. Good for concurrency and avoids predictable pseudo-random sequences.
    return secrets.randbelow(100) + 1

def demo_rng_float(min_value: float, max_value: float) -> float:
    if max_value <= min_value:
        return round(min_value, 2)
    # 10,000 steps gives smooth demo multipliers without using predictable random.random().
    step = secrets.randbelow(10001) / 10000
    return round(min_value + ((max_value - min_value) * step), 2)

def generate_email_code() -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(6))

def send_email_code(to_email: str, code: str, purpose: str):
    # SMTP is optional. If SMTP_ENABLED=false, backend still returns success for setup/testing.
    if os.getenv("SMTP_ENABLED", "false").lower() != "true":
        print(f"[DEV EMAIL CODE] {purpose} code for {to_email}: {code}")
        return

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM", user or "no-reply@example.com")
    if not all([host, user, password]):
        print(f"[SMTP MISSING] {purpose} code for {to_email}: {code}")
        return

    subject = "Your verification code"
    body = f"Your {purpose} code is: {code}\n\nThis code will expire soon."
    msg = f"From: {from_email}\r\nTo: {to_email}\r\nSubject: {subject}\r\n\r\n{body}"

    with smtplib.SMTP(host, port, timeout=10) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(from_email, [to_email], msg.encode("utf-8"))


class RegisterIn(BaseModel):
    name: str
    email: EmailStr
    password: str
    referral_code: str | None = None

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class VerifyEmailIn(BaseModel):
    email: EmailStr
    code: str

class ResendCodeIn(BaseModel):
    email: EmailStr

class ForgotPasswordIn(BaseModel):
    email: EmailStr

class ResetPasswordIn(BaseModel):
    email: EmailStr
    code: str
    new_password: str

class DepositIn(BaseModel):
    amount: int
    note: str = ""

class CoinGrantIn(BaseModel):
    amount: int
    note: str = "Admin demo coin grant"

class BetIn(BaseModel):
    game_id: int
    amount: int

class GameUpdate(BaseModel):
    status: str
    min_bet: int
    max_bet: int
    risk_level: str
    win_chance: int
    payout_min: float
    payout_max: float
    result_mode: str
    visible: bool

class BannerUpdate(BaseModel):
    banner_text: str
    banner_visible: bool
    banner_color: str

class SiteBrandUpdate(BaseModel):
    site_name: str = "Educational Webbing Site"
    site_logo_text: str = "E"
    splash_enabled: bool = True
    splash_title: str = "Educational Webbing Site"
    splash_subtitle: str = "Loading secure lobby..."
    game_loading_enabled: bool = True
    game_loading_title: str = "Preparing Game"
    game_loading_message: str = "Please wait while the game is loading. Read the instructions before playing."
    game_instruction_image: str = ""

class MessageIn(BaseModel):
    title: str
    body: str
    user_id: int | None = None

@app.on_event("startup")
def startup():
    init_db()
    seed_games()
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    if admin_email and admin_password:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM users WHERE email=%s", (admin_email.lower(),))
                if not cur.fetchone():
                    cur.execute("INSERT INTO users(name,email,password_hash,balance,is_admin) VALUES(%s,%s,%s,%s,%s) RETURNING id,email",
                                ("Admin", admin_email.lower(), hash_password(admin_password), 0, True))
                    admin = cur.fetchone()
                    cur.execute("UPDATE users SET referral_code=%s WHERE id=%s", (make_referral_code(admin["id"], admin["email"]), admin["id"]))
                    conn.commit()

@app.get("/health")
def health():
    return {"ok": True, "mode": "educational-demo-only"}

@app.post("/auth/register")
def register(data: RegisterIn):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM settings WHERE key='registration_enabled'")
            reg = cur.fetchone()
            if reg and reg["value"] == "false":
                raise HTTPException(status_code=403, detail="Registration is disabled")

            try:
                referred_by = None
                if data.referral_code:
                    cur.execute("SELECT id FROM users WHERE referral_code=%s", (data.referral_code.strip(),))
                    ref = cur.fetchone()
                    if ref:
                        referred_by = ref["id"]

                cur.execute("""INSERT INTO users(name,email,password_hash,balance,is_admin,referred_by_user_id,email_verified)
                               VALUES(%s,%s,%s,%s,%s,%s,%s)
                               RETURNING id,name,email,balance,is_admin,referral_code,referred_by_user_id,email_verified,created_at""",
                            (data.name, data.email.lower(), hash_password(data.password), 10000, False, referred_by, False))
                user = cur.fetchone()
                code = make_referral_code(user["id"], user["email"])
                cur.execute("UPDATE users SET referral_code=%s WHERE id=%s RETURNING id,name,email,balance,is_admin,referral_code,referred_by_user_id,email_verified,created_at",
                            (code, user["id"]))
                user = cur.fetchone()

                verify_code = generate_email_code()
                cur.execute("""INSERT INTO email_verifications(user_id,email,code,purpose,expires_at)
                               VALUES(%s,%s,%s,'signup',NOW() + INTERVAL '10 minutes')""",
                            (user["id"], user["email"], verify_code))

                if referred_by:
                    cur.execute("SELECT value FROM settings WHERE key='referral_bonus'")
                    bonus_row = cur.fetchone()
                    bonus = int(bonus_row["value"]) if bonus_row else 1000
                    cur.execute("SELECT balance FROM users WHERE id=%s FOR UPDATE", (referred_by,))
                    ref_user = cur.fetchone()
                    if ref_user:
                        before = ref_user["balance"]
                        after = before + bonus
                        cur.execute("UPDATE users SET balance=%s, referral_bonus_earned=referral_bonus_earned+%s WHERE id=%s",
                                    (after, bonus, referred_by))
                        cur.execute("""INSERT INTO coin_ledger(user_id,type,amount,balance_before,balance_after,note)
                                       VALUES(%s,'referral_bonus',%s,%s,%s,%s)""",
                                    (referred_by, bonus, before, after, f"Referral bonus from user {user['id']}"))
                        cur.execute("""INSERT INTO referral_rewards(referrer_user_id,referred_user_id,amount)
                                       VALUES(%s,%s,%s) ON CONFLICT DO NOTHING""",
                                    (referred_by, user["id"], bonus))
                conn.commit()
                send_email_code(user["email"], verify_code, "signup verification")
            except Exception as e:
                conn.rollback()
                raise HTTPException(status_code=400, detail="Email already exists or invalid referral")

    return {"token": create_token(user), "user": user, "verify_required": True}

@app.post("/auth/login")
def login(data: LoginIn):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email=%s", (data.email.lower(),))
            user = cur.fetchone()
            cur.execute("SELECT value FROM settings WHERE key='email_verification_enabled'")
            ev = cur.fetchone()
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid login")
    if ev and ev["value"] == "true" and not user.get("email_verified") and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Email verification required")
    safe = {k: user[k] for k in ["id","name","email","balance","is_admin","referral_code","email_verified","created_at"] if k in user}
    return {"token": create_token(user), "user": safe}

@app.post("/auth/verify-email")
def verify_email(data: VerifyEmailIn):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT ev.*, u.id AS uid FROM email_verifications ev
                           JOIN users u ON u.id=ev.user_id
                           WHERE ev.email=%s AND ev.code=%s AND ev.purpose='signup'
                           AND ev.used=false AND ev.expires_at>NOW()
                           ORDER BY ev.id DESC LIMIT 1""", (data.email.lower(), data.code.strip()))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=400, detail="Invalid or expired code")
            cur.execute("UPDATE email_verifications SET used=true WHERE id=%s", (row["id"],))
            cur.execute("UPDATE users SET email_verified=true WHERE id=%s RETURNING id,name,email,balance,is_admin,referral_code,email_verified,created_at", (row["uid"],))
            user = cur.fetchone()
            conn.commit()
    return {"token": create_token(user), "user": user}

@app.post("/auth/resend-code")
def resend_code(data: ResendCodeIn):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id,email FROM users WHERE email=%s", (data.email.lower(),))
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            code = generate_email_code()
            cur.execute("""INSERT INTO email_verifications(user_id,email,code,purpose,expires_at)
                           VALUES(%s,%s,%s,'signup',NOW() + INTERVAL '10 minutes')""", (user["id"], user["email"], code))
            conn.commit()
    send_email_code(user["email"], code, "signup verification")
    return {"ok": True}

@app.post("/auth/forgot-password")
def forgot_password(data: ForgotPasswordIn):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM settings WHERE key='forgot_password_enabled'")
            fp = cur.fetchone()
            if fp and fp["value"] == "false":
                raise HTTPException(status_code=403, detail="Forgot password is disabled")
            cur.execute("SELECT id,email FROM users WHERE email=%s", (data.email.lower(),))
            user = cur.fetchone()
            if not user:
                return {"ok": True}
            code = generate_email_code()
            cur.execute("""INSERT INTO email_verifications(user_id,email,code,purpose,expires_at)
                           VALUES(%s,%s,%s,'reset',NOW() + INTERVAL '10 minutes')""", (user["id"], user["email"], code))
            conn.commit()
    send_email_code(data.email.lower(), code, "password reset")
    return {"ok": True}

@app.post("/auth/reset-password")
def reset_password(data: ResetPasswordIn):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT ev.*, u.id AS uid FROM email_verifications ev
                           JOIN users u ON u.id=ev.user_id
                           WHERE ev.email=%s AND ev.code=%s AND ev.purpose='reset'
                           AND ev.used=false AND ev.expires_at>NOW()
                           ORDER BY ev.id DESC LIMIT 1""", (data.email.lower(), data.code.strip()))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=400, detail="Invalid or expired code")
            cur.execute("UPDATE email_verifications SET used=true WHERE id=%s", (row["id"],))
            cur.execute("UPDATE users SET password_hash=%s WHERE id=%s", (hash_password(data.new_password), row["uid"]))
            conn.commit()
    return {"ok": True}

@app.get("/me")
def me(user=Depends(current_user)):
    return user

@app.get("/settings/public")
def public_settings():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key,value FROM settings")
            rows = cur.fetchall()
    return {r["key"]: r["value"] for r in rows}

@app.get("/games")
def games():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM games WHERE visible=true ORDER BY category,name")
            return cur.fetchall()

@app.post("/deposits")
def create_deposit(data: DepositIn, user=Depends(current_user)):
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO deposit_requests(user_id,amount,note) VALUES(%s,%s,%s) RETURNING *",
                        (user["id"], data.amount, data.note))
            row = cur.fetchone()
            conn.commit()
    return row

@app.get("/deposits/my")
def my_deposits(user=Depends(current_user)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM deposit_requests WHERE user_id=%s ORDER BY id DESC", (user["id"],))
            return cur.fetchall()

@app.post("/bets")
def place_bet(data: BetIn, user=Depends(current_user)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM games WHERE id=%s AND visible=true", (data.game_id,))
            game = cur.fetchone()
            if not game:
                raise HTTPException(status_code=404, detail="Game not found")
            if game["status"] == "maintenance":
                raise HTTPException(status_code=409, detail="এই গেমটি এখন মেইনটেন্যান্স চলছে")
            if game["status"] != "active":
                raise HTTPException(status_code=409, detail="এই গেমটি বর্তমানে বন্ধ আছে")
            if data.amount < game["min_bet"] or data.amount > game["max_bet"]:
                raise HTTPException(status_code=400, detail=f"Bet must be {game['min_bet']} to {game['max_bet']}")
            cur.execute("SELECT balance FROM users WHERE id=%s FOR UPDATE", (user["id"],))
            bal = cur.fetchone()["balance"]
            if bal < data.amount:
                raise HTTPException(status_code=400, detail="Insufficient balance")

            # Separate per-game educational demo engines.
            # Existing API flow is preserved: validate -> lock balance -> calculate result -> update balance -> save bet/ledger.
            engine_result = calculate_demo_game_result(game, data.amount)
            payout = engine_result.payout
            multiplier = engine_result.multiplier
            rng_roll = engine_result.rng_roll
            new_balance = bal - data.amount + payout

            cur.execute("UPDATE users SET balance=%s WHERE id=%s", (new_balance, user["id"]))
            cur.execute("""INSERT INTO bets(user_id,game_id,amount,result,payout,multiplier,balance_before,balance_after,rng_roll)
                           VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                        (user["id"], game["id"], data.amount, engine_result.result, payout, multiplier, bal, new_balance, rng_roll))
            bet = cur.fetchone()
            cur.execute("""INSERT INTO coin_ledger(user_id,type,amount,balance_before,balance_after,note)
                           VALUES(%s,'bet_result',%s,%s,%s,%s)""",
                        (user["id"], payout - data.amount, bal, new_balance, f"{game['name']} {bet['result']} via {engine_result.engine_name}"))
            conn.commit()
    return {
        "bet": bet,
        "coin_wallet": {
            "balance_before": bal,
            "bet_amount": data.amount,
            "payout": payout,
            "net_change": payout - data.amount,
            "balance_after": new_balance,
            "outcome": engine_result.result,
        },
        "new_balance": new_balance,
        "engine": {
            "name": engine_result.engine_name,
            "type": engine_result.engine_type,
            "version": ENGINE_VERSION,
            "details": engine_result.details,
        },
        "educational_note": "Demo coins only. No real money, deposit, withdrawal, or real gambling service."
    }

@app.get("/bets/my")
def my_bets(user=Depends(current_user)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT b.*, g.name AS game_name FROM bets b JOIN games g ON g.id=b.game_id
                           WHERE b.user_id=%s ORDER BY b.id DESC LIMIT 100""", (user["id"],))
            return cur.fetchall()

@app.get("/messages/my")
def my_messages(user=Depends(current_user)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM messages WHERE user_id=%s ORDER BY id DESC", (user["id"],))
            return cur.fetchall()

@app.get("/referrals/my")
def my_referrals(user=Depends(current_user)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT id,name,email,referral_code,referral_bonus_earned FROM users WHERE id=%s""", (user["id"],))
            me = cur.fetchone()
            cur.execute("""SELECT u.id,u.name,u.email,r.amount,r.created_at
                           FROM referral_rewards r
                           JOIN users u ON u.id=r.referred_user_id
                           WHERE r.referrer_user_id=%s
                           ORDER BY r.created_at DESC""", (user["id"],))
            refs = cur.fetchall()
    return {"me": me, "referrals": refs}

@app.get("/ledger/my")
def my_ledger(user=Depends(current_user)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT * FROM coin_ledger WHERE user_id=%s ORDER BY id DESC LIMIT 100""", (user["id"],))
            return cur.fetchall()

# Admin endpoints
@app.get("/admin/stats")
def admin_stats(user=Depends(current_user)):
    admin_user(user)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total_users FROM users")
            users = cur.fetchone()["total_users"]
            cur.execute("SELECT COUNT(*) AS pending FROM deposit_requests WHERE status='processing'")
            pending = cur.fetchone()["pending"]
            cur.execute("SELECT COUNT(*) AS total_bets FROM bets")
            bets = cur.fetchone()["total_bets"]
            cur.execute("SELECT COALESCE(SUM(balance),0) AS points FROM users")
            points = cur.fetchone()["points"]
    return {"total_users": users, "pending_deposits": pending, "total_bets": bets, "total_points": points}

@app.get("/admin/users")
def admin_users(user=Depends(current_user)):
    admin_user(user)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id,name,email,balance,is_admin,created_at FROM users ORDER BY id DESC")
            return cur.fetchall()

@app.post("/admin/users/{target_user_id}/coins")
def admin_grant_demo_coins(target_user_id: int, data: CoinGrantIn, user=Depends(current_user)):
    admin_user(user)
    if data.amount == 0:
        raise HTTPException(status_code=400, detail="Amount cannot be zero")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id,balance FROM users WHERE id=%s FOR UPDATE", (target_user_id,))
            target = cur.fetchone()
            if not target:
                raise HTTPException(status_code=404, detail="User not found")
            before = target["balance"]
            after = before + data.amount
            if after < 0:
                raise HTTPException(status_code=400, detail="Coin balance cannot go below zero")
            cur.execute("UPDATE users SET balance=%s WHERE id=%s", (after, target_user_id))
            cur.execute("""INSERT INTO coin_ledger(user_id,type,amount,balance_before,balance_after,note)
                           VALUES(%s,'admin_coin_grant',%s,%s,%s,%s)""",
                        (target_user_id, data.amount, before, after, data.note or "Admin demo coin grant"))
            conn.commit()
    return {"ok": True, "user_id": target_user_id, "balance_before": before, "amount": data.amount, "balance_after": after}

@app.get("/admin/deposits")
def admin_deposits(user=Depends(current_user)):
    admin_user(user)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT d.*, u.name, u.email FROM deposit_requests d
                           JOIN users u ON u.id=d.user_id ORDER BY d.id DESC""")
            return cur.fetchall()

@app.post("/admin/deposits/{deposit_id}/approve")
def approve_deposit(deposit_id: int, user=Depends(current_user)):
    admin_user(user)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM deposit_requests WHERE id=%s FOR UPDATE", (deposit_id,))
            dep = cur.fetchone()
            if not dep or dep["status"] != "processing":
                raise HTTPException(status_code=400, detail="Invalid request")
            cur.execute("SELECT balance FROM users WHERE id=%s FOR UPDATE", (dep["user_id"],))
            u = cur.fetchone()
            before = u["balance"]
            after = before + dep["amount"]
            cur.execute("UPDATE users SET balance=%s WHERE id=%s", (after, dep["user_id"]))
            cur.execute("""INSERT INTO coin_ledger(user_id,type,amount,balance_before,balance_after,note)
                           VALUES(%s,'deposit_approved',%s,%s,%s,%s)""",
                        (dep["user_id"], dep["amount"], before, after, f"Deposit request #{deposit_id} approved"))
            cur.execute("UPDATE deposit_requests SET status='approved', reviewed_at=NOW() WHERE id=%s", (deposit_id,))
            conn.commit()
    return {"ok": True}

@app.post("/admin/deposits/{deposit_id}/reject")
def reject_deposit(deposit_id: int, user=Depends(current_user)):
    admin_user(user)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE deposit_requests SET status='rejected', reviewed_at=NOW() WHERE id=%s AND status='processing'", (deposit_id,))
            conn.commit()
    return {"ok": True}

@app.get("/admin/games")
def admin_games(user=Depends(current_user)):
    admin_user(user)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM games ORDER BY category,name")
            return cur.fetchall()

@app.put("/admin/games/{game_id}")
def update_game(game_id: int, data: GameUpdate, user=Depends(current_user)):
    admin_user(user)
    if not (1 <= data.win_chance <= 95):
        raise HTTPException(status_code=400, detail="Win chance must be 1-95")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE games SET status=%s,min_bet=%s,max_bet=%s,risk_level=%s,win_chance=%s,
                           payout_min=%s,payout_max=%s,result_mode=%s,visible=%s WHERE id=%s RETURNING *""",
                        (data.status, data.min_bet, data.max_bet, data.risk_level, data.win_chance,
                         data.payout_min, data.payout_max, data.result_mode, data.visible, game_id))
            row = cur.fetchone()
            conn.commit()
    return row

@app.put("/admin/banner")
def update_banner(data: BannerUpdate, user=Depends(current_user)):
    admin_user(user)
    values = {
        "banner_text": data.banner_text,
        "banner_visible": "true" if data.banner_visible else "false",
        "banner_color": data.banner_color
    }
    with get_conn() as conn:
        with conn.cursor() as cur:
            for k, v in values.items():
                cur.execute("INSERT INTO settings(key,value) VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value", (k, v))
            conn.commit()
    return {"ok": True}

@app.post("/admin/messages")
def send_message(data: MessageIn, user=Depends(current_user)):
    admin_user(user)
    with get_conn() as conn:
        with conn.cursor() as cur:
            if data.user_id:
                cur.execute("INSERT INTO messages(user_id,title,body) VALUES(%s,%s,%s)", (data.user_id, data.title, data.body))
            else:
                cur.execute("SELECT id FROM users WHERE is_admin=false")
                for row in cur.fetchall():
                    cur.execute("INSERT INTO messages(user_id,title,body) VALUES(%s,%s,%s)", (row["id"], data.title, data.body))
            conn.commit()
    return {"ok": True}


@app.put("/admin/site-branding")
def update_site_branding(data: SiteBrandUpdate, user=Depends(current_user)):
    admin_user(user)
    values = {
        "site_name": data.site_name,
        "site_logo_text": data.site_logo_text[:3],
        "splash_enabled": "true" if data.splash_enabled else "false",
        "splash_title": data.splash_title,
        "splash_subtitle": data.splash_subtitle,
        "game_loading_enabled": "true" if data.game_loading_enabled else "false",
        "game_loading_title": data.game_loading_title,
        "game_loading_message": data.game_loading_message,
        "game_instruction_image": data.game_instruction_image
    }
    with get_conn() as conn:
        with conn.cursor() as cur:
            for k, v in values.items():
                cur.execute("INSERT INTO settings(key,value) VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value", (k, v))
            conn.commit()
    return {"ok": True}

class SupportUpdate(BaseModel):
    support_whatsapp: str = "#"
    support_telegram: str = "#"
    support_livechat: str = "#"

@app.put("/admin/support")
def update_support(data: SupportUpdate, user=Depends(current_user)):
    admin_user(user)
    values = {
        "support_whatsapp": data.support_whatsapp,
        "support_telegram": data.support_telegram,
        "support_livechat": data.support_livechat
    }
    with get_conn() as conn:
        with conn.cursor() as cur:
            for k, v in values.items():
                cur.execute("INSERT INTO settings(key,value) VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value", (k, v))
            conn.commit()
    return {"ok": True}

class ReferralSettingsUpdate(BaseModel):
    referral_bonus: int

class AuthSettingsUpdate(BaseModel):
    email_verification_enabled: bool = True
    forgot_password_enabled: bool = True
    registration_enabled: bool = True
    smtp_enabled: bool = False

@app.put("/admin/referral-settings")
def update_referral_settings(data: ReferralSettingsUpdate, user=Depends(current_user)):
    admin_user(user)
    if data.referral_bonus < 0 or data.referral_bonus > 1000000:
        raise HTTPException(status_code=400, detail="Invalid referral bonus")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO settings(key,value) VALUES('referral_bonus',%s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value", (str(data.referral_bonus),))
            conn.commit()
    return {"ok": True}

@app.put("/admin/auth-settings")
def update_auth_settings(data: AuthSettingsUpdate, user=Depends(current_user)):
    admin_user(user)
    values = {
        "email_verification_enabled": "true" if data.email_verification_enabled else "false",
        "forgot_password_enabled": "true" if data.forgot_password_enabled else "false",
        "registration_enabled": "true" if data.registration_enabled else "false",
        "smtp_enabled": "true" if data.smtp_enabled else "false"
    }
    with get_conn() as conn:
        with conn.cursor() as cur:
            for k, v in values.items():
                cur.execute("INSERT INTO settings(key,value) VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value", (k, v))
            conn.commit()
    return {"ok": True}
