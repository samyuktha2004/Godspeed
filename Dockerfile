FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY requirements.txt requirements.deploy.txt ./
RUN pip install --no-cache-dir -r requirements.deploy.txt

# Pre-download the BGE-M3 model so cold starts are fast
RUN python3 -c "from FlagEmbedding import BGEM3FlagModel; BGEM3FlagModel('BAAI/bge-m3', use_fp16=False)"

# Download spacy model
RUN python3 -m spacy download en_core_web_sm

# Copy app code
COPY . .

# HuggingFace Spaces requires port 7860
EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
