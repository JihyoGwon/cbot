# Python 3.11 slim 이미지 사용
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 필수 패키지 설치 (필요한 경우)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     gcc \
#     libc-dev \
#     && rm -rf /var/lib/apt/lists/*

# 의존성 파일 복사
COPY requirements.txt .

# 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# Cloud Run에서 제공하는 PORT 환경변수 사용 (기본값 8080)
ENV PORT=8080

# Gunicorn으로 Flask 앱 실행
# workers: 워커 프로세스 수
# threads: 워커당 스레드 수
# timeout: 타임아웃 설정 (0은 무제한, Cloud Run 권장)
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app

