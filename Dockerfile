FROM python:3.11-slim

# Prevent Python from writing .pyc files and configure unbuffered stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CHROME_HEADLESS=true \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    PYTHONPATH=/app:/app/libraries

# Install system dependencies: headless Chromium, Chromium driver, and CA certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root application user
RUN groupadd -r appuser && \
    useradd -r -g appuser -m -d /home/appuser -s /bin/bash appuser

# Set working directory
WORKDIR /app

# Install project Python dependencies
COPY requirements.txt /app/requirements.txt
# gcc and kernel headers are needed temporarily to build evdev from source
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev linux-libc-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove gcc libc6-dev linux-libc-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app

# Ensure runtime directories exist and are owned by appuser
RUN mkdir -p /app/results /app/data /app/data/temp /app/data/output && \
    chown -R appuser:appuser /app /home/appuser

# Setup entrypoint script supporting both default task execution and arbitrary commands/daemon
RUN printf '#!/bin/sh\nset -e\nif [ $# -eq 0 ]; then\n  set -- robot --outputdir results tasks/amazon/wishlist_amazon_price_updater.robot\nelif [ "${1#-}" != "$1" ]; then\n  set -- robot "$@"\nfi\nexec "$@"\n' > /usr/local/bin/entrypoint.sh \
    && chmod +x /usr/local/bin/entrypoint.sh

# Switch to non-root user
USER appuser

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["robot", "--outputdir", "results", "tasks/amazon/wishlist_amazon_price_updater.robot"]
