# Use official Python image
FROM python:3.10

# Install Tesseract
RUN apt-get update && apt-get install -y tesseract-ocr

# Set working directory
WORKDIR /app

# Copy code
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run your Flask app with gunicorn
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]
