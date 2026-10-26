<?php
// EduConnect LMS - Document Text Extractor
// Extracts clean text from uploaded course materials (PDF, Markdown, TXT, DOCX)

class DocumentExtractor {
    /**
     * Supported file extensions
     */
    public static array $supportedExtensions = ['txt', 'md', 'pdf', 'docx', 'html', 'json', 'csv'];

    /**
     * Extract text from a local file path
     */
    public static function extractFromFile(string $filePath): string {
        if (!file_exists($filePath) || !is_readable($filePath)) {
            error_log("[DocumentExtractor] File not found or not readable: $filePath");
            return '';
        }

        // File size guard (max 25MB to prevent memory exhaustion)
        $size = @filesize($filePath);
        if ($size === 0) {
            return '';
        }
        if ($size > 25 * 1024 * 1024) {
            error_log("[DocumentExtractor] File exceeds 25MB limit: $filePath");
            return '';
        }

        $ext = strtolower(pathinfo($filePath, PATHINFO_EXTENSION));

        // Plain text formats
        if (in_array($ext, ['txt', 'md', 'html', 'json', 'csv', ''])) {
            $content = @file_get_contents($filePath);
            return $content !== false ? trim($content) : '';
        }

        // PDF Extraction
        if ($ext === 'pdf') {
            return self::extractPdf($filePath);
        }

        // Word DOCX Extraction (via native ZipArchive)
        if ($ext === 'docx') {
            return self::extractDocx($filePath);
        }

        // Fallback: try raw read
        $raw = @file_get_contents($filePath);
        return $raw !== false ? trim($raw) : '';
    }

    /**
     * Native DOCX text extraction from word/document.xml
     */
    private static function extractDocx(string $filePath): string {
        if (!class_exists('ZipArchive')) return '';
        $zip = new ZipArchive();
        if ($zip->open($filePath) === true) {
            $xml = $zip->getFromName('word/document.xml');
            $zip->close();
            if ($xml !== false) {
                $text = strip_tags(str_replace(['</w:p>', '</w:tr>'], ["\n", "\n"], $xml));
                return trim(preg_replace('/\n{3,}/', "\n\n", $text));
            }
        }
        return '';
    }

    /**
     * Extract text from a remote URL (e.g. Supabase Storage public or signed URL)
     */
    public static function extractFromUrl(string $url): string {
        if (empty($url)) return '';

        // If local file path passed by mistake
        if (file_exists($url)) {
            return self::extractFromFile($url);
        }

        $tmpDir = sys_get_temp_dir();
        $ext = strtolower(pathinfo(parse_url($url, PHP_URL_PATH), PATHINFO_EXTENSION)) ?: 'txt';
        $tmpFile = $tmpDir . DIRECTORY_SEPARATOR . 'lms_extract_' . bin2hex(random_bytes(8)) . '.' . $ext;

        $ch = curl_init($url);
        $fp = fopen($tmpFile, 'wb');
        curl_setopt_array($ch, [
            CURLOPT_FILE => $fp,
            CURLOPT_HEADER => 0,
            CURLOPT_FOLLOWLOCATION => true,
            CURLOPT_TIMEOUT => 60,
            CURLOPT_SSL_VERIFYPEER => false
        ]);
        curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        fclose($fp);

        if ($httpCode >= 200 && $httpCode < 300 && file_exists($tmpFile) && filesize($tmpFile) > 0) {
            $text = self::extractFromFile($tmpFile);
            @unlink($tmpFile);
            return $text;
        }

        if (file_exists($tmpFile)) {
            @unlink($tmpFile);
        }

        error_log("[DocumentExtractor] Failed to download document from URL: $url (HTTP $httpCode)");
        return '';
    }

    /**
     * High-speed PDF text extraction using PyMuPDF (fitz) or fallback
     */
    private static function extractPdf(string $pdfPath): string {
        $realPath = realpath($pdfPath);
        if (!$realPath) return '';

        // 1. Primary method: PyMuPDF via Python
        $pyCmd = 'python -c "import fitz, sys; doc = fitz.open(sys.argv[1]); print(\"\\n\".join(p.get_text() for p in doc))" ' . escapeshellarg($realPath);
        $output = @shell_exec($pyCmd);
        if ($output !== null && strlen(trim($output)) > 10) {
            return trim($output);
        }

        // 2. Secondary fallback: Stream parser for uncompressed PDF text
        $content = @file_get_contents($realPath);
        if ($content !== false) {
            $text = '';
            if (preg_match_all('/\((.*?)\)\s*Tj/s', $content, $matches)) {
                $text = implode(' ', $matches[1]);
            }
            if (strlen(trim($text)) > 20) {
                return trim($text);
            }
        }

        return '';
    }
}
