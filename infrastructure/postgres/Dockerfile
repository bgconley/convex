FROM paradedb/paradedb:latest-pg16

# Install Apache AGE build dependencies
USER root
RUN apt-get update && apt-get install -y \
    build-essential \
    libreadline-dev \
    zlib1g-dev \
    flex \
    bison \
    postgresql-server-dev-16 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Build and install Apache AGE
RUN git clone --branch release/PG16/1.5.0 https://github.com/apache/age.git /tmp/age \
    && cd /tmp/age \
    && make install \
    && rm -rf /tmp/age

# Copy initialization script (extensions only — tables via Alembic)
COPY init.sql /docker-entrypoint-initdb.d/01-init.sql

# Copy tuned PostgreSQL configuration
COPY postgresql.conf /etc/postgresql/postgresql.conf

USER postgres
