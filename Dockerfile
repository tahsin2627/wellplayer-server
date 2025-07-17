# Use an official lightweight Python image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies, including aria2
RUN apt-get update && apt-get install -y aria2 && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install the Python libraries
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . .

# Expose the port Gunicorn will run on
EXPOSE 10000

# Command to run your application using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]
