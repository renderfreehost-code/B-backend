import crypto from "crypto";

export function playDemoGame(game, amount){
  const roll = crypto.randomInt(1, 101);
  const winChance = Number(game.win_chance || 50);
  const win = roll <= winChance;
  const min = Number(game.payout_min || 1.1);
  const max = Number(game.payout_max || 2.0);
  const multiplier = win ? Number((min + Math.random() * (max-min)).toFixed(2)) : 0;
  const payout = win ? Number((amount * multiplier).toFixed(2)) : 0;
  const category = String(game.category || "Number");
  const details = {
    roll,
    win_chance: winChance,
    demo_only: true,
    animation_family: category.toLowerCase().replaceAll(" ","_")
  };
  if(category==="Crash") details.demo_crash_point_x = win ? multiplier : Number((1 + Math.random()*2.2).toFixed(2));
  if(category==="Mines" || String(game.slug).includes("mines")) details.safe_reveals = win ? crypto.randomInt(4,11) : crypto.randomInt(1,5);
  if(category==="Casino") details.number = crypto.randomInt(0,37), details.color = details.number === 0 ? "green" : (details.number % 2 ? "red" : "black");
  if(category==="Sports") details.score = {home: crypto.randomInt(0,5), away: crypto.randomInt(0,5)};
  return {result: win ? "win" : "loss", multiplier, payout, details};
}
