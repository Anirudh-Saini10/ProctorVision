FROM python:3.11-slim

WORKDIR /app

# Install system libraries needed by OpenCV, MediaPipe, and PyTorch.
# libgl1-mesa-glx + libglib2.0-0 = OpenGL runtime for MediaPipe's native code
# libgomp1 = OpenMP runtime (required by MediaPipe C++ backend and torch)
# libsm6 + libxext6 + libxrender1 = additional X11 libs MediaPipe may need
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglx-mesa0 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    nodejs \
    npm \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (heavy layer — cache first)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Install frontend npm deps
COPY frontend/package*.json ./frontend/
RUN cd frontend && npm install

# Copy full frontend source and build
# Use .env.production to set VITE_API_URL='' (same-origin)
COPY frontend/ ./frontend/
RUN cd frontend && npm run build

# Copy backend code
COPY backend/ ./backend/

# Pre-download ML model files (HF Spaces blocks large binaries in git push,
# so we fetch them at build time instead).
RUN mkdir -p backend/models \
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

# ── HF Spaces requires the container to run as user 1000 ──
# Create user BEFORE chown so chown can resolve the uid.
RUN useradd -m -u 1000 user

# Make /tmp writable (for ultralytics config, mediapipe temp files)
RUN mkdir -p /tmp/ultralytics && chmod 777 /tmp/ultralytics

# Give ownership of the entire /app to user 1000
RUN chown -R user:user /app

USER user

# Environment
ENV PYTHONUNBUFFERED=1
ENV TF_CPP_MIN_LOG_LEVEL=3
ENV YOLO_CONFIG_DIR=/tmp/ultralytics
ENV ULTRALYTICS_DIR=/tmp/ultralytics
# MediaPipe may try to write to HOME — make sure it resolves to a writable dir
ENV HOME=/home/user
# Prevent matplotlib / fontconfig from writing to read-only dirs
ENV MPLCONFIGDIR=/tmp/matplotlib
ENV FONTCONFIG_PATH=/tmp/fontconfig

# HF Spaces default port
EXPOSE 7860

CMD ["sh", "-c", "cd backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}"]
