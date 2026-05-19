FROM python:3.11

WORKDIR /app

# Install system libraries needed by OpenCV, MediaPipe, and PyTorch
# libgomp1 = OpenMP runtime (required by MediaPipe C++ backend and torch)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
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

# Pre-download ML model files (HF Spaces blocks large binaries in git push,
# so we fetch them at build time instead).
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* \
    && mkdir -p backend/models \
    && curl -fsSL -o backend/models/face_landmarker.task \
       https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task \
    && curl -fsSL -o backend/yolov8n.pt \
       https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt \
    && ls -lh backend/models/face_landmarker.task backend/yolov8n.pt \
    # Build-time validation: ensure files are not empty / truncated
    && test -s backend/models/face_landmarker.task \
    && test $(stat -c%s backend/models/face_landmarker.task) -gt 1000000 \
    && test -s backend/yolov8n.pt \
    && test $(stat -c%s backend/yolov8n.pt) -gt 5000000

# Environment
ENV PYTHONUNBUFFERED=1
ENV TF_CPP_MIN_LOG_LEVEL=3
ENV YOLO_CONFIG_DIR=/tmp/ultralytics
ENV ULTRALYTICS_DIR=/tmp/ultralytics

# HF Spaces default port
EXPOSE 7860

CMD ["sh", "-c", "cd backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}"]
