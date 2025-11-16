-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    version TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- Chapters table
CREATE TABLE IF NOT EXISTS chapters (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chapter_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    user_notes TEXT,
    UNIQUE(document_id, chapter_number)
);

-- Sections table
CREATE TABLE IF NOT EXISTS sections (
    id SERIAL PRIMARY KEY,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    parent_section_id INTEGER REFERENCES sections(id) ON DELETE CASCADE,
    section_number TEXT NOT NULL,
    prefix TEXT,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    depth INTEGER NOT NULL,
    page_number TEXT,
    embedding vector(1536),
    metadata JSONB,
    full_text_search tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(title, '') || ' ' || coalesce(text, ''))
    ) STORED,
    UNIQUE(chapter_id, section_number)
);

CREATE INDEX IF NOT EXISTS idx_sections_fts ON sections USING GIN(full_text_search);
CREATE INDEX IF NOT EXISTS idx_sections_embedding ON sections USING hnsw (embedding vector_cosine_ops);

-- Numbered items table
CREATE TABLE IF NOT EXISTS numbered_items (
    id SERIAL PRIMARY KEY,
    section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS section_references (
    id SERIAL PRIMARY KEY,
    source_section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    target_section_id INTEGER REFERENCES sections(id) ON DELETE SET NULL,
    reference_type TEXT NOT NULL,
    reference_text TEXT NOT NULL,
    position_start INTEGER,
    position_end INTEGER,
    CHECK (reference_type IN ('section', 'table', 'figure', 'external'))
);

CREATE INDEX IF NOT EXISTS idx_references_source ON section_references(source_section_id);
CREATE INDEX IF NOT EXISTS idx_references_target ON section_references(target_section_id);

-- Tables table
CREATE TABLE IF NOT EXISTS tables (
    id SERIAL PRIMARY KEY,
    table_id TEXT UNIQUE NOT NULL,
    section_id INTEGER REFERENCES sections(id) ON DELETE CASCADE,
    headers JSONB NOT NULL,
    rows JSONB NOT NULL,
    page_number INTEGER,
    accuracy DOUBLE PRECISION,
    embedding vector(1536)
);

CREATE INDEX IF NOT EXISTS idx_tables_embedding ON tables USING hnsw (embedding vector_cosine_ops);

-- Figures table
CREATE TABLE IF NOT EXISTS figures (
    id SERIAL PRIMARY KEY,
    figure_id TEXT UNIQUE NOT NULL,
    section_id INTEGER REFERENCES sections(id) ON DELETE CASCADE,
    image_path TEXT,
    page_number INTEGER,
    dimensions JSONB,
    format TEXT,
    caption TEXT,
    embedding vector(1536)
);

CREATE INDEX IF NOT EXISTS idx_figures_embedding ON figures USING hnsw (embedding vector_cosine_ops);
