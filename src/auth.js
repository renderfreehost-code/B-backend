import jwt from "jsonwebtoken";
import bcrypt from "bcryptjs";
import { query } from "./db.js";

export async function hashPassword(password){
  return bcrypt.hash(password, 10);
}

export async function verifyPassword(password, hash){
  return bcrypt.compare(password, hash);
}

export function createToken(user){
  return jwt.sign({id:user.id, email:user.email, is_admin:user.is_admin}, process.env.JWT_SECRET || "dev_secret", {expiresIn:"7d"});
}

export async function requireAuth(req,res,next){
  try{
    const header = req.headers.authorization || "";
    const token = header.startsWith("Bearer ") ? header.slice(7) : null;
    if(!token) return res.status(401).json({error:"Unauthorized"});
    const payload = jwt.verify(token, process.env.JWT_SECRET || "dev_secret");
    const {rows} = await query("select id,name,email,balance,is_admin,created_at from users where id=$1", [payload.id]);
    if(!rows[0]) return res.status(401).json({error:"Unauthorized"});
    req.user = rows[0];
    next();
  }catch(e){ return res.status(401).json({error:"Unauthorized"}); }
}

export function requireAdmin(req,res,next){
  if(!req.user?.is_admin) return res.status(403).json({error:"Admin only"});
  next();
}
