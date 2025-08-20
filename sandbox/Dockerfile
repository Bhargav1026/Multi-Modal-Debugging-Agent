FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file
COPY backend/requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend application code
COPY backend/ .

# Copy the entrypoint script
COPY sandbox/entrypoint.sh .

# Make the entrypoint script executable
RUN chmod +x entrypoint.sh

# Set the entrypoint for the container
ENTRYPOINT ["./entrypoint.sh"]