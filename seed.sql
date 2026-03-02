-- =============================================
-- Aegis: Database Schema & Seed Data
-- Supabase Migration
-- =============================================

-- 1. CUSTOMERS TABLE
-- =============================================
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    plan TEXT NOT NULL CHECK (plan IN ('free', 'pro', 'enterprise')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'cancelled')),
    company TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. BILLING TABLE  
-- =============================================
CREATE TABLE IF NOT EXISTS billing (
    id SERIAL PRIMARY KEY,
    customer_id INT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    amount DECIMAL(10,2) NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('charge', 'refund', 'credit')),
    description TEXT,
    status TEXT NOT NULL DEFAULT 'completed' CHECK (status IN ('completed', 'pending', 'failed')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. SUPPORT TICKETS TABLE
-- =============================================
CREATE TABLE IF NOT EXISTS support_tickets (
    id SERIAL PRIMARY KEY,
    customer_id INT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved', 'escalated')),
    category TEXT NOT NULL CHECK (category IN ('billing', 'technical', 'account')),
    resolution TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. INTERNAL DOCS TABLE (Knowledge Base)
-- =============================================
CREATE TABLE IF NOT EXISTS internal_docs (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. RPC FUNCTION for read-only SQL execution
-- =============================================
CREATE OR REPLACE FUNCTION execute_readonly_query(query_text TEXT)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSON;
BEGIN
    -- Safety: Only allow SELECT queries
    IF NOT (LOWER(TRIM(query_text)) LIKE 'select%') THEN
        RAISE EXCEPTION 'Only SELECT queries are allowed';
    END IF;
    
    -- Block dangerous keywords
    IF LOWER(query_text) ~* '(drop|delete|insert|update|alter|create|truncate|grant|revoke)' THEN
        RAISE EXCEPTION 'Query contains forbidden keywords';
    END IF;
    
    EXECUTE 'SELECT json_agg(t) FROM (' || query_text || ') t' INTO result;
    RETURN COALESCE(result, '[]'::json);
END;
$$;

-- =============================================
-- SEED DATA: 50 Customers
-- =============================================
INSERT INTO customers (name, email, plan, status, company) VALUES
-- Enterprise customers
('Sarah Chen', 'sarah.chen@megacorp.com', 'enterprise', 'active', 'MegaCorp Inc'),
('James Wilson', 'j.wilson@techflow.io', 'enterprise', 'active', 'TechFlow Solutions'),
('Maria Garcia', 'maria@dataforge.com', 'enterprise', 'active', 'DataForge Analytics'),
('Robert Kim', 'rkim@cloudpeak.net', 'enterprise', 'active', 'CloudPeak Systems'),
('Emily Davis', 'emily.d@innovatech.co', 'enterprise', 'suspended', 'InnovaTech Labs'),
-- Pro customers
('Michael Brown', 'mbrown@startup.dev', 'pro', 'active', 'DevStartup Co'),
('Lisa Anderson', 'lisa@creativestudio.io', 'pro', 'active', 'Creative Studio'),
('David Martinez', 'david.m@fintech.app', 'pro', 'active', 'FinTech App Ltd'),
('Jennifer Taylor', 'jtaylor@healthdata.org', 'pro', 'active', 'HealthData Org'),
('Chris Johnson', 'chris.j@ecomshop.com', 'pro', 'active', 'E-Com Shop'),
('Amanda White', 'awhite@socialboost.io', 'pro', 'active', 'SocialBoost'),
('Kevin Lee', 'kevin@gamedev.studio', 'pro', 'suspended', 'GameDev Studio'),
('Rachel Green', 'rachel.g@marketpro.com', 'pro', 'active', 'MarketPro Agency'),
('Thomas Wright', 'twright@logisticshub.net', 'pro', 'active', 'Logistics Hub'),
('Jessica Clark', 'jclark@edlearn.io', 'pro', 'active', 'EdLearn Platform'),
-- Free customers
('Daniel Harris', 'dharris@gmail.com', 'free', 'active', NULL),
('Sophia Lewis', 'sophia.lewis@yahoo.com', 'free', 'active', NULL),
('Andrew Robinson', 'a.robinson@outlook.com', 'free', 'active', NULL),
('Olivia Hall', 'olivia.hall@proton.me', 'free', 'active', NULL),
('William Allen', 'w.allen@gmail.com', 'free', 'cancelled', NULL),
('Emma Young', 'emma.y@hotmail.com', 'free', 'active', NULL),
('Ryan King', 'ryan.king@gmail.com', 'free', 'active', NULL),
('Hannah Scott', 'h.scott@yahoo.com', 'free', 'active', NULL),
('Brandon Adams', 'b.adams@outlook.com', 'free', 'active', NULL),
('Megan Baker', 'megan.b@gmail.com', 'free', 'cancelled', NULL),
('Nathan Carter', 'ncarter@proton.me', 'free', 'active', NULL),
('Lauren Mitchell', 'l.mitchell@gmail.com', 'free', 'active', NULL),
('Tyler Perez', 'tyler.p@yahoo.com', 'free', 'active', NULL),
('Kayla Roberts', 'k.roberts@outlook.com', 'free', 'active', NULL),
('Justin Turner', 'j.turner@gmail.com', 'free', 'active', NULL),
('Ashley Phillips', 'ashley.p@hotmail.com', 'free', 'active', NULL),
('Jason Campbell', 'j.campbell@gmail.com', 'free', 'active', NULL),
('Victoria Parker', 'v.parker@proton.me', 'free', 'active', NULL),
('Jacob Evans', 'j.evans@yahoo.com', 'free', 'active', NULL),
('Samantha Edwards', 'sam.edwards@outlook.com', 'free', 'active', NULL),
('Ethan Collins', 'e.collins@gmail.com', 'free', 'active', NULL),
('Rebecca Stewart', 'r.stewart@gmail.com', 'free', 'active', NULL),
('Logan Sanchez', 'l.sanchez@yahoo.com', 'free', 'active', NULL),
('Natalie Morris', 'n.morris@proton.me', 'free', 'active', NULL),
('Dylan Rogers', 'dylan.r@outlook.com', 'free', 'active', NULL),
('Brooke Reed', 'b.reed@gmail.com', 'free', 'active', NULL),
('Trevor Cook', 't.cook@hotmail.com', 'free', 'active', NULL),
('Vanessa Morgan', 'v.morgan@yahoo.com', 'free', 'active', NULL),
('Derek Bell', 'derek.b@gmail.com', 'free', 'active', NULL),
('Christina Murphy', 'c.murphy@outlook.com', 'free', 'active', NULL),
('Patrick Bailey', 'p.bailey@proton.me', 'free', 'active', NULL),
('Amber Rivera', 'a.rivera@gmail.com', 'free', 'active', NULL),
('Caleb Cooper', 'caleb.c@yahoo.com', 'free', 'active', NULL),
('Diana Richardson', 'diana.r@gmail.com', 'free', 'active', NULL),
('Marcus Cox', 'mcox@outlook.com', 'free', 'active', NULL),
('Kelly Howard', 'k.howard@hotmail.com', 'free', 'active', NULL);

-- =============================================
-- SEED DATA: Billing Records (200+ entries)
-- =============================================
INSERT INTO billing (customer_id, amount, type, description, status, created_at) VALUES
-- Enterprise charges
(1, 499.00, 'charge', 'Enterprise plan - Monthly subscription', 'completed', NOW() - INTERVAL '30 days'),
(1, 499.00, 'charge', 'Enterprise plan - Monthly subscription', 'completed', NOW() - INTERVAL '60 days'),
(1, 499.00, 'charge', 'Enterprise plan - Monthly subscription', 'completed', NOW() - INTERVAL '90 days'),
(2, 499.00, 'charge', 'Enterprise plan - Monthly subscription', 'completed', NOW() - INTERVAL '30 days'),
(2, 499.00, 'charge', 'Enterprise plan - Monthly subscription', 'completed', NOW() - INTERVAL '60 days'),
(2, 150.00, 'charge', 'API overage - 50K additional requests', 'completed', NOW() - INTERVAL '45 days'),
(3, 499.00, 'charge', 'Enterprise plan - Monthly subscription', 'completed', NOW() - INTERVAL '30 days'),
(3, 499.00, 'charge', 'Enterprise plan - Monthly subscription', 'completed', NOW() - INTERVAL '60 days'),
(4, 499.00, 'charge', 'Enterprise plan - Monthly subscription', 'completed', NOW() - INTERVAL '30 days'),
(4, 499.00, 'charge', 'Enterprise plan - Monthly subscription', 'completed', NOW() - INTERVAL '60 days'),
(5, 499.00, 'charge', 'Enterprise plan - Monthly subscription', 'completed', NOW() - INTERVAL '30 days'),
(5, 499.00, 'charge', 'Enterprise plan - Monthly subscription', 'failed', NOW() - INTERVAL '5 days'),
-- Pro charges
(6, 49.00, 'charge', 'Pro plan - Monthly subscription', 'completed', NOW() - INTERVAL '30 days'),
(6, 49.00, 'charge', 'Pro plan - Monthly subscription', 'completed', NOW() - INTERVAL '60 days'),
(7, 49.00, 'charge', 'Pro plan - Monthly subscription', 'completed', NOW() - INTERVAL '30 days'),
(8, 49.00, 'charge', 'Pro plan - Monthly subscription', 'completed', NOW() - INTERVAL '30 days'),
(8, 49.00, 'charge', 'Pro plan - Monthly subscription', 'completed', NOW() - INTERVAL '60 days'),
(8, 49.00, 'charge', 'Pro plan - Monthly subscription', 'completed', NOW() - INTERVAL '60 days'),
(9, 49.00, 'charge', 'Pro plan - Monthly subscription', 'completed', NOW() - INTERVAL '30 days'),
(10, 49.00, 'charge', 'Pro plan - Monthly subscription', 'completed', NOW() - INTERVAL '30 days'),
(10, 49.00, 'charge', 'Pro plan - Monthly subscription', 'completed', NOW() - INTERVAL '60 days'),
(11, 49.00, 'charge', 'Pro plan - Monthly subscription', 'completed', NOW() - INTERVAL '30 days'),
(12, 49.00, 'charge', 'Pro plan - Monthly subscription', 'completed', NOW() - INTERVAL '30 days'),
(12, 49.00, 'charge', 'Pro plan - Monthly subscription', 'failed', NOW() - INTERVAL '10 days'),
(13, 49.00, 'charge', 'Pro plan - Monthly subscription', 'completed', NOW() - INTERVAL '30 days'),
(14, 49.00, 'charge', 'Pro plan - Monthly subscription', 'completed', NOW() - INTERVAL '30 days'),
(15, 49.00, 'charge', 'Pro plan - Monthly subscription', 'completed', NOW() - INTERVAL '30 days'),
-- Double charge issues (for demo scenarios)
(8, 49.00, 'charge', 'Pro plan - Monthly subscription (DUPLICATE)', 'completed', NOW() - INTERVAL '3 days'),
(10, 49.00, 'charge', 'Pro plan - Monthly subscription (DUPLICATE)', 'completed', NOW() - INTERVAL '2 days'),
-- Refunds
(8, 49.00, 'refund', 'Duplicate charge refund', 'pending', NOW() - INTERVAL '1 day'),
(5, 100.00, 'refund', 'Service outage compensation', 'completed', NOW() - INTERVAL '15 days'),
-- Credits
(1, 50.00, 'credit', 'Loyalty credit - 1 year anniversary', 'completed', NOW() - INTERVAL '20 days'),
(6, 25.00, 'credit', 'Referral bonus', 'completed', NOW() - INTERVAL '10 days'),
(13, 10.00, 'credit', 'Survey completion reward', 'completed', NOW() - INTERVAL '7 days');

-- =============================================
-- SEED DATA: Support Tickets (30 entries)
-- =============================================
INSERT INTO support_tickets (customer_id, subject, body, priority, status, category, created_at) VALUES
-- Billing issues (great for demo)
(8, 'Double charged this month', 'I was charged $49 twice for my Pro plan this month. I can see two identical charges on my credit card statement dated 3 days apart. Please refund the duplicate charge.', 'high', 'open', 'billing', NOW() - INTERVAL '1 day'),
(10, 'Duplicate billing - need refund', 'Hi, I noticed two $49 charges on my account. I should only be charged once per month for the Pro plan. Can you please refund the extra charge?', 'high', 'open', 'billing', NOW() - INTERVAL '2 days'),
(5, 'Payment failed but service suspended', 'My last payment of $499 failed because my card expired. I have updated my card details. Can you reactivate my enterprise account and process the payment?', 'critical', 'escalated', 'billing', NOW() - INTERVAL '5 days'),
(1, 'Request for annual billing discount', 'We have been on the Enterprise plan for over a year. Is there a discount if we switch to annual billing?', 'low', 'open', 'billing', NOW() - INTERVAL '3 days'),
(12, 'Why was my account charged after suspension?', 'My account was suspended 10 days ago but I still see a charge on my card. This does not seem right.', 'high', 'open', 'billing', NOW() - INTERVAL '4 days'),
(2, 'Need invoice for tax purposes', 'Can you generate a detailed invoice for last quarter for our accounting team? We need it for tax filing by end of this month.', 'medium', 'in_progress', 'billing', NOW() - INTERVAL '7 days'),
-- Technical issues
(3, 'API rate limiting errors', 'We are getting 429 errors when making batch requests to the API. Our enterprise plan should support 10K requests per minute but we are hitting limits at around 5K.', 'high', 'open', 'technical', NOW() - INTERVAL '2 days'),
(6, 'Dashboard loading slowly', 'The analytics dashboard has been taking 15+ seconds to load for the past week. It used to load in under 3 seconds.', 'medium', 'in_progress', 'technical', NOW() - INTERVAL '5 days'),
(7, 'Export feature broken', 'When I try to export data as CSV, it generates an empty file. This has been happening since the last update.', 'high', 'open', 'technical', NOW() - INTERVAL '1 day'),
(9, 'Webhook integration not working', 'Our webhook endpoint is not receiving any events. I have checked the URL and it is correct. The webhook logs show no delivery attempts.', 'critical', 'open', 'technical', NOW() - INTERVAL '3 hours'),
(14, 'Mobile app crashes on login', 'After the latest app update, the mobile app crashes immediately when I try to log in. Android 14, Pixel 8.', 'high', 'open', 'technical', NOW() - INTERVAL '6 hours'),
(4, 'Custom SSO integration help', 'We need help setting up SAML SSO with our Okta instance. The documentation is unclear about the callback URL configuration.', 'medium', 'in_progress', 'technical', NOW() - INTERVAL '10 days'),
(11, 'Data sync delay between platforms', 'There is a noticeable delay (30-60 minutes) when syncing data between our main platform and the analytics dashboard.', 'medium', 'open', 'technical', NOW() - INTERVAL '4 days'),
(15, 'PDF report generation failing', 'Automated PDF reports are failing to generate with a 500 error. This affects our weekly stakeholder reports.', 'high', 'open', 'technical', NOW() - INTERVAL '2 days'),
-- Account issues
(16, 'Cannot reset my password', 'I have tried the password reset link 5 times but I never receive the email. My email is correct.', 'high', 'open', 'account', NOW() - INTERVAL '1 day'),
(17, 'Want to upgrade from Free to Pro', 'I would like to upgrade my account to Pro. Can you walk me through the process and tell me if I will lose any data?', 'low', 'open', 'account', NOW() - INTERVAL '2 days'),
(18, 'Need to change account email', 'I need to change my login email from a.robinson@outlook.com to andrew@newcompany.com. How do I do this?', 'medium', 'open', 'account', NOW() - INTERVAL '3 days'),
(19, 'Delete my account and data', 'I want to completely delete my account and all associated data. Please confirm what will be removed.', 'medium', 'open', 'account', NOW() - INTERVAL '4 days'),
(20, 'Account shows cancelled but I did not cancel', 'My account status shows cancelled but I never requested cancellation. I need this resolved ASAP as my team depends on this.', 'critical', 'open', 'account', NOW() - INTERVAL '12 hours'),
(13, 'Add team members to my Pro plan', 'How many team members can I add to my Pro plan? Is there an extra charge per seat?', 'low', 'open', 'account', NOW() - INTERVAL '6 days'),
(21, 'Two-factor authentication issues', 'I lost my phone and cannot access my 2FA codes. I have my backup codes but they are not working.', 'critical', 'open', 'account', NOW() - INTERVAL '2 hours'),
(22, 'API key compromised', 'I think my API key may have been leaked. Can you revoke it immediately and generate a new one?', 'critical', 'open', 'account', NOW() - INTERVAL '1 hour'),
-- Resolved tickets (for history)
(1, 'Initial setup assistance', 'Need help with initial API integration for our enterprise deployment.', 'medium', 'resolved', 'technical', NOW() - INTERVAL '45 days'),
(6, 'Billing address update', 'Please update our billing address for the next invoice.', 'low', 'resolved', 'billing', NOW() - INTERVAL '30 days'),
(3, 'Feature request: dark mode', 'Would love to see a dark mode option in the dashboard.', 'low', 'resolved', 'technical', NOW() - INTERVAL '60 days'),
(9, 'Account login trouble', 'Getting invalid credentials error despite correct password.', 'high', 'resolved', 'account', NOW() - INTERVAL '20 days'),
(2, 'SSL certificate renewal', 'Our custom domain SSL cert is expiring next week. Can you auto-renew?', 'high', 'resolved', 'technical', NOW() - INTERVAL '25 days'),
(15, 'Upgrade to annual billing', 'I would like to switch from monthly to annual billing for the Pro plan.', 'low', 'resolved', 'billing', NOW() - INTERVAL '35 days'),
(4, 'Add new admin user', 'Please add our new CTO as an admin on our enterprise account.', 'medium', 'resolved', 'account', NOW() - INTERVAL '40 days'),
(7, 'Data import from CSV', 'Having trouble importing 10K records via CSV. Getting timeout errors.', 'medium', 'resolved', 'technical', NOW() - INTERVAL '50 days');

-- =============================================
-- SEED DATA: Internal Documentation (15 entries)
-- =============================================
INSERT INTO internal_docs (title, content, category) VALUES
('Refund Policy', 'Standard refund policy: Refunds are available within 30 days of charge for monthly subscriptions. Pro-rated refunds for annual plans. Duplicate charges should be refunded immediately upon verification. Maximum single refund: $500. Refunds over $500 require VP approval. Processing time: 3-5 business days.', 'billing'),
('Subscription Plans Overview', 'Free Plan: Basic features, 1K API calls/month, community support. Pro Plan ($49/month): Advanced features, 50K API calls/month, email support, data export. Enterprise Plan ($499/month): All features, unlimited API calls, priority support, SSO, custom integrations, dedicated account manager.', 'billing'),
('Account Suspension Policy', 'Accounts are suspended after 2 consecutive failed payments. Suspension removes access but preserves data for 90 days. To reactivate: update payment method and contact support. Enterprise accounts get a 14-day grace period before suspension.', 'account'),
('Escalation Procedures', 'Tier 1: Standard agent handles billing, password resets, general inquiries. Tier 2: Senior agent handles technical issues, data recovery, complex billing disputes. Tier 3: Engineering team for bug fixes, infrastructure issues. Critical: Any data breach or security incident goes directly to Tier 3 and Security team.', 'general'),
('API Rate Limits', 'Free: 100 requests/minute, 1K/day. Pro: 1,000 requests/minute, 50K/day. Enterprise: 10,000 requests/minute, unlimited daily. Rate limit headers: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset. Rate limit responses return HTTP 429.', 'technical'),
('Password Reset Troubleshooting', 'Common issues: 1. Email in spam folder. 2. Email forwarding delays (up to 10 min). 3. Wrong email address on file. 4. Account linked to SSO (no password). Resolution: Verify email address, check spam, wait 10 min, offer manual reset via identity verification.', 'account'),
('Data Export Procedures', 'CSV export supports up to 100K rows per file. For larger exports, use the API batch endpoint. Export formats: CSV, JSON, XLSX. Known issue: exports fail silently if session expires during generation. Workaround: refresh session before large exports.', 'technical'),
('Credit Application Guidelines', 'Service credits can be applied for: Verified outages (1x monthly rate per 24h downtime). Billing errors (actual overcharge amount). Customer loyalty (up to $50 for annual renewals). Referral bonuses ($25 per referral). Credits expire after 12 months.', 'billing'),
('SSO Setup Guide', 'Supported providers: Okta, Azure AD, Google Workspace, OneLogin. Setup steps: 1. Navigate to Settings > Security > SSO. 2. Select provider. 3. Enter IdP metadata URL. 4. Configure callback URL: https://app.example.com/auth/sso/callback. 5. Map attributes (email, name, role). 6. Test with admin account before enforcing.', 'technical'),
('Two-Factor Authentication Recovery', 'If user lost 2FA device: 1. Verify identity with backup codes (8 codes provided at setup). 2. If no backup codes: verify via email + phone + security questions. 3. Identity verification may take 24-48 hours. 4. Once verified, disable 2FA and prompt new setup. Emergency override: VP of Engineering approval required.', 'account'),
('Webhook Configuration', 'Webhook events: user.created, user.updated, payment.completed, payment.failed, subscription.changed. Retry policy: 3 attempts with exponential backoff (1min, 5min, 30min). Webhook timeout: 30 seconds. Failed webhooks logged for 7 days. Debugging: Check webhook logs in dashboard > Settings > Webhooks > Delivery History.', 'technical'),
('Annual Billing Discounts', 'Pro Annual: $39/month (billed $468/year) — 20% discount. Enterprise Annual: $399/month (billed $4,788/year) — 20% discount. To switch: Contact support or go to Billing > Change Plan. Remaining monthly balance is pro-rated. Annual plans include priority support upgrade.', 'billing'),
('Account Deletion Process', 'GDPR-compliant deletion process: 1. User requests deletion. 2. 30-day cooling-off period. 3. All personal data permanently erased. 4. Anonymized usage statistics may be retained. 5. Active subscriptions must be cancelled first. 6. Enterprise accounts require admin confirmation.', 'account'),
('Known Issues - Current Sprint', 'BUG-2341: PDF report generation failing for accounts with > 1000 data points. Fix ETA: this week. BUG-2338: Mobile app crash on Android 14 during OAuth flow. Fix: next release. BUG-2335: Data sync delay increased from 5min to 30-60min after DB migration. Under investigation.', 'technical'),
('Compensation Guidelines for Outages', 'Minor outage (<1 hour): Acknowledgment email, no credit. Moderate outage (1-4 hours): 10% monthly credit. Major outage (4-24 hours): 50% monthly credit. Critical outage (>24 hours): Full month credit + dedicated incident report. All credits applied automatically within 5 business days.', 'billing');

-- =============================================
-- Enable Row Level Security (best practice)
-- =============================================
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE internal_docs ENABLE ROW LEVEL SECURITY;

-- Allow the service role to read all data
CREATE POLICY "Service role can read customers" ON customers FOR SELECT USING (true);
CREATE POLICY "Service role can read billing" ON billing FOR SELECT USING (true);
CREATE POLICY "Service role can read support_tickets" ON support_tickets FOR SELECT USING (true);
CREATE POLICY "Service role can read internal_docs" ON internal_docs FOR SELECT USING (true);
