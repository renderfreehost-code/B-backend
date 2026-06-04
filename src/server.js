import "dotenv/config";
import express from "express";
import cors from "cors";
import { query } from "./db.js";
import { hashPassword, verifyPassword, createToken, requireAuth, requireAdmin } from "./auth.js";
import { playDemoGame, gameFamily } from "./engine.js";

const app=express();
const PORT=process.env.PORT||8000;
const clients=new Set();

const origins=(process.env.CORS_ORIGINS||"*").split(",").map(s=>s.trim()).filter(Boolean);
app.use(cors({origin:(origin,cb)=>!origin||origins.includes("*")||origins.includes(origin)?cb(null,true):cb(new Error("CORS blocked")),credentials:true}));
app.use(express.json({limit:"1mb"}));

function emit(event,payload){
  const data=`event: ${event}\ndata: ${JSON.stringify(payload)}\n\n`;
  for(const res of clients){try{res.write(data)}catch{}}
}
function safeInt(v,d=0){const n=Number(v);return Number.isFinite(n)?n:d}

app.get("/",(req,res)=>res.json({status:"ok",name:"Educational Webbing Hitech API",version:"3.0"}));
app.get("/health",(req,res)=>res.json({status:"ok",clients:clients.size}));
app.get("/events",(req,res)=>{
  res.writeHead(200,{"Content-Type":"text/event-stream","Cache-Control":"no-cache","Connection":"keep-alive","Access-Control-Allow-Origin":"*"});
  res.write(`event: connected\ndata: {"ok":true}\n\n`);
  clients.add(res); req.on("close",()=>clients.delete(res));
});

