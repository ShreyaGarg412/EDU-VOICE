# ✅ Use official Python image
FROM python:3.10-slim

# ✅ Install system dependencies (Tesseract)
RUN apt-get update && \
    apt-get install -y tesseract-ocr libgl1 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# ✅ Set working directory
WORKDIR /app

# ✅ Copy project files
COPY . .

# ✅ Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# ✅ Run Gunicorn with increased timeout
CMD ["gunicorn", "app:app", "--timeout", "500", "--workers", "3", "--bind", "0.0.0.0:5000"]

