# Use an official lightweight Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables to optimize Python behavior inside the container
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Copy only the requirements file first to leverage Docker's cache layers
COPY requirements.txt .

# Install the application dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application source code into the container
COPY app/ ./app/

# Expose the port your application listens on (e.g., 8000 for FastAPI/Django, 5000 for Flask)
EXPOSE 8001

# Specify the command to run your application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
