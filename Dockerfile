# Use official Python image
FROM python:3.10

# Set work directory
WORKDIR /app

# Copy project files to container
COPY . .

# Install dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expose port (Render uses 10000+ ports automatically)
EXPOSE 8000

# Run app using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
