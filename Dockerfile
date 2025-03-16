# Use official Python image
FROM python:3.12.9

# Install OpenCV dependencies
RUN apt-get update && apt-get install -y libgl1 libglib2.0-0

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run Gunicorn
CMD ["gunicorn", "tripplanner.wsgi", "--bind", "0.0.0.0:8000"]
