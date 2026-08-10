-- GIGABYTE AI Agent - schema bootstrap
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS motherboards (
    id              SERIAL PRIMARY KEY,
    model_name      VARCHAR(120) UNIQUE NOT NULL,
    series          VARCHAR(60)  NOT NULL,
    socket          VARCHAR(30)  NOT NULL,
    chipset         VARCHAR(30)  NOT NULL,
    form_factor     VARCHAR(20)  NOT NULL,
    memory_type     VARCHAR(20)  NOT NULL,
    memory_slots    INTEGER      NOT NULL,
    max_memory_gb   INTEGER      NOT NULL,
    pcie_version    VARCHAR(20)  NOT NULL,
    m2_slots        INTEGER      NOT NULL,
    wifi            BOOLEAN      NOT NULL DEFAULT FALSE,
    price_twd       INTEGER      NOT NULL,
    release_date    DATE         NOT NULL,
    description     TEXT         NOT NULL,
    extra_specs     JSONB        NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS uploaded_files (
    id              SERIAL PRIMARY KEY,
    filename        VARCHAR(260) NOT NULL,
    content_type    VARCHAR(120),
    size_bytes      INTEGER NOT NULL,
    chunk_count     INTEGER NOT NULL DEFAULT 0,
    status          VARCHAR(20) NOT NULL DEFAULT 'processing',
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS kb_documents (
    id                SERIAL PRIMARY KEY,
    motherboard_id    INTEGER REFERENCES motherboards(id) ON DELETE CASCADE,
    uploaded_file_id  INTEGER REFERENCES uploaded_files(id) ON DELETE CASCADE,
    title             VARCHAR(200) NOT NULL,
    content           TEXT NOT NULL,
    embedding         VECTOR(768) NOT NULL,
    doc_metadata      JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Approximate nearest-neighbour index for cosine distance search.
-- (lists is small here since the demo dataset is tiny; tune for real data volumes.)
CREATE INDEX IF NOT EXISTS kb_documents_embedding_idx
    ON kb_documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);

CREATE INDEX IF NOT EXISTS motherboards_model_name_idx ON motherboards (model_name);
CREATE INDEX IF NOT EXISTS motherboards_series_idx ON motherboards (series);

CREATE TABLE IF NOT EXISTS conversations (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(200) NOT NULL DEFAULT '新對話',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    id               SERIAL PRIMARY KEY,
    conversation_id  INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role             VARCHAR(20) NOT NULL,
    content          TEXT NOT NULL DEFAULT '',
    steps            JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS messages_conversation_created_idx
    ON messages (conversation_id, created_at);
