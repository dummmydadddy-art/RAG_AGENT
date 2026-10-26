-- Supabase Database Security & Performance Remediation Patch
-- Run this script in the Supabase SQL Editor (https://supabase.com/dashboard) for your project

-- 1. Fix RLS Disabled errors on live session tables
ALTER TABLE IF EXISTS public.live_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.live_chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.live_session_raised_hands ENABLE ROW LEVEL SECURITY;

-- 2. Fix Function Search Path Mutable warning
-- Sets the search path explicitly to prevent search path hijacking of security definer functions
ALTER FUNCTION public.handle_new_user() SET search_path = public, pg_catalog, pg_temp;

-- 3. Fix Public Can Execute SECURITY DEFINER Function warnings
-- Revokes execute rights from anon and authenticated roles on the handle_new_user profile sync trigger function
REVOKE EXECUTE ON FUNCTION public.handle_new_user() FROM public;
REVOKE EXECUTE ON FUNCTION public.handle_new_user() FROM anon;
REVOKE EXECUTE ON FUNCTION public.handle_new_user() FROM authenticated;

-- (Optional) If you want to satisfy the "RLS Enabled No Policy" INFO lints, 
-- you can define a default fallback "deny all" policy on all tables. 
-- However, enabling RLS without policies naturally defaults to denying all public/authenticated access 
-- which is already highly secure, while allowing your PHP backend (running as service_role) full access.
