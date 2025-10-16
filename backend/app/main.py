
import os, json, datetime as dt
from typing import List, Optional
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BOT_API_KEY = os.getenv("BOT_API_KEY","BOT_LOCAL")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS","https://chat.openai.com,http://localhost").split(",")
if not OPENAI_API_KEY: raise RuntimeError("OPENAI_API_KEY missing")

client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI(title="IG Content Coach API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class Post(BaseModel):
    id: str
    type: Optional[str] = "reel"
    date: Optional[str] = None
    caption: Optional[str] = ""
    likes: Optional[int] = 0
    comments: Optional[int] = 0
    views: Optional[int] = 0
    saves: Optional[int] = 0
    reach: Optional[int] = 0
    duration_sec: Optional[int] = 0
    hashtags: Optional[List[str]] = []

class AnalyzeIn(BaseModel):
    account_url: str
    follower_count: Optional[int] = 0
    goals: Optional[List[str]] = []
    posts: List[Post] = []

class AnalyzeOut(BaseModel):
    account_url: str
    scorecard: dict
    diagnostics: dict
    recommendations: dict
    plan_30d: List[str]

def auth(x_api_key: str = Header(...)):
    if x_api_key != BOT_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True

def summarize(posts: List[Post], followers: int):
    n = len(posts)
    mix = {"reel":0,"photo":0,"carousel":0}
    for p in posts:
        t = (p.type or "reel").lower()
        if t in mix: mix[t]+=1
    # 간단 지표
    avg_caption = sum(len((p.caption or "")) for p in posts)/n if n else 0
    avg_hashtags = sum(len((p.hashtags or [])) for p in posts)/n if n else 0
    avg_duration = sum((p.duration_sec or 0) for p in posts)/n if n else 0
    avg_er = sum(((p.likes or 0)+(p.comments or 0))/max(1,followers) for p in posts)/n if n else 0
    avg_vtr = sum(((p.views or 0))/max(1,followers) for p in posts)/n if n else 0
    # 업로드 간격
    dates = []
    for p in posts:
        if p.date:
            try: dates.append(dt.datetime.fromisoformat(p.date).date())
            except: pass
    gap = 0
    if len(dates)>=2:
        dates.sort()
        gaps = [(dates[i]-dates[i-1]).days for i in range(1,len(dates))]
        gap = sum(gaps)/len(gaps) if gaps else 0
    return {
        "n": n, "mix": mix, "avg_caption_len": avg_caption, "avg_hashtag_cnt": avg_hashtags,
        "avg_duration_sec": avg_duration, "avg_er": avg_er, "avg_vtr": avg_vtr, "avg_gap_days": gap
    }

SYSTEM = "You are a Korean Instagram content strategist. Be concrete and data-driven. Keep it short and actionable."
USER_TMPL = """다음 데이터를 바탕으로 한국어로 피드백을 작성해줘.
입력(JSON): {payload}
출력 섹션:
1) Scorecard(10점 만점) – 훅, 리텐션, 포맷믹스, 캡션/해시태그, 빈도, 총평
2) Diagnostics – 핵심 문제 3~5개
3) Recommendations – 밀어야 할 포맷 2개(이유), 개선할 포맷 2개(구체 수정안 3개), 새 아이디어 5개(제목/훅/구성)
4) 30일 실행 계획 – 주차별 미션 + KPI 목표치"""

@app.post("/analyze", response_model=AnalyzeOut, dependencies=[Depends(auth)])
def analyze(inp: AnalyzeIn):
    summary = summarize(inp.posts, inp.follower_count or 0)
    payload = {
        "account_url": inp.account_url,
        "follower_count": inp.follower_count,
        "goals": inp.goals,
        "summary_metrics": summary,
        "sample_posts": [
            {"id": p.id, "type": p.type, "likes": p.likes, "comments": p.comments, "views": p.views,
             "saves": p.saves, "duration_sec": p.duration_sec, "caption": (p.caption or "")[:160]} for p in inp.posts[:6]
        ]
    }
    resp = client.chat.completions.create(
        model="gpt-5.1",
        messages=[{"role":"system","content":SYSTEM},{"role":"user","content":USER_TMPL.format(payload=json.dumps(payload, ensure_ascii=False))}],
        temperature=0.3
    )
    text = resp.choices[0].message.content
    # 간단 포장
    lines = text.split("\n")
    out = {"scorecard":{"raw":""},"diagnostics":{"raw":""},"recommendations":{"raw":""},"plan_30d":[]}
    sec="scorecard"; buf=[]
    def flush(s):
        t="\n".join(buf).strip()
        if s=="scorecard": out["scorecard"]["raw"]=t
        elif s=="diagnostics": out["diagnostics"]["raw"]=t
        elif s=="recommendations": out["recommendations"]["raw"]=t
        elif s=="plan": out["plan_30d"]=[x.strip("-• ") for x in t.split("\n") if x.strip()]
        buf.clear()
    for ln in lines:
        s=ln.strip()
        if s.startswith("2)"): flush("scorecard"); sec="diagnostics"; continue
        if s.startswith("3)"): flush("diagnostics"); sec="recommendations"; continue
        if s.startswith("4)"): flush("recommendations"); sec="plan"; continue
        buf.append(ln)
    flush("plan")
    return {"account_url": inp.account_url, **out}
from fastapi.openapi.utils import get_openapi

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title="IG Content Coach API",
        version="1.0.0",
        routes=app.routes,
    )
    if PUBLIC_BASE_URL:
        schema["servers"] = [{"url": PUBLIC_BASE_URL}]
    app.openapi_schema = schema
    return app.openapi_schema

app.openapi = custom_openapi

from fastapi.responses import FileResponse

@app.get("/privacy")
def privacy_page():
    return FileResponse("app/privacy.html")

