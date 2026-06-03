import "dotenv/config";
import express from "express";
import cors from "cors";
import { query } from "./db.js";
import { hashPassword, verifyPassword, createToken, requireAuth, requireAdmin } from "./auth.js";
import { playDemoGame } from "./engine.js";

const app = express();
const PORT = process.env.PORT || 8000;

const origins = (process.env.CORS_ORIGINS || "*").split(",").map(s=>s.trim()).filter(Boolean);
app.use(cors({origin:(origin, cb)=> !origin || origins.includes("*") || origins.includes(origin) ? cb(null,true) : cb(new Error("CORS blocked"))}));
app.use(express.json());

app.get("/", (req,res)=>res.json({status:"ok", message:"Node Express backend running"}));
app.get("/health", (req,res)=>res.json({status:"ok"}));

async function init(){
  await query(`create table if not exists users(
    id bigserial primary key,
    name text not null,
    email text unique not null,
    password_hash text not null,
    balance numeric(12,2) default 1000,
    is_admin boolean default false,
    created_at timestamptz default now()
  )`);
  await query(`create table if not exists games(
    id bigserial primary key,
    name text not null,
    slug text unique not null,
    category text not null,
    min_bet numeric(12,2) default 10,
    max_bet numeric(12,2) default 10000,
    win_chance numeric(5,2) default 50,
    payout_min numeric(8,2) default 1.1,
    payout_max numeric(8,2) default 2.0,
    visible boolean default true,
    status text default 'active'
  )`);
  await query(`create table if not exists bets(
    id bigserial primary key,
    user_id bigint references users(id),
    game_id bigint references games(id),
    amount numeric(12,2) not null,
    result text not null,
    multiplier numeric(8,2) default 0,
    payout numeric(12,2) default 0,
    engine_details jsonb default '{}',
    created_at timestamptz default now()
  )`);
  await query(`create table if not exists coin_ledger(
    id bigserial primary key,
    user_id bigint references users(id),
    type text not null,
    amount numeric(12,2) not null,
    balance_after numeric(12,2) not null,
    note text,
    created_at timestamptz default now()
  )`);

  const adminEmail = process.env.ADMIN_EMAIL || "admin@example.com";
  const adminPass = process.env.ADMIN_PASSWORD || "Admin123456";
  const existing = await query("select id from users where email=$1", [adminEmail.toLowerCase()]);
  if(!existing.rows[0]){
    await query("insert into users(name,email,password_hash,balance,is_admin) values($1,$2,$3,$4,true)", ["Admin", adminEmail.toLowerCase(), await hashPassword(adminPass), 0]);
  }

  const gameCount = await query("select count(*)::int as c from games");
  if(gameCount.rows[0].c === 0){
    const games = [
      ["Aviator","aviator","Crash"],["Rocket Crash","rocket-crash","Crash"],["Mines","mines","Number"],["Dice","dice","Number"],["Plinko","plinko","Number"],
      ["Roulette","roulette","Casino"],["Blackjack","blackjack","Cards"],["Poker","poker","Cards"],["Classic Slot","classic-slot","Slots"],["Fruit Slot","fruit-slot","Slots"],
      ["Cricket","cricket","Sports"],["Football","football","Sports"],["Live Roulette","live-roulette","Live Casino"],["Live Blackjack","live-blackjack","Live Casino"],
      ["Penalty Shootout","penalty-shootout","Arcade"],["Spin Wheel","spin-wheel","Arcade"],["Race Demo","race-demo","Arcade"]
    ];
    for(const [name,slug,cat] of games){
      await query("insert into games(name,slug,category,win_chance,payout_min,payout_max) values($1,$2,$3,$4,$5,$6) on conflict(slug) do nothing", [name,slug,cat, cat==="Crash"?45:55, 1.1, cat==="Crash"?8:3]);
    }
  }
}

