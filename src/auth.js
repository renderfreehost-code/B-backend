import jwt from "jsonwebtoken";
import bcrypt from "bcryptjs";
import { query } from "./db.js";

export async function hashPassword(password){
  return bcrypt.hash(String(password || ""), 10);
}

export async function verifyPassword(password, hash){
  return bcrypt.compare(String(password || ""), hash || "");
}

export function createToken(user){
  return jwt.sign(
    {id:user.id, email:user.email, is_admin:user.is_admin},
    process.env.JWT_SECRET || "dev_secret_change_me",
    {expiresIn:"7d"}
  );
}

export async function requireAuth(req,res,next){
  try{
    const header = req.headers.authorization || "";
    const token = header.startsWith("Bearer ") ? header.slice(7) : null;
    if(!token) return res.status(401).json({error:"Unauthorized"});
    const payload = jwt.verify(token, process.env.JWT_SECRET || "dev_secret_change_me");
    const {rows} = await query("select id,name,email,balance,is_admin,is_banned,avatar,created_at from users where id=$1", [payload.id]);
    const user = rows[0];
    if(!user) return res.status(401).json({error:"Unauthorized"});
    if(user.is_banned) return res.status(403).json({error:"Your account is banned"});
    req.user = user;
    next();
  }catch(e){ return res.status(401).json({error:"Unauthorized"}); }
}

export function requireAdmin(req,res,next){
  if(!req.user?.is_admin) return res.status(403).json({error:"Admin only"});
  next();
}
