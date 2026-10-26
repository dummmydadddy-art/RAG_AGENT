<?php
// LMS Main Router & Controller
ini_set('display_errors', '0');
error_reporting(E_ALL);
file_put_contents(__DIR__ . '/api_debug.log', date('Y-m-d H:i:s') . ' ' . ($_SERVER['REQUEST_METHOD'] ?? '') . ' ' . ($_SERVER['REQUEST_URI'] ?? '') . "\n", FILE_APPEND);

require_once 'config.php';
require_once 'db.php';
require_once 'rag_service.php';
require_once 'rag_safety_boundary.php';
require_once 'rag_query_condenser.php';
require_once 'document_extractor.php';
require_once 'auth_middleware.php';
require_once 'payment.php';

// Helper function to resolve Auth requests in database.php
function supabaseCreateUser($email, $password, $metadata = []) {
    $body = [
        'email' => $email,
        'password' => $password,
        'email_confirm' => true,
        'user_metadata' => $metadata
    ];
    
    // Call Supabase Auth Admin API
    global $SUPABASE_PROJECT_URL;
    $authUrl = rtrim($SUPABASE_PROJECT_URL, '/') . "/auth/v1/admin/users";
    global $SUPABASE_SERVICE_ROLE_KEY;
    
    $ch = curl_init($authUrl);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'POST');
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($body));
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        "apikey: " . $SUPABASE_SERVICE_ROLE_KEY,
        "Authorization: Bearer " . $SUPABASE_SERVICE_ROLE_KEY,
        "Content-Type: application/json"
    ]);
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    $decoded = json_decode($response, true);
    return [
        'success' => ($httpCode >= 200 && $httpCode < 300),
        'status' => $httpCode,
        'data' => $decoded,
        'error' => ($httpCode >= 300) ? ($decoded['message'] ?? $response) : null
    ];
}

function supabaseDeleteUser($userId) {
    global $SUPABASE_SERVICE_ROLE_KEY;
    global $SUPABASE_PROJECT_URL;
    $authUrl = rtrim($SUPABASE_PROJECT_URL, '/') . "/auth/v1/admin/users/" . $userId;
    
    $ch = curl_init($authUrl);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'DELETE');
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        "apikey: " . $SUPABASE_SERVICE_ROLE_KEY,
        "Authorization: Bearer " . $SUPABASE_SERVICE_ROLE_KEY,
        "Content-Type: application/json"
    ]);
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    return [
        'success' => ($httpCode >= 200 && $httpCode < 300),
        'status' => $httpCode,
        'error' => ($httpCode >= 300) ? $response : null
    ];
}

function supabaseUpdateAuthUser($userId, $data) {
    global $SUPABASE_SERVICE_ROLE_KEY;
    global $SUPABASE_PROJECT_URL;
    $authUrl = rtrim($SUPABASE_PROJECT_URL, '/') . "/auth/v1/admin/users/" . $userId;
    
    $ch = curl_init($authUrl);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'PUT');
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        "apikey: " . $SUPABASE_SERVICE_ROLE_KEY,
        "Authorization: Bearer " . $SUPABASE_SERVICE_ROLE_KEY,
        "Content-Type: application/json"
    ]);
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    $decoded = json_decode($response, true);
    return [
        'success' => ($httpCode >= 200 && $httpCode < 300),
        'status' => $httpCode,
        'data' => $decoded,
        'error' => ($httpCode >= 300) ? ($decoded['message'] ?? $response) : null
    ];
}

// Extract request path and method
$requestUri = $_SERVER['REQUEST_URI'];
$requestPath = parse_url($requestUri, PHP_URL_PATH);
$method = $_SERVER['REQUEST_METHOD'];

// Get relative path of routing
$scriptName = $_SERVER['SCRIPT_NAME'];
$basePath = dirname($scriptName);
$route = substr($requestPath, strlen($basePath));
$route = '/' . ltrim($route, '/');

// Read input body
$inputJSON = file_get_contents('php://input');
$input = json_decode($inputJSON, true) ?: [];

// Clean empty string UUID columns to prevent database validation errors
if (isset($input['id']) && $input['id'] === '') {
    unset($input['id']);
}
foreach (['teacher_id', 'course_id', 'batch_id', 'student_id', 'assignment_id', 'exam_id', 'question_id'] as $key) {
    if (isset($input[$key]) && $input[$key] === '') {
        $input[$key] = null;
    }
}

