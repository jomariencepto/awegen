-- ============================================================
-- Migration: fix_exam_module_questions.sql
-- Run this against your MySQL/MariaDB database ONCE,
-- then restart the Flask backend.
-- ============================================================

-- 1. Add correct_answer column to module_questions
--    (nullable so existing rows are unaffected)
ALTER TABLE module_questions
    ADD COLUMN IF NOT EXISTS correct_answer TEXT NULL
    COMMENT 'Stored answer generated during module NLP processing';

-- 2. Create exam_modules association table
--    (many-to-many between exams and modules)
CREATE TABLE IF NOT EXISTS exam_modules (
    id         INT          AUTO_INCREMENT PRIMARY KEY,
    exam_id    INT          NOT NULL,
    module_id  INT          NOT NULL,
    created_at DATETIME     DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_em_exam   FOREIGN KEY (exam_id)   REFERENCES exams(exam_id)     ON DELETE CASCADE,
    CONSTRAINT fk_em_module FOREIGN KEY (module_id) REFERENCES modules(module_id) ON DELETE CASCADE,
    UNIQUE KEY uq_exam_module (exam_id, module_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
