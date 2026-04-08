--
-- PostgreSQL database dump
--

\restrict Ga92wzyp317tGqWZu1k21YFGgosgIhN8bxb3nNzdDght3BAGNh8wvyeVnoXoGbG

-- Dumped from database version 16.11
-- Dumped by pg_dump version 16.11

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: outflowreason; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.outflowreason AS ENUM (
    'REFUND',
    'TRANSFER',
    'PAYOUT',
    'SETTLEMENT',
    'PLATFORM_FEE',
    'ADJUSTMENT'
);


--
-- Name: paymentstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.paymentstatus AS ENUM (
    'PAYMENT_INITIATED',
    'PAYMENT_PENDING',
    'PAYMENT_EXPIRED'
);


--
-- Name: qr_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.qr_type AS ENUM (
    'STATIC',
    'DYNAMIC'
);


--
-- Name: qrstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.qrstatus AS ENUM (
    'ACTIVE',
    'INACTIVE',
    'EXPIRED'
);


--
-- Name: scanstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.scanstatus AS ENUM (
    'SCANNED_ONLY',
    'PAYMENT_INITIATED',
    'PAYMENT_SUCCESS',
    'PAYMENT_FAILED'
);


--
-- Name: transactionstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.transactionstatus AS ENUM (
    'PENDING',
    'SUCCESS',
    'FAILED',
    'CANCELLED'
);


