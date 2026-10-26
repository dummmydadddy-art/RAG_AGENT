-- Supabase PostgreSQL database schema for LMS
-- This script sets up the 24 tables, relationships, and triggers.

-- Enable UUID extension if not enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop tables in reverse dependency order if they exist
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP FUNCTION IF EXISTS public.handle_new_user();

DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS timetable CASCADE;
DROP TABLE IF EXISTS certificates CASCADE;
DROP TABLE IF EXISTS payment_transactions CASCADE;
DROP TABLE IF EXISTS fee_records CASCADE;
DROP TABLE IF EXISTS notifications CASCADE;
DROP TABLE IF EXISTS exam_results CASCADE;
DROP TABLE IF EXISTS coding_submissions CASCADE;
DROP TABLE IF EXISTS coding_questions CASCADE;
DROP TABLE IF EXISTS mcq_options CASCADE;
DROP TABLE IF EXISTS mcq_questions CASCADE;
DROP TABLE IF EXISTS exams CASCADE;
DROP TABLE IF EXISTS assignment_submissions CASCADE;
DROP TABLE IF EXISTS assignments CASCADE;
DROP TABLE IF EXISTS materials CASCADE;
DROP TABLE IF EXISTS attendance CASCADE;
DROP TABLE IF EXISTS student_batches CASCADE;
DROP TABLE IF EXISTS student_courses CASCADE;
DROP TABLE IF EXISTS batches CASCADE;
DROP TABLE IF EXISTS courses CASCADE;
DROP TABLE IF EXISTS students CASCADE;
DROP TABLE IF EXISTS teachers CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS roles CASCADE;

-- 1. Roles table
CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);

-- Populate roles
INSERT INTO roles (id, name) VALUES 
(1, 'SUPER_ADMIN'),
(2, 'TEACHER'),
(3, 'STUDENT')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name;

-- 2. Users table (linked to Supabase auth.users)
CREATE TABLE users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    role_id INT NOT NULL REFERENCES roles(id),
    status VARCHAR(20) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Teachers table (profile information)
CREATE TABLE teachers (
    id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    full_name VARCHAR(255) NOT NULL,
    mobile_number VARCHAR(20),
    email VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 4. Students table (profile information)
CREATE TABLE students (
    id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    full_name VARCHAR(255) NOT NULL,
    mobile_number VARCHAR(20),
    email VARCHAR(255) NOT NULL,
    address TEXT,
    admission_date DATE DEFAULT CURRENT_DATE NOT NULL,
    fee_amount NUMERIC(10,2) DEFAULT 0.00 NOT NULL,
    fee_paid NUMERIC(10,2) DEFAULT 0.00 NOT NULL,
    fee_pending NUMERIC(10,2) DEFAULT 0.00 NOT NULL,
    status VARCHAR(20) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 5. Courses table
CREATE TABLE courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_name VARCHAR(255) NOT NULL,
    course_code VARCHAR(50) UNIQUE NOT NULL,
    course_description TEXT,
    duration VARCHAR(100) NOT NULL,
    fees NUMERIC(10,2) NOT NULL,
    teacher_id UUID REFERENCES teachers(id) ON DELETE SET NULL,
    certificate_enabled BOOLEAN DEFAULT TRUE NOT NULL,
    status VARCHAR(20) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 6. Batches table
CREATE TABLE batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_name VARCHAR(255) NOT NULL,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    teacher_id UUID REFERENCES teachers(id) ON DELETE SET NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    batch_timing VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 7. Student courses relationship table
CREATE TABLE student_courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT unique_student_course UNIQUE (student_id, course_id)
);

-- 8. Student batches relationship table
CREATE TABLE student_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    batch_id UUID NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT unique_student_batch UNIQUE (student_id, batch_id)
);

-- 9. Attendance table
CREATE TABLE attendance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    batch_id UUID NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('PRESENT', 'ABSENT')),
    marked_by UUID REFERENCES teachers(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT unique_student_batch_date UNIQUE (student_id, batch_id, date)
);

