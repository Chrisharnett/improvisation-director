# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 8765 available. Expose port 8080 for health checks
EXPOSE 8765 8080

# Define environment variable
ENV NAME=improvdirector

# Run your backend server
CMD ["python", "improvDirector.py"]