// Router Switcher
try {
    switch (true) {
        // --- PUBLIC ROUTE: Check User Existence ---
        case ($route === '/api/auth/check-user' && $method === 'POST'):
            $email = $input['email'] ?? '';
            if (empty($email)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing email']);
                break;
            }
            
            $res = supabaseSelect('users', 'id', ['email' => 'eq.' . $email]);
            $exists = false;
            if ($res['success'] && !empty($res['data'])) {
                $exists = true;
            }
            echo json_encode(['success' => true, 'exists' => $exists]);
            break;

        // --- PUBLIC ROUTE: Request Forgot Password OTP ---
        case ($route === '/api/auth/forgot-password' && $method === 'POST'):
            $email = $input['email'] ?? '';
            if (empty($email)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Email is required']);
                break;
            }

            // 1. Check if user exists
            $userRes = supabaseSelect('users', 'id', ['email' => 'eq.' . $email], true);
            if (!$userRes['success'] || empty($userRes['data'])) {
                http_response_code(404);
                echo json_encode(['success' => false, 'error' => 'User with this ID does not exist']);
                break;
            }

            // 2. Generate random 6-digit OTP
            $otp = strval(rand(100000, 999999));
            $expiresAt = time() + 300; // 5 minutes validity

            // 3. Save to local otps.json cache file
            $otpFile = __DIR__ . '/otps.json';
            $otps = [];
            if (file_exists($otpFile)) {
                $otps = json_decode(file_get_contents($otpFile), true) ?: [];
            }
            $otps[$email] = [
                'otp' => $otp,
                'expires_at' => $expiresAt
            ];
            file_put_contents($otpFile, json_encode($otps, JSON_PRETTY_PRINT));

            // 4. Log OTP to last_otp.txt for development testing
            file_put_contents(__DIR__ . '/last_otp.txt', $otp);

            // 5. Try to send email
            $subject = "LMS Password Reset OTP";
            $message = "Your verification OTP is: " . $otp . "\nThis OTP is valid for 5 minutes.";
            $headers = "From: noreply@lms.com\r\nReply-To: noreply@lms.com\r\n";
            $headers .= "Content-Type: text/plain; charset=UTF-8\r\n";
            $mailSent = @mail($email, $subject, $message, $headers, "-f noreply@lms.com");

            echo json_encode([
                'success' => true,
                'message' => 'OTP has been sent to your email.'
            ]);
            break;

        // --- PUBLIC ROUTE: Verify Forgot Password OTP ---
        case ($route === '/api/auth/verify-otp' && $method === 'POST'):
            $email = $input['email'] ?? '';
            $otp = $input['otp'] ?? '';
            if (empty($email) || empty($otp)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Email and OTP are required']);
                break;
            }

            $otpFile = __DIR__ . '/otps.json';
            $otps = [];
            if (file_exists($otpFile)) {
                $otps = json_decode(file_get_contents($otpFile), true) ?: [];
            }

            if (!isset($otps[$email])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'No active OTP request found for this email']);
                break;
            }

            $otpData = $otps[$email];
            if ($otpData['otp'] !== $otp) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Invalid OTP code entered']);
                break;
            }

            if (time() > $otpData['expires_at']) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'OTP code has expired']);
                break;
            }

            echo json_encode(['success' => true, 'message' => 'OTP verified successfully']);
            break;

        // --- PUBLIC ROUTE: Reset Password with Verified OTP ---
        case ($route === '/api/auth/reset-password' && $method === 'POST'):
            $email = $input['email'] ?? '';
            $otp = $input['otp'] ?? '';
            $newPassword = $input['new_password'] ?? '';
            if (empty($email) || empty($otp) || empty($newPassword)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Email, OTP, and new password are required']);
                break;
            }

            if (strlen($newPassword) < 6) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Password must be at least 6 characters']);
                break;
            }

            // 1. Verify OTP again
            $otpFile = __DIR__ . '/otps.json';
            $otps = [];
            if (file_exists($otpFile)) {
                $otps = json_decode(file_get_contents($otpFile), true) ?: [];
            }

            if (!isset($otps[$email]) || $otps[$email]['otp'] !== $otp || time() > $otps[$email]['expires_at']) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Invalid or expired OTP request']);
                break;
            }

            // 2. Fetch User UUID
            $userRes = supabaseSelect('users', 'id', ['email' => 'eq.' . $email], true);
            if (!$userRes['success'] || empty($userRes['data'])) {
                http_response_code(404);
                echo json_encode(['success' => false, 'error' => 'User not found']);
                break;
            }
            $userId = $userRes['data']['id'];

            // 3. Update Supabase Auth Password
            $updateRes = supabaseUpdateAuthUser($userId, ['password' => $newPassword]);
            if (!$updateRes['success']) {
                http_response_code(500);
                echo json_encode(['success' => false, 'error' => $updateRes['error'] ?: 'Failed to update auth password']);
                break;
            }

            // 4. Invalidate OTP
            unset($otps[$email]);
            file_put_contents($otpFile, json_encode($otps, JSON_PRETTY_PRINT));

            echo json_encode(['success' => true, 'message' => 'Password has been reset successfully']);
            break;

        // --- PUBLIC ROUTE: Certificate Verification ---
        case ($route === '/api/certificates/verify' && $method === 'GET'):
            $certId = $_GET['certificate_id'] ?? '';
            if (empty($certId)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing certificate_id']);
                break;
            }
            
            $res = supabaseSelect('certificates', '*, students(full_name), courses(course_name)', ['certificate_id' => $certId], true);
            if (!$res['success'] || empty($res['data'])) {
                http_response_code(404);
                echo json_encode(['success' => false, 'error' => 'Certificate not found or invalid']);
            } else {
                echo json_encode(['success' => true, 'certificate' => $res['data']]);
            }
            break;

        // --- AUTH: Retrieve Current User Profile ---
        case ($route === '/api/auth/profile' && $method === 'GET'):
            $user = verifyToken();
            if ($user['role'] === 'SUPER_ADMIN') {
                echo json_encode(['success' => true, 'profile' => $user]);
            } elseif ($user['role'] === 'TEACHER') {
                $res = supabaseSelect('teachers', '*', ['id' => $user['id']], true);
                echo json_encode(['success' => true, 'profile' => array_merge($user, $res['data'] ?: [])]);
            } else {
                $res = supabaseSelect('students', '*', ['id' => $user['id']], true);
                echo json_encode(['success' => true, 'profile' => array_merge($user, $res['data'] ?: [])]);
            }
            break;

        case ($route === '/api/auth/profile' && $method === 'PUT'):
            $user = verifyToken();
            $email = $input['email'] ?? '';
            $fullName = $input['full_name'] ?? '';
            
            if (empty($email)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Email is required']);
                break;
            }
            
            // 1. Update Supabase Auth
            $authData = ['email' => $email, 'email_confirm' => true];
            if (!empty($fullName)) {
                $authData['user_metadata'] = ['full_name' => $fullName];
            }
            $authRes = supabaseUpdateAuthUser($user['id'], $authData);
            if (!$authRes['success']) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Auth update failed: ' . $authRes['error']]);
                break;
            }
            
            // 2. Update public.users email
            supabaseUpdate('users', ['email' => $email], ['id' => $user['id']]);
            
            // 3. Update profile table depending on role
            if ($user['role'] === 'TEACHER') {
                $teacherData = ['email' => $email];
                if (!empty($fullName)) {
                    $teacherData['full_name'] = $fullName;
                }
                supabaseUpdate('teachers', $teacherData, ['id' => $user['id']]);
            } elseif ($user['role'] === 'STUDENT') {
                $studentData = ['email' => $email];
                if (!empty($fullName)) {
                    $studentData['full_name'] = $fullName;
                }
                supabaseUpdate('students', $studentData, ['id' => $user['id']]);
            }
            
            // 4. Invalidate Token Cache
            $token = getBearerToken();
            if ($token) {
                $tokenHash = md5($token);
                $cacheFile = __DIR__ . '/.token_cache/' . $tokenHash . '.json';
                if (file_exists($cacheFile)) {
                    @unlink($cacheFile);
                }
            }
            
            echo json_encode(['success' => true]);
            break;

        // --- COURSES ENDPOINTS ---
        case ($route === '/api/courses' && $method === 'GET'):
            $user = verifyToken();
            if ($user['role'] === 'STUDENT') {
                $res = supabaseSelect('courses', '*, teachers(full_name), student_courses!inner(student_id)', [
                    'student_courses.student_id' => $user['id'],
                    'status' => 'ACTIVE'
                ]);
                if ($res['success'] && !empty($res['data'])) {
                    foreach ($res['data'] as &$c) {
                        unset($c['student_courses']);
                    }
                }
                echo json_encode(['success' => $res['success'], 'courses' => $res['data'] ?: [], 'error' => $res['error']]);
            } else {
                // Admin and Teachers view all courses
                $res = supabaseSelect('courses', '*, teachers(full_name)');
                echo json_encode(['success' => true, 'courses' => $res['data'] ?: []]);
            }
            break;

        case ($route === '/api/courses' && $method === 'POST'):
            requireRole(['SUPER_ADMIN']);
            if (empty($input['course_name']) || empty($input['course_code']) || empty($input['fees'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing required course fields']);
                break;
            }
            $allowedFields = [
                'course_name', 'course_code', 'course_description', 'duration', 
                'fees', 'teacher_id', 'certificate_enabled', 'status'
            ];
            $filteredInput = array_intersect_key($input, array_flip($allowedFields));
            $res = supabaseInsert('courses', $filteredInput);
            echo json_encode(['success' => $res['success'], 'course' => $res['data'], 'error' => $res['error']]);
            break;

        case (preg_match('/^\/api\/courses\/([a-zA-Z0-9-]+)$/', $route, $matches) && $method === 'PUT'):
            requireRole(['SUPER_ADMIN']);
            $courseId = $matches[1];
            $allowedFields = [
                'course_name', 'course_code', 'course_description', 'duration', 
                'fees', 'teacher_id', 'certificate_enabled', 'status'
            ];
            $filteredInput = array_intersect_key($input, array_flip($allowedFields));
            $res = supabaseUpdate('courses', $filteredInput, ['id' => $courseId]);
            echo json_encode(['success' => $res['success'], 'course' => $res['data'], 'error' => $res['error']]);
            break;

        case (preg_match('/^\/api\/courses\/([a-zA-Z0-9-]+)$/', $route, $matches) && $method === 'DELETE'):
            requireRole(['SUPER_ADMIN']);
            $courseId = $matches[1];
            $res = supabaseDelete('courses', ['id' => $courseId]);
            echo json_encode(['success' => $res['success'], 'error' => $res['error']]);
            break;

        // --- BATCHES ENDPOINTS ---
        case ($route === '/api/batches' && $method === 'GET'):
            $user = verifyToken();
            if ($user['role'] === 'STUDENT') {
                $res = supabaseSelect('batches', '*, courses(course_name), teachers(full_name), student_batches!inner(student_id)', [
                    'student_batches.student_id' => $user['id']
                ]);
                if ($res['success'] && !empty($res['data'])) {
                    foreach ($res['data'] as &$b) {
                        unset($b['student_batches']);
                    }
                }
                echo json_encode(['success' => $res['success'], 'batches' => $res['data'] ?: [], 'error' => $res['error']]);
            } else {
                $res = supabaseSelect('batches', '*, courses(course_name), teachers(full_name)');
                echo json_encode(['success' => true, 'batches' => $res['data'] ?: []]);
            }
            break;

        case ($route === '/api/batches' && $method === 'POST'):
            requireRole(['SUPER_ADMIN']);
            if (empty($input['batch_name']) || empty($input['course_id']) || empty($input['start_date'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing batch configurations']);
                break;
            }
            $allowedFields = [
                'batch_name', 'course_id', 'teacher_id', 'start_date', 'end_date', 'batch_timing', 'status'
            ];
            $filteredInput = array_intersect_key($input, array_flip($allowedFields));
            $res = supabaseInsert('batches', $filteredInput);
            echo json_encode(['success' => $res['success'], 'batch' => $res['data'], 'error' => $res['error']]);
            break;

        case (preg_match('/^\/api\/batches\/([a-zA-Z0-9-]+)$/', $route, $matches) && $method === 'PUT'):
            requireRole(['SUPER_ADMIN']);
            $batchId = $matches[1];
            $allowedFields = [
                'batch_name', 'course_id', 'teacher_id', 'start_date', 'end_date', 'batch_timing', 'status'
            ];
            $filteredInput = array_intersect_key($input, array_flip($allowedFields));
            $res = supabaseUpdate('batches', $filteredInput, ['id' => $batchId]);
            echo json_encode(['success' => $res['success'], 'batch' => $res['data'], 'error' => $res['error']]);
            break;

        case (preg_match('/^\/api\/batches\/([a-zA-Z0-9-]+)$/', $route, $matches) && $method === 'DELETE'):
            requireRole(['SUPER_ADMIN']);
            $batchId = $matches[1];
            $res = supabaseDelete('batches', ['id' => $batchId]);
            echo json_encode(['success' => $res['success'], 'error' => $res['error']]);
            break;

        // --- USERS MANAGEMENT (TEACHERS AND STUDENTS) ---
        case ($route === '/api/users/students' && $method === 'GET'):
            // Support phone-based lookup for n8n chatbot (service key or JWT)
            $phone = $_GET['phone'] ?? '';
            if (!empty($phone)) {
                // Phone lookup - accessible by service key OR admin/teacher JWT
                $user = verifyTokenOrApiKey();
                // Clean phone: remove leading + or country code prefix variations
                $cleanPhone = preg_replace('/[^0-9]/', '', $phone);
                // Try exact match first, then last 10 digits
                $res = supabaseSelect('students', '*, student_courses(course_id, courses(course_name, duration, course_code)), student_batches(batch_id, batches(batch_name, start_date, end_date, batch_timing, teachers(full_name)))', [
                    'mobile_number' => 'ilike.*' . substr($cleanPhone, -10)
                ]);
                if ($res['success'] && !empty($res['data'])) {
                    $student = $res['data'][0];
                    $courseName = 'N/A';
                    $courseDuration = 'N/A';
                    $batchName = 'N/A';
                    $className = '';
                    $teacherName = 'N/A';
                    $startDate = '';
                    $endDate = '';
                    $batchTiming = '';
                    if (!empty($student['student_courses'])) {
                        foreach ($student['student_courses'] as $sc) {
                            if (!empty($sc['courses']['course_name'])) {
                                if (stripos($sc['courses']['course_name'], 'Full Stack') !== false) {
                                    $courseName = $sc['courses']['course_name'];
                                    $courseDuration = $sc['courses']['duration'] ?? '6 Months';
                                    break;
                                }
                            }
                        }
                        if ($courseName === 'N/A') {
                            $courseName = $student['student_courses'][0]['courses']['course_name'] ?? 'N/A';
                            $courseDuration = $student['student_courses'][0]['courses']['duration'] ?? 'N/A';
                        }
                    }
                    if (!empty($student['student_batches'])) {
                        $batch = $student['student_batches'][0]['batches'] ?? [];
                        $batchName = $batch['batch_name'] ?? 'N/A';
                        $className = $batchName;
                        $startDate = $batch['start_date'] ?? '';
                        $endDate = $batch['end_date'] ?? '';
                        $batchTiming = $batch['batch_timing'] ?? '';
                        $teacherName = $batch['teachers']['full_name'] ?? 'N/A';
                    }
                    echo json_encode([
                        'success' => true,
                        'studentId' => $student['id'],
                        'name' => $student['full_name'],
                        'email' => $student['email'],
                        'className' => $className,
                        'courseName' => $courseName,
                        'courseDuration' => $courseDuration,
                        'batchName' => $batchName,
                        'teacherName' => $teacherName,
                        'startDate' => $startDate,
                        'endDate' => $endDate,
                        'batchTiming' => $batchTiming,
                        'phone' => $student['mobile_number']
                    ]);
                } else {
                    // Student not found by phone - return empty (not an error)
                    echo json_encode([
                        'success' => true,
                        'studentId' => '',
                        'name' => '',
                        'className' => '',
                        'message' => 'No student found with this phone number'
                    ]);
                }
                break;
            }
            
            requireRole(['SUPER_ADMIN', 'TEACHER']);
            $batchId = $_GET['batch_id'] ?? '';
            
            if (!empty($batchId)) {
                $res = supabaseSelect('student_batches', 'student_id, students(*)', ['batch_id' => $batchId]);
                $studentsData = [];
                if ($res['success'] && !empty($res['data'])) {
                    foreach ($res['data'] as $enrollment) {
                        if (!empty($enrollment['students'])) {
                            $student = $enrollment['students'];
                            $student['course_name'] = 'N/A';
                            $student['batch_name'] = 'N/A';
                            $studentsData[] = $student;
                        }
                    }
                }
            } else {
                $res = supabaseSelect('students', '*, student_courses(course_id, courses(course_name)), student_batches(batch_id, batches(batch_name))');
                $studentsData = [];
                if ($res['success'] && !empty($res['data'])) {
                    foreach ($res['data'] as $student) {
                        $courseName = 'N/A';
                        $batchName = 'N/A';
                        $courseId = '';
                        $batchId = '';
                        if (!empty($student['student_courses'])) {
                            $courseName = $student['student_courses'][0]['courses']['course_name'] ?? 'N/A';
                            $courseId = $student['student_courses'][0]['course_id'] ?? '';
                        }
                        if (!empty($student['student_batches'])) {
                            $batchName = $student['student_batches'][0]['batches']['batch_name'] ?? 'N/A';
                            $batchId = $student['student_batches'][0]['batch_id'] ?? '';
                        }
                        $student['course_name'] = $courseName;
                        $student['batch_name'] = $batchName;
                        $student['course_id'] = $courseId;
                        $student['batch_id'] = $batchId;
                        
                        unset($student['student_courses']);
                        unset($student['student_batches']);
                        
                        $studentsData[] = $student;
                    }
                }
            }
            echo json_encode(['success' => true, 'students' => $studentsData]);
            break;

        case ($route === '/api/users/students' && $method === 'POST'):
            requireRole(['SUPER_ADMIN', 'TEACHER']);
            if (empty($input['email']) || empty($input['password']) || empty($input['full_name'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing email, password or name']);
                break;
            }
            // Create student in Supabase Auth, metadata triggers insertion into students table
            $meta = [
                'role_id' => 3,
                'full_name' => $input['full_name'],
                'mobile_number' => $input['mobile_number'] ?? '',
                'address' => $input['address'] ?? '',
                'fee_amount' => (float)($input['fee_amount'] ?? 0.00)
            ];
            
            $res = supabaseCreateUser($input['email'], $input['password'], $meta);
            if (!$res['success']) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => $res['error']]);
                break;
            }
            
            // Assign student to course and batch if provided
            $studentId = $res['data']['id'];
            if (!empty($input['course_id'])) {
                supabaseInsert('student_courses', ['student_id' => $studentId, 'course_id' => $input['course_id']]);
            }
            if (!empty($input['batch_id'])) {
                supabaseInsert('student_batches', ['student_id' => $studentId, 'batch_id' => $input['batch_id']]);
            }
            
            echo json_encode(['success' => true, 'student' => $res['data']]);
            break;

        case ($route === '/api/users/teachers' && $method === 'GET'):
            requireRole(['SUPER_ADMIN', 'TEACHER']);
            $res = supabaseSelect('teachers', '*');
            echo json_encode(['success' => true, 'teachers' => $res['data'] ?: []]);
            break;

        case ($route === '/api/users/teachers' && $method === 'POST'):
            requireRole(['SUPER_ADMIN']);
            if (empty($input['email']) || empty($input['password']) || empty($input['full_name'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing teacher info']);
                break;
            }
            $meta = [
                'role_id' => 2,
                'full_name' => $input['full_name'],
                'mobile_number' => $input['mobile_number'] ?? ''
            ];
            $res = supabaseCreateUser($input['email'], $input['password'], $meta);
            
            if ($res['success'] && !empty($res['data'])) {
                $teacherId = $res['data']['id'];
                
                // Assign multiple courses
                if (!empty($input['course_ids']) && is_array($input['course_ids'])) {
                    foreach ($input['course_ids'] as $courseId) {
                        supabaseUpdate('courses', ['teacher_id' => $teacherId], ['id' => $courseId]);
                    }
                }
                
                // Assign multiple batches
                if (!empty($input['batch_ids']) && is_array($input['batch_ids'])) {
                    foreach ($input['batch_ids'] as $batchId) {
                        supabaseUpdate('batches', ['teacher_id' => $teacherId], ['id' => $batchId]);
                    }
                }
            }
            echo json_encode(['success' => $res['success'], 'teacher' => $res['data'], 'error' => $res['error']]);
            break;

        case (preg_match('/^\/api\/users\/students\/([a-zA-Z0-9-]+)$/', $route, $matches) && $method === 'PUT'):
            requireRole(['SUPER_ADMIN']);
            $studentId = $matches[1];
            if (empty($input['email']) || empty($input['full_name'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing email or full_name']);
                break;
            }
            
            // 1. Update Supabase Auth
            $authData = ['email' => $input['email'], 'email_confirm' => true];
            if (!empty($input['password'])) {
                $authData['password'] = $input['password'];
            }
            $authRes = supabaseUpdateAuthUser($studentId, $authData);
            if (!$authRes['success']) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Failed to update Auth: ' . $authRes['error']]);
                break;
            }
            
            // 2. Update public.users email
            supabaseUpdate('users', ['email' => $input['email']], ['id' => $studentId]);
            
            // 3. Update public.students details
            $studentData = [
                'full_name' => $input['full_name'],
                'mobile_number' => $input['mobile_number'] ?? '',
                'address' => $input['address'] ?? '',
                'email' => $input['email']
            ];
            if (isset($input['fee_amount']) && $input['fee_amount'] !== '') {
                $studentData['fee_amount'] = (float)$input['fee_amount'];
                // Recalculate fee_pending
                $stdRes = supabaseSelect('students', 'fee_paid', ['id' => $studentId], true);
                if ($stdRes['success'] && !empty($stdRes['data'])) {
                    $feePaid = (float)($stdRes['data']['fee_paid'] ?? 0);
                    $studentData['fee_pending'] = (float)$input['fee_amount'] - $feePaid;
                }
            }
            
            $res = supabaseUpdate('students', $studentData, ['id' => $studentId]);
            
            // 4. Update Course Assignment
            if (!empty($input['course_id'])) {
                supabaseDelete('student_courses', ['student_id' => $studentId]);
                supabaseInsert('student_courses', ['student_id' => $studentId, 'course_id' => $input['course_id']]);
            }
            
            // 5. Update Batch Assignment
            if (!empty($input['batch_id'])) {
                supabaseDelete('student_batches', ['student_id' => $studentId]);
                supabaseInsert('student_batches', ['student_id' => $studentId, 'batch_id' => $input['batch_id']]);
            }
            
            echo json_encode(['success' => true]);
            break;

        case (preg_match('/^\/api\/users\/teachers\/([a-zA-Z0-9-]+)$/', $route, $matches) && $method === 'PUT'):
            requireRole(['SUPER_ADMIN']);
            $teacherId = $matches[1];
            if (empty($input['email']) || empty($input['full_name'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing email or full_name']);
                break;
            }
            
            // 1. Update Supabase Auth
            $authData = ['email' => $input['email'], 'email_confirm' => true];
            if (!empty($input['password'])) {
                $authData['password'] = $input['password'];
            }
            $authRes = supabaseUpdateAuthUser($teacherId, $authData);
            if (!$authRes['success']) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Failed to update Auth: ' . $authRes['error']]);
                break;
            }
            
            // 2. Update public.users email
            supabaseUpdate('users', ['email' => $input['email']], ['id' => $teacherId]);
            
            // 3. Update public.teachers details
            $teacherData = [
                'full_name' => $input['full_name'],
                'mobile_number' => $input['mobile_number'] ?? '',
                'email' => $input['email']
            ];
            $res = supabaseUpdate('teachers', $teacherData, ['id' => $teacherId]);
            
            // 4. Sync courses
            if (isset($input['course_ids']) && is_array($input['course_ids'])) {
                supabaseUpdate('courses', ['teacher_id' => null], ['teacher_id' => $teacherId]);
                foreach ($input['course_ids'] as $courseId) {
                    supabaseUpdate('courses', ['teacher_id' => $teacherId], ['id' => $courseId]);
                }
            }
            
            // 5. Sync batches
            if (isset($input['batch_ids']) && is_array($input['batch_ids'])) {
                supabaseUpdate('batches', ['teacher_id' => null], ['teacher_id' => $teacherId]);
                foreach ($input['batch_ids'] as $batchId) {
                    supabaseUpdate('batches', ['teacher_id' => $teacherId], ['id' => $batchId]);
                }
            }
            
            echo json_encode(['success' => true]);
            break;

        // Toggle user active/inactive
        case (preg_match('/^\/api\/users\/([a-zA-Z0-9-]+)\/status$/', $route, $matches) && $method === 'PUT'):
            requireRole(['SUPER_ADMIN']);
            $targetUserId = $matches[1];
            if (!isset($input['status'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing status']);
                break;
            }
            
            // Update profile status in users
            $res = supabaseUpdate('users', ['status' => $input['status']], ['id' => $targetUserId]);
            // Also update respective sub table
            supabaseUpdate('students', ['status' => $input['status']], ['id' => $targetUserId]);
            supabaseUpdate('teachers', ['status' => $input['status']], ['id' => $targetUserId]);
            
            echo json_encode(['success' => $res['success'], 'error' => $res['error']]);
            break;

        // Delete user (removes user from Supabase Auth; cascade deletes from database)
        case (preg_match('/^\/api\/users\/([a-zA-Z0-9-]+)$/', $route, $matches) && $method === 'DELETE'):
            requireRole(['SUPER_ADMIN']);
            $targetUserId = $matches[1];

            // 1. Check if user is a student and has certificates
            $certCheck = supabaseSelect('certificates', 'id', ['student_id' => $targetUserId]);
            if ($certCheck['success'] && !empty($certCheck['data'])) {
                // Preserve student profile & certificates; deactivate account and change credentials
                $randomPassword = bin2hex(random_bytes(16)) . 'A1!';
                $randomEmail = 'archived_' . time() . '_' . $targetUserId . '@lms-archived.com';

                // Update Supabase Auth credentials
                $authUpdate = supabaseUpdateAuthUser($targetUserId, [
                    'email' => $randomEmail,
                    'password' => $randomPassword
                ]);

                if ($authUpdate['success']) {
                    // Update status and email in public database tables
                    supabaseUpdate('users', ['status' => 'INACTIVE', 'email' => $randomEmail], ['id' => $targetUserId]);
                    supabaseUpdate('students', ['status' => 'INACTIVE', 'email' => $randomEmail], ['id' => $targetUserId]);
                    echo json_encode(['success' => true, 'archived' => true, 'message' => 'User has active certificates. Account has been deactivated to preserve records.']);
                } else {
                    http_response_code(500);
                    echo json_encode(['success' => false, 'error' => 'Failed to update auth credentials: ' . ($authUpdate['error'] ?? '')]);
                }
                break;
            }

            $res = supabaseDeleteUser($targetUserId);
            if ($res['success']) {
                echo json_encode(['success' => true]);
            } else {
                http_response_code($res['status'] >= 400 && $res['status'] < 600 ? $res['status'] : 400);
                echo json_encode(['success' => false, 'error' => $res['error'] ?? 'Failed to delete user']);
            }
            break;

        // --- ATTENDANCE ENDPOINTS ---
        case ($route === '/api/attendance' && $method === 'GET'):
            $user = verifyTokenOrApiKey();
            $batchId = $_GET['batch_id'] ?? '';
            $date = $_GET['date'] ?? '';

            if ($user['role'] === 'STUDENT') {
                $res = supabaseSelect('attendance', '*, batches(batch_name)', ['student_id' => $user['id']]);
                echo json_encode(['success' => true, 'attendance' => $res['data'] ?: []]);
            } elseif ($user['role'] === 'SERVICE' && (!empty($_GET['student_id']) || !empty($_GET['phone']))) {
                // n8n service account: look up attendance by student_id query param or phone fallback
                $sid = $_GET['student_id'] ?? '';
                if (empty($sid) || strpos($sid, '{{') !== false) {
                    if (!empty($_GET['phone'])) {
                        $p = preg_replace('/[^0-9]/', '', $_GET['phone']);
                        $sr = supabaseSelect('students', 'id', ['mobile_number' => 'ilike.*' . substr($p, -10)]);
                        if ($sr['success'] && !empty($sr['data'])) {
                            $sid = $sr['data'][0]['id'];
                        }
                    }
                    if (empty($sid) || strpos($sid, '{{') !== false) {
                        $sr = supabaseSelect('students', 'id');
                        if ($sr['success'] && !empty($sr['data'])) {
                            $sid = $sr['data'][0]['id'];
                        }
                    }
                }
                if (!empty($sid) && strpos($sid, '{{') === false) {
                    $res = supabaseSelect('attendance', '*, batches(batch_name)', ['student_id' => $sid]);
                    echo json_encode(['success' => true, 'attendance' => $res['data'] ?: []]);
                } else {
                    echo json_encode(['success' => true, 'attendance' => []]);
                }
            } else {
                if (empty($batchId)) {
                    http_response_code(400);
                    echo json_encode(['success' => false, 'error' => 'batch_id required for list']);
                    break;
                }
                $params = ['batch_id' => $batchId];
                if (!empty($date)) {
                    $params['date'] = $date;
                }
                $res = supabaseSelect('attendance', '*, students(full_name)', $params);
                echo json_encode(['success' => true, 'attendance' => $res['data'] ?: []]);
            }
            break;

        case ($route === '/api/attendance' && $method === 'POST'):
            $user = requireRole(['TEACHER']);
            if (empty($input['batch_id']) || empty($input['date']) || empty($input['records'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing attendance configurations']);
                break;
            }
            
            // records should be array of objects: [{student_id, status}]
            $inserted = [];
            foreach ($input['records'] as $record) {
                $attData = [
                    'student_id' => $record['student_id'],
                    'batch_id' => $input['batch_id'],
                    'date' => $input['date'],
                    'status' => $record['status'], // 'PRESENT', 'ABSENT'
                    'marked_by' => $user['id']
                ];
                // Check if already exists for upsert
                $exist = supabaseSelect('attendance', 'id', [
                    'student_id' => $record['student_id'],
                    'batch_id' => $input['batch_id'],
                    'date' => $input['date']
                ], true);

                if ($exist['success'] && !empty($exist['data'])) {
                    $res = supabaseUpdate('attendance', $attData, ['id' => $exist['data']['id']]);
                } else {
                    $res = supabaseInsert('attendance', $attData);
                }
                if ($res['success']) {
                    $inserted[] = $res['data'];
                }
            }
            echo json_encode(['success' => true, 'records' => $inserted]);
            break;

        // --- STUDY MATERIAL ENDPOINTS ---
        case ($route === '/api/materials' && $method === 'GET'):
            $user = verifyTokenOrApiKey();
            if ($user['role'] === 'STUDENT') {
                $res = supabaseSelect('materials', '*, courses(course_name), batches!inner(batch_name, student_batches!inner(student_id))', [
                    'batches.student_batches.student_id' => $user['id']
                ]);
                if ($res['success'] && !empty($res['data'])) {
                    foreach ($res['data'] as &$m) {
                        if (isset($m['batches']['student_batches'])) {
                            unset($m['batches']['student_batches']);
                        }
                    }
                }
                echo json_encode(['success' => $res['success'], 'materials' => $res['data'] ?: [], 'error' => $res['error']]);
            } elseif ($user['role'] === 'SERVICE' && (!empty($_GET['student_id']) || !empty($_GET['phone']))) {
                // n8n service account: look up materials by student_id query param or phone fallback
                $sid = $_GET['student_id'] ?? '';
                if (empty($sid) || strpos($sid, '{{') !== false) {
                    if (!empty($_GET['phone'])) {
                        $p = preg_replace('/[^0-9]/', '', $_GET['phone']);
                        $sr = supabaseSelect('students', 'id', ['mobile_number' => 'ilike.*' . substr($p, -10)]);
                        if ($sr['success'] && !empty($sr['data'])) {
                            $sid = $sr['data'][0]['id'];
                        }
                    }
                    if (empty($sid) || strpos($sid, '{{') !== false) {
                        $sr = supabaseSelect('students', 'id');
                        if ($sr['success'] && !empty($sr['data'])) {
                            $sid = $sr['data'][0]['id'];
                        }
                    }
                }
                if (!empty($sid) && strpos($sid, '{{') === false) {
                    $res = supabaseSelect('materials', '*, courses(course_name), batches!inner(batch_name, student_batches!inner(student_id))', [
                        'batches.student_batches.student_id' => $sid
                    ]);
                    if ($res['success'] && !empty($res['data'])) {
                        foreach ($res['data'] as &$m) {
                            if (isset($m['batches']['student_batches'])) {
                                unset($m['batches']['student_batches']);
                            }
                        }
                    }
                    echo json_encode(['success' => $res['success'], 'materials' => $res['data'] ?: [], 'error' => $res['error']]);
                } else {
                    echo json_encode(['success' => true, 'materials' => []]);
                }
            } else {
                $batchId = $_GET['batch_id'] ?? '';
                $params = [];
                if (!empty($batchId)) {
                    $params['batch_id'] = $batchId;
                }
                $res = supabaseSelect('materials', '*, courses(course_name), batches(batch_name)', $params);
                echo json_encode(['success' => true, 'materials' => $res['data'] ?: []]);
            }
            break;

        case ($route === '/api/materials' && $method === 'POST'):
            $user = requireRole(['TEACHER']);
            if (empty($input['title']) || empty($input['file_url']) || empty($input['course_id']) || empty($input['batch_id'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing upload details']);
                break;
            }
            $input['uploaded_by'] = $user['id'];
            $res = supabaseInsert('materials', $input);
            
            // Auto-ingest material content into RAG vector store
            if ($res['success'] && !empty($res['data'])) {
                $matData = is_array($res['data']) ? (isset($res['data'][0]) ? $res['data'][0] : $res['data']) : [];
                $matId = $matData['id'] ?? '';
                $contentToIndex = trim(($input['content'] ?? '') ?: ($input['description'] ?? ''));
                
                // If content is empty or short, extract text from uploaded document file (PDF, TXT, MD, etc.)
                if (strlen($contentToIndex) < 15 && !empty($input['file_url'])) {
                    try {
                        $extractedText = DocumentExtractor::extractFromUrl($input['file_url']);
                        if (!empty($extractedText)) {
                            $contentToIndex = $extractedText;
                        }
                    } catch (Throwable $e) {
                        error_log("Document extraction error for material {$matId}: " . $e->getMessage());
                    }
                }

                if (!empty($matId) && !empty($contentToIndex) && strlen($contentToIndex) >= 15) {
                    try {
                        RagService::ingestMaterial(
                            $matId,
                            $input['title'],
                            $contentToIndex,
                            $input['course_id'] ?? null,
                            $input['batch_id'] ?? null,
                            ['file_name' => $input['file_name'] ?? '', 'file_type' => $input['file_type'] ?? 'notes', 'file_url' => $input['file_url'] ?? '']
                        );
                    } catch (Throwable $e) {
                        error_log("RAG auto-ingest error: " . $e->getMessage());
                    }
                }
            }
            
            echo json_encode(['success' => $res['success'], 'material' => $res['data'], 'error' => $res['error']]);
            break;

        case (preg_match('/^\/api\/materials\/([a-zA-Z0-9-]+)$/', $route, $matches) && $method === 'DELETE'):
            $user = requireRole(['TEACHER']);
            $materialId = $matches[1];
            $res = supabaseDelete('materials', ['id' => $materialId]);
            if ($res['success']) {
                try {
                    RagService::deleteMaterialChunks($materialId);
                } catch (Throwable $e) {
                    error_log("RAG chunk deletion error: " . $e->getMessage());
                }
            }
            echo json_encode(['success' => $res['success'], 'error' => $res['error']]);
            break;

        case (preg_match('/^\/api\/materials\/([a-zA-Z0-9-]+)$/', $route, $matches) && in_array($method, ['PUT', 'PATCH'])):
            $user = requireRole(['TEACHER']);
            $materialId = $matches[1];
            
            // 1. Update in Supabase
            $res = supabaseUpdate('materials', $input, ['id' => $materialId]);
            
            // 2. Re-index RAG if content or file_url was modified
            $contentToIndex = trim(($input['content'] ?? '') ?: ($input['description'] ?? ''));
            if (strlen($contentToIndex) < 15 && !empty($input['file_url'])) {
                try {
                    $extractedText = DocumentExtractor::extractFromUrl($input['file_url']);
                    if (!empty($extractedText)) {
                        $contentToIndex = $extractedText;
                    }
                } catch (Throwable $e) {
                    error_log("Document re-extraction error on material {$materialId}: " . $e->getMessage());
                }
            }
            
            if (!empty($contentToIndex) && strlen($contentToIndex) >= 15) {
                try {
                    $courseId = $input['course_id'] ?? null;
                    $batchId = $input['batch_id'] ?? null;
                    $title = $input['title'] ?? 'Updated Material';
                    if (empty($courseId) || empty($batchId)) {
                        $curr = supabaseSelect('materials', 'course_id, batch_id, title', ['id' => $materialId], true);
                        if ($curr['success'] && !empty($curr['data'])) {
                            if (empty($courseId)) $courseId = $curr['data']['course_id'] ?? null;
                            if (empty($batchId)) $batchId = $curr['data']['batch_id'] ?? null;
                            if (empty($input['title'])) $title = $curr['data']['title'] ?? $title;
                        }
                    }
                    RagService::ingestMaterial(
                        $materialId,
                        $title,
                        $contentToIndex,
                        $courseId,
                        $batchId,
                        ['file_name' => $input['file_name'] ?? '', 'file_type' => $input['file_type'] ?? 'notes']
                    );
                } catch (Throwable $e) {
                    error_log("RAG re-ingest error on update: " . $e->getMessage());
                }
            }
            
            echo json_encode(['success' => $res['success'], 'material' => $res['data'], 'error' => $res['error']]);
            break;

        // --- ASSIGNMENTS ---
        case ($route === '/api/assignments' && $method === 'GET'):
            $user = verifyToken();
            if ($user['role'] === 'STUDENT') {
                $res = supabaseSelect('assignments', '*, batches!inner(batch_name, student_batches!inner(student_id))', [
                    'batches.student_batches.student_id' => $user['id']
                ]);
                if ($res['success'] && !empty($res['data'])) {
                    foreach ($res['data'] as &$a) {
                        if (isset($a['batches']['student_batches'])) {
                            unset($a['batches']['student_batches']);
                        }
                    }
                }
                echo json_encode(['success' => $res['success'], 'assignments' => $res['data'] ?: [], 'error' => $res['error']]);
            } else {
                $batchId = $_GET['batch_id'] ?? '';
                $params = [];
                if (!empty($batchId)) {
                    $params['batch_id'] = $batchId;
                }
                $res = supabaseSelect('assignments', '*, batches(batch_name)', $params);
                echo json_encode(['success' => true, 'assignments' => $res['data'] ?: []]);
            }
            break;

        case ($route === '/api/assignments' && $method === 'POST'):
            $user = requireRole(['TEACHER']);
            if (empty($input['title']) || empty($input['due_date']) || empty($input['course_id']) || empty($input['batch_id'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing assignment settings']);
                break;
            }
            $input['uploaded_by'] = $user['id'];
            $res = supabaseInsert('assignments', $input);
            echo json_encode(['success' => $res['success'], 'assignment' => $res['data'], 'error' => $res['error']]);
            break;

        case ($route === '/api/assignments/submit' && $method === 'POST'):
            $user = requireRole(['STUDENT']);
            if (empty($input['assignment_id']) || empty($input['file_url']) || empty($input['file_name'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing submission data']);
                break;
            }
            $subData = [
                'assignment_id' => $input['assignment_id'],
                'student_id' => $user['id'],
                'file_name' => $input['file_name'],
                'file_url' => $input['file_url'],
                'status' => 'SUBMITTED'
            ];
            
            // Check if already submitted for updates
            $exist = supabaseSelect('assignment_submissions', 'id', [
                'assignment_id' => $input['assignment_id'],
                'student_id' => $user['id']
            ], true);
            
            if ($exist['success'] && !empty($exist['data'])) {
                $res = supabaseUpdate('assignment_submissions', $subData, ['id' => $exist['data']['id']]);
            } else {
                $res = supabaseInsert('assignment_submissions', $subData);
            }
            echo json_encode(['success' => $res['success'], 'submission' => $res['data'], 'error' => $res['error']]);
            break;

        case ($route === '/api/assignments/submissions' && $method === 'GET'):
            requireRole(['TEACHER', 'SUPER_ADMIN']);
            $assignmentId = $_GET['assignment_id'] ?? '';
            $params = [];
            if (!empty($assignmentId)) {
                $params['assignment_id'] = $assignmentId;
            }
            $res = supabaseSelect('assignment_submissions', '*, students(full_name), assignments(title)', $params);
            echo json_encode(['success' => true, 'submissions' => $res['data'] ?: []]);
            break;

        case ($route === '/api/assignments/evaluate' && $method === 'POST'):
            $user = requireRole(['TEACHER']);
            if (empty($input['submission_id']) || !isset($input['score'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing evaluation scores']);
                break;
            }
            $evalData = [
                'score' => (float)$input['score'],
                'feedback' => $input['feedback'] ?? '',
                'evaluated_by' => $user['id'],
                'status' => 'EVALUATED'
            ];
            $res = supabaseUpdate('assignment_submissions', $evalData, ['id' => $input['submission_id']]);
            echo json_encode(['success' => $res['success'], 'submission' => $res['data']]);
            break;

        // --- EXAMINATIONS SYSTEM (MCQ & CODING) ---
        case ($route === '/api/exams' && $method === 'GET'):
            $user = verifyToken();
            if ($user['role'] === 'STUDENT') {
                $res = supabaseSelect('exams', '*, batches!inner(batch_name, student_batches!inner(student_id))', [
                    'batches.student_batches.student_id' => $user['id']
                ]);
                if ($res['success'] && !empty($res['data'])) {
                    $resultsRes = supabaseSelect('exam_results', 'exam_id', ['student_id' => $user['id']]);
                    $attemptedExams = array_column($resultsRes['data'] ?: [], 'exam_id');
                    
                    foreach ($res['data'] as &$e) {
                        if (isset($e['batches']['student_batches'])) {
                            unset($e['batches']['student_batches']);
                        }
                        $e['attempted'] = in_array($e['id'], $attemptedExams);
                    }
                }
                echo json_encode(['success' => $res['success'], 'exams' => $res['data'] ?: [], 'error' => $res['error']]);
            } else {
                $batchId = $_GET['batch_id'] ?? '';
                $params = [];
                if (!empty($batchId)) {
                    $params['batch_id'] = $batchId;
                }
                $res = supabaseSelect('exams', '*, batches(batch_name)', $params);
                echo json_encode(['success' => true, 'exams' => $res['data'] ?: []]);
            }
            break;

        case ($route === '/api/exams' && $method === 'POST'):
            $user = requireRole(['TEACHER', 'SUPER_ADMIN']);
            if (empty($input['title']) || empty($input['exam_type']) || empty($input['batch_id']) || empty($input['course_id'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing exam parameters']);
                break;
            }
            
            $examData = [
                'title' => $input['title'],
                'exam_type' => $input['exam_type'], // 'MCQ' or 'CODING'
                'course_id' => $input['course_id'],
                'batch_id' => $input['batch_id'],
                'time_limit_minutes' => (int)$input['time_limit_minutes'],
                'due_date' => $input['due_date'],
                'created_by' => $user['id']
            ];
            
            $examRes = supabaseInsert('exams', $examData);
            if (!$examRes['success']) {
                echo json_encode(['success' => false, 'error' => $examRes['error']]);
                break;
            }
            
            $exam = is_array($examRes['data']) ? $examRes['data'][0] : $examRes['data'];
            
            // Save questions if provided
            if ($input['exam_type'] === 'MCQ' && !empty($input['questions'])) {
                foreach ($input['questions'] as $q) {
                    $qRes = supabaseInsert('mcq_questions', [
                        'exam_id' => $exam['id'],
                        'question_text' => $q['question_text'],
                        'marks' => (float)$q['marks']
                    ]);
                    if ($qRes['success'] && !empty($q['options'])) {
                        $qObj = is_array($qRes['data']) ? $qRes['data'][0] : $qRes['data'];
                        foreach ($q['options'] as $opt) {
                            supabaseInsert('mcq_options', [
                                'question_id' => $qObj['id'],
                                'option_text' => $opt['option_text'],
                                'is_correct' => (bool)$opt['is_correct']
                            ]);
                        }
                    }
                }
            } elseif ($input['exam_type'] === 'CODING' && !empty($input['questions'])) {
                foreach ($input['questions'] as $q) {
                    supabaseInsert('coding_questions', [
                        'exam_id' => $exam['id'],
                        'question_text' => $q['question_text'],
                        'description' => $q['description'] ?? '',
                        'max_marks' => (float)$q['max_marks']
                    ]);
                }
            }

            // Auto-notify batch students of new pop-quiz or exam
            $isPopQuiz = stripos($exam['title'] ?? '', 'pop quiz') !== false;
            $notifTitle = $isPopQuiz ? "⚡ Remedial Pop Quiz: {$exam['title']}" : "📝 New Exam Scheduled: {$exam['title']}";
            $notifMsg = $isPopQuiz
                ? "A new targeted remedial pop-quiz '{$exam['title']}' has been dispatched to your batch. Complete it to reinforce key concepts!"
                : "A new {$exam['exam_type']} exam '{$exam['title']}' has been scheduled for your batch. Time limit: {$exam['time_limit_minutes']} mins.";

            supabaseInsert('notifications', [
                'title' => $notifTitle,
                'message' => $notifMsg,
                'target_type' => 'BATCH',
                'target_id' => $input['batch_id'],
                'notification_type' => $isPopQuiz ? 'QUIZ' : 'EXAM',
                'sender_id' => $user['id']
            ]);

            echo json_encode(['success' => true, 'exam' => $exam]);
            break;

        case (preg_match('/^\/api\/exams\/([a-zA-Z0-9-]+)\/details$/', $route, $matches) && $method === 'GET'):
            $user = verifyToken();
            $examId = $matches[1];
            
            $examRes = supabaseSelect('exams', '*', ['id' => $examId], true);
            if (!$examRes['success'] || empty($examRes['data'])) {
                http_response_code(404);
                echo json_encode(['success' => false, 'error' => 'Exam not found']);
                break;
            }
            
            $exam = $examRes['data'];

            if ($user['role'] === 'STUDENT') {
                $existResult = supabaseSelect('exam_results', 'id', ['exam_id' => $examId, 'student_id' => $user['id']], true);
                if (!empty($existResult['data'])) {
                    http_response_code(403);
                    echo json_encode(['success' => false, 'error' => 'You have already attempted this exam.']);
                    break;
                }
            }
            
            if ($exam['exam_type'] === 'MCQ') {
                $qRes = supabaseSelect('mcq_questions', '*', ['exam_id' => $examId]);
                $questions = $qRes['data'] ?: [];
                
                foreach ($questions as &$q) {
                    $optRes = supabaseSelect('mcq_options', '*', ['question_id' => $q['id']]);
                    $opts = $optRes['data'] ?: [];
                    // For student, hide correctness flag
                    if ($user['role'] === 'STUDENT') {
                        foreach ($opts as &$o) {
                            unset($o['is_correct']);
                        }
                    }
                    $q['options'] = $opts;
                }
                $exam['questions'] = $questions;
            } else {
                $qRes = supabaseSelect('coding_questions', '*', ['exam_id' => $examId]);
                $exam['questions'] = $qRes['data'] ?: [];
            }
            
            echo json_encode(['success' => true, 'exam' => $exam]);
            break;

        case ($route === '/api/exams/submit' && $method === 'POST'):
            $user = requireRole(['STUDENT']);
            if (empty($input['exam_id'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing exam_id']);
                break;
            }
            
            $examId = $input['exam_id'];
            $examRes = supabaseSelect('exams', '*', ['id' => $examId], true);
            $exam = $examRes['data'];
            
            // Central Guard: Reject if already attempted/finalized
            $existResult = supabaseSelect('exam_results', 'id', ['exam_id' => $examId, 'student_id' => $user['id']], true);
            if (!empty($existResult['data'])) {
                http_response_code(403);
                echo json_encode(['success' => false, 'error' => 'You have already attempted and finalized this exam.']);
                break;
            }
            
            if ($exam['exam_type'] === 'MCQ') {
                // Auto evaluate MCQ
                // Answers submitted should look like: {answers: {question_id: option_id}}
                $answers = $input['answers'] ?? [];
                $qRes = supabaseSelect('mcq_questions', '*', ['exam_id' => $examId]);
                $questions = $qRes['data'] ?: [];
                
                $questionsWithOpts = [];
                foreach ($questions as $q) {
                    $optRes = supabaseSelect('mcq_options', '*', ['question_id' => $q['id']]);
                    $q['options'] = $optRes['data'] ?: [];
                    $questionsWithOpts[] = $q;
                }

                $evalResult = RagService::evaluateMcqBreakdown($questionsWithOpts, $answers);
                $totalScore = $evalResult['score'];
                $maxScore = $evalResult['max_score'];
                $pct = $evalResult['percentage'];
                $breakdown = $evalResult['breakdown'];
                $guidance = $evalResult['guidance'];

                // Record MCQ Results (First Attempt is Final)
                $resData = [
                    'exam_id' => $examId,
                    'student_id' => $user['id'],
                    'score' => $totalScore,
                    'max_score' => $maxScore,
                    'feedback' => "Auto-evaluated MCQ Exam ({$totalScore}/{$maxScore}, {$pct}%)"
                ];
                
                $res = supabaseInsert('exam_results', $resData);

                // If this is a remedial pop-quiz, record evaluation analytics for knowledge gap resolution tracking
                if (stripos($exam['title'] ?? '', 'pop quiz') !== false || stripos($exam['title'] ?? '', 'remedial') !== false) {
                    RagService::recordRemedialResult(
                        $examId,
                        $exam['title'] ?? 'Pop Quiz',
                        $exam['course_id'] ?? null,
                        $exam['batch_id'] ?? null,
                        $user['id'],
                        (float)$totalScore,
                        (float)$maxScore
                    );
                }

                // Fetch remedial recommendations for reinforcement
                $topicForRecs = $exam['title'] ?? 'Full Stack Development';
                $recResult = RagService::getRemedialResourceRecommendations($topicForRecs, $exam['course_id'] ?? null, $exam['batch_id'] ?? null);
                $recommendations = $recResult['recommendations'] ?? [];

                echo json_encode([
                    'success' => $res['success'],
                    'score' => $totalScore,
                    'max_score' => $maxScore,
                    'percentage' => $pct,
                    'breakdown' => $breakdown,
                    'guidance' => $guidance,
                    'recommendations' => $recommendations,
                    'error' => $res['error']
                ]);
            } else {
                // Coding exam submission
                // Check if this is a finalize request
                if (!empty($input['finalize'])) {
                    // Calculate total max marks for coding questions in this exam
                    $questionsRes = supabaseSelect('coding_questions', 'max_marks', ['exam_id' => $examId]);
                    $maxScore = 0;
                    foreach ($questionsRes['data'] ?: [] as $q) {
                        $maxScore += (float)$q['max_marks'];
                    }
                    
                    $resData = [
                        'exam_id' => $examId,
                        'student_id' => $user['id'],
                        'score' => 0,
                        'max_score' => $maxScore,
                        'feedback' => 'Coding Exam Submitted - Pending Evaluation'
                    ];
                    $res = supabaseInsert('exam_results', $resData);
                    echo json_encode(['success' => $res['success'], 'error' => $res['error']]);
                    break;
                }
                
                // Otherwise it's a coding challenge answer text submission
                if (empty($input['coding_question_id'])) {
                    http_response_code(400);
                    echo json_encode(['success' => false, 'error' => 'Missing coding_question_id']);
                    break;
                }
                
                // Accept either answer_text (new text-based) or file_url (legacy)
                $answerText = $input['answer_text'] ?? '';
                $fileUrl = $input['file_url'] ?? '';
                
                if (empty($answerText) && empty($fileUrl)) {
                    http_response_code(400);
                    echo json_encode(['success' => false, 'error' => 'Missing answer_text or file_url']);
                    break;
                }
                
                // Store text answers using solution_file_url column; mark with special file name
                $subData = [
                    'exam_id' => $examId,
                    'coding_question_id' => $input['coding_question_id'],
                    'student_id' => $user['id'],
                    'solution_file_name' => !empty($answerText) ? 'Text Answer' : ($input['file_name'] ?? 'Solution.txt'),
                    'solution_file_url' => !empty($answerText) ? $answerText : $fileUrl,
                    'status' => 'SUBMITTED'
                ];
                
                $exist = supabaseSelect('coding_submissions', 'id', [
                    'coding_question_id' => $input['coding_question_id'],
                    'student_id' => $user['id']
                ], true);
                
                if ($exist['success'] && !empty($exist['data'])) {
                    $res = supabaseUpdate('coding_submissions', $subData, ['id' => $exist['data']['id']]);
                } else {
                    $res = supabaseInsert('coding_submissions', $subData);
                }
                echo json_encode(['success' => $res['success'], 'submission' => $res['data']]);
            }
            break;

        case ($route === '/api/exams/submissions' && $method === 'GET'):
            requireRole(['TEACHER', 'SUPER_ADMIN']);
            $examId = $_GET['exam_id'] ?? '';
            $params = [];
            if (!empty($examId)) {
                $params['exam_id'] = $examId;
            }
            $res = supabaseSelect('coding_submissions', '*, students(full_name), coding_questions(question_text)', $params);
            echo json_encode(['success' => true, 'submissions' => $res['data'] ?: []]);
            break;

        case ($route === '/api/exams/evaluate' && $method === 'POST'):
            $user = requireRole(['TEACHER']);
            if (empty($input['submission_id']) || !isset($input['score'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing coding score']);
                break;
            }
            
            // 1. Update coding submission
            $subUpdate = supabaseUpdate('coding_submissions', [
                'score' => (float)$input['score'],
                'feedback' => $input['feedback'] ?? '',
                'evaluated_by' => $user['id'],
                'status' => 'EVALUATED'
            ], ['id' => $input['submission_id']]);
            
            if (!$subUpdate['success']) {
                echo json_encode(['success' => false, 'error' => 'Failed to save score']);
                break;
            }
            
            $submission = is_array($subUpdate['data']) ? $subUpdate['data'][0] : $subUpdate['data'];
            
            // 2. Roll up coding results into main exam_results table (aggregate all coding questions of this exam)
            $examId = $submission['exam_id'];
            $studentId = $submission['student_id'];
            
            // Get total score of student for this exam
            $allSubmitsRes = supabaseSelect('coding_submissions', 'score', [
                'exam_id' => $examId,
                'student_id' => $studentId,
                'status' => 'EVALUATED'
            ]);
            
            $totalScore = 0;
            foreach ($allSubmitsRes['data'] ?: [] as $s) {
                $totalScore += (float)$s['score'];
            }
            
            // Find max marks for coding questions in this exam
            $questionsRes = supabaseSelect('coding_questions', 'max_marks', ['exam_id' => $examId]);
            $maxScore = 0;
            foreach ($questionsRes['data'] ?: [] as $q) {
                $maxScore += (float)$q['max_marks'];
            }
            
            // Save to exam_results
            $resData = [
                'exam_id' => $examId,
                'student_id' => $studentId,
                'score' => $totalScore,
                'max_score' => $maxScore,
                'evaluated_by' => $user['id']
            ];
            
            $exist = supabaseSelect('exam_results', 'id', ['exam_id' => $examId, 'student_id' => $studentId], true);
            if ($exist['success'] && !empty($exist['data'])) {
                supabaseUpdate('exam_results', $resData, ['id' => $exist['data']['id']]);
            } else {
                supabaseInsert('exam_results', $resData);
            }
            
            echo json_encode(['success' => true, 'message' => 'Scoring complete']);
            break;

        // --- RESULTS AND MARKS SUMMARY ---
        case ($route === '/api/results' && $method === 'GET'):
            $user = verifyToken();
            if ($user['role'] === 'STUDENT') {
                $res = supabaseSelect('exam_results', '*, exams(title, exam_type)', ['student_id' => $user['id']]);
                $asgRes = supabaseSelect('assignment_submissions', '*, assignments(title)', ['student_id' => $user['id'], 'status' => 'EVALUATED']);
                echo json_encode([
                    'success' => true, 
                    'exams' => $res['data'] ?: [],
                    'assignments' => $asgRes['data'] ?: []
                ]);
            } else {
                $res = supabaseSelect('exam_results', '*, students(full_name), exams(title)');
                echo json_encode(['success' => true, 'results' => $res['data'] ?: []]);
            }
            break;

        // --- SYSTEM SETTINGS ---
        case ($route === '/api/settings' && $method === 'GET'):
            $settingsFile = __DIR__ . '/settings.json';
            $settings = ['digital_payment_enabled' => true];
            if (file_exists($settingsFile)) {
                $settings = json_decode(file_get_contents($settingsFile), true) ?: ['digital_payment_enabled' => true];
            }
            echo json_encode(['success' => true, 'settings' => $settings]);
            break;

        case ($route === '/api/settings' && $method === 'POST'):
            requireRole(['SUPER_ADMIN']);
            $settingsFile = __DIR__ . '/settings.json';
            $settings = ['digital_payment_enabled' => true];
            if (file_exists($settingsFile)) {
                $settings = json_decode(file_get_contents($settingsFile), true) ?: ['digital_payment_enabled' => true];
            }
            if (isset($input['digital_payment_enabled'])) {
                $settings['digital_payment_enabled'] = (bool)$input['digital_payment_enabled'];
            }
            file_put_contents($settingsFile, json_encode($settings, JSON_PRETTY_PRINT));
            echo json_encode(['success' => true, 'settings' => $settings]);
            break;

        // --- FEE & PAYMENTS ---
        case ($route === '/api/fees' && $method === 'GET'):
            $user = verifyTokenOrApiKey();
            if ($user['role'] === 'STUDENT') {
                $ledger = supabaseSelect('fee_records', '*', ['student_id' => $user['id']], true);
                $txns = supabaseSelect('payment_transactions', '*', ['student_id' => $user['id']]);
                echo json_encode([
                    'success' => true,
                    'ledger' => $ledger['data'] ?: null,
                    'transactions' => $txns['data'] ?: []
                ]);
            } elseif ($user['role'] === 'SERVICE' && (!empty($_GET['student_id']) || !empty($_GET['phone']))) {
                // n8n service account: look up fees by student_id query param or phone fallback
                $sid = $_GET['student_id'] ?? '';
                if (empty($sid) || strpos($sid, '{{') !== false) {
                    if (!empty($_GET['phone'])) {
                        $p = preg_replace('/[^0-9]/', '', $_GET['phone']);
                        $sr = supabaseSelect('students', 'id', ['mobile_number' => 'ilike.*' . substr($p, -10)]);
                        if ($sr['success'] && !empty($sr['data'])) {
                            $sid = $sr['data'][0]['id'];
                        }
                    }
                    if (empty($sid) || strpos($sid, '{{') !== false) {
                        $sr = supabaseSelect('students', 'id');
                        if ($sr['success'] && !empty($sr['data'])) {
                            $sid = $sr['data'][0]['id'];
                        }
                    }
                }
                if (!empty($sid) && strpos($sid, '{{') === false) {
                    $ledger = supabaseSelect('fee_records', '*', ['student_id' => $sid], true);
                    $txns = supabaseSelect('payment_transactions', '*', ['student_id' => $sid]);
                    echo json_encode([
                        'success' => true,
                        'ledger' => $ledger['data'] ?: null,
                        'transactions' => $txns['data'] ?: []
                    ]);
                } else {
                    echo json_encode(['success' => true, 'ledger' => null, 'transactions' => []]);
                }
            } else {
                // Admin and Teacher view all fees
                $ledger = supabaseSelect('fee_records', '*, students(full_name)');
                $txns = supabaseSelect('payment_transactions', '*, students(full_name)');
                echo json_encode([
                    'success' => true,
                    'ledgers' => $ledger['data'] ?: [],
                    'transactions' => $txns['data'] ?: []
                ]);
            }
            break;

        case ($route === '/api/fees/override' && $method === 'POST'):
            requireRole(['SUPER_ADMIN']);
            if (empty($input['student_id']) || !isset($input['fee_amount'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing student_id or fee_amount']);
                break;
            }
            $studentId = $input['student_id'];
            $newFee = (float)$input['fee_amount'];
            
            // Recalculate
            $studentRes = supabaseSelect('students', 'fee_paid', ['id' => $studentId], true);
            $paid = $studentRes['success'] ? (float)$studentRes['data']['fee_paid'] : 0.00;
            $pending = max(0.00, $newFee - $paid);
            
            // Update student record
            supabaseUpdate('students', [
                'fee_amount' => $newFee,
                'fee_pending' => $pending
            ], ['id' => $studentId]);
            
            // Update fee ledger
            $status = ($pending <= 0.01) ? 'PAID' : (($paid > 0) ? 'PARTIAL' : 'PENDING');
            $res = supabaseUpdate('fee_records', [
                'total_amount' => $newFee,
                'pending_amount' => $pending,
                'status' => $status,
                'updated_at' => date('Y-m-d H:i:s')
            ], ['student_id' => $studentId]);
            
            echo json_encode(['success' => $res['success'], 'ledger' => $res['data']]);
            break;

        case ($route === '/api/fees/pay' && $method === 'POST'):
            $user = verifyToken(); // Student can pay online, Admin can record cash/online
            if (empty($input['student_id']) || empty($input['amount']) || empty($input['payment_method'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing student, amount or method']);
                break;
            }
            
            // Enforce teacher restriction (TRD: Teacher cannot edit fee payments)
            if ($user['role'] === 'TEACHER') {
                http_response_code(403);
                echo json_encode(['success' => false, 'error' => 'Teachers cannot record payments']);
                break;
            }

            // Check if digital payments are enabled when attempting ONLINE payment
            if ($input['payment_method'] === 'ONLINE') {
                $settingsFile = __DIR__ . '/settings.json';
                $settings = ['digital_payment_enabled' => true];
                if (file_exists($settingsFile)) {
                    $settings = json_decode(file_get_contents($settingsFile), true) ?: ['digital_payment_enabled' => true];
                }
                if (empty($settings['digital_payment_enabled'])) {
                    http_response_code(400);
                    echo json_encode(['success' => false, 'error' => 'Online payments are currently disabled by the administration.']);
                    break;
                }
            }

            $res = createPayment($input['student_id'], $input['amount'], $input['payment_method']);
            echo json_encode($res);
            break;

        case ($route === '/api/fees/request' && $method === 'POST'):
            $user = requireRole(['SUPER_ADMIN']);
            if (empty($input['amount']) || empty($input['due_date']) || empty($input['target_type'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing fee request details']);
                break;
            }
            
            $amount = (float)$input['amount'];
            $dueDate = $input['due_date'];
            $targetType = $input['target_type'];
            $targetId = $input['target_id'] ?? null;
            
            // Find target student IDs
            $studentIds = [];
            if ($targetType === 'INDIVIDUAL') {
                if (empty($targetId)) {
                    http_response_code(400);
                    echo json_encode(['success' => false, 'error' => 'target_id is required for INDIVIDUAL target']);
                    break;
                }
                $studentIds = [$targetId];
            } elseif ($targetType === 'COURSE') {
                if (empty($targetId)) {
                    http_response_code(400);
                    echo json_encode(['success' => false, 'error' => 'target_id is required for COURSE target']);
                    break;
                }
                $cRes = supabaseSelect('student_courses', 'student_id', ['course_id' => $targetId]);
                $studentIds = array_column($cRes['data'] ?: [], 'student_id');
            } elseif ($targetType === 'REMAINING') {
                $sRes = supabaseSelect('students', 'id, fee_pending');
                $studentIds = [];
                foreach ($sRes['data'] ?: [] as $s) {
                    if ((float)$s['fee_pending'] > 0.01) {
                        $studentIds[] = $s['id'];
                    }
                }
            } else {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Invalid target_type']);
                break;
            }
            
            if (empty($studentIds)) {
                echo json_encode(['success' => true, 'count' => 0, 'message' => 'No target students found']);
                break;
            }
            
            $count = 0;
            foreach ($studentIds as $sId) {
                // Fetch student details to recalculate
                $studentRes = supabaseSelect('students', 'fee_paid', ['id' => $sId], true);
                if (!$studentRes['success'] || empty($studentRes['data'])) {
                    continue;
                }
                $paid = (float)$studentRes['data']['fee_paid'];
                $pending = max(0.00, $amount - $paid);
                
                // Update student record
                supabaseUpdate('students', [
                    'fee_amount' => $amount,
                    'fee_pending' => $pending
                ], ['id' => $sId]);
                
                // Update fee ledger
                $status = ($pending <= 0.01) ? 'PAID' : (($paid > 0) ? 'PARTIAL' : 'PENDING');
                supabaseUpdate('fee_records', [
                    'total_amount' => $amount,
                    'pending_amount' => $pending,
                    'status' => $status,
                    'updated_at' => date('Y-m-d H:i:s')
                ], ['student_id' => $sId]);
                
                // Send notification to the student
                $notifData = [
                    'title' => 'Fee Payment Request',
                    'message' => "A fee request of INR " . number_format($amount, 2) . " has been issued. Due Date: " . $dueDate . ". Please clear the remaining balance.",
                    'sender_id' => $user['id'],
                    'target_type' => 'INDIVIDUAL_STUDENT',
                    'target_id' => $sId,
                    'notification_type' => 'GENERAL'
                ];
                supabaseInsert('notifications', $notifData);
                $count++;
            }
            
            echo json_encode(['success' => true, 'count' => $count, 'message' => "Fee request successfully sent to $count student(s)"]);
            break;

        case ($route === '/api/fees/verify-payment' && $method === 'POST'):
            verifyToken(); // Student triggers verification upon online success modal callback
            if (empty($input['transaction_id'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'transaction_id required']);
                break;
            }
            $razorpayPaymentId = $input['razorpay_payment_id'] ?? null;
            $razorpayOrderId = $input['razorpay_order_id'] ?? null;
            $razorpaySignature = $input['razorpay_signature'] ?? null;
            
            $res = verifyPayment($input['transaction_id'], $razorpayPaymentId, $razorpayOrderId, $razorpaySignature);
            echo json_encode($res);
            break;

        case (preg_match('/^\/api\/fees\/transactions\/([a-zA-Z0-9_-]+)\/receipt$/', $route, $matches) && $method === 'GET'):
            verifyToken();
            $txnId = $matches[1];
            $receipt = downloadReceipt($txnId);
            echo json_encode(['success' => !isset($receipt['error']), 'receipt' => $receipt]);
            break;

        // --- WEEKLY TIMETABLE ---
        case ($route === '/api/timetable' && $method === 'GET'):
            $user = verifyToken();
            if ($user['role'] === 'STUDENT') {
                $res = supabaseSelect('timetable', '*, courses!inner(course_name, student_courses!inner(student_id)), batches!inner(batch_name, student_batches!inner(student_id)), teachers(full_name)', [
                    'batches.student_batches.student_id' => $user['id'],
                    'courses.student_courses.student_id' => $user['id']
                ]);
                if ($res['success'] && !empty($res['data'])) {
                    foreach ($res['data'] as &$t) {
                        if (isset($t['batches']['student_batches'])) {
                            unset($t['batches']['student_batches']);
                        }
                        if (isset($t['courses']['student_courses'])) {
                            unset($t['courses']['student_courses']);
                        }
                    }
                }
                echo json_encode(['success' => $res['success'], 'timetable' => $res['data'] ?: [], 'error' => $res['error']]);
            } else {
                $batchId = $_GET['batch_id'] ?? '';
                $params = [];
                if (!empty($batchId)) {
                    $params['batch_id'] = $batchId;
                }
                $res = supabaseSelect('timetable', '*, courses(course_name), batches(batch_name), teachers(full_name)', $params);
                echo json_encode(['success' => true, 'timetable' => $res['data'] ?: []]);
            }
            break;

        case ($route === '/api/timetable' && $method === 'POST'):
            $user = requireRole(['TEACHER', 'SUPER_ADMIN']);
            
            // Bulk insertion
            if (isset($input['slots']) && is_array($input['slots'])) {
                $inserted = [];
                foreach ($input['slots'] as $slot) {
                    if (empty($slot['day_of_week']) || empty($slot['start_time']) || empty($slot['end_time']) || empty($slot['topic'])) {
                        continue;
                    }
                    $slotData = [
                        'day_of_week' => $slot['day_of_week'],
                        'start_time' => $slot['start_time'],
                        'end_time' => $slot['end_time'],
                        'topic' => $slot['topic'],
                        'course_id' => $input['course_id'],
                        'batch_id' => $input['batch_id'],
                        'teacher_id' => !empty($slot['teacher_id']) ? $slot['teacher_id'] : (($user['role'] === 'TEACHER') ? $user['id'] : null)
                    ];
                    $res = supabaseInsert('timetable', $slotData);
                    if ($res['success']) {
                        $inserted[] = $res['data'];
                    }
                }
                echo json_encode(['success' => true, 'timetable' => $inserted]);
                break;
            }
            
            // Fallback: Single slot creation
            if (empty($input['day_of_week']) || empty($input['start_time']) || empty($input['end_time']) || empty($input['topic']) || empty($input['course_id']) || empty($input['batch_id'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing timetable details']);
                break;
            }
            $input['teacher_id'] = $input['teacher_id'] ?? (($user['role'] === 'TEACHER') ? $user['id'] : null);
            $res = supabaseInsert('timetable', $input);
            echo json_encode(['success' => $res['success'], 'timetable' => $res['data'], 'error' => $res['error']]);
            break;

        case (preg_match('/^\/api\/timetable\/([a-zA-Z0-9-]+)$/', $route, $matches) && $method === 'PUT'):
            $user = requireRole(['TEACHER', 'SUPER_ADMIN']);
            $id = $matches[1];
            if (empty($input['day_of_week']) || empty($input['start_time']) || empty($input['end_time']) || empty($input['topic']) || empty($input['course_id']) || empty($input['batch_id'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing timetable details']);
                break;
            }
            $updateData = [
                'day_of_week' => $input['day_of_week'],
                'start_time' => $input['start_time'],
                'end_time' => $input['end_time'],
                'topic' => $input['topic'],
                'course_id' => $input['course_id'],
                'batch_id' => $input['batch_id'],
                'teacher_id' => !empty($input['teacher_id']) ? $input['teacher_id'] : null
            ];
            $res = supabaseUpdate('timetable', $updateData, ['id' => $id]);
            echo json_encode(['success' => $res['success'], 'timetable' => $res['data'], 'error' => $res['error']]);
            break;

        case (preg_match('/^\/api\/timetable\/([a-zA-Z0-9-]+)$/', $route, $matches) && $method === 'DELETE'):
            $user = requireRole(['TEACHER', 'SUPER_ADMIN']);
            $id = $matches[1];
            $res = supabaseDelete('timetable', ['id' => $id]);
            echo json_encode(['success' => $res['success'], 'error' => $res['error']]);
            break;

        // --- NOTIFICATION SYSTEM ---
        case ($route === '/api/notifications' && $method === 'GET'):
            $user = verifyToken();
            
            // Build filter: Student sees ALL and notifications matching their course or batch, or individual notifications
            if ($user['role'] === 'STUDENT') {
                // Fetch student batches & courses
                $cRes = supabaseSelect('student_courses', 'course_id', ['student_id' => $user['id']]);
                $bRes = supabaseSelect('student_batches', 'batch_id', ['student_id' => $user['id']]);
                
                $courseIds = array_column($cRes['data'] ?: [], 'course_id');
                $batchIds = array_column($bRes['data'] ?: [], 'batch_id');
                
                // Fetch notifications
                $notifsRes = supabaseSelect('notifications', '*, users(email)');
                $filtered = [];
                foreach ($notifsRes['data'] ?: [] as $n) {
                    if ($n['target_type'] === 'ALL') {
                        $filtered[] = $n;
                    } elseif ($n['target_type'] === 'COURSE' && in_array($n['target_id'], $courseIds)) {
                        $filtered[] = $n;
                    } elseif ($n['target_type'] === 'BATCH' && in_array($n['target_id'], $batchIds)) {
                        $filtered[] = $n;
                    } elseif ($n['target_type'] === 'INDIVIDUAL_STUDENT' && $n['target_id'] === $user['id']) {
                        $filtered[] = $n;
                    }
                }
                // Sort notifications by created_at descending (latest first)
                usort($filtered, function($a, $b) {
                    return strtotime($b['created_at'] ?? '') - strtotime($a['created_at'] ?? '');
                });
                echo json_encode(['success' => true, 'notifications' => $filtered]);
            } else {
                // Admin and Teachers view all notifications
                $res = supabaseSelect('notifications', '*, users(email)');
                $notifs = $res['data'] ?: [];
                // Sort notifications by created_at descending (latest first)
                usort($notifs, function($a, $b) {
                    return strtotime($b['created_at'] ?? '') - strtotime($a['created_at'] ?? '');
                });
                echo json_encode(['success' => true, 'notifications' => $notifs]);
            }
            break;

        case ($route === '/api/notifications' && $method === 'POST'):
            $user = verifyTokenOrApiKey();
            if (empty($input['title']) || empty($input['message']) || empty($input['target_type']) || empty($input['notification_type'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing notification configurations']);
                break;
            }
            $input['sender_id'] = $user['id'];
            $res = supabaseInsert('notifications', $input);
            echo json_encode(['success' => $res['success'], 'notification' => $res['data'], 'error' => $res['error']]);
            break;

        // --- CERTIFICATES ---
        case ($route === '/api/certificates' && $method === 'GET'):
            $user = verifyToken();
            if ($user['role'] === 'STUDENT') {
                $res = supabaseSelect('certificates', '*, students(full_name), courses(course_name)', ['student_id' => $user['id']]);
                echo json_encode(['success' => true, 'certificates' => $res['data'] ?: []]);
            } else {
                $res = supabaseSelect('certificates', '*, students(full_name), courses(course_name)');
                echo json_encode(['success' => true, 'certificates' => $res['data'] ?: []]);
            }
            break;

        case ($route === '/api/certificates' && $method === 'POST'):
            $user = requireRole(['SUPER_ADMIN']);
            if (empty($input['student_id']) || empty($input['course_id'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing student_id or course_id']);
                break;
            }
            
            $certId = 'CERT_' . strtoupper(substr(md5($input['student_id'] . $input['course_id'] . time()), 0, 10));
            
            // Build dynamic absolute URL for QR code (so mobile phone cameras can scan and open it)
            $protocol = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? "https" : "http";
            $host = $_SERVER['HTTP_HOST'];
            
            // If running locally, route backend port (8000) to React frontend port (5173)
            if ($host === 'localhost:8000' || $host === '127.0.0.1:8000') {
                $host = 'localhost:5173';
            }
            
            $absoluteVerificationUrl = $protocol . "://" . $host . "/verify-certificate/" . $certId;
            $verificationUrl = "/verify-certificate/" . $certId;
            
            $certData = [
                'student_id' => $input['student_id'],
                'course_id' => $input['course_id'],
                'certificate_id' => $certId,
                'verification_url' => $verificationUrl,
                'qr_code_url' => 'https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=' . urlencode($absoluteVerificationUrl)
            ];
            
            if (!empty($input['completion_date'])) {
                $certData['completion_date'] = $input['completion_date'];
            }
            
            $res = supabaseInsert('certificates', $certData);
            echo json_encode(['success' => $res['success'], 'certificate' => $res['data'], 'error' => $res['error']]);
            break;

        case (preg_match('/^\/api\/certificates\/([a-zA-Z0-9-]+)$/', $route, $matches) && $method === 'DELETE'):
            $user = requireRole(['SUPER_ADMIN']);
            $certId = $matches[1];
            $res = supabaseDelete('certificates', ['id' => $certId]);
            echo json_encode(['success' => $res['success'], 'error' => $res['error']]);
            break;

        // --- GENERAL MANAGEMENT REPORTS ---
        case ($route === '/api/reports' && $method === 'GET'):
            $user = verifyToken();
            $reportType = $_GET['type'] ?? '';

            if ($user['role'] === 'SUPER_ADMIN') {
                // Fetch datasets
                $students = supabaseSelect('students', 'id, full_name, fee_amount, fee_paid, fee_pending');
                $attendance = supabaseSelect('attendance', 'status');
                $courses = supabaseSelect('courses', 'id, course_name, fees');
                $exams = supabaseSelect('exams', 'id, title');
                
                echo json_encode([
                    'success' => true,
                    'summary' => [
                        'total_students' => count($students['data'] ?: []),
                        'total_courses' => count($courses['data'] ?: []),
                        'total_exams' => count($exams['data'] ?: []),
                        'revenue' => [
                            'collected' => array_sum(array_column($students['data'] ?: [], 'fee_paid')),
                            'pending' => array_sum(array_column($students['data'] ?: [], 'fee_pending'))
                        ]
                    ]
                ]);
            } elseif ($user['role'] === 'TEACHER') {
                $attendance = supabaseSelect('attendance', 'status, student_id', ['marked_by' => $user['id']]);
                $exams = supabaseSelect('exams', 'id, title', ['created_by' => $user['id']]);
                
                echo json_encode([
                    'success' => true,
                    'summary' => [
                        'attendance_records' => count($attendance['data'] ?: []),
                        'exams_created' => count($exams['data'] ?: [])
                    ]
                ]);
            } else {
                // Student progress report
                $attendance = supabaseSelect('attendance', 'status', ['student_id' => $user['id']]);
                $results = supabaseSelect('exam_results', 'score, max_score', ['student_id' => $user['id']]);
                
                $totalAtt = count($attendance['data'] ?: []);
                $presentAtt = 0;
                foreach ($attendance['data'] ?: [] as $a) {
                    if ($a['status'] === 'PRESENT') $presentAtt++;
                }
                
                echo json_encode([
                    'success' => true,
                    'progress' => [
                        'attendance_percentage' => $totalAtt > 0 ? round(($presentAtt / $totalAtt) * 100, 2) : 100,
                        'exams_attempted' => count($results['data'] ?: [])
                    ]
                ]);
            }
            break;

        // --- LIVE SESSIONS ENDPOINTS ---
        case ($route === '/api/live-sessions' && $method === 'GET'):
            $user = verifyToken();
            if ($user['role'] === 'STUDENT') {
                $res = supabaseSelect('live_sessions', '*, courses(course_name), batches!inner(batch_name, student_batches!inner(student_id)), teachers(full_name)', [
                    'batches.student_batches.student_id' => $user['id']
                ]);
                if ($res['success'] && !empty($res['data'])) {
                    // Clean internal tables injected by PostgREST inner join structure
                    foreach ($res['data'] as &$session) {
                        if (isset($session['batches']['student_batches'])) {
                            unset($session['batches']['student_batches']);
                        }
                    }
                }
                echo json_encode(['success' => $res['success'], 'live_sessions' => $res['data'] ?: [], 'error' => $res['error']]);
            } else {
                $params = [];
                if ($user['role'] === 'TEACHER') {
                    $params['teacher_id'] = $user['id'];
                }
                $res = supabaseSelect('live_sessions', '*, courses(course_name), batches(batch_name), teachers(full_name)', $params);
                echo json_encode(['success' => $res['success'], 'live_sessions' => $res['data'] ?: [], 'error' => $res['error']]);
            }
            break;

        case ($route === '/api/live-sessions' && $method === 'POST'):
            $user = requireRole(['TEACHER', 'SUPER_ADMIN']);
            if (empty($input['course_id']) || empty($input['batch_id']) || empty($input['session_type']) || empty($input['scheduled_at'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing required live session fields']);
                break;
            }
            $sessionData = [
                'course_id' => $input['course_id'],
                'batch_id' => $input['batch_id'],
                'teacher_id' => $user['id'],
                'session_type' => $input['session_type'],
                'message' => $input['message'] ?? '',
                'meeting_link' => $input['meeting_link'] ?? null,
                'video_link' => $input['video_link'] ?? null,
                'chat_enabled' => isset($input['chat_enabled']) ? (bool)$input['chat_enabled'] : true,
                'raise_hand_enabled' => isset($input['raise_hand_enabled']) ? (bool)$input['raise_hand_enabled'] : true,
                'voice_enabled' => isset($input['voice_enabled']) ? (bool)$input['voice_enabled'] : true,
                'scheduled_at' => $input['scheduled_at'],
                'status' => $input['status'] ?? 'SCHEDULED'
            ];
            $res = supabaseInsert('live_sessions', $sessionData);
            echo json_encode(['success' => $res['success'], 'live_session' => $res['data'], 'error' => $res['error']]);
            break;

        case (preg_match('/^\/api\/live-sessions\/([a-zA-Z0-9-]+)$/', $route, $matches) && $method === 'PUT'):
            $user = verifyToken();
            $sessionId = $matches[1];
            // Check authorization: teachers can edit their own session, admins edit all
            $check = supabaseSelect('live_sessions', 'teacher_id', ['id' => $sessionId], true);
            if (!$check['success'] || empty($check['data'])) {
                http_response_code(404);
                echo json_encode(['success' => false, 'error' => 'Live session not found']);
                break;
            }
            if ($user['role'] !== 'SUPER_ADMIN' && $check['data']['teacher_id'] !== $user['id']) {
                http_response_code(403);
                echo json_encode(['success' => false, 'error' => 'Forbidden: You cannot modify this live session']);
                break;
            }

            $allowedFields = ['status', 'chat_enabled', 'raise_hand_enabled', 'voice_enabled', 'message', 'meeting_link', 'video_link', 'scheduled_at'];
            $updateData = [];
            foreach ($allowedFields as $field) {
                if (isset($input[$field])) {
                    if (in_array($field, ['chat_enabled', 'raise_hand_enabled', 'voice_enabled'])) {
                        $updateData[$field] = (bool)$input[$field];
                    } else {
                        $updateData[$field] = $input[$field];
                    }
                }
            }

            if (empty($updateData)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'No fields to update']);
                break;
            }

            $res = supabaseUpdate('live_sessions', $updateData, ['id' => $sessionId]);
            echo json_encode(['success' => $res['success'], 'live_session' => $res['data'], 'error' => $res['error']]);
            break;

        case (preg_match('/^\/api\/live-sessions\/([a-zA-Z0-9-]+)$/', $route, $matches) && $method === 'DELETE'):
            $user = requireRole(['TEACHER', 'SUPER_ADMIN']);
            $sessionId = $matches[1];
            
            // Check authorization: teachers can delete their own session, admins delete all
            if ($user['role'] === 'TEACHER') {
                $check = supabaseSelect('live_sessions', 'teacher_id', ['id' => $sessionId], true);
                if (!$check['success'] || empty($check['data']) || $check['data']['teacher_id'] !== $user['id']) {
                    http_response_code(403);
                    echo json_encode(['success' => false, 'error' => 'Forbidden: You cannot delete this live session']);
                    break;
                }
            }
            
            $res = supabaseDelete('live_sessions', ['id' => $sessionId]);
            echo json_encode(['success' => $res['success'], 'error' => $res['error']]);
            break;

        case (preg_match('/^\/api\/live-sessions\/([a-zA-Z0-9-]+)\/chats$/', $route, $matches) && $method === 'GET'):
            $user = verifyToken();
            $sessionId = $matches[1];
            // Order chat messages by created_at in ascending order (using .asc operator for PostgREST)
            $res = supabaseSelect('live_chat_messages', '*', ['session_id' => $sessionId, 'order' => 'created_at.asc']);
            echo json_encode(['success' => $res['success'], 'chats' => $res['data'] ?: [], 'error' => $res['error']]);
            break;

        case (preg_match('/^\/api\/live-sessions\/([a-zA-Z0-9-]+)\/chats$/', $route, $matches) && $method === 'POST'):
            $user = verifyToken();
            $sessionId = $matches[1];
            
            $messageType = $input['message_type'] ?? 'TEXT';
            if ($messageType === 'VOICE' && empty($input['voice_url'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Voice URL is required for voice messages']);
                break;
            }
            if ($messageType === 'TEXT' && empty($input['message'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Message is required']);
                break;
            }

            // Verify live session exists and chat is enabled
            $session = supabaseSelect('live_sessions', 'chat_enabled, voice_enabled', ['id' => $sessionId], true);
            if (!$session['success'] || empty($session['data'])) {
                http_response_code(404);
                echo json_encode(['success' => false, 'error' => 'Live session not found']);
                break;
            }
            if (!$session['data']['chat_enabled']) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Live chat is disabled for this session']);
                break;
            }
            if ($messageType === 'VOICE' && !$session['data']['voice_enabled']) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Voice messages are disabled for this session']);
                break;
            }

            // Fetch latest sender full name from profile table
            $senderName = $user['full_name'];
            if ($user['role'] === 'TEACHER') {
                $prof = supabaseSelect('teachers', 'full_name', ['id' => $user['id']], true);
                if ($prof['success'] && !empty($prof['data'])) {
                    $senderName = $prof['data']['full_name'];
                }
            } else if ($user['role'] === 'STUDENT') {
                $prof = supabaseSelect('students', 'full_name', ['id' => $user['id']], true);
                if ($prof['success'] && !empty($prof['data'])) {
                    $senderName = $prof['data']['full_name'];
                }
            }

            $chatData = [
                'session_id' => $sessionId,
                'user_id' => $user['id'],
                'sender_name' => $senderName,
                'sender_role' => $user['role'],
                'message' => $input['message'] ?? ($messageType === 'VOICE' ? '[Voice Message]' : ''),
                'message_type' => $messageType,
                'voice_url' => $input['voice_url'] ?? null
            ];

            $res = supabaseInsert('live_chat_messages', $chatData);
            echo json_encode(['success' => $res['success'], 'chat' => $res['data'], 'error' => $res['error']]);
            break;

        case (preg_match('/^\/api\/live-sessions\/([a-zA-Z0-9-]+)\/raised-hands$/', $route, $matches) && $method === 'GET'):
            $user = verifyToken();
            $sessionId = $matches[1];
            // Retrieve raised hands with students' names
            $res = supabaseSelect('live_session_raised_hands', '*, students(full_name)', ['session_id' => $sessionId, 'status' => 'RAISED']);
            echo json_encode(['success' => $res['success'], 'raised_hands' => $res['data'] ?: [], 'error' => $res['error']]);
            break;

        case (preg_match('/^\/api\/live-sessions\/([a-zA-Z0-9-]+)\/raise-hand$/', $route, $matches) && $method === 'POST'):
            $user = requireRole(['STUDENT']);
            $sessionId = $matches[1];
            
            // Check if hand-raise is enabled
            $session = supabaseSelect('live_sessions', 'raise_hand_enabled', ['id' => $sessionId], true);
            if (!$session['success'] || empty($session['data'])) {
                http_response_code(404);
                echo json_encode(['success' => false, 'error' => 'Live session not found']);
                break;
            }
            if (!$session['data']['raise_hand_enabled']) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Raise hand is disabled for this session']);
                break;
            }

            // UPSERT/insert the raised hand
            $handData = [
                'session_id' => $sessionId,
                'student_id' => $user['id'],
                'status' => 'RAISED'
            ];
            
            // Try to select first to see if it already exists
            $checkExist = supabaseSelect('live_session_raised_hands', 'id, status', [
                'session_id' => $sessionId,
                'student_id' => $user['id']
            ], true);
            
            if ($checkExist['success'] && !empty($checkExist['data'])) {
                // If it exists, update it to RAISED
                $res = supabaseUpdate('live_session_raised_hands', ['status' => 'RAISED'], ['id' => $checkExist['data']['id']]);
            } else {
                $res = supabaseInsert('live_session_raised_hands', $handData);
            }
            
            echo json_encode(['success' => $res['success'], 'raised_hand' => $res['data'], 'error' => $res['error']]);
            break;

        case (preg_match('/^\/api\/live-sessions\/([a-zA-Z0-9-]+)\/resolve-hand$/', $route, $matches) && $method === 'POST'):
            $user = requireRole(['TEACHER', 'SUPER_ADMIN']);
            $sessionId = $matches[1];
            $studentId = $input['student_id'] ?? '';

            if (empty($studentId)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Missing student_id']);
                break;
            }

            // Set the status to RESOLVED
            $res = supabaseUpdate('live_session_raised_hands', ['status' => 'RESOLVED'], [
                'session_id' => $sessionId,
                'student_id' => $studentId
            ]);
            echo json_encode(['success' => $res['success'], 'error' => $res['error']]);
            break;

        case ($route === '/api/upload-audio' && $method === 'POST'):
            $user = verifyToken();
            if (empty($_FILES['audio'])) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'No audio file uploaded']);
                break;
            }
            
            $file = $_FILES['audio'];
            if ($file['error'] !== UPLOAD_ERR_OK) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'File upload error code: ' . $file['error']]);
                break;
            }
            
            $fileContent = file_get_contents($file['tmp_name']);
            if ($fileContent === false) {
                http_response_code(500);
                echo json_encode(['success' => false, 'error' => 'Failed to read uploaded file content']);
                break;
            }
            
            // Determine path based on role
            $folder = ($user['role'] === 'STUDENT') ? 'student_uploads' : 'uploads';
            $fileName = 'voice_' . bin2hex(random_bytes(8)) . '_' . time() . '.webm';
            $filePath = $folder . '/' . $fileName;
            
            // Upload to Supabase using service key
            global $SUPABASE_URL, $SUPABASE_SERVICE_ROLE_KEY;
            $storageUrl = str_replace('/rest/v1/', '/storage/v1/object/lms-files/', $SUPABASE_URL) . $filePath;
            
            $ch = curl_init();
            curl_setopt($ch, CURLOPT_URL, $storageUrl);
            curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
            curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'POST');
            curl_setopt($ch, CURLOPT_POSTFIELDS, $fileContent);
            curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
            
            $headers = [
                "apikey: " . $SUPABASE_SERVICE_ROLE_KEY,
                "Authorization: Bearer " . $SUPABASE_SERVICE_ROLE_KEY,
                "Content-Type: audio/webm"
            ];
            curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
            
            $response = curl_exec($ch);
            $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
            $error = curl_error($ch);
            curl_close($ch);
            
            if ($error) {
                http_response_code(500);
                echo json_encode(['success' => false, 'error' => 'cURL storage error: ' . $error]);
                break;
            }
            
            if ($httpCode >= 200 && $httpCode < 300) {
                // Get public URL
                $publicUrl = str_replace('/rest/v1/', '/storage/v1/object/public/lms-files/', $SUPABASE_URL) . $filePath;
                echo json_encode(['success' => true, 'publicUrl' => $publicUrl]);
            } else {
                http_response_code($httpCode ?: 500);
                echo json_encode(['success' => false, 'error' => 'Storage upload failed (HTTP ' . $httpCode . '): ' . $response]);
            }
            break;

        // --- RAG ENDPOINTS ---
        
        // RAG Stats
        case ($route === '/api/rag/stats' && $method === 'GET'):
            $user = verifyTokenOrApiKey();
            echo json_encode(RagService::getStats());
            break;

        // RAG Ask & Stream - Grounded Q&A with confidence gate & Socratic mode
        case (($route === '/api/rag/ask' || $route === '/api/rag/stream') && $method === 'POST'):
            $user = verifyTokenOrApiKey();
            $question = trim($input['question'] ?? $input['query'] ?? '');
            if (empty($question)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'question is required']);
                break;
            }

            $isStream = ($route === '/api/rag/stream') || !empty($input['stream']);
            $mode = in_array(strtolower($input['mode'] ?? ''), ['socratic', 'direct']) ? strtolower($input['mode']) : 'direct';
            
            // Safety boundary check
            $boundary = RagSafetyBoundary::evaluate($question);
            if ($boundary['action'] === 'ABSTAIN') {
                $abstainText = 'I apologize, but that question is outside the scope of the EduConnect LMS curriculum.';
                if ($isStream) {
                    if (!headers_sent()) {
                        header('Content-Type: text/event-stream; charset=UTF-8');
                        header('Cache-Control: no-cache, no-transform');
                        header('Connection: keep-alive');
                        header('X-Accel-Buffering: no');
                    }
                    while (ob_get_level() > 0) @ob_end_flush();
                    flush();
                    echo "event: metadata\ndata: " . json_encode(['sources' => [], 'confidence' => 0.0, 'abstain' => true, 'reason' => $boundary['reason'], 'mode' => $mode]) . "\n\n";
                    echo "event: token\ndata: " . json_encode(['token' => $abstainText]) . "\n\n";
                    echo "event: done\ndata: " . json_encode(['success' => true, 'answer' => $abstainText, 'sources' => [], 'abstain' => true, 'mode' => $mode]) . "\n\n";
                    flush();
                } else {
                    echo json_encode([
                        'success' => true,
                        'answer' => $abstainText,
                        'sources' => [],
                        'grounded' => false,
                        'abstain' => true,
                        'reason' => $boundary['reason'],
                        'mode' => $mode
                    ]);
                }
                break;
            }
            
            $courseId = $input['course_id'] ?? null;
            $batchId = $input['batch_id'] ?? null;
            $studentId = $input['student_id'] ?? ($user['role'] === 'STUDENT' ? $user['id'] : null);
            
            // Strict student authorization & scope enforcement
            if ($user['role'] === 'STUDENT') {
                $studentId = $user['id'];
                $sb = supabaseSelect('student_batches', 'batch_id, batches(course_id)', ['student_id' => $studentId], true);
                if ($sb['success'] && !empty($sb['data'])) {
                    $authBatchId = $sb['data']['batch_id'] ?? null;
                    $authCourseId = $sb['data']['batches']['course_id'] ?? null;
                    if (!empty($courseId) && $courseId !== $authCourseId) {
                        $authFailMsg = 'You do not have permission to access curriculum materials for this course.';
                        if ($isStream) {
                            if (!headers_sent()) {
                                header('Content-Type: text/event-stream; charset=UTF-8');
                                header('Cache-Control: no-cache, no-transform');
                                header('Connection: keep-alive');
                                header('X-Accel-Buffering: no');
                            }
                            while (ob_get_level() > 0) @ob_end_flush();
                            flush();
                            echo "event: metadata\ndata: " . json_encode(['sources' => [], 'confidence' => 0.0, 'abstain' => true, 'reason' => 'Unauthorized course access attempt', 'mode' => $mode]) . "\n\n";
                            echo "event: token\ndata: " . json_encode(['token' => $authFailMsg]) . "\n\n";
                            echo "event: done\ndata: " . json_encode(['success' => true, 'answer' => $authFailMsg, 'sources' => [], 'abstain' => true, 'mode' => $mode]) . "\n\n";
                            flush();
                        } else {
                            echo json_encode([
                                'success' => true,
                                'answer' => $authFailMsg,
                                'sources' => [],
                                'grounded' => false,
                                'abstain' => true,
                                'reason' => 'Unauthorized course access attempt',
                                'mode' => $mode
                            ]);
                        }
                        break;
                    }
                    $courseId = $authCourseId;
                    $batchId = $authBatchId;
                }
            } elseif (!empty($studentId) && (empty($courseId) || empty($batchId))) {
                $sb = supabaseSelect('student_batches', 'batch_id, batches(course_id)', ['student_id' => $studentId], true);
                if ($sb['success'] && !empty($sb['data'])) {
                    if (empty($batchId)) $batchId = $sb['data']['batch_id'] ?? null;
                    if (empty($courseId)) $courseId = $sb['data']['batches']['course_id'] ?? null;
                }
            }
            
            // Conversational query condensation
            $history = $input['history'] ?? $input['messages'] ?? [];
            $activeQuestion = $question;
            if (!empty($history)) {
                $condensed = RagQueryCondenser::condense($question, $history);
                $activeQuestion = $condensed['condensed_query'];
            }
            
            $studentName = $user['full_name'] ?? 'Student';

            // Real-Time SSE Stream Mode
            if ($isStream) {
                RagService::askStream($activeQuestion, $courseId, $batchId, $studentName, 4, $mode, $history, $studentId);
                break;
            }

            // Synchronous Mode
            $askRes = RagService::ask($activeQuestion, $courseId, $batchId, $studentName, 4, $mode);

            // Auto-persist conversation history if student context is present
            if (!empty($studentId) && !empty($askRes['answer'])) {
                try {
                    supabaseInsert('conversation_history', [
                        'student_id' => $studentId,
                        'role' => 'user',
                        'content' => $question
                    ]);
                    supabaseInsert('conversation_history', [
                        'student_id' => $studentId,
                        'role' => 'assistant',
                        'content' => $askRes['answer']
                    ]);
                } catch (\Throwable $e) {
                    // Silently ignore if conversation_history table is pending migration
                }
            }

            echo json_encode($askRes);
            break;

        // RAG NLI Claim Fact-Checking & Grounding Verification
        case ($route === '/api/rag/verify-claims' && $method === 'POST'):
            $user = verifyTokenOrApiKey();
            $answer = trim($input['answer'] ?? '');
            $sources = $input['sources'] ?? [];
            if (empty($answer)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'answer parameter is required']);
                break;
            }
            $verificationRes = RagService::verifyAnswerClaims($answer, $sources);
            echo json_encode(array_merge(['success' => true], $verificationRes));
            break;

        // Teacher Knowledge-Gap Heatmap & Curriculum Telemetry
        case (($route === '/api/rag/teacher/analytics' || $route === '/api/rag/analytics') && in_array($method, ['GET', 'POST'])):
            $user = verifyTokenOrApiKey();
            if ($user['role'] !== 'SERVICE' && !in_array($user['role'], ['SUPER_ADMIN', 'ADMIN', 'TEACHER'])) {
                http_response_code(403);
                echo json_encode(['success' => false, 'error' => 'Forbidden: Teacher or Admin access required']);
                break;
            }
            $courseId = $input['course_id'] ?? $_GET['course_id'] ?? null;
            $batchId = $input['batch_id'] ?? $_GET['batch_id'] ?? null;
            
            $analytics = RagService::getTeacherAnalytics($courseId, $batchId);
            echo json_encode($analytics);
            break;

        // Generate practice questions targeting specific knowledge gap or topic
        case ($route === '/api/rag/teacher/generate-practice' && $method === 'POST'):
            $user = verifyTokenOrApiKey();
            if ($user['role'] !== 'SERVICE' && !in_array($user['role'], ['SUPER_ADMIN', 'ADMIN', 'TEACHER'])) {
                http_response_code(403);
                echo json_encode(['success' => false, 'error' => 'Forbidden: Teacher or Admin access required']);
                break;
            }
            $topic = trim($input['topic'] ?? $input['question'] ?? '');
            if (empty($topic)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'topic or question parameter is required']);
                break;
            }
            $courseId = $input['course_id'] ?? null;
            $batchId = $input['batch_id'] ?? null;
            $count = isset($input['count']) ? max(1, min(10, (int)$input['count'])) : 3;
            $difficulty = $input['difficulty'] ?? 'AUTO';
            $studentId = $input['student_id'] ?? null;

            $practiceRes = RagService::generateQuiz($topic, $courseId, $batchId, $count, $difficulty, $studentId);
            if (!empty($practiceRes['questions']) && is_array($practiceRes['questions'])) {
                $formattedQuiz = [];
                foreach ($practiceRes['questions'] as $q) {
                    $opts = [];
                    $correct = $q['correct_answer'] ?? 'A';
                    foreach (($q['options'] ?? []) as $key => $val) {
                        $opts[] = [
                            'id' => $key,
                            'text' => $val,
                            'is_correct' => ($key === $correct)
                        ];
                    }
                    $formattedQuiz[] = [
                        'question' => $q['question'],
                        'options' => $opts,
                        'difficulty_tier' => $q['difficulty_tier'] ?? $practiceRes['difficulty_tier'] ?? 'APPLICATION',
                        'explanation' => "Grounded directly in indexed course curriculum.",
                        'citation' => $q['source_citation'] ?? ''
                    ];
                }
                $practiceRes['quiz'] = $formattedQuiz;
            }
            echo json_encode($practiceRes);
            break;

        // Teacher Autopilot Settings & Trigger Management
        case ($route === '/api/rag/teacher/autopilot' && in_array($method, ['GET', 'POST'])):
            $user = verifyTokenOrApiKey();
            if ($user['role'] !== 'SERVICE' && !in_array($user['role'], ['SUPER_ADMIN', 'ADMIN', 'TEACHER'])) {
                http_response_code(403);
                echo json_encode(['success' => false, 'error' => 'Forbidden: Teacher or Admin access required']);
                break;
            }
            $courseId = $input['course_id'] ?? $_GET['course_id'] ?? null;
            $batchId = $input['batch_id'] ?? $_GET['batch_id'] ?? null;

            if ($method === 'GET') {
                $config = RagService::getAutopilotConfig($courseId, $batchId);
                $events = RagService::getAutopilotEvents($courseId, $batchId, 10);
                echo json_encode([
                    'success' => true,
                    'config' => $config,
                    'events' => $events
                ]);
            } else {
                $action = $input['action'] ?? 'save_config';
                if ($action === 'evaluate' || $action === 'check_triggers') {
                    $force = !empty($input['force']);
                    $evalRes = RagService::evaluateAutopilotTriggers($courseId, $batchId, $user['id'], $force);
                    echo json_encode($evalRes);
                } else {
                    // save config
                    $savedConfig = RagService::saveAutopilotConfig([
                        'course_id' => $courseId,
                        'batch_id' => $batchId,
                        'enabled' => !empty($input['enabled']),
                        'threshold' => $input['threshold'] ?? 3,
                        'auto_publish' => !empty($input['auto_publish']),
                        'question_count' => $input['question_count'] ?? 3,
                        'time_limit_minutes' => $input['time_limit_minutes'] ?? 15
                    ]);
                    echo json_encode(['success' => true, 'config' => $savedConfig]);
                }
            }
            break;

        // Student Personal Mastery & Remedial Learning Journey
        case ($route === '/api/rag/student/mastery' && in_array($method, ['GET', 'POST'])):
            $user = verifyTokenOrApiKey();
            $studentId = $input['student_id'] ?? $_GET['student_id'] ?? $user['id'] ?? null;
            if (empty($studentId)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'Student ID is required']);
                break;
            }
            $courseId = $input['course_id'] ?? $_GET['course_id'] ?? null;
            $batchId = $input['batch_id'] ?? $_GET['batch_id'] ?? null;

            $masteryData = RagService::getStudentMasteryJourney($studentId, $courseId, $batchId);
            echo json_encode($masteryData);
            break;

        // Remedial Resource Recommendations for Knowledge Gaps
        case ($route === '/api/rag/remedial/resources' && in_array($method, ['GET', 'POST'])):
            $user = verifyTokenOrApiKey();
            $topic = trim($input['topic'] ?? $_GET['topic'] ?? '');
            if (empty($topic)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'topic parameter is required']);
                break;
            }
            $courseId = $input['course_id'] ?? $_GET['course_id'] ?? null;
            $batchId = $input['batch_id'] ?? $_GET['batch_id'] ?? null;

            $recs = RagService::getRemedialResourceRecommendations($topic, $courseId, $batchId);
            echo json_encode($recs);
            break;

        // Resolve Adaptive Difficulty Tier for Student / Topic
        case ($route === '/api/rag/adaptive/difficulty' && in_array($method, ['GET', 'POST'])):
            $user = verifyTokenOrApiKey();
            $topic = trim($input['topic'] ?? $_GET['topic'] ?? '');
            if (empty($topic)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'topic parameter is required']);
                break;
            }
            $studentId = $input['student_id'] ?? $_GET['student_id'] ?? ($user['role'] === 'STUDENT' ? $user['id'] : null);
            $courseId = $input['course_id'] ?? $_GET['course_id'] ?? null;
            $batchId = $input['batch_id'] ?? $_GET['batch_id'] ?? null;

            $diffData = RagService::resolveAdaptiveDifficulty($studentId, $topic, $courseId, $batchId);
            echo json_encode(array_merge(['success' => true, 'topic' => $topic, 'student_id' => $studentId], $diffData));
            break;

        // AI Concept Doctor: Initiate In-Context Socratic Consultation
        case ($route === '/api/rag/concept-doctor/initiate' && $method === 'POST'):
            $user = verifyTokenOrApiKey();
            $studentId = $input['student_id'] ?? ($user['role'] === 'STUDENT' ? $user['id'] : null);
            $topic = trim($input['topic'] ?? '');
            $question = trim($input['question'] ?? '');
            $studentChoice = trim($input['student_choice'] ?? '');
            $correctChoice = trim($input['correct_choice'] ?? '');
            $courseId = $input['course_id'] ?? null;
            $batchId = $input['batch_id'] ?? null;

            if (empty($topic) || empty($question)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'topic and question are required']);
                break;
            }

            $docRes = RagService::initiateConceptDoctorSession(
                $studentId ?: 'std_anon',
                $topic,
                $question,
                $studentChoice,
                $correctChoice,
                $courseId,
                $batchId
            );
            echo json_encode($docRes);
            break;

        // AI Concept Doctor: Interactive Turn & Breakthrough Evaluation
        case ($route === '/api/rag/concept-doctor/message' && $method === 'POST'):
            $user = verifyTokenOrApiKey();
            $studentId = $input['student_id'] ?? ($user['role'] === 'STUDENT' ? $user['id'] : null);
            $topic = trim($input['topic'] ?? '');
            $question = trim($input['question'] ?? '');
            $correctChoice = trim($input['correct_choice'] ?? '');
            $studentMessage = trim($input['message'] ?? '');
            $history = $input['history'] ?? [];
            $courseId = $input['course_id'] ?? null;
            $batchId = $input['batch_id'] ?? null;

            if (empty($studentMessage)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'message is required']);
                break;
            }

            $turnRes = RagService::respondConceptDoctorTurn(
                $studentId ?: 'std_anon',
                $topic,
                $question,
                $correctChoice,
                $studentMessage,
                $history,
                $courseId,
                $batchId
            );
            echo json_encode($turnRes);
            break;

        // RAG-Grounded Quiz Generator
        case ($route === '/api/rag/quiz' && $method === 'POST'):
            $user = verifyTokenOrApiKey();
            $topic = trim($input['topic'] ?? $input['query'] ?? '');
            if (empty($topic)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'topic parameter is required']);
                break;
            }
            
            $courseId = $input['course_id'] ?? null;
            $batchId = $input['batch_id'] ?? null;
            $studentId = $input['student_id'] ?? ($user['role'] === 'STUDENT' ? $user['id'] : null);

            // Strict student authorization for quiz generation
            if ($user['role'] === 'STUDENT') {
                $studentId = $user['id'];
                $sb = supabaseSelect('student_batches', 'batch_id, batches(course_id)', ['student_id' => $studentId], true);
                if ($sb['success'] && !empty($sb['data'])) {
                    $authBatchId = $sb['data']['batch_id'] ?? null;
                    $authCourseId = $sb['data']['batches']['course_id'] ?? null;
                    if (!empty($courseId) && $courseId !== $authCourseId) {
                        echo json_encode([
                            'success' => false,
                            'error' => 'Unauthorized course quiz access',
                            'quiz' => null,
                            'sources' => []
                        ]);
                        break;
                    }
                    $courseId = $authCourseId;
                    $batchId = $authBatchId;
                }
            } elseif (!empty($studentId) && (empty($courseId) || empty($batchId))) {
                $sb = supabaseSelect('student_batches', 'batch_id, batches(course_id)', ['student_id' => $studentId], true);
                if ($sb['success'] && !empty($sb['data'])) {
                    if (empty($batchId)) $batchId = $sb['data']['batch_id'] ?? null;
                    if (empty($courseId)) $courseId = $sb['data']['batches']['course_id'] ?? null;
                }
            }

            $count = isset($input['count']) ? max(1, min(10, (int)$input['count'])) : 5;
            $difficulty = $input['difficulty'] ?? 'AUTO';
            $quizRes = RagService::generateQuiz($topic, $courseId, $batchId, $count, $difficulty, $studentId);
            echo json_encode($quizRes);
            break;

        // RAG Active Quiz Session Sync (save/retrieve)
        case ($route === '/api/rag/quiz/active' && $method === 'POST'):
            $user = verifyTokenOrApiKey();
            $chatId = trim((string)($input['chat_id'] ?? $input['session_id'] ?? ''));
            $questions = $input['questions'] ?? [];
            if (empty($chatId) || empty($questions)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'chat_id and questions are required']);
                break;
            }
            RagService::saveActiveQuiz($chatId, $questions);
            echo json_encode(['success' => true, 'chat_id' => $chatId, 'questions_count' => count($questions)]);
            break;

        case ($route === '/api/rag/quiz/active' && $method === 'GET'):
            $user = verifyTokenOrApiKey();
            $chatId = trim((string)($_GET['chat_id'] ?? $_GET['session_id'] ?? ''));
            if (empty($chatId)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'chat_id is required']);
                break;
            }
            $activeQuiz = RagService::getActiveQuiz($chatId);
            echo json_encode(['success' => !empty($activeQuiz), 'questions' => $activeQuiz ?: []]);
            break;

        // RAG Deterministic Quiz Evaluator
        case ($route === '/api/rag/quiz/evaluate' && $method === 'POST'):
            $user = verifyTokenOrApiKey();
            $chatId = trim((string)($input['chat_id'] ?? $input['session_id'] ?? ''));
            $questions = $input['questions'] ?? [];
            $answers = $input['answers'] ?? $input['student_answers'] ?? $input['response'] ?? '';

            // If questions array is not provided, look up from persistent session store
            if (empty($questions) && !empty($chatId)) {
                $questions = RagService::getActiveQuiz($chatId) ?: [];
            }

            if (empty($questions) || empty($answers)) {
                http_response_code(400);
                echo json_encode([
                    'success' => false,
                    'error' => empty($answers) ? 'answers are required' : 'No active quiz found for this chat session'
                ]);
                break;
            }

            $evalRes = RagService::evaluateQuiz($questions, $answers);
            if (!empty($chatId)) {
                RagService::clearActiveQuiz($chatId);
            }
            echo json_encode($evalRes);
            break;

        
        // Ingest document or document chunks
        case ($route === '/api/rag/ingest' && $method === 'POST'):
            $user = verifyTokenOrApiKey();
            if ($user['role'] !== 'SERVICE' && !in_array($user['role'], ['SUPER_ADMIN', 'TEACHER'])) {
                http_response_code(403);
                echo json_encode(['success' => false, 'error' => 'Forbidden: Teacher, Admin, or Service Key required']);
                break;
            }
            
            // Support direct full-text document ingestion via RagService
            if (!empty($input['content'])) {
                $matId = $input['material_id'] ?? bin2hex(random_bytes(16));
                $title = $input['title'] ?? 'Course Document';
                $courseId = $input['course_id'] ?? null;
                $batchId = $input['batch_id'] ?? null;
                $metadata = $input['metadata'] ?? [];
                
                $ingestRes = RagService::ingestMaterial($matId, $title, $input['content'], $courseId, $batchId, $metadata);
                echo json_encode($ingestRes);
                break;
            }

            // Support direct document file URL or path ingestion (PDF, Markdown, TXT, etc.)
            if (!empty($input['file_url']) || !empty($input['file_path'])) {
                $matId = $input['material_id'] ?? bin2hex(random_bytes(16));
                $title = $input['title'] ?? 'Course Document';
                $target = $input['file_url'] ?? $input['file_path'];
                $courseId = $input['course_id'] ?? null;
                $batchId = $input['batch_id'] ?? null;
                $metadata = $input['metadata'] ?? [];

                $ingestRes = RagService::ingestMaterialDocument($matId, $title, $target, $courseId, $batchId, $metadata);
                echo json_encode($ingestRes);
                break;
            }
            
            // Otherwise support pre-chunked ingestion
            $materialId = $input['material_id'] ?? '';
            $chunks = $input['chunks'] ?? [];
            
            if (empty($materialId) || empty($chunks)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'content OR (material_id and chunks[]) are required']);
                break;
            }
            
            // Update material status to processing
            supabaseUpdate('materials', ['ingestion_status' => 'processing'], ['id' => $materialId]);
            
            $insertedCount = 0;
            $errors = [];
            
            foreach ($chunks as $index => $chunk) {
                $chunkContent = $chunk['content'] ?? '';
                $chunkMetadata = $chunk['metadata'] ?? new stdClass();
                $embedding = $chunk['embedding'] ?? null;
                
                if (empty($chunkContent)) continue;
                
                $chunkData = [
                    'material_id' => $materialId,
                    'chunk_index' => $index,
                    'content' => $chunkContent,
                    'metadata' => json_encode($chunkMetadata)
                ];
                
                // If embedding provided, add it
                if ($embedding && is_array($embedding)) {
                    $chunkData['embedding'] = '[' . implode(',', $embedding) . ']';
                }
                
                $res = supabaseInsert('document_chunks', $chunkData);
                if ($res['success']) {
                    $insertedCount++;
                } else {
                    $errors[] = "Chunk $index: " . ($res['error'] ?? 'unknown error');
                }
            }
            
            // Update material status
            $status = empty($errors) ? 'completed' : (($insertedCount > 0) ? 'completed' : 'failed');
            supabaseUpdate('materials', [
                'ingestion_status' => $status,
                'chunk_count' => $insertedCount
            ], ['id' => $materialId]);
            
            echo json_encode([
                'success' => true,
                'inserted' => $insertedCount,
                'total' => count($chunks),
                'errors' => $errors
            ]);
            break;

        // Semantic search across document chunks (hybrid BM25 + dense vector RRF)
        case ($route === '/api/rag/search' && $method === 'POST'):
            $user = verifyTokenOrApiKey();
            $query = trim($input['query'] ?? $_GET['query'] ?? '');
            
            if (empty($query)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'query parameter is required']);
                break;
            }

            $courseId = $input['course_id'] ?? $_GET['course_id'] ?? null;
            $batchId = $input['batch_id'] ?? $_GET['batch_id'] ?? null;
            $studentId = $input['student_id'] ?? $_GET['student_id'] ?? ($user['role'] === 'STUDENT' ? $user['id'] : null);

            // Strict student authorization & scope enforcement
            if ($user['role'] === 'STUDENT') {
                $studentId = $user['id'];
                $sb = supabaseSelect('student_batches', 'batch_id, batches(course_id)', ['student_id' => $studentId], true);
                if ($sb['success'] && !empty($sb['data'])) {
                    $authBatchId = $sb['data']['batch_id'] ?? null;
                    $authCourseId = $sb['data']['batches']['course_id'] ?? null;
                    if (!empty($courseId) && $courseId !== $authCourseId) {
                        echo json_encode([
                            'success' => true,
                            'backend' => 'hybrid_rrf',
                            'count' => 0,
                            'results' => []
                        ]);
                        break;
                    }
                    $courseId = $authCourseId;
                    $batchId = $authBatchId;
                }
            } elseif (!empty($studentId) && (empty($courseId) || empty($batchId))) {
                $sb = supabaseSelect('student_batches', 'batch_id, batches(course_id)', ['student_id' => $studentId], true);
                if ($sb['success'] && !empty($sb['data'])) {
                    if (empty($batchId)) $batchId = $sb['data']['batch_id'] ?? null;
                    if (empty($courseId)) $courseId = $sb['data']['batches']['course_id'] ?? null;
                }
            }

            $limit = isset($input['limit']) ? (int)$input['limit'] : (isset($input['top_k']) ? (int)$input['top_k'] : 4);
            $threshold = isset($input['threshold']) ? (float)$input['threshold'] : 0.20;
            
            $searchRes = RagService::search($query, $courseId, $batchId, $limit, $threshold);
            echo json_encode($searchRes);
            break;

        // Generate embeddings via Ollama (used by n8n ingestion workflow)
        case ($route === '/api/rag/embed' && $method === 'POST'):
            $user = verifyTokenOrApiKey();
            $texts = $input['texts'] ?? [];
            
            if (empty($texts) || !is_array($texts)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'texts[] array is required']);
                break;
            }
            
            // Prepend search_document: prefix for document embeddings
            $prefixedTexts = array_map(function($t) {
                return 'search_document: ' . $t;
            }, $texts);
            
            $ollamaUrl = 'http://localhost:11434/api/embed';
            $ch = curl_init($ollamaUrl);
            curl_setopt_array($ch, [
                CURLOPT_POST => true,
                CURLOPT_POSTFIELDS => json_encode([
                    'model' => 'nomic-embed-text',
                    'input' => $prefixedTexts
                ]),
                CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
                CURLOPT_RETURNTRANSFER => true,
                CURLOPT_TIMEOUT => 120
            ]);
            $response = curl_exec($ch);
            $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
            $error = curl_error($ch);
            curl_close($ch);
            
            if ($error || $httpCode !== 200) {
                http_response_code(502);
                echo json_encode(['success' => false, 'error' => 'Ollama error: ' . ($error ?: "HTTP $httpCode")]);
                break;
            }
            
            $data = json_decode($response, true);
            echo json_encode([
                'success' => true,
                'embeddings' => $data['embeddings'] ?? []
            ]);
            break;

        // Check RAG ingestion status for a material  
        case (preg_match('/^\/api\/rag\/status\/([a-zA-Z0-9-]+)$/', $route, $matches) && $method === 'GET'):
            $user = verifyTokenOrApiKey();
            $materialId = $matches[1];
            
            $res = supabaseSelect('materials', 'id,title,ingestion_status,chunk_count', ['id' => $materialId], true);
            if (!$res['success'] || empty($res['data'])) {
                http_response_code(404);
                echo json_encode(['success' => false, 'error' => 'Material not found']);
                break;
            }
            
            echo json_encode(['success' => true, 'material' => $res['data']]);
            break;

        // Delete all chunks for a material (re-indexing)
        case (preg_match('/^\/api\/rag\/chunks\/([a-zA-Z0-9-]+)$/', $route, $matches) && $method === 'DELETE'):
            $user = verifyTokenOrApiKey();
            $materialId = $matches[1];
            
            // Delete chunks
            $res = supabaseDelete('document_chunks', ['material_id' => $materialId]);
            
            // Reset material status
            supabaseUpdate('materials', [
                'ingestion_status' => 'pending',
                'chunk_count' => 0
            ], ['id' => $materialId]);
            
            echo json_encode(['success' => true, 'message' => 'Chunks deleted, material ready for re-indexing']);
            break;

        // Save conversation turn
        case ($route === '/api/rag/conversation' && $method === 'POST'):
            $user = verifyTokenOrApiKey();
            $studentId = ($user['role'] === 'STUDENT') ? $user['id'] : ($input['student_id'] ?? '');
            $role = $input['role'] ?? '';
            $content = $input['content'] ?? '';
            
            if (empty($studentId) || empty($role) || empty($content)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'student_id, role, and content are required']);
                break;
            }
            
            $res = supabaseInsert('conversation_history', [
                'student_id' => $studentId,
                'role' => $role,
                'content' => $content
            ]);
            echo json_encode(['success' => $res['success'], 'error' => $res['error']]);
            break;

        // Get conversation history
        case ($route === '/api/rag/conversation' && $method === 'GET'):
            $user = verifyTokenOrApiKey();
            $studentId = ($user['role'] === 'STUDENT') ? $user['id'] : ($_GET['student_id'] ?? '');
            $limit = $_GET['limit'] ?? '10';
            
            if (empty($studentId)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => 'student_id is required']);
                break;
            }
            
            $res = supabaseSelect(
                'conversation_history',
                '*',
                [
                    'student_id' => $studentId,
                    'order' => 'created_at.desc',
                    'limit' => $limit
                ]
            );
            
            // Reverse to get chronological order
            $messages = array_reverse($res['data'] ?: []);
            echo json_encode(['success' => true, 'messages' => $messages]);
            break;

        default:
            http_response_code(404);
            echo json_encode(['success' => false, 'error' => 'API route not found: ' . $route]);
            break;
    }
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode([
        'success' => false,
        'error' => 'Internal server error: ' . $e->getMessage()
    ]);
}