-- 10. Materials table (videos, PDFs, notes, assignments, practice questions)
CREATE TABLE materials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    file_name VARCHAR(255) NOT NULL,
    file_url TEXT NOT NULL,
    file_type VARCHAR(50) NOT NULL, -- 'video', 'pdf', 'notes', 'assignment', 'practice'
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    batch_id UUID NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    uploaded_by UUID REFERENCES teachers(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 11. Assignments table
CREATE TABLE assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    file_name VARCHAR(255),
    file_url TEXT,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    batch_id UUID NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    due_date TIMESTAMP WITH TIME ZONE NOT NULL,
    uploaded_by UUID REFERENCES teachers(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 12. Assignment submissions table
CREATE TABLE assignment_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id UUID NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_url TEXT NOT NULL,
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    score NUMERIC(5,2),
    feedback TEXT,
    evaluated_by UUID REFERENCES teachers(id) ON DELETE SET NULL,
    status VARCHAR(20) DEFAULT 'SUBMITTED' CHECK (status IN ('SUBMITTED', 'EVALUATED')),
    CONSTRAINT unique_student_assignment UNIQUE (assignment_id, student_id)
);

-- 13. Exams table
CREATE TABLE exams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    exam_type VARCHAR(20) NOT NULL CHECK (exam_type IN ('MCQ', 'CODING')),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    batch_id UUID NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    time_limit_minutes INT NOT NULL,
    due_date TIMESTAMP WITH TIME ZONE NOT NULL,
    created_by UUID REFERENCES teachers(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 14. MCQ Questions table
CREATE TABLE mcq_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_id UUID NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    marks NUMERIC(5,2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 15. MCQ Options table
CREATE TABLE mcq_options (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id UUID NOT NULL REFERENCES mcq_questions(id) ON DELETE CASCADE,
    option_text TEXT NOT NULL,
    is_correct BOOLEAN DEFAULT FALSE NOT NULL
);

-- 16. Coding Questions table
CREATE TABLE coding_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_id UUID NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    description TEXT,
    max_marks NUMERIC(5,2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 17. Coding Submissions table
CREATE TABLE coding_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_id UUID NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    coding_question_id UUID NOT NULL REFERENCES coding_questions(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    solution_file_name VARCHAR(255) NOT NULL,
    solution_file_url TEXT NOT NULL,
    score NUMERIC(5,2),
    feedback TEXT,
    evaluated_by UUID REFERENCES teachers(id) ON DELETE SET NULL,
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    status VARCHAR(20) DEFAULT 'SUBMITTED' CHECK (status IN ('SUBMITTED', 'EVALUATED')),
    CONSTRAINT unique_student_coding_question UNIQUE (coding_question_id, student_id)
);

-- 18. Exam Results table (aggregate scores for MCQ exams or general exam summaries)
CREATE TABLE exam_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_id UUID NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    score NUMERIC(5,2) NOT NULL,
    max_score NUMERIC(5,2) NOT NULL,
    feedback TEXT,
    evaluated_by UUID REFERENCES teachers(id) ON DELETE SET NULL,
    evaluated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    CONSTRAINT unique_student_exam_result UNIQUE (exam_id, student_id)
);

-- 19. Notifications table
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    sender_id UUID REFERENCES users(id) ON DELETE SET NULL,
    target_type VARCHAR(20) NOT NULL CHECK (target_type IN ('ALL', 'COURSE', 'BATCH', 'INDIVIDUAL_STUDENT', 'INDIVIDUAL_TEACHER')),
    target_id UUID, -- References course_id, batch_id, student_id, or teacher_id
    notification_type VARCHAR(20) NOT NULL CHECK (notification_type IN ('ANNOUNCEMENT', 'EXAM', 'LECTURE', 'ASSIGNMENT', 'GENERAL')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 20. Fee Records table
CREATE TABLE fee_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    total_amount NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    paid_amount NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    pending_amount NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PARTIAL', 'PAID')),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT unique_fee_record_student UNIQUE (student_id)
);

-- 21. Payment Transactions table
CREATE TABLE payment_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    amount NUMERIC(10,2) NOT NULL,
    payment_method VARCHAR(20) NOT NULL CHECK (payment_method IN ('CASH', 'ONLINE')),
    payment_status VARCHAR(20) NOT NULL CHECK (payment_status IN ('SUCCESS', 'FAILED', 'PENDING')),
    transaction_id VARCHAR(100),
    invoice_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 22. Certificates table
CREATE TABLE certificates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    completion_date DATE NOT NULL DEFAULT CURRENT_DATE,
    certificate_id VARCHAR(100) UNIQUE NOT NULL,
    qr_code_url TEXT,
    verification_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT unique_student_course_cert UNIQUE (student_id, course_id)
);

-- 23. Timetable table
CREATE TABLE timetable (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    day_of_week VARCHAR(20) NOT NULL CHECK (day_of_week IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')),
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    topic VARCHAR(255) NOT NULL,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    batch_id UUID NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    teacher_id UUID REFERENCES teachers(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 24. Audit logs table
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(255) NOT NULL,
    details TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Setup index structures for performance
CREATE INDEX idx_users_role_id ON users(role_id);
CREATE INDEX idx_courses_teacher_id ON courses(teacher_id);
CREATE INDEX idx_batches_course_id ON batches(course_id);
CREATE INDEX idx_batches_teacher_id ON batches(teacher_id);
CREATE INDEX idx_attendance_student_id ON attendance(student_id);
CREATE INDEX idx_attendance_batch_id ON attendance(batch_id);
CREATE INDEX idx_materials_course_batch ON materials(course_id, batch_id);
CREATE INDEX idx_assignments_course_batch ON assignments(course_id, batch_id);
CREATE INDEX idx_assignment_submissions_student ON assignment_submissions(student_id);
CREATE INDEX idx_exams_course_batch ON exams(course_id, batch_id);
CREATE INDEX idx_exam_results_student ON exam_results(student_id);
CREATE INDEX idx_notifications_target ON notifications(target_type, target_id);
CREATE INDEX idx_fee_records_student ON fee_records(student_id);
CREATE INDEX idx_payment_transactions_student ON payment_transactions(student_id);
CREATE INDEX idx_timetable_batch ON timetable(batch_id);

-- Profile Sync Function and Trigger
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
    assigned_role_id INT;
    meta_full_name VARCHAR(255);
    meta_mobile VARCHAR(20);
    meta_address TEXT;
    meta_fee_amount NUMERIC(10,2);
BEGIN
    -- Extract values from raw user metadata, default role_id is 3 (STUDENT)
    assigned_role_id := COALESCE((new.raw_user_meta_data->>'role_id')::int, 3);
    meta_full_name := COALESCE(new.raw_user_meta_data->>'full_name', split_part(new.email, '@', 1));
    meta_mobile := COALESCE(new.raw_user_meta_data->>'mobile_number', '');
    meta_address := COALESCE(new.raw_user_meta_data->>'address', '');
    meta_fee_amount := COALESCE((new.raw_user_meta_data->>'fee_amount')::numeric, 0.00);

    -- Insert profile row
    INSERT INTO public.users (id, email, role_id, status)
    VALUES (new.id, new.email, assigned_role_id, 'ACTIVE');

    -- Insert into respective profile table
    IF assigned_role_id = 1 THEN
        -- Super Admin doesn't need separate detailed table, profile in users is enough.
        NULL;
    ELSIF assigned_role_id = 2 THEN
        INSERT INTO public.teachers (id, full_name, email, mobile_number, status)
        VALUES (new.id, meta_full_name, new.email, meta_mobile, 'ACTIVE');
    ELSIF assigned_role_id = 3 THEN
        INSERT INTO public.students (id, full_name, email, mobile_number, address, fee_amount, fee_paid, fee_pending, status)
        VALUES (new.id, meta_full_name, new.email, meta_mobile, meta_address, meta_fee_amount, 0.00, meta_fee_amount, 'ACTIVE');
        
        -- Create initial fee record
        INSERT INTO public.fee_records (student_id, total_amount, paid_amount, pending_amount, status)
        VALUES (new.id, meta_fee_amount, 0.00, meta_fee_amount, 'PENDING');
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 25. Live Sessions table
CREATE TABLE IF NOT EXISTS public.live_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID NOT NULL REFERENCES public.courses(id) ON DELETE CASCADE,
    batch_id UUID NOT NULL REFERENCES public.batches(id) ON DELETE CASCADE,
    teacher_id UUID NOT NULL REFERENCES public.teachers(id) ON DELETE CASCADE,
    session_type VARCHAR(50) NOT NULL CHECK (session_type IN ('LIVE', 'RECORDED_AS_LIVE')),
    message TEXT,
    meeting_link TEXT,
    video_link TEXT,
    chat_enabled BOOLEAN DEFAULT TRUE NOT NULL,
    raise_hand_enabled BOOLEAN DEFAULT TRUE NOT NULL,
    scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(20) DEFAULT 'SCHEDULED' CHECK (status IN ('SCHEDULED', 'ACTIVE', 'COMPLETED')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 26. Live Chat Messages table
CREATE TABLE IF NOT EXISTS public.live_chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES public.live_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    sender_name VARCHAR(255) NOT NULL,
    sender_role VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 27. Live Session Raised Hands table
CREATE TABLE IF NOT EXISTS public.live_session_raised_hands (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES public.live_sessions(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES public.students(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'RAISED' CHECK (status IN ('RAISED', 'RESOLVED')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT unique_session_student_hand UNIQUE (session_id, student_id)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_live_sessions_batch ON public.live_sessions(batch_id);
CREATE INDEX IF NOT EXISTS idx_live_chat_messages_session ON public.live_chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_live_session_raised_hands_session ON public.live_session_raised_hands(session_id);

-- 28. Add columns for Voice Message Feature
ALTER TABLE public.live_sessions ADD COLUMN IF NOT EXISTS voice_enabled BOOLEAN DEFAULT TRUE NOT NULL;
ALTER TABLE public.live_chat_messages ADD COLUMN IF NOT EXISTS message_type VARCHAR(10) DEFAULT 'TEXT' NOT NULL CHECK (message_type IN ('TEXT', 'VOICE'));
ALTER TABLE public.live_chat_messages ADD COLUMN IF NOT EXISTS voice_url TEXT;

