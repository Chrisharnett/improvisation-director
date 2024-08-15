# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

#COPY CERT/cert.pem /app/CERT/cert.pem
#COPY CERT/key.pem /app/CERT/key.pem

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 8765 available to the world outside this container
EXPOSE 8765

# Define environment variable
ENV NAME=improvdirector

# Run your backend server
CMD ["python", "ImprovDirectorServer.py"]