async function init(){
  await query(`create table if not exists users(
    id bigserial primary key, name text not null, email text unique not null, password_hash text not null,
    balance numeric(12,2) default 1000, is_admin boolean default false, is_banned boolean default false,
    avatar text, created_at timestamptz default now()
  )`);
  await query(`alter table users add column if not exists is_banned boolean default false`);
  await query(`alter table users add column if not exists avatar text`);
  await query(`create table if not exists games(
    id bigserial primary key, name text not null, slug text unique not null, category text not null,
    min_bet numeric(12,2) default 10, max_bet numeric(12,2) default 10000, win_chance numeric(5,2) default 50,
    payout_min numeric(8,2) default 1.1, payout_max numeric(8,2) default 2.0,
    visible boolean default true, status text default 'active', engine_family text default 'number',
    animation_key text, maintenance_message text, display_order int default 999, template_no int default 999, featured boolean default false, play_mode text default 'demo_engine', client_url text, created_at timestamptz default now()
  )`);
  await query(`alter table games add column if not exists engine_family text default 'number'`);
  await query(`alter table games add column if not exists animation_key text`);
  await query(`alter table games add column if not exists maintenance_message text`);
  await query(`alter table games add column if not exists display_order int default 999`);
  await query(`alter table games add column if not exists template_no int default 999`);
  await query(`alter table games add column if not exists featured boolean default false`);
  await query(`alter table games add column if not exists play_mode text default 'demo_engine'`);
  await query(`alter table games add column if not exists client_url text`);
  await query(`create table if not exists bets(
    id bigserial primary key, user_id bigint references users(id), game_id bigint references games(id),
    amount numeric(12,2) not null, result text not null, multiplier numeric(8,2) default 0,
    payout numeric(12,2) default 0, engine_details jsonb default '{}', created_at timestamptz default now()
  )`);
  await query(`create table if not exists coin_ledger(
    id bigserial primary key, user_id bigint references users(id), type text not null, amount numeric(12,2) not null,
    balance_after numeric(12,2) not null, note text, created_at timestamptz default now()
  )`);
  await query(`create index if not exists idx_bets_user_created on bets(user_id, created_at desc)`);
  await query(`create index if not exists idx_bets_created on bets(created_at desc)`);
  await query(`create index if not exists idx_ledger_user_created on coin_ledger(user_id, created_at desc)`);
  await query(`create index if not exists idx_games_active on games(status,visible)`);
  await query(`create index if not exists idx_games_order on games(display_order,template_no,id)`);

  const adminEmail=(process.env.ADMIN_EMAIL||"admin@example.com").toLowerCase();
  const adminPass=process.env.ADMIN_PASSWORD||"Admin123456";
  const existing=await query("select id from users where email=$1",[adminEmail]);
  if(!existing.rows[0]) await query("insert into users(name,email,password_hash,balance,is_admin) values($1,$2,$3,$4,true)",["Admin",adminEmail,await hashPassword(adminPass),0]);

  const seed=[
    ["Aviator","aviator","Crash",45,1.2,8],["Rocket Crash","rocket-crash","Crash",43,1.2,10],["Galaxy Flight","galaxy-flight","Crash",44,1.2,9],
    ["Mines","mines","Number",52,1.2,4],["Tower","tower","Number",50,1.2,5],["Dice","dice","Number",55,1.1,2.5],["Plinko","plinko","Number",53,1.1,5],["Coin Flip","coin-flip","Number",49,1.9,2],["Keno","keno","Number",50,1.3,4],
    ["Limbo","limbo","Number",50,1.2,6],
    ["Roulette","roulette","Casino",48,1.5,3],["European Roulette","european-roulette","Casino",48,1.5,3],["Spin Wheel","spin-wheel","Arcade",50,1.2,4],
    ["Blackjack","blackjack","Cards",49,1.4,2.5],["Baccarat","baccarat","Cards",50,1.3,2.2],["Poker","poker","Cards",45,1.5,5],["Dragon Tiger","dragon-tiger","Cards",49,1.4,2.3],
    ["Classic Slot","classic-slot","Slots",42,1.3,8],["Fruit Slot","fruit-slot","Slots",43,1.3,7],["Mega Slot","mega-slot","Slots",40,1.5,12],
    ["Cricket","cricket","Sports",50,1.4,3],["Football","football","Sports",50,1.4,3],["Basketball","basketball","Sports",50,1.4,3],["Tennis","tennis","Sports",50,1.4,3],
    ["Live Roulette","live-roulette","Live Casino",48,1.4,3],["Live Blackjack","live-blackjack","Live Casino",49,1.4,2.5],["Live Baccarat","live-baccarat","Live Casino",49,1.4,2.5],
    ["Penalty Shootout","penalty-shootout","Arcade",50,1.4,4],["Race Demo","race-demo","Arcade",48,1.4,5],["Scratch Card","scratch-card","Arcade",45,1.4,7],
    ["Tai Xiu (High-Low Dice)","casino-master-tai-xiu","Casino Master",50,1.1,3],
    ["Bau Cua (Animal Dice)","casino-master-bau-cua","Casino Master",50,1.1,3],
    ["Mini Poker Slot","casino-master-mini-poker-slot","Casino Master",45,1.2,6],
    ["Lucky Wheel","casino-master-lucky-wheel","Casino Master",48,1.2,5],
    ["High-Low Card","casino-master-high-low-card","Casino Master",50,1.2,4],
    ["Fishing Game","casino-master-fishing","Casino Master",48,1.2,5],
    ["Sam Loc","casino-master-sam-loc","Casino Master",50,1.2,4],
    ["Ba Cay (Three Cards)","casino-master-ba-cay","Casino Master",50,1.2,4],
    ["Xi Dach (Vietnamese Blackjack)","casino-master-xi-dach","Casino Master",49,1.2,4],
    ["Mau Binh (Chinese Poker)","casino-master-mau-binh","Casino Master",48,1.2,5],
    ["Tien Len Mien Nam","casino-master-tien-len-mien-nam","Casino Master",50,1.2,4],
    ["Lieng","casino-master-lieng","Casino Master",49,1.2,4],
    ["Xi To (Poker Variant)","casino-master-xi-to","Casino Master",48,1.2,5],
    ["Poker","casino-master-poker","Casino Master",48,1.2,5],
    ["Blackjack","casino-master-blackjack","Casino Master",49,1.2,4],
    ["Xoc Dia","casino-master-xoc-dia","Casino Master",49,1.2,4],
    ["Chinese Chess","casino-master-chinese-chess","Casino Master",50,1.2,3],
    ["Dark Chess","casino-master-dark-chess","Casino Master",50,1.2,3],
    ["Caro (Gomoku)","casino-master-caro","Casino Master",50,1.2,3],
    ["Slot Treasure","casino-master-slot-treasure","Casino Master",44,1.2,8],
    ["Slot Secret Agent","casino-master-slot-secret-agent","Casino Master",44,1.2,8],
    ["Slot Avengers","casino-master-slot-avengers","Casino Master",44,1.2,8],
    ["Slot Kingdom","casino-master-slot-kingdom","Casino Master",44,1.2,8],
    ["Tien Len Solo","casino-master-tien-len-solo","Casino Master",50,1.2,4],
    ["Sam Loc Solo","casino-master-sam-loc-solo","Casino Master",50,1.2,4],
    ["Bai Cao","casino-master-bai-cao","Casino Master",50,1.2,4],
    ["Mau Binh Ace","casino-master-mau-binh-ace","Casino Master",48,1.2,5],
    ["Diamond Mini Game","casino-master-diamond-mini","Casino Master",47,1.2,5]
  ];
  for(const [name,slug,category,win,min,max] of seed){
    const temp={name,slug,category}; const fam=gameFamily(temp);
    await query(`insert into games(name,slug,category,win_chance,payout_min,payout_max,engine_family,animation_key)
      values($1,$2,$3,$4,$5,$6,$7,$8)
      on conflict(slug) do update set engine_family=excluded.engine_family, animation_key=excluded.animation_key`,
      [name,slug,category,win,min,max,fam,slug]);
  }

  const originalClients=[
    [1,1,'dice','/game-clients/dice/index.html'],
    [2,2,'mines','/game-clients/mines/index.html'],
    [3,3,'plinko','/game-clients/plinko/index.html'],
    [4,4,'limbo','/game-clients/limbo/index.html'],
    [5,5,'spin-wheel','/game-clients/spin-wheel/index.html'],
    [6,6,'aviator','/game-clients/aviator/index.html']
  ];
  for(const [displayOrder,templateNo,slug,clientUrl] of originalClients){
    await query(`update games set category='Fully Playable Original UI', display_order=$1, template_no=$2, featured=true, play_mode='original_client', client_url=$3 where slug=$4`,[displayOrder,templateNo,clientUrl,slug]);
  }
  await query(`update games set display_order=100+id, template_no=100+id, play_mode=coalesce(play_mode,'demo_engine') where play_mode is null or play_mode <> 'original_client'`);
}

