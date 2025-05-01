FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Copy the project files to the container
COPY . /app

# Create and activate a virtual environment
RUN python -m venv .venv \
    && . .venv/bin/activate \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install nonebot2 nonebot-adapter-onebot

# Expose port 8080
EXPOSE 8080

# Set the default command to run the bot
CMD [".venv/bin/nb", "run"]
