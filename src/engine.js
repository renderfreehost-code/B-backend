import crypto from "crypto";

const clamp=(n,min,max)=>Math.max(min,Math.min(max,n));
const fixed=n=>Number(Number(n).toFixed(2));
const rand=(min,max)=>crypto.randomInt(min,max+1);
const pick=arr=>arr[rand(0,arr.length-1)];

export function gameFamily(game){
  const slug=String(game.slug||game.name||"").toLowerCase();
  const name=String(game.name||"").toLowerCase();
  const text=`${slug} ${name}`;
  const cat=String(game.category||"").toLowerCase();
  if(cat==="crash" || text.includes("aviator") || text.includes("rocket") || text.includes("flight")) return "crash";
  if(text.includes("mines") || text.includes("tower")) return "mines";
  if(text.includes("plinko")) return "plinko";
  if(text.includes("slot") || text.includes("diamond")) return "slots";
  if(text.includes("blackjack") || text.includes("xidach") || text.includes("xi-dach") || text.includes("baccarat") || text.includes("dragon")) return "blackjack";
  if(text.includes("poker") || text.includes("sam-loc") || text.includes("ba-cay") || text.includes("lieng") || text.includes("xi-to") || text.includes("tien-len") || text.includes("mau-binh") || text.includes("bai-cao")) return "cards";
  if(text.includes("chess") || text.includes("caro")) return "board";
  if(text.includes("fishing")) return "fishing";
  if(text.includes("roulette") || text.includes("wheel") || text.includes("tai-xiu") || text.includes("bau-cua") || text.includes("xoc-dia") || cat==="casino") return "roulette";
  if(cat==="cards") return "cards";
  if(cat==="slots") return "slots";
  if(cat==="sports" || text.includes("cricket") || text.includes("football")) return "sports";
  if(cat==="live casino") return "live";
  if(cat==="arcade") return "arcade";
  return "number";
}

function textBoard(game){
  const slug=String(game.slug||game.name||"").toLowerCase();
  if(slug.includes("caro")) return "15x15";
  if(slug.includes("chess")) return "9x10";
  return "table";
}

export function playDemoGame(game, amount){
  const family=gameFamily(game);
  const winChance=clamp(Number(game.win_chance || 50), 1, 99);
  const roll=rand(1,100);
  const win=roll<=winChance;
  const min=Number(game.payout_min || 1.1);
  const max=Math.max(min+.01, Number(game.payout_max || 2));
  let multiplier=win ? fixed(min + Math.random()*(max-min)) : 0;
  let details={family, roll, win_chance:winChance, round_seed:crypto.randomBytes(8).toString("hex"), demo_only:true};

  if(family==="crash"){
    const target=fixed(min + Math.random()*(max-min));
    const crashPoint=win ? fixed(target + Math.random()*Math.max(0.2,max-target)) : fixed(1 + Math.random()*Math.max(0.15,min));
    multiplier=win ? target : 0;
    details={...details, demo_crash_point_x:crashPoint, target_cashout_x:target, flight_path:win?"cashout":"crash", altitude:rand(120,950)};
  } else if(family==="mines"){
    const mineCount=rand(3,8), safeReveals=win?rand(5,14):rand(1,5);
    const mines=[...new Set(Array.from({length:mineCount},()=>rand(0,24)))];
    details={...details, mine_count:mineCount, safe_reveals:safeReveals, hit_mine:!win, mine_index:win?null:(mines[0]||6), mines};
  } else if(family==="plinko"){
    details={...details, bucket:rand(0,8), path:Array.from({length:9},()=>pick(["L","R"])), bounce_score:rand(100,999)};
  } else if(family==="roulette"){
    const number=rand(0,36);
    details={...details, number, color:number===0?"green":(number%2?"red":"black"), sector:pick(["low","middle","high"])};
  } else if(family==="blackjack"){
    const player=win?rand(18,21):rand(12,20);
    const dealer=win?rand(16,Math.max(16,player-1)):rand(Math.max(player,17),21);
    details={...details, player_total:player, dealer_total:dealer, player_cards:[pick(["A","K","Q","J","10","9"]),pick(["8","7","6","5","4"])], dealer_cards:[pick(["A","K","Q","10"]),pick(["9","8","7","6"])]};
  } else if(family==="cards"){
    details={...details, hand_rank:win?pick(["pair","flush","straight","three_of_kind"]):pick(["high_card","miss","fold"]), cards:[pick(["A♠","K♥","Q♦","J♣"]),pick(["10♠","9♥","8♦"]),pick(["7♣","6♠","5♥"])]};
  } else if(family==="slots"){
    const symbols=win?[pick(["7","⭐","💎"]),pick(["7","⭐","💎"]),pick(["7","⭐","💎"])]:[pick(["🍒","BAR","⭐","7"]),pick(["🍋","BAR","💎","A"]),pick(["🍇","K","⭐","Q"])];
    details={...details, reels:symbols, line:win?"payline_active":"no_payline", spin_id:rand(10000,99999)};
  } else if(family==="board"){
    details={...details, board_size: textBoard(game), move_count: rand(8,36), captured: win?rand(2,9):rand(0,3), status: win?"checkmate_or_five_in_row":"opponent_advantage"};
  } else if(family==="fishing"){
    details={...details, fish_caught: win?rand(5,22):rand(0,4), boss_fish: win && rand(0,1)===1, ammo_used: rand(6,40), ocean_level: rand(1,5)};
  } else if(family==="sports"){
    let home=rand(0,5), away=rand(0,5);
    if(win && home<away) [home,away]=[away,home];
    if(!win && home>=away) away=home+rand(1,3);
    details={...details, score:{home,away}, timer:`${rand(60,90)}'`, market:win?"market_success":"market_failed"};
  } else if(family==="live"){
    details={...details, demo_round:`LIVE-${Date.now().toString().slice(-5)}`, dealer_action:win?"paid":"collected", table:pick(["VIP A","VIP B","Gold Table"])};
  } else if(family==="arcade"){
    details={...details, score:win?rand(800,9999):rand(10,799), combo:win?rand(2,12):1, level:rand(1,5)};
  } else {
    const dice=[rand(1,6), rand(1,6)];
    details={...details, dice, total:dice[0]+dice[1], side:pick(["HEADS","TAILS"]), draw:Array.from({length:5},()=>rand(1,40))};
  }
  const payout=win ? fixed(amount*multiplier) : 0;
  return {result:win?"win":"loss", multiplier, payout, details};
}
