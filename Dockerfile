FROM python:3.11-slim

# System deps + Node.js 20
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY requirements.txt requirements.deploy.txt ./
RUN pip install --no-cache-dir -r requirements.deploy.txt

# Pre-download the BGE-M3 model so cold starts are fast.
# use_fp16=True matches the runtime load in agent/tools/doc_search.py and
# ingestion/pipeline/embedder.py — keeps the image ~1 GB smaller (half-precision
# weights only) and avoids downloading weights the app never uses.
RUN python3 -c "from FlagEmbedding import BGEM3FlagModel; BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)"

# Download spacy model
RUN python3 -m spacy download en_core_web_sm

# Build the React frontend
COPY frontend/package.json frontend/package-lock.json* frontend/
RUN cd frontend && npm install

COPY frontend/ frontend/
RUN cd frontend && npm run build

# Copy remaining app code
COPY . .

# HuggingFace Spaces requires port 7860; other platforms may inject $PORT
ENV PORT=7860
EXPOSE 7860

# Shell-form so $PORT is expanded by the container at start time
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}"]
