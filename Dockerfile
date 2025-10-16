# 使用官方 Python 運行時作為父鏡像
FROM python:3.10.12-slim

# 設置環境變數
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    USE_POSIX_PATH=1

# 設置工作目錄
WORKDIR /app

# 複製 requirements.txt
COPY requirements.txt .

# 安裝依賴
RUN pip install --no-cache-dir -r requirements.txt

# 創建日誌目錄
RUN mkdir -p /app/logs && chmod 777 /app/logs

# 複製應用代碼
COPY . .

# 確保日誌目錄存在並有正確權限
RUN mkdir -p /app/logs && chmod 777 /app/logs && touch /app/logs/crawler.log && chmod 666 /app/logs/crawler.log

# 暴露端口
EXPOSE 80

# 設置運行指令
CMD ["python", "/app/travl4u_travel_crawler/main.py"]