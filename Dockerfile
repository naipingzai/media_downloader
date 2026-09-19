FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5555

# 默认以 Web 模式启动
CMD ["python", "main.py", "web"]
