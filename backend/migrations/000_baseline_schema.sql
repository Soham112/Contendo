--
-- PostgreSQL database dump
--

\restrict yt48dmL4EDF69hh3tih4GgbKAn8k9zJeLWEaymoUl6LMdIwKFKyWyhq45p6eXum

-- Dumped from database version 17.6
-- Dumped by pg_dump version 18.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA public;


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS 'standard public schema';


--
-- Name: match_embeddings(public.vector, text, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.match_embeddings(query_embedding public.vector, match_user_id text, match_count integer) RETURNS TABLE(id text, content text, source_id text, source_title text, source_type text, tags text, chunk_index integer, total_chunks integer, content_hash text, node_type text, memory_context text, ingested_at timestamp with time zone, similarity double precision)
    LANGUAGE sql STABLE
    AS $$
  SELECT
    id,
    content,
    source_id,
    source_title,
    source_type,
    tags,
    chunk_index,
    total_chunks,
    content_hash,
    node_type,
    memory_context,
    ingested_at,
    1 - (embedding <=> query_embedding) AS similarity
  FROM embeddings
  WHERE user_id = match_user_id
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: chunk_entities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chunk_entities (
    chunk_id text NOT NULL,
    entity_id uuid NOT NULL,
    user_id text NOT NULL,
    relationship_type text NOT NULL,
    CONSTRAINT chunk_entities_relationship_type_check CHECK ((relationship_type = ANY (ARRAY['mentions'::text, 'explains'::text, 'used_in'::text, 'contrasts_with'::text])))
);


--
-- Name: embeddings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.embeddings (
    id text NOT NULL,
    user_id text,
    content text,
    embedding public.vector(384),
    source_id text,
    source_title text,
    source_type text,
    tags text,
    chunk_index integer,
    total_chunks integer,
    content_hash text,
    node_type text DEFAULT 'chunk'::text,
    ingested_at timestamp with time zone DEFAULT now(),
    memory_context text
);


--
-- Name: entities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.entities (
    entity_id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id text NOT NULL,
    entity_name text NOT NULL,
    entity_type text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT entities_entity_type_check CHECK ((entity_type = ANY (ARRAY['technology'::text, 'company'::text, 'project'::text, 'concept'::text, 'methodology'::text, 'market'::text, 'metric'::text, 'person'::text])))
);


--
-- Name: experience_nodes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.experience_nodes (
    experience_id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id text NOT NULL,
    node_type text NOT NULL,
    entity_name text NOT NULL,
    role text,
    start_date text,
    end_date text,
    domain_areas text,
    description text,
    context_label text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT experience_nodes_node_type_check CHECK ((node_type = ANY (ARRAY['work'::text, 'personal_project'::text, 'education'::text])))
);


--
-- Name: generation_traces; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.generation_traces (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id text NOT NULL,
    post_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    topic text,
    context text,
    format text,
    tone text,
    length text,
    quality text,
    retrieval_query text,
    retrieval_path text,
    retrieval_confidence text,
    retrieved jsonb,
    retrieved_context text,
    profile_snapshot jsonb,
    node_outputs jsonb,
    llm_calls jsonb,
    score integer,
    iterations integer,
    archetype text,
    eval_status text DEFAULT 'pending'::text
);


--
-- Name: post_versions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.post_versions (
    id integer NOT NULL,
    post_id integer,
    version_number integer,
    content text,
    authenticity_score integer,
    version_type text,
    svg_diagrams jsonb,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: post_versions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.post_versions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: post_versions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.post_versions_id_seq OWNED BY public.post_versions.id;


--
-- Name: posts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.posts (
    id integer NOT NULL,
    user_id uuid,
    topic text,
    format text,
    tone text,
    content text,
    authenticity_score integer,
    svg_diagrams jsonb,
    archetype text DEFAULT ''::text,
    published_at timestamp with time zone,
    published_platform text,
    published_content text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: posts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.posts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: posts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.posts_id_seq OWNED BY public.posts.id;


--
-- Name: profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.profiles (
    id uuid NOT NULL,
    data jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: source_nodes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.source_nodes (
    id integer NOT NULL,
    user_id text,
    source_id text,
    source_title text,
    source_type text,
    summary text,
    tags text,
    ingested_at timestamp with time zone DEFAULT now()
);


--
-- Name: source_nodes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.source_nodes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: source_nodes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.source_nodes_id_seq OWNED BY public.source_nodes.id;


--
-- Name: source_retrieval_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.source_retrieval_stats (
    id integer NOT NULL,
    user_id text,
    source_title text,
    retrieval_count integer DEFAULT 0,
    last_retrieved_at timestamp with time zone DEFAULT now()
);


--
-- Name: source_retrieval_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.source_retrieval_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: source_retrieval_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.source_retrieval_stats_id_seq OWNED BY public.source_retrieval_stats.id;


--
-- Name: topic_nodes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.topic_nodes (
    id integer NOT NULL,
    user_id text,
    tag text,
    source_ids text
);


--
-- Name: topic_nodes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.topic_nodes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: topic_nodes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.topic_nodes_id_seq OWNED BY public.topic_nodes.id;


--
-- Name: usage_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usage_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id text NOT NULL,
    event_type text NOT NULL,
    input_tokens integer DEFAULT 0,
    output_tokens integer DEFAULT 0,
    estimated_cost_usd numeric(10,6) DEFAULT 0,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: user_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_events (
    id bigint NOT NULL,
    user_id text NOT NULL,
    event_type text NOT NULL,
    page_url text,
    button_name text,
    metadata jsonb DEFAULT '{}'::jsonb,
    "timestamp" timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: user_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.user_events ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.user_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: post_versions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.post_versions ALTER COLUMN id SET DEFAULT nextval('public.post_versions_id_seq'::regclass);


--
-- Name: posts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.posts ALTER COLUMN id SET DEFAULT nextval('public.posts_id_seq'::regclass);


--
-- Name: source_nodes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_nodes ALTER COLUMN id SET DEFAULT nextval('public.source_nodes_id_seq'::regclass);


--
-- Name: source_retrieval_stats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_retrieval_stats ALTER COLUMN id SET DEFAULT nextval('public.source_retrieval_stats_id_seq'::regclass);


--
-- Name: topic_nodes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topic_nodes ALTER COLUMN id SET DEFAULT nextval('public.topic_nodes_id_seq'::regclass);


--
-- Name: chunk_entities chunk_entities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunk_entities
    ADD CONSTRAINT chunk_entities_pkey PRIMARY KEY (chunk_id, entity_id);


--
-- Name: embeddings embeddings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.embeddings
    ADD CONSTRAINT embeddings_pkey PRIMARY KEY (id);


--
-- Name: entities entities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entities
    ADD CONSTRAINT entities_pkey PRIMARY KEY (entity_id);


--
-- Name: entities entities_user_id_entity_name_entity_type_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entities
    ADD CONSTRAINT entities_user_id_entity_name_entity_type_key UNIQUE (user_id, entity_name, entity_type);


--
-- Name: experience_nodes experience_nodes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.experience_nodes
    ADD CONSTRAINT experience_nodes_pkey PRIMARY KEY (experience_id);


--
-- Name: generation_traces generation_traces_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.generation_traces
    ADD CONSTRAINT generation_traces_pkey PRIMARY KEY (id);


--
-- Name: post_versions post_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.post_versions
    ADD CONSTRAINT post_versions_pkey PRIMARY KEY (id);


--
-- Name: posts posts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.posts
    ADD CONSTRAINT posts_pkey PRIMARY KEY (id);


--
-- Name: profiles profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_pkey PRIMARY KEY (id);


--
-- Name: source_nodes source_nodes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_nodes
    ADD CONSTRAINT source_nodes_pkey PRIMARY KEY (id);


--
-- Name: source_retrieval_stats source_retrieval_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_retrieval_stats
    ADD CONSTRAINT source_retrieval_stats_pkey PRIMARY KEY (id);


--
-- Name: source_retrieval_stats source_retrieval_stats_user_id_source_title_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_retrieval_stats
    ADD CONSTRAINT source_retrieval_stats_user_id_source_title_key UNIQUE (user_id, source_title);


--
-- Name: topic_nodes topic_nodes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topic_nodes
    ADD CONSTRAINT topic_nodes_pkey PRIMARY KEY (id);


--
-- Name: usage_events usage_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usage_events
    ADD CONSTRAINT usage_events_pkey PRIMARY KEY (id);


--
-- Name: user_events user_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_events
    ADD CONSTRAINT user_events_pkey PRIMARY KEY (id);


--
-- Name: embeddings_embedding_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX embeddings_embedding_idx ON public.embeddings USING ivfflat (embedding public.vector_cosine_ops) WITH (lists='100');


--
-- Name: idx_chunk_entities_chunk_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chunk_entities_chunk_id ON public.chunk_entities USING btree (chunk_id);


--
-- Name: idx_chunk_entities_entity_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chunk_entities_entity_id ON public.chunk_entities USING btree (entity_id);


--
-- Name: idx_chunk_entities_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chunk_entities_user_id ON public.chunk_entities USING btree (user_id);


--
-- Name: idx_entities_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_entities_user_id ON public.entities USING btree (user_id);


--
-- Name: idx_entities_user_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_entities_user_name ON public.entities USING btree (user_id, entity_name);


--
-- Name: idx_experience_nodes_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_experience_nodes_type ON public.experience_nodes USING btree (user_id, node_type);


--
-- Name: idx_experience_nodes_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_experience_nodes_user_id ON public.experience_nodes USING btree (user_id);


--
-- Name: idx_generation_traces_eval_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_generation_traces_eval_status ON public.generation_traces USING btree (eval_status);


--
-- Name: idx_generation_traces_user_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_generation_traces_user_created ON public.generation_traces USING btree (user_id, created_at DESC);


--
-- Name: idx_user_events_event_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_events_event_type ON public.user_events USING btree (event_type);


--
-- Name: idx_user_events_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_events_timestamp ON public.user_events USING btree ("timestamp");


--
-- Name: idx_user_events_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_events_user_id ON public.user_events USING btree (user_id);


--
-- Name: usage_events_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX usage_events_created_at_idx ON public.usage_events USING btree (created_at);


--
-- Name: usage_events_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX usage_events_user_id_idx ON public.usage_events USING btree (user_id);


--
-- Name: chunk_entities chunk_entities_entity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunk_entities
    ADD CONSTRAINT chunk_entities_entity_id_fkey FOREIGN KEY (entity_id) REFERENCES public.entities(entity_id) ON DELETE CASCADE;


--
-- Name: generation_traces generation_traces_post_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.generation_traces
    ADD CONSTRAINT generation_traces_post_id_fkey FOREIGN KEY (post_id) REFERENCES public.posts(id) ON DELETE SET NULL;


--
-- Name: post_versions post_versions_post_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.post_versions
    ADD CONSTRAINT post_versions_post_id_fkey FOREIGN KEY (post_id) REFERENCES public.posts(id) ON DELETE CASCADE;


--
-- Name: posts posts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.posts
    ADD CONSTRAINT posts_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: profiles profiles_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: chunk_entities; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.chunk_entities ENABLE ROW LEVEL SECURITY;

--
-- Name: embeddings; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.embeddings ENABLE ROW LEVEL SECURITY;

--
-- Name: entities; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.entities ENABLE ROW LEVEL SECURITY;

--
-- Name: experience_nodes; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.experience_nodes ENABLE ROW LEVEL SECURITY;

--
-- Name: generation_traces; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.generation_traces ENABLE ROW LEVEL SECURITY;

--
-- Name: post_versions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.post_versions ENABLE ROW LEVEL SECURITY;

--
-- Name: posts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.posts ENABLE ROW LEVEL SECURITY;

--
-- Name: profiles; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

--
-- Name: source_nodes; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.source_nodes ENABLE ROW LEVEL SECURITY;

--
-- Name: source_retrieval_stats; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.source_retrieval_stats ENABLE ROW LEVEL SECURITY;

--
-- Name: topic_nodes; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.topic_nodes ENABLE ROW LEVEL SECURITY;

--
-- Name: usage_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.usage_events ENABLE ROW LEVEL SECURITY;

--
-- Name: user_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.user_events ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--

\unrestrict yt48dmL4EDF69hh3tih4GgbKAn8k9zJeLWEaymoUl6LMdIwKFKyWyhq45p6eXum