app.post("/auth/register", async (req,res)=>{
  try{
    const {name,email,password} = req.body;
    if(!email || !password) return res.status(400).json({error:"Email and password required"});
    const pass = await hashPassword(password);
    const {rows} = await query("insert into users(name,email,password_hash,balance) values($1,$2,$3,1000) returning id,name,email,balance,is_admin", [name || "User", email.toLowerCase(), pass]);
    res.json({token:createToken(rows[0]), user:rows[0]});
  }catch(e){ res.status(400).json({error:"Email already exists or invalid data"}); }
});

app.post("/auth/login", async (req,res)=>{
  const {email,password} = req.body;
  const {rows} = await query("select * from users where email=$1", [String(email||"").toLowerCase()]);
  const user = rows[0];
  if(!user || !(await verifyPassword(password||"", user.password_hash))) return res.status(401).json({error:"Invalid email or password"});
  delete user.password_hash;
  res.json({token:createToken(user), user});
});

app.get("/me", requireAuth, (req,res)=>res.json(req.user));

app.get("/games", async (req,res)=>{
  const {rows} = await query("select * from games where visible=true and status='active' order by category,id");
  res.json(rows);
});

app.post("/bets", requireAuth, async (req,res)=>{
  const amount = Number(req.body.amount || 0);
  const gameId = Number(req.body.game_id);
  if(amount <= 0) return res.status(400).json({error:"Invalid amount"});
  const gameRes = await query("select * from games where id=$1 and visible=true and status='active'", [gameId]);
  const game = gameRes.rows[0];
  if(!game) return res.status(404).json({error:"Game not found"});
  if(amount < Number(game.min_bet) || amount > Number(game.max_bet)) return res.status(400).json({error:"Bet amount out of range"});
  if(Number(req.user.balance) < amount) return res.status(400).json({error:"Insufficient demo coins"});

  const engine = playDemoGame(game, amount);
  const newBalance = Number(req.user.balance) - amount + engine.payout;

  await query("update users set balance=$1 where id=$2", [newBalance, req.user.id]);
  const bet = await query("insert into bets(user_id,game_id,amount,result,multiplier,payout,engine_details) values($1,$2,$3,$4,$5,$6,$7) returning *", [req.user.id, game.id, amount, engine.result, engine.multiplier, engine.payout, engine.details]);
  await query("insert into coin_ledger(user_id,type,amount,balance_after,note) values($1,$2,$3,$4,$5)", [req.user.id, engine.result==="win"?"bet_win":"bet_loss", engine.result==="win"?engine.payout:-amount, newBalance, game.name]);

  res.json({bet:{...bet.rows[0], game_name:game.name}, engine:{details:engine.details}, new_balance:newBalance});
});

app.get("/bets/my", requireAuth, async (req,res)=>{
  const {rows} = await query(`select b.*, g.name as game_name from bets b join games g on g.id=b.game_id where b.user_id=$1 order by b.id desc limit 100`, [req.user.id]);
  res.json(rows);
});

app.get("/admin/stats", requireAuth, requireAdmin, async (req,res)=>{
  const users = await query("select count(*)::int c from users");
  const games = await query("select count(*)::int c from games");
  const bets = await query("select count(*)::int c from bets");
  const coins = await query("select coalesce(sum(balance),0)::float c from users");
  res.json({users:users.rows[0].c, games:games.rows[0].c, bets:bets.rows[0].c, coins:coins.rows[0].c});
});

app.post("/admin/coins", requireAuth, requireAdmin, async (req,res)=>{
  const {email, amount, reason} = req.body;
  const user = await query("select * from users where email=$1", [String(email||"").toLowerCase()]);
  if(!user.rows[0]) return res.status(404).json({error:"User not found"});
  const newBalance = Number(user.rows[0].balance) + Number(amount);
  await query("update users set balance=$1 where id=$2", [newBalance, user.rows[0].id]);
  await query("insert into coin_ledger(user_id,type,amount,balance_after,note) values($1,'admin_adjust',$2,$3,$4)", [user.rows[0].id, Number(amount), newBalance, reason || "admin_update"]);
  res.json({ok:true, new_balance:newBalance});
});

init().then(()=>app.listen(PORT, ()=>console.log(`Server running on ${PORT}`))).catch(err=>{console.error(err); process.exit(1);});