app.post("/auth/register",async(req,res)=>{
  try{
    const {name,email,password}=req.body;
    if(!email||!password) return res.status(400).json({error:"Email and password required"});
    const {rows}=await query("insert into users(name,email,password_hash,balance) values($1,$2,$3,1000) returning id,name,email,balance,is_admin,is_banned,avatar,created_at",[name||"User",String(email).toLowerCase(),await hashPassword(password)]);
    const user=rows[0]; emit("stats",{type:"user_registered"}); res.json({token:createToken(user),user});
  }catch(e){res.status(400).json({error:"Email already exists or invalid data"});}
});
app.post("/auth/login",async(req,res)=>{
  const {email,password}=req.body; const {rows}=await query("select * from users where email=$1",[String(email||"").toLowerCase()]);
  const user=rows[0]; if(!user||!(await verifyPassword(password,user.password_hash))) return res.status(401).json({error:"Invalid email or password"});
  if(user.is_banned) return res.status(403).json({error:"Account banned"}); delete user.password_hash; res.json({token:createToken(user),user});
});
app.get("/me",requireAuth,(req,res)=>res.json(req.user));
app.get("/games",async(req,res)=>{const {rows}=await query("select * from games where visible=true and status='active' order by display_order asc, template_no asc, id asc");res.json(rows)});
app.get("/bets/my",requireAuth,async(req,res)=>{const {rows}=await query(`select b.*,g.name game_name,g.category from bets b join games g on g.id=b.game_id where b.user_id=$1 order by b.id desc limit 100`,[req.user.id]);res.json(rows)});
app.get("/ledger/my",requireAuth,async(req,res)=>{const {rows}=await query("select * from coin_ledger where user_id=$1 order by id desc limit 100",[req.user.id]);res.json(rows)});

app.post("/bets",requireAuth,async(req,res)=>{
  const amount=safeInt(req.body.amount), gameId=safeInt(req.body.game_id);
  if(amount<=0) return res.status(400).json({error:"Invalid amount"});
  const gameRes=await query("select * from games where id=$1 and visible=true and status='active'",[gameId]);
  const game=gameRes.rows[0]; if(!game) return res.status(404).json({error:"Game disabled or not found"});
  if(amount<Number(game.min_bet)||amount>Number(game.max_bet)) return res.status(400).json({error:"Bet amount out of range"});
  if(Number(req.user.balance)<amount) return res.status(400).json({error:"Insufficient demo coins"});
  const engine=playDemoGame(game,amount), newBalance=Number(req.user.balance)-amount+engine.payout;
  await query("update users set balance=$1 where id=$2",[newBalance,req.user.id]);
  const bet=await query("insert into bets(user_id,game_id,amount,result,multiplier,payout,engine_details) values($1,$2,$3,$4,$5,$6,$7) returning *",[req.user.id,game.id,amount,engine.result,engine.multiplier,engine.payout,engine.details]);
  await query("insert into coin_ledger(user_id,type,amount,balance_after,note) values($1,$2,$3,$4,$5)",[req.user.id,engine.result==="win"?"bet_win":"bet_loss",engine.result==="win"?engine.payout:-amount,newBalance,game.name]);
  const payload={bet:{...bet.rows[0],game_name:game.name,category:game.category},engine:{details:engine.details},new_balance:newBalance};
  emit("bet",payload); emit("stats",{type:"bet"}); res.json(payload);
});

