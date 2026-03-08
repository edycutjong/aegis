-- =============================================
-- Aegis: Full Reset — Drop all tables, functions & policies
-- Run this to wipe the schema entirely, then re-run seed.sql
-- =============================================

-- 1. Drop RLS policies (must drop before tables)
DROP POLICY IF EXISTS "Service role can read customers"       ON customers;
DROP POLICY IF EXISTS "Service role can read billing"         ON billing;
DROP POLICY IF EXISTS "Service role can read support_tickets" ON support_tickets;
DROP POLICY IF EXISTS "Service role can read internal_docs"   ON internal_docs;

-- 2. Drop the read-only RPC function
DROP FUNCTION IF EXISTS execute_readonly_query(TEXT);

-- 3. Drop tables in reverse FK dependency order
DROP TABLE IF EXISTS support_tickets CASCADE;
DROP TABLE IF EXISTS billing         CASCADE;
DROP TABLE IF EXISTS internal_docs   CASCADE;
DROP TABLE IF EXISTS customers       CASCADE;
