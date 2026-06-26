FROM python:3.12-slim-bookworm

WORKDIR /app
COPY load/telegram-mock/mock_server.py .

EXPOSE 8081

CMD ["python", "mock_server.py"]
