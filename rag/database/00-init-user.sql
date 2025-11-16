-- Create rag user and database if they do not exist.
-- This is idempotent and safe to run multiple times.
\connect postgres

DO
$do$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rag_user') THEN
        CREATE ROLE rag_user WITH LOGIN PASSWORD 'rag_password';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'building_codes') THEN
        CREATE DATABASE building_codes OWNER rag_user;
    END IF;
END
$do$;

-- Grant privileges to the role for the database if needed
\connect building_codes
GRANT ALL PRIVILEGES ON DATABASE building_codes TO rag_user;
