--
-- PostgreSQL database dump
--

\restrict DSfG9JrR7qftxRZ40F6j5e4O63wIBsg8FyjMiaP43i1EyIxbREejzLG4UW3Z4V6

-- Dumped from database version 17.6
-- Dumped by pg_dump version 18.4

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
-- Name: current_org_id(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.current_org_id() RETURNS bigint
    LANGUAGE sql STABLE SECURITY DEFINER
    AS $$
    SELECT COALESCE(
        (auth.jwt() ->> 'org_id')::BIGINT,
        0
    );
$$;


--
-- Name: current_user_role(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.current_user_role() RETURNS text
    LANGUAGE sql STABLE SECURITY DEFINER
    AS $$
    SELECT COALESCE(auth.jwt() ->> 'role', '');
$$;


--
-- Name: custom_access_token_hook(jsonb); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.custom_access_token_hook(event jsonb) RETURNS jsonb
    LANGUAGE plpgsql STABLE SECURITY DEFINER
    AS $$
DECLARE
    claims   JSONB;
    user_row RECORD;
BEGIN
    SELECT org_id, role
    INTO user_row
    FROM public.profiles
    WHERE id = (event ->> 'user_id')::UUID;

    IF NOT FOUND THEN
        RETURN event;
    END IF;

    claims := event -> 'claims';
    claims := jsonb_set(claims, '{org_id}', to_jsonb(user_row.org_id));
    claims := jsonb_set(claims, '{role}',   to_jsonb(user_row.role));

    RETURN jsonb_set(event, '{claims}', claims);
END;
$$;


--
-- Name: handle_new_user(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.handle_new_user() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    -- Only insert profile if org_id is provided in metadata
    -- Users created from the dashboard without metadata are skipped
    IF (NEW.raw_user_meta_data ->> 'org_id') IS NOT NULL THEN
        INSERT INTO public.profiles (id, org_id, email, full_name, role, active)
        VALUES (
            NEW.id,
            (NEW.raw_user_meta_data ->> 'org_id')::BIGINT,
            NEW.email,
            COALESCE(NEW.raw_user_meta_data ->> 'full_name', ''),
            COALESCE(NEW.raw_user_meta_data ->> 'role', 'analyst'),
            TRUE
        );
    END IF;
    RETURN NEW;
END;
$$;


--
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: ai_response_cache; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_response_cache (
    id bigint NOT NULL,
    org_id bigint NOT NULL,
    content_hash text NOT NULL,
    model text DEFAULT ''::text NOT NULL,
    result_json jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE ai_response_cache; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.ai_response_cache IS 'Per-tenant GPT response cache. Cross-tenant cache hits are structurally impossible.';


--
-- Name: ai_response_cache_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_response_cache_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_response_cache_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_response_cache_id_seq OWNED BY public.ai_response_cache.id;


--
-- Name: controls; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.controls (
    id bigint NOT NULL,
    org_id bigint NOT NULL,
    control_id text NOT NULL,
    title text NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    control_type text DEFAULT 'manual'::text NOT NULL,
    status text DEFAULT 'not_tested'::text NOT NULL,
    owner text DEFAULT ''::text NOT NULL,
    tsc_criteria jsonb DEFAULT '[]'::jsonb NOT NULL,
    ai_suggested_criteria jsonb DEFAULT '[]'::jsonb NOT NULL,
    source text DEFAULT 'manual'::text NOT NULL,
    notes text DEFAULT ''::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    frequency text,
    requires_population boolean DEFAULT false NOT NULL,
    requires_sample boolean DEFAULT false NOT NULL,
    suggested_sample_size integer,
    narrative text,
    narrative_approved_at timestamp with time zone,
    narrative_flags jsonb DEFAULT '[]'::jsonb,
    CONSTRAINT controls_control_type_check CHECK ((control_type = ANY (ARRAY['manual'::text, 'automated'::text, 'itdm'::text]))),
    CONSTRAINT controls_frequency_check CHECK ((frequency = ANY (ARRAY['annual'::text, 'semi_annual'::text, 'quarterly'::text, 'monthly'::text, 'weekly'::text, 'daily'::text, 'continuous'::text, 'adhoc'::text]))),
    CONSTRAINT controls_source_check CHECK ((source = ANY (ARRAY['manual'::text, 'csv'::text, 'ai_interpreted'::text]))),
    CONSTRAINT controls_status_check CHECK ((status = ANY (ARRAY['not_tested'::text, 'exception_noted'::text, 'cleared'::text, 'tested_no_exceptions'::text])))
);


--
-- Name: COLUMN controls.tsc_criteria; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.controls.tsc_criteria IS 'JSONB array of TSC codes this control satisfies.';


--
-- Name: COLUMN controls.ai_suggested_criteria; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.controls.ai_suggested_criteria IS 'JSONB array returned by criteria_suggester.py — for review, not enforced.';


--
-- Name: controls_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.controls_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: controls_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.controls_id_seq OWNED BY public.controls.id;


--
-- Name: criteria_recommendations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.criteria_recommendations (
    id integer NOT NULL,
    org_id integer NOT NULL,
    criteria_code character varying(10) NOT NULL,
    recommendation text NOT NULL,
    report_type character varying(10) DEFAULT 'type1'::character varying NOT NULL,
    generated_by text,
    generated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT criteria_recommendations_report_type_check CHECK (((report_type)::text = ANY ((ARRAY['type1'::character varying, 'type2'::character varying])::text[])))
);


--
-- Name: criteria_recommendations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.criteria_recommendations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: criteria_recommendations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.criteria_recommendations_id_seq OWNED BY public.criteria_recommendations.id;


--
-- Name: evidence_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.evidence_files (
    id integer NOT NULL,
    org_id integer NOT NULL,
    control_id integer NOT NULL,
    criteria_code character varying(10),
    phase character varying(30) NOT NULL,
    sample_reference text,
    filename text NOT NULL,
    file_type text NOT NULL,
    extracted_text text,
    evaluation jsonb,
    uploaded_by text,
    uploaded_at timestamp with time zone DEFAULT now() NOT NULL,
    evaluated_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT evidence_files_phase_check CHECK (((phase)::text = ANY ((ARRAY['walkthrough'::character varying, 'testing_population'::character varying, 'testing_ipe'::character varying, 'testing_sample'::character varying])::text[])))
);


--
-- Name: evidence_files_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.evidence_files_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: evidence_files_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.evidence_files_id_seq OWNED BY public.evidence_files.id;


--
-- Name: false_positive_patterns; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.false_positive_patterns (
    id bigint NOT NULL,
    org_id bigint NOT NULL,
    pattern_type text NOT NULL,
    cve_id text DEFAULT ''::text NOT NULL,
    vendor text DEFAULT ''::text NOT NULL,
    source_feed text DEFAULT ''::text NOT NULL,
    incident_type text DEFAULT ''::text NOT NULL,
    confidence text DEFAULT 'medium'::text NOT NULL,
    created_from_incident_id bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT false_positive_patterns_confidence_check CHECK ((confidence = ANY (ARRAY['high'::text, 'medium'::text, 'low'::text])))
);


--
-- Name: COLUMN false_positive_patterns.pattern_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.false_positive_patterns.pattern_type IS 'cve_id | vendor_source | vendor_incident_type';


--
-- Name: false_positive_patterns_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.false_positive_patterns_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: false_positive_patterns_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.false_positive_patterns_id_seq OWNED BY public.false_positive_patterns.id;


--
-- Name: incidents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.incidents (
    id bigint NOT NULL,
    org_id bigint NOT NULL,
    article_link text NOT NULL,
    title text NOT NULL,
    summary text DEFAULT ''::text NOT NULL,
    source_feed text DEFAULT ''::text NOT NULL,
    published_at text DEFAULT ''::text NOT NULL,
    vendor text NOT NULL,
    vendor_id bigint,
    severity text DEFAULT 'unknown'::text NOT NULL,
    incident_type text DEFAULT ''::text NOT NULL,
    ai_reason text DEFAULT ''::text NOT NULL,
    soc_criteria jsonb DEFAULT '[]'::jsonb NOT NULL,
    soc_type text DEFAULT ''::text NOT NULL,
    alert_status text DEFAULT 'new'::text NOT NULL,
    event_classification text DEFAULT 'unclassified'::text NOT NULL,
    notified_at timestamp with time zone,
    acknowledged_by text DEFAULT ''::text NOT NULL,
    acknowledged_at timestamp with time zone,
    notes text DEFAULT ''::text NOT NULL,
    detected_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT incidents_alert_status_check CHECK ((alert_status = ANY (ARRAY['new'::text, 'notified'::text, 'acknowledged'::text, 'resolved'::text, 'false_positive'::text, 'likely_false_positive'::text]))),
    CONSTRAINT incidents_event_classification_check CHECK ((event_classification = ANY (ARRAY['unclassified'::text, 'system_event'::text, 'system_incident'::text]))),
    CONSTRAINT incidents_severity_check CHECK ((severity = ANY (ARRAY['critical'::text, 'high'::text, 'medium'::text, 'low'::text, 'unknown'::text])))
);


--
-- Name: COLUMN incidents.soc_criteria; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.incidents.soc_criteria IS 'JSONB array of TSC codes, e.g. ["CC6.1","CC7.2"].';


--
-- Name: COLUMN incidents.event_classification; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.incidents.event_classification IS 'Used by PDF export: unclassified | system_event | system_incident.';


--
-- Name: incidents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.incidents_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: incidents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.incidents_id_seq OWNED BY public.incidents.id;


--
-- Name: organizations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organizations (
    id bigint NOT NULL,
    name text NOT NULL,
    slug text NOT NULL,
    ai_provider text DEFAULT 'openai'::text NOT NULL,
    ai_api_key_encrypted text DEFAULT ''::text NOT NULL,
    ai_model text DEFAULT 'gpt-4.1-mini'::text NOT NULL,
    tsc_scope jsonb DEFAULT '["Security"]'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    plan text DEFAULT 'free'::text NOT NULL,
    subscription_status text DEFAULT 'trialing'::text NOT NULL,
    stripe_customer_id text,
    trial_ends_at timestamp with time zone DEFAULT (now() + '14 days'::interval),
    plan_updated_at timestamp with time zone DEFAULT now(),
    examination_type text DEFAULT 'type2'::text NOT NULL,
    CONSTRAINT organizations_examination_type_check CHECK ((examination_type = ANY (ARRAY['type1'::text, 'type2'::text]))),
    CONSTRAINT organizations_plan_check CHECK ((plan = ANY (ARRAY['free'::text, 'pro'::text, 'enterprise'::text]))),
    CONSTRAINT organizations_subscription_status_check CHECK ((subscription_status = ANY (ARRAY['trialing'::text, 'active'::text, 'past_due'::text, 'cancelled'::text])))
);


--
-- Name: TABLE organizations; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.organizations IS 'One row per tenant. All other tables reference this via org_id.';


--
-- Name: COLUMN organizations.ai_api_key_encrypted; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.organizations.ai_api_key_encrypted IS 'Fernet-encrypted per-org AI key. Empty = use platform default.';


--
-- Name: COLUMN organizations.tsc_scope; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.organizations.tsc_scope IS 'AICPA Trust Service Categories in scope: Security always included.';


--
-- Name: organizations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.organizations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: organizations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.organizations_id_seq OWNED BY public.organizations.id;


--
-- Name: profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.profiles (
    id uuid NOT NULL,
    org_id bigint NOT NULL,
    email text NOT NULL,
    full_name text DEFAULT ''::text NOT NULL,
    role text DEFAULT 'analyst'::text NOT NULL,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_login_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    password_hash text DEFAULT ''::text NOT NULL,
    CONSTRAINT profiles_role_check CHECK ((role = ANY (ARRAY['admin'::text, 'analyst'::text, 'auditor'::text])))
);


--
-- Name: TABLE profiles; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.profiles IS 'App-level user profile linked to auth.users. Stores org membership, role, active flag.';


--
-- Name: COLUMN profiles.role; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.profiles.role IS 'admin = full access; analyst = read/write; auditor = read-only.';


--
-- Name: readiness_assessments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.readiness_assessments (
    id bigint NOT NULL,
    org_id bigint NOT NULL,
    report_type text DEFAULT 'type1'::text NOT NULL,
    tsc_scope jsonb DEFAULT '[]'::jsonb NOT NULL,
    overall_score numeric(5,2) DEFAULT 0 NOT NULL,
    status text DEFAULT 'in_progress'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    CONSTRAINT readiness_assessments_report_type_check CHECK ((report_type = ANY (ARRAY['type1'::text, 'type2'::text]))),
    CONSTRAINT readiness_assessments_status_check CHECK ((status = ANY (ARRAY['in_progress'::text, 'completed'::text])))
);


--
-- Name: readiness_assessments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.readiness_assessments_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: readiness_assessments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.readiness_assessments_id_seq OWNED BY public.readiness_assessments.id;


--
-- Name: readiness_responses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.readiness_responses (
    id bigint NOT NULL,
    assessment_id bigint NOT NULL,
    org_id bigint NOT NULL,
    criteria_code text NOT NULL,
    has_process boolean DEFAULT false NOT NULL,
    is_documented boolean DEFAULT false NOT NULL,
    is_consistent boolean DEFAULT false NOT NULL,
    notes text DEFAULT ''::text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: readiness_responses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.readiness_responses_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: readiness_responses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.readiness_responses_id_seq OWNED BY public.readiness_responses.id;


--
-- Name: readiness_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.readiness_results (
    id bigint NOT NULL,
    assessment_id bigint NOT NULL,
    org_id bigint NOT NULL,
    criteria_code text NOT NULL,
    status text DEFAULT 'not_covered'::text NOT NULL,
    source text DEFAULT 'questionnaire'::text NOT NULL,
    control_ids jsonb DEFAULT '[]'::jsonb NOT NULL,
    ai_recommendation text DEFAULT ''::text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT readiness_results_source_check CHECK ((source = ANY (ARRAY['control_inventory'::text, 'questionnaire'::text]))),
    CONSTRAINT readiness_results_status_check CHECK ((status = ANY (ARRAY['covered'::text, 'partial'::text, 'not_covered'::text])))
);


--
-- Name: readiness_results_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.readiness_results_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: readiness_results_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.readiness_results_id_seq OWNED BY public.readiness_results.id;


--
-- Name: vendors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vendors (
    id bigint NOT NULL,
    org_id bigint NOT NULL,
    name text NOT NULL,
    aliases jsonb DEFAULT '[]'::jsonb NOT NULL,
    category text DEFAULT ''::text NOT NULL,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: COLUMN vendors.aliases; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vendors.aliases IS 'JSON array of alternate names, e.g. ["Azure","MSFT"].';


--
-- Name: COLUMN vendors.category; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vendors.category IS 'e.g. cloud, hr, cicd, identity.';


--
-- Name: vendors_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vendors_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vendors_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vendors_id_seq OWNED BY public.vendors.id;


--
-- Name: ai_response_cache id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_response_cache ALTER COLUMN id SET DEFAULT nextval('public.ai_response_cache_id_seq'::regclass);


--
-- Name: controls id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.controls ALTER COLUMN id SET DEFAULT nextval('public.controls_id_seq'::regclass);


--
-- Name: criteria_recommendations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.criteria_recommendations ALTER COLUMN id SET DEFAULT nextval('public.criteria_recommendations_id_seq'::regclass);


--
-- Name: evidence_files id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_files ALTER COLUMN id SET DEFAULT nextval('public.evidence_files_id_seq'::regclass);


--
-- Name: false_positive_patterns id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.false_positive_patterns ALTER COLUMN id SET DEFAULT nextval('public.false_positive_patterns_id_seq'::regclass);


--
-- Name: incidents id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incidents ALTER COLUMN id SET DEFAULT nextval('public.incidents_id_seq'::regclass);


--
-- Name: organizations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizations ALTER COLUMN id SET DEFAULT nextval('public.organizations_id_seq'::regclass);


--
-- Name: readiness_assessments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.readiness_assessments ALTER COLUMN id SET DEFAULT nextval('public.readiness_assessments_id_seq'::regclass);


--
-- Name: readiness_responses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.readiness_responses ALTER COLUMN id SET DEFAULT nextval('public.readiness_responses_id_seq'::regclass);


--
-- Name: readiness_results id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.readiness_results ALTER COLUMN id SET DEFAULT nextval('public.readiness_results_id_seq'::regclass);


--
-- Name: vendors id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors ALTER COLUMN id SET DEFAULT nextval('public.vendors_id_seq'::regclass);


--
-- Name: ai_response_cache ai_response_cache_org_id_content_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_response_cache
    ADD CONSTRAINT ai_response_cache_org_id_content_hash_key UNIQUE (org_id, content_hash);


--
-- Name: ai_response_cache ai_response_cache_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_response_cache
    ADD CONSTRAINT ai_response_cache_pkey PRIMARY KEY (id);


--
-- Name: controls controls_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.controls
    ADD CONSTRAINT controls_pkey PRIMARY KEY (id);


--
-- Name: criteria_recommendations criteria_recommendations_org_id_criteria_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.criteria_recommendations
    ADD CONSTRAINT criteria_recommendations_org_id_criteria_code_key UNIQUE (org_id, criteria_code);


--
-- Name: criteria_recommendations criteria_recommendations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.criteria_recommendations
    ADD CONSTRAINT criteria_recommendations_pkey PRIMARY KEY (id);


--
-- Name: evidence_files evidence_files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_files
    ADD CONSTRAINT evidence_files_pkey PRIMARY KEY (id);


--
-- Name: false_positive_patterns false_positive_patterns_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.false_positive_patterns
    ADD CONSTRAINT false_positive_patterns_pkey PRIMARY KEY (id);


--
-- Name: incidents incidents_org_id_article_link_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incidents
    ADD CONSTRAINT incidents_org_id_article_link_key UNIQUE (org_id, article_link);


--
-- Name: incidents incidents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incidents
    ADD CONSTRAINT incidents_pkey PRIMARY KEY (id);


--
-- Name: organizations organizations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_pkey PRIMARY KEY (id);


--
-- Name: organizations organizations_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_slug_key UNIQUE (slug);


--
-- Name: profiles profiles_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_email_key UNIQUE (email);


--
-- Name: profiles profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_pkey PRIMARY KEY (id);


--
-- Name: readiness_assessments readiness_assessments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.readiness_assessments
    ADD CONSTRAINT readiness_assessments_pkey PRIMARY KEY (id);


--
-- Name: readiness_responses readiness_responses_assessment_id_criteria_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.readiness_responses
    ADD CONSTRAINT readiness_responses_assessment_id_criteria_code_key UNIQUE (assessment_id, criteria_code);


--
-- Name: readiness_responses readiness_responses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.readiness_responses
    ADD CONSTRAINT readiness_responses_pkey PRIMARY KEY (id);


--
-- Name: readiness_results readiness_results_assessment_id_criteria_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.readiness_results
    ADD CONSTRAINT readiness_results_assessment_id_criteria_code_key UNIQUE (assessment_id, criteria_code);


--
-- Name: readiness_results readiness_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.readiness_results
    ADD CONSTRAINT readiness_results_pkey PRIMARY KEY (id);


--
-- Name: vendors vendors_org_id_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors
    ADD CONSTRAINT vendors_org_id_name_key UNIQUE (org_id, name);


--
-- Name: vendors vendors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors
    ADD CONSTRAINT vendors_pkey PRIMARY KEY (id);


--
-- Name: ai_response_cache_content_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ai_response_cache_content_hash_idx ON public.ai_response_cache USING btree (content_hash);


--
-- Name: idx_ai_cache_org; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_cache_org ON public.ai_response_cache USING btree (org_id, content_hash);


--
-- Name: idx_ai_cache_org_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_cache_org_hash ON public.ai_response_cache USING btree (org_id, content_hash);


--
-- Name: idx_assessments_org_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assessments_org_id ON public.readiness_assessments USING btree (org_id);


--
-- Name: idx_controls_org_controlid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_controls_org_controlid ON public.controls USING btree (org_id, control_id);


--
-- Name: idx_controls_org_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_controls_org_status ON public.controls USING btree (org_id, status);


--
-- Name: idx_criteria_recs_org; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_criteria_recs_org ON public.criteria_recommendations USING btree (org_id);


--
-- Name: idx_evidence_files_control_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_evidence_files_control_id ON public.evidence_files USING btree (control_id);


--
-- Name: idx_evidence_files_control_phase; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_evidence_files_control_phase ON public.evidence_files USING btree (control_id, phase);


--
-- Name: idx_evidence_files_org_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_evidence_files_org_id ON public.evidence_files USING btree (org_id);


--
-- Name: idx_evidence_files_unevaluated; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_evidence_files_unevaluated ON public.evidence_files USING btree (control_id) WHERE (evaluation IS NULL);


--
-- Name: idx_fp_org_cve; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fp_org_cve ON public.false_positive_patterns USING btree (org_id, cve_id) WHERE (cve_id <> ''::text);


--
-- Name: idx_fp_org_vendor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fp_org_vendor ON public.false_positive_patterns USING btree (org_id, vendor);


--
-- Name: idx_incidents_detected; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_incidents_detected ON public.incidents USING btree (detected_at DESC);


--
-- Name: idx_incidents_org_severity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_incidents_org_severity ON public.incidents USING btree (org_id, severity);


--
-- Name: idx_incidents_org_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_incidents_org_status ON public.incidents USING btree (org_id, alert_status);


--
-- Name: idx_incidents_org_vendor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_incidents_org_vendor ON public.incidents USING btree (org_id, vendor);


--
-- Name: idx_profiles_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_profiles_email ON public.profiles USING btree (email);


--
-- Name: idx_profiles_org_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_profiles_org_id ON public.profiles USING btree (org_id);


--
-- Name: idx_responses_assessment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_responses_assessment ON public.readiness_responses USING btree (assessment_id);


--
-- Name: idx_results_assessment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_results_assessment ON public.readiness_results USING btree (assessment_id);


--
-- Name: idx_results_org_criteria; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_results_org_criteria ON public.readiness_results USING btree (org_id, criteria_code);


--
-- Name: idx_vendors_org_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vendors_org_active ON public.vendors USING btree (org_id, active);


--
-- Name: criteria_recommendations criteria_recs_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER criteria_recs_updated_at BEFORE UPDATE ON public.criteria_recommendations FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: evidence_files evidence_files_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER evidence_files_updated_at BEFORE UPDATE ON public.evidence_files FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: readiness_assessments trg_assessments_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_assessments_updated_at BEFORE UPDATE ON public.readiness_assessments FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: controls trg_controls_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_controls_updated_at BEFORE UPDATE ON public.controls FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: incidents trg_incidents_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_incidents_updated_at BEFORE UPDATE ON public.incidents FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: profiles trg_profiles_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_profiles_updated_at BEFORE UPDATE ON public.profiles FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: readiness_responses trg_responses_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_responses_updated_at BEFORE UPDATE ON public.readiness_responses FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: readiness_results trg_results_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_results_updated_at BEFORE UPDATE ON public.readiness_results FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: ai_response_cache ai_response_cache_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_response_cache
    ADD CONSTRAINT ai_response_cache_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: controls controls_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.controls
    ADD CONSTRAINT controls_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: criteria_recommendations criteria_recommendations_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.criteria_recommendations
    ADD CONSTRAINT criteria_recommendations_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: evidence_files evidence_files_control_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_files
    ADD CONSTRAINT evidence_files_control_id_fkey FOREIGN KEY (control_id) REFERENCES public.controls(id) ON DELETE CASCADE;


--
-- Name: evidence_files evidence_files_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence_files
    ADD CONSTRAINT evidence_files_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: false_positive_patterns false_positive_patterns_created_from_incident_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.false_positive_patterns
    ADD CONSTRAINT false_positive_patterns_created_from_incident_id_fkey FOREIGN KEY (created_from_incident_id) REFERENCES public.incidents(id) ON DELETE SET NULL;


--
-- Name: false_positive_patterns false_positive_patterns_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.false_positive_patterns
    ADD CONSTRAINT false_positive_patterns_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: incidents incidents_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incidents
    ADD CONSTRAINT incidents_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: incidents incidents_vendor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incidents
    ADD CONSTRAINT incidents_vendor_id_fkey FOREIGN KEY (vendor_id) REFERENCES public.vendors(id) ON DELETE SET NULL;


--
-- Name: profiles profiles_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: readiness_assessments readiness_assessments_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.readiness_assessments
    ADD CONSTRAINT readiness_assessments_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: readiness_responses readiness_responses_assessment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.readiness_responses
    ADD CONSTRAINT readiness_responses_assessment_id_fkey FOREIGN KEY (assessment_id) REFERENCES public.readiness_assessments(id) ON DELETE CASCADE;


--
-- Name: readiness_responses readiness_responses_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.readiness_responses
    ADD CONSTRAINT readiness_responses_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: readiness_results readiness_results_assessment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.readiness_results
    ADD CONSTRAINT readiness_results_assessment_id_fkey FOREIGN KEY (assessment_id) REFERENCES public.readiness_assessments(id) ON DELETE CASCADE;


--
-- Name: readiness_results readiness_results_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.readiness_results
    ADD CONSTRAINT readiness_results_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: vendors vendors_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors
    ADD CONSTRAINT vendors_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: ai_response_cache ai_cache: tenant isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "ai_cache: tenant isolation" ON public.ai_response_cache USING ((org_id = public.current_org_id()));


--
-- Name: ai_response_cache; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.ai_response_cache ENABLE ROW LEVEL SECURITY;

--
-- Name: controls; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.controls ENABLE ROW LEVEL SECURITY;

--
-- Name: controls controls: delete non-auditor; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "controls: delete non-auditor" ON public.controls FOR DELETE USING (((org_id = public.current_org_id()) AND (public.current_user_role() <> 'auditor'::text)));


--
-- Name: controls controls: insert non-auditor; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "controls: insert non-auditor" ON public.controls FOR INSERT WITH CHECK (((org_id = public.current_org_id()) AND (public.current_user_role() <> 'auditor'::text)));


--
-- Name: controls controls: read own org; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "controls: read own org" ON public.controls FOR SELECT USING ((org_id = public.current_org_id()));


--
-- Name: controls controls: update non-auditor; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "controls: update non-auditor" ON public.controls FOR UPDATE USING (((org_id = public.current_org_id()) AND (public.current_user_role() <> 'auditor'::text)));


--
-- Name: criteria_recommendations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.criteria_recommendations ENABLE ROW LEVEL SECURITY;

--
-- Name: criteria_recommendations criteria_recs_delete; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY criteria_recs_delete ON public.criteria_recommendations FOR DELETE USING ((org_id = ( SELECT profiles.org_id
   FROM public.profiles
  WHERE (profiles.id = auth.uid()))));


--
-- Name: criteria_recommendations criteria_recs_insert; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY criteria_recs_insert ON public.criteria_recommendations FOR INSERT WITH CHECK ((org_id = ( SELECT profiles.org_id
   FROM public.profiles
  WHERE (profiles.id = auth.uid()))));


--
-- Name: criteria_recommendations criteria_recs_select; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY criteria_recs_select ON public.criteria_recommendations FOR SELECT USING ((org_id = ( SELECT profiles.org_id
   FROM public.profiles
  WHERE (profiles.id = auth.uid()))));


--
-- Name: criteria_recommendations criteria_recs_update; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY criteria_recs_update ON public.criteria_recommendations FOR UPDATE USING ((org_id = ( SELECT profiles.org_id
   FROM public.profiles
  WHERE (profiles.id = auth.uid()))));


--
-- Name: evidence_files; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.evidence_files ENABLE ROW LEVEL SECURITY;

--
-- Name: evidence_files evidence_files_delete_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY evidence_files_delete_policy ON public.evidence_files FOR DELETE USING ((org_id = ( SELECT profiles.org_id
   FROM public.profiles
  WHERE (profiles.id = auth.uid()))));


--
-- Name: evidence_files evidence_files_insert_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY evidence_files_insert_policy ON public.evidence_files FOR INSERT WITH CHECK ((org_id = ( SELECT profiles.org_id
   FROM public.profiles
  WHERE (profiles.id = auth.uid()))));


--
-- Name: evidence_files evidence_files_select_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY evidence_files_select_policy ON public.evidence_files FOR SELECT USING ((org_id = ( SELECT profiles.org_id
   FROM public.profiles
  WHERE (profiles.id = auth.uid()))));


--
-- Name: evidence_files evidence_files_update_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY evidence_files_update_policy ON public.evidence_files FOR UPDATE USING ((org_id = ( SELECT profiles.org_id
   FROM public.profiles
  WHERE (profiles.id = auth.uid()))));


--
-- Name: false_positive_patterns; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.false_positive_patterns ENABLE ROW LEVEL SECURITY;

--
-- Name: false_positive_patterns fp_patterns: delete non-auditor; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "fp_patterns: delete non-auditor" ON public.false_positive_patterns FOR DELETE USING (((org_id = public.current_org_id()) AND (public.current_user_role() <> 'auditor'::text)));


--
-- Name: false_positive_patterns fp_patterns: insert non-auditor; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "fp_patterns: insert non-auditor" ON public.false_positive_patterns FOR INSERT WITH CHECK (((org_id = public.current_org_id()) AND (public.current_user_role() <> 'auditor'::text)));


--
-- Name: false_positive_patterns fp_patterns: read own org; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "fp_patterns: read own org" ON public.false_positive_patterns FOR SELECT USING ((org_id = public.current_org_id()));


--
-- Name: incidents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.incidents ENABLE ROW LEVEL SECURITY;

--
-- Name: incidents incidents: delete non-auditor; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "incidents: delete non-auditor" ON public.incidents FOR DELETE USING (((org_id = public.current_org_id()) AND (public.current_user_role() <> 'auditor'::text)));


--
-- Name: incidents incidents: insert non-auditor; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "incidents: insert non-auditor" ON public.incidents FOR INSERT WITH CHECK (((org_id = public.current_org_id()) AND (public.current_user_role() <> 'auditor'::text)));


--
-- Name: incidents incidents: read own org; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "incidents: read own org" ON public.incidents FOR SELECT USING ((org_id = public.current_org_id()));


--
-- Name: incidents incidents: update non-auditor; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "incidents: update non-auditor" ON public.incidents FOR UPDATE USING (((org_id = public.current_org_id()) AND (public.current_user_role() <> 'auditor'::text)));


--
-- Name: organizations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;

--
-- Name: organizations organizations: read own; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "organizations: read own" ON public.organizations FOR SELECT USING ((id = public.current_org_id()));


--
-- Name: profiles; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

--
-- Name: profiles profiles: admin update any in org; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "profiles: admin update any in org" ON public.profiles FOR UPDATE USING (((org_id = public.current_org_id()) AND (public.current_user_role() = 'admin'::text)));


--
-- Name: profiles profiles: read own org; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "profiles: read own org" ON public.profiles FOR SELECT USING ((org_id = public.current_org_id()));


--
-- Name: profiles profiles: update own record; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "profiles: update own record" ON public.profiles FOR UPDATE USING ((id = auth.uid()));


--
-- Name: readiness_assessments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.readiness_assessments ENABLE ROW LEVEL SECURITY;

--
-- Name: readiness_assessments readiness_assessments: insert non-auditor; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "readiness_assessments: insert non-auditor" ON public.readiness_assessments FOR INSERT WITH CHECK (((org_id = public.current_org_id()) AND (public.current_user_role() <> 'auditor'::text)));


--
-- Name: readiness_assessments readiness_assessments: read own org; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "readiness_assessments: read own org" ON public.readiness_assessments FOR SELECT USING ((org_id = public.current_org_id()));


--
-- Name: readiness_assessments readiness_assessments: update non-auditor; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "readiness_assessments: update non-auditor" ON public.readiness_assessments FOR UPDATE USING (((org_id = public.current_org_id()) AND (public.current_user_role() <> 'auditor'::text)));


--
-- Name: readiness_responses; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.readiness_responses ENABLE ROW LEVEL SECURITY;

--
-- Name: readiness_responses readiness_responses: tenant isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "readiness_responses: tenant isolation" ON public.readiness_responses USING ((org_id = public.current_org_id()));


--
-- Name: readiness_results; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.readiness_results ENABLE ROW LEVEL SECURITY;

--
-- Name: readiness_results readiness_results: tenant isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "readiness_results: tenant isolation" ON public.readiness_results USING ((org_id = public.current_org_id()));


--
-- Name: vendors; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vendors ENABLE ROW LEVEL SECURITY;

--
-- Name: vendors vendors: tenant isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "vendors: tenant isolation" ON public.vendors USING ((org_id = public.current_org_id()));


--
-- PostgreSQL database dump complete
--

\unrestrict DSfG9JrR7qftxRZ40F6j5e4O63wIBsg8FyjMiaP43i1EyIxbREejzLG4UW3Z4V6

