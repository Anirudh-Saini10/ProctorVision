FROM python:3.11-slim

WORKDIR /app

# Install Node.js + npm for frontend build
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (heavy layer — cache first)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Install frontend npm deps
COPY frontend/package*.json ./frontend/
RUN cd frontend && npm install

# Copy full frontend source and build
COPY frontend/ ./frontend/
RUN cd frontend && npm run build

# Copy backend code
COPY backend/ ./backend/

# Environment
ENV PYTHONUNBUFFERED=1
ENV TF_CPP_MIN_LOG_LEVEL=3
ENV YOLO_CONFIG_DIR=/tmp/ultralytics
ENV ULTRALYTICS_DIR=/tmp/ultralytics

# HF Spaces default port
EXPOSE 7860

CMD ["sh", "-c", "cd backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}"]