app.get("/admin/stats",requireAuth,requireAdmin,async(req,res)=>{
  const users=await query("select count(*)::int c from users"), activeUsers=await query("select count(*)::int c from users where is_banned=false");
  const games=await query("select count(*)::int c from games"), enabledGames=await query("select count(*)::int c from games where visible=true and status='active'");
  const bets=await query("select count(*)::int c from bets"), coins=await query("select coalesce(sum(balance),0)::float c from users");
  const recent=await query(`select b.id,b.amount,b.result,b.payout,b.created_at,u.email,g.name game_name from bets b join users u on u.id=b.user_id join games g on g.id=b.game_id order by b.id desc limit 10`);
  res.json({users:users.rows[0].c,activeUsers:activeUsers.rows[0].c,games:games.rows[0].c,enabledGames:enabledGames.rows[0].c,bets:bets.rows[0].c,coins:coins.rows[0].c,liveClients:clients.size,recentBets:recent.rows});
});
app.get("/admin/users",requireAuth,requireAdmin,async(req,res)=>{const q=`%${String(req.query.q||"").toLowerCase()}%`;const {rows}=await query("select id,name,email,balance,is_admin,is_banned,created_at from users where lower(email) like $1 or lower(name) like $1 order by id desc limit 250",[q]);res.json(rows)});
app.patch("/admin/users/:id",requireAuth,requireAdmin,async(req,res)=>{const id=safeInt(req.params.id);const cur=await query("select * from users where id=$1",[id]);if(!cur.rows[0])return res.status(404).json({error:"User not found"});const next={...cur.rows[0],...req.body};const {rows}=await query("update users set is_banned=$1,is_admin=$2 where id=$3 returning id,name,email,balance,is_admin,is_banned,created_at",[!!next.is_banned,!!next.is_admin,id]);emit("stats",{type:"user_updated"});res.json(rows[0])});
app.post("/admin/coins",requireAuth,requireAdmin,async(req,res)=>{const {email,amount,reason}=req.body;const u=await query("select * from users where email=$1",[String(email||"").toLowerCase()]);if(!u.rows[0])return res.status(404).json({error:"User not found"});const newBalance=Number(u.rows[0].balance)+Number(amount);await query("update users set balance=$1 where id=$2",[newBalance,u.rows[0].id]);await query("insert into coin_ledger(user_id,type,amount,balance_after,note) values($1,'admin_adjust',$2,$3,$4)",[u.rows[0].id,Number(amount),newBalance,reason||"admin_update"]);emit("stats",{type:"coin_update"});res.json({ok:true,new_balance:newBalance})});
app.get("/admin/games/all",requireAuth,requireAdmin,async(req,res)=>{const {rows}=await query("select * from games order by display_order asc, template_no asc, id asc");res.json(rows)});
app.patch("/admin/games/:id",requireAuth,requireAdmin,async(req,res)=>{const id=safeInt(req.params.id);const cur=await query("select * from games where id=$1",[id]);if(!cur.rows[0])return res.status(404).json({error:"Game not found"});const n={...cur.rows[0],...req.body};n.engine_family=gameFamily(n);const {rows}=await query(`update games set name=$1,category=$2,min_bet=$3,max_bet=$4,win_chance=$5,payout_min=$6,payout_max=$7,visible=$8,status=$9,engine_family=$10,animation_key=$11,display_order=$12,template_no=$13,featured=$14,play_mode=$15,client_url=$16 where id=$17 returning *`,[n.name,n.category,n.min_bet,n.max_bet,n.win_chance,n.payout_min,n.payout_max,!!n.visible,n.status,n.engine_family,n.animation_key||n.slug,safeInt(n.display_order,999),safeInt(n.template_no,999),!!n.featured,n.play_mode||'demo_engine',n.client_url||null,id]);emit("stats",{type:"game_updated"});res.json(rows[0])});
app.get("/admin/bets",requireAuth,requireAdmin,async(req,res)=>{const {rows}=await query(`select b.*,u.email,g.name game_name,g.category from bets b join users u on u.id=b.user_id join games g on g.id=b.game_id order by b.id desc limit 350`);res.json(rows)});
app.get("/admin/ledger",requireAuth,requireAdmin,async(req,res)=>{const {rows}=await query(`select l.*,u.email from coin_ledger l join users u on u.id=l.user_id order by l.id desc limit 350`);res.json(rows)});

init().then(()=>app.listen(PORT,()=>console.log(`Server running on ${PORT}`))).catch(e=>{console.error(e);process.exit(1)});