--
-- Name: transactiontype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.transactiontype AS ENUM (
    'INCOMING',
    'OUTGOING'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: payment_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_sessions (
    id integer NOT NULL,
    amount integer NOT NULL,
    status public.paymentstatus NOT NULL,
    started_at timestamp without time zone,
    expired_at timestamp without time zone,
    qr_id integer NOT NULL,
    user_id integer NOT NULL,
    transaction_id integer
);


--
-- Name: payment_sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payment_sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payment_sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payment_sessions_id_seq OWNED BY public.payment_sessions.id;


--
-- Name: qr_codes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qr_codes (
    id integer NOT NULL,
    payload_data text NOT NULL,
    payload_json json,
    qr_type public.qr_type NOT NULL,
    status public.qrstatus NOT NULL,
    created_at timestamp without time zone,
    vendor_id integer NOT NULL,
    currency_code character varying(3),
    reference_number character varying(50),
    last_scanned_at timestamp without time zone
);


--
-- Name: qr_codes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.qr_codes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: qr_codes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.qr_codes_id_seq OWNED BY public.qr_codes.id;


--
-- Name: scanlogs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scanlogs (
    id integer NOT NULL,
    status public.scanstatus NOT NULL,
    "timestamp" timestamp without time zone,
    qr_id integer NOT NULL,
    user_id integer NOT NULL
);


--
-- Name: scanlogs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.scanlogs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: scanlogs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.scanlogs_id_seq OWNED BY public.scanlogs.id;


--
-- Name: transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transactions (
    id integer NOT NULL,
    amount integer NOT NULL,
    currency character varying(3),
    type public.transactiontype NOT NULL,
    status public.transactionstatus NOT NULL,
    outflow_reason public.outflowreason,
    mpesa_receipt character varying(150),
    phone character varying(20),
    callback_response json,
    initated_at timestamp without time zone NOT NULL,
    completed_at timestamp without time zone NOT NULL,
    user_id integer,
    vendor_id integer,
    qrcode_id integer
);


--
-- Name: transactions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transactions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transactions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transactions_id_seq OWNED BY public.transactions.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    phone_number character varying(20) NOT NULL,
    email character varying(120) NOT NULL,
    password_hash character varying(256) NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    is_active boolean,
    last_login timestamp without time zone,
    last_logout timestamp without time zone
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: vendors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vendors (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    business_name character varying(150),
    business_shortcode character varying(20) NOT NULL,
    merchant_id character varying(100),
    mcc character varying(8),
    country_code character varying(2),
    currency_code character varying(3),
    store_label character varying(50),
    email character varying(120) NOT NULL,
    phone character varying(20) NOT NULL,
    password_hash character varying(256) NOT NULL,
    psp_id character varying(100),
    psp_name character varying(150),
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    is_active boolean,
    last_login timestamp without time zone,
    last_logout timestamp without time zone
);


--
-- Name: vendors_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vendors_id_seq
    AS integer
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
-- Name: payment_sessions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_sessions ALTER COLUMN id SET DEFAULT nextval('public.payment_sessions_id_seq'::regclass);


--
-- Name: qr_codes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qr_codes ALTER COLUMN id SET DEFAULT nextval('public.qr_codes_id_seq'::regclass);


--
-- Name: scanlogs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scanlogs ALTER COLUMN id SET DEFAULT nextval('public.scanlogs_id_seq'::regclass);


--
-- Name: transactions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions ALTER COLUMN id SET DEFAULT nextval('public.transactions_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: vendors id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors ALTER COLUMN id SET DEFAULT nextval('public.vendors_id_seq'::regclass);


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.alembic_version (version_num) FROM stdin;
c7b9d1f5a2e1
\.


--
-- Data for Name: payment_sessions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.payment_sessions (id, amount, status, started_at, expired_at, qr_id, user_id, transaction_id) FROM stdin;
1	150	PAYMENT_PENDING	2026-04-02 16:04:33.677812	2026-04-02 16:04:33.677812	1	1	1
2	300	PAYMENT_INITIATED	2026-04-02 16:04:33.677812	2026-04-02 16:04:33.677812	2	2	2
\.


--
-- Data for Name: qr_codes; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.qr_codes (id, payload_data, payload_json, qr_type, status, created_at, vendor_id, currency_code, reference_number, last_scanned_at) FROM stdin;
1	EMVCO|M1|123456	{"merchant": "Merchant One", "shortcode": "123456"}	STATIC	ACTIVE	2026-04-02 16:04:33.677812	1	404	REF-QR-0001	2026-04-02 16:04:33.677812
2	EMVCO|M2|654321	{"merchant": "Merchant Two", "shortcode": "654321"}	DYNAMIC	ACTIVE	2026-04-02 16:04:33.677812	2	404	REF-QR-0002	2026-04-02 16:04:33.677812
\.


--
-- Data for Name: scanlogs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.scanlogs (id, status, "timestamp", qr_id, user_id) FROM stdin;
1	SCANNED_ONLY	2026-04-02 16:04:33.677812	1	1
2	PAYMENT_SUCCESS	2026-04-02 16:04:33.677812	2	2
\.


--
-- Data for Name: transactions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.transactions (id, amount, currency, type, status, outflow_reason, mpesa_receipt, phone, callback_response, initated_at, completed_at, user_id, vendor_id, qrcode_id) FROM stdin;
1	150	404	INCOMING	SUCCESS	\N	MPESA-0001	+254700000001	{"result": "ok", "code": 0}	2026-04-02 16:04:33.677812	2026-04-02 16:04:33.677812	1	1	1
2	300	404	OUTGOING	PENDING	TRANSFER	MPESA-0002	+254711000002	{"result": "pending", "code": 1}	2026-04-02 16:04:33.677812	2026-04-02 16:04:33.677812	\N	2	2
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.users (id, name, phone_number, email, password_hash, created_at, updated_at, is_active, last_login, last_logout) FROM stdin;
1	Alice User	+254700000001	alice.user@example.com	scrypt:32768:8:1$u7woPdlqzlvNfasm$f64d398e45fcb9a1b7a5a74e8c58cfb237b82bbcc6b63ede686ffaf40753dca6d4182bdcc927a186f84378895d37141b69104577808c09ac6593dd25d5daa5bb	2026-04-02 16:04:33.677812	2026-04-02 16:04:33.677812	t	\N	\N
2	Bob User	+254700000002	bob.user@example.com	scrypt:32768:8:1$2n2Svy4CseNCvQVK$9df83739236b482afa28dc609f9541968d4a8fde09756d0277948f1f202cdae2c1ea44115c9eab8408fc82a4ce5d9c05bb8083f5b595e889c7318f5358861c54	2026-04-02 16:04:33.677812	2026-04-02 16:04:33.677812	t	\N	\N
\.


--
-- Data for Name: vendors; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.vendors (id, name, business_name, business_shortcode, merchant_id, mcc, country_code, currency_code, store_label, email, phone, password_hash, psp_id, psp_name, created_at, updated_at, is_active, last_login, last_logout) FROM stdin;
1	Merchant One	Merchant One Store	123456	MRC001	5411	KE	404	Nairobi CBD	merchant1@example.com	+254711000001	scrypt:32768:8:1$7FVkcTHQFiARy2ET$295e7a349ee58505347c0dafd19dde262193a1a0365744c3dd548ebf8628f5437b4ef2a0e9f53ffff5c2652ce4c002ac8501849f1bd5ce5cfb4488fcc774fed4	PSP001	Demo PSP	2026-04-02 16:04:33.677812	2026-04-02 16:04:33.677812	t	\N	\N
2	Merchant Two	Merchant Two Shop	654321	MRC002	5812	KE	404	Westlands	merchant2@example.com	+254711000002	scrypt:32768:8:1$m5R11T1pmnTisxfN$2529b2d50ba375c3cbdf7f9112781c8672270d280afe29c58d2bd60884738fa24d2bbbfb2138d48bf8385e8b1922a4c5738728fe677a9acec2005ea4a906cd0c	PSP002	Demo PSP	2026-04-02 16:04:33.677812	2026-04-02 16:04:33.677812	t	\N	\N
\.


--
-- Name: payment_sessions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.payment_sessions_id_seq', 1, false);


--
-- Name: qr_codes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.qr_codes_id_seq', 1, false);


--
-- Name: scanlogs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.scanlogs_id_seq', 1, false);


--
-- Name: transactions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.transactions_id_seq', 1, false);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.users_id_seq', 1, false);


--
-- Name: vendors_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.vendors_id_seq', 1, false);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: payment_sessions payment_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_sessions
    ADD CONSTRAINT payment_sessions_pkey PRIMARY KEY (id);


--
-- Name: qr_codes qr_codes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qr_codes
    ADD CONSTRAINT qr_codes_pkey PRIMARY KEY (id);


--
-- Name: scanlogs scanlogs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scanlogs
    ADD CONSTRAINT scanlogs_pkey PRIMARY KEY (id);


--
-- Name: transactions transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_pkey PRIMARY KEY (id);


--
-- Name: users uq_user_email; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT uq_user_email UNIQUE (email);


--
-- Name: users uq_user_phone_number; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT uq_user_phone_number UNIQUE (phone_number);


--
-- Name: vendors uq_vendor_business_shortcode; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors
    ADD CONSTRAINT uq_vendor_business_shortcode UNIQUE (business_shortcode);


--
-- Name: vendors uq_vendor_email; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors
    ADD CONSTRAINT uq_vendor_email UNIQUE (email);


--
-- Name: vendors uq_vendor_phone; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors
    ADD CONSTRAINT uq_vendor_phone UNIQUE (phone);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: vendors vendors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors
    ADD CONSTRAINT vendors_pkey PRIMARY KEY (id);


--
-- Name: ix_transactions_mpesa_receipt; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transactions_mpesa_receipt ON public.transactions USING btree (mpesa_receipt);


--
-- Name: payment_sessions payment_sessions_qr_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_sessions
    ADD CONSTRAINT payment_sessions_qr_id_fkey FOREIGN KEY (qr_id) REFERENCES public.qr_codes(id);


--
-- Name: payment_sessions payment_sessions_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_sessions
    ADD CONSTRAINT payment_sessions_transaction_id_fkey FOREIGN KEY (transaction_id) REFERENCES public.transactions(id);


--
-- Name: payment_sessions payment_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_sessions
    ADD CONSTRAINT payment_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: qr_codes qr_codes_vendor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qr_codes
    ADD CONSTRAINT qr_codes_vendor_id_fkey FOREIGN KEY (vendor_id) REFERENCES public.vendors(id);


--
-- Name: scanlogs scanlogs_qr_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scanlogs
    ADD CONSTRAINT scanlogs_qr_id_fkey FOREIGN KEY (qr_id) REFERENCES public.qr_codes(id);


--
-- Name: scanlogs scanlogs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scanlogs
    ADD CONSTRAINT scanlogs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: transactions transactions_qrcode_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_qrcode_id_fkey FOREIGN KEY (qrcode_id) REFERENCES public.qr_codes(id);


--
-- Name: transactions transactions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: transactions transactions_vendor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_vendor_id_fkey FOREIGN KEY (vendor_id) REFERENCES public.vendors(id);


--
-- PostgreSQL database dump complete
--

\unrestrict Ga92wzyp317tGqWZu1k21YFGgosgIhN8bxb3nNzdDght3BAGNh8wvyeVnoXoGbG

