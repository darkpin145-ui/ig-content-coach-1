# IG Content Coach (Fresh Build)
인스타그램 계정 URL과 최근 게시물 요약 데이터를 입력하면
어떤 콘텐츠를 보강/제작할지 피드백과 30일 실행 계획을 제안하는 API입니다.

## 빠른 시작
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # OPENAI_API_KEY, BOT_API_KEY 채우기
uvicorn app.main:app --host 0.0.0.0 --port 8001

## 테스트(로컬)
POST http://localhost:8001/analyze  (헤더: x-api-key: BOT_LOCAL)
Body 예시:
{
  "account_url": "https://www.instagram.com/youraccount/",
  "follower_count": 10000,
  "goals": ["브랜드 인지도","회원권 전환"],
  "posts": [
    {"id":"1","type":"reel","date":"2025-09-20","caption":"루틴","likes":380,"comments":22,"views":11000,"saves":40,"duration_sec":21,"hashtags":["#헬스","#모닝"]},
    {"id":"2","type":"photo","date":"2025-09-23","caption":"포스터","likes":150,"comments":5,"hashtags":["#신규"]}
  ]
}
