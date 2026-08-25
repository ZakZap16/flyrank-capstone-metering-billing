-- scripts/init.sql
CREATE ROLE app_user WITH LOGIN PASSWORD 'dev_password';
CREATE DATABASE metering_billing OWNER app_user;
GRANT ALL PRIVILEGES ON DATABASE metering_billing TO app_user;

\c metering_billing

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CREATE ON SCHEMA public TO app_user;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";