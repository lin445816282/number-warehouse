"""
数字仓库认证系统 — 独立模块，零侵入现有代码
"""
import os
import hashlib
import secrets
import time
from datetime import datetime, timedelta
from collections import defaultdict

from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import bcrypt

# ===== 配置 =====
SESSION_EXPIRE_HOURS = 24
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 30
RATE_WINDOW_SECONDS = 900  # 15 分钟

# 密码：从环境变量读取，无则用默认
_PASSWORD = os.environ.get("NW_PASSWORD", "xiaolin2024")
_PASSWORD_HASH = bcrypt.hashpw(_PASSWORD.encode(), bcrypt.gensalt())

# 速率限制存储（内存，重启清零——可接受）
_failed_attempts: defaultdict[str, list[float]] = defaultdict(list)
_lockout_until: dict[str, float] = {}

# 路由白名单：无需认证
_WHITELIST = {"/auth/login", "/auth/logout", "/favicon.ico", "/api/threshold/results", "/api/threshold/compute", "/api/threshold"}

# ===== 工具函数 =====

def _generate_token() -> str:
    return hashlib.sha256(secrets.token_bytes(64)).hexdigest()

def _get_db():
    """获取数据库连接（延迟导入避免循环依赖）"""
    import main
    return main.get_db()

def _rate_check(ip: str) -> bool:
    """检查 IP 是否被锁定或超限。返回 True=放行"""
    now = time.time()
    # 检查锁定
    if ip in _lockout_until and now < _lockout_until[ip]:
        return False
    # 清理过期记录
    _failed_attempts[ip] = [t for t in _failed_attempts[ip] if now - t < RATE_WINDOW_SECONDS]
    return len(_failed_attempts[ip]) < MAX_FAILED_ATTEMPTS

def _rate_record(ip: str):
    """记录一次失败"""
    now = time.time()
    _failed_attempts[ip].append(now)
    _failed_attempts[ip] = [t for t in _failed_attempts[ip] if now - t < RATE_WINDOW_SECONDS]
    if len(_failed_attempts[ip]) >= MAX_FAILED_ATTEMPTS:
        _lockout_until[ip] = now + LOCKOUT_MINUTES * 60

# ===== 数据库初始化 =====

def init_auth_db():
    """创建 sessions 表（幂等）"""
    db = _get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS auth_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT
        )
    """)
    db.commit()

# ===== API 路由 =====

auth_router = APIRouter(prefix="/auth", tags=["auth"])

@auth_router.post("/login")
async def login(request: Request):
    """登录：验证密码 → 生成 session → 设置 cookie"""
    ip = request.client.host if request.client else "unknown"
    
    if not _rate_check(ip):
        raise HTTPException(status_code=429, detail="尝试次数过多，请30分钟后再试")
    
    try:
        body = await request.json()
    except Exception:
        _rate_record(ip)
        raise HTTPException(status_code=400, detail="请求格式错误")
    
    password = body.get("password", "")
    
    if not bcrypt.checkpw(password.encode(), _PASSWORD_HASH):
        _rate_record(ip)
        raise HTTPException(status_code=401, detail="密码错误")
    
    # 登录成功，清除失败记录
    _failed_attempts.pop(ip, None)
    _lockout_until.pop(ip, None)
    
    # 生成 session
    token = _generate_token()
    expires = (datetime.utcnow() + timedelta(hours=SESSION_EXPIRE_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
    ua = request.headers.get("user-agent", "")[:256]
    
    db = _get_db()
    db.execute(
        "INSERT INTO auth_sessions (token, user_id, expires_at, ip_address, user_agent) VALUES (?, 1, ?, ?, ?)",
        (token, expires, ip, ua)
    )
    db.commit()
    
    response = JSONResponse({"ok": True, "message": "登录成功"})
    response.set_cookie(
        key="nw_session",
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=SESSION_EXPIRE_HOURS * 3600,
        path="/"
    )
    return response

@auth_router.post("/logout")
async def logout(request: Request):
    """登出：删除 session → 清除 cookie"""
    token = request.cookies.get("nw_session", "")
    if token:
        db = _get_db()
        db.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
        db.commit()
    
    response = JSONResponse({"ok": True})
    response.delete_cookie("nw_session", path="/")
    return response

# ===== 中间件 =====

class AuthMiddleware(BaseHTTPMiddleware):
    """拦截所有请求，未认证返回登录页"""
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # 白名单放行
        if path in _WHITELIST:
            return await call_next(request)
        
        # 登录页静态资源放行（login.html 需要的 CSS/JS 内联，无外部资源）
        # 但 /auth/login POST 已在白名单
        
        # 验证 session
        token = request.cookies.get("nw_session", "")
        if token:
            db = _get_db()
            row = db.execute(
                "SELECT id, expires_at FROM auth_sessions WHERE token = ?",
                (token,)
            ).fetchone()
            if row:
                expires = row["expires_at"]
                if expires > datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"):
                    # 有效 session，放行
                    return await call_next(request)
                else:
                    # 过期，清理
                    db.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
                    db.commit()
        
        # 未认证 → 返回登录页
        return await _serve_login_page()

async def _serve_login_page():
    """返回独立登录页"""
    import main
    login_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "login.html")
    try:
        with open(login_path, "r", encoding="utf-8") as f:
            html = f.read()
        resp = HTMLResponse(html, status_code=200)
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp
    except FileNotFoundError:
        return HTMLResponse("<h1>登录页缺失，请联系管理员</h1>", status_code=500)
