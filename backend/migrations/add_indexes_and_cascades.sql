-- ============================================================
-- Migration: Add indexes on FK/filter columns + CASCADE deletes
-- Run against awegen_db (and awegen_test_db) via phpMyAdmin or CLI
-- Safe to re-run: every statement uses IF NOT EXISTS or checks
-- ============================================================

-- -----------------------------------------------
-- 1. MODULES table
-- -----------------------------------------------
CREATE INDEX IF NOT EXISTS ix_modules_teacher_id       ON modules(teacher_id);
CREATE INDEX IF NOT EXISTS ix_modules_subject_id       ON modules(subject_id);
CREATE INDEX IF NOT EXISTS ix_modules_processing_status ON modules(processing_status);
CREATE INDEX IF NOT EXISTS ix_modules_is_archived      ON modules(is_archived);
CREATE INDEX IF NOT EXISTS ix_modules_teacher_status   ON modules(teacher_id, processing_status);

-- -----------------------------------------------
-- 2. MODULE_CONTENT — FK index + CASCADE
-- -----------------------------------------------
CREATE INDEX IF NOT EXISTS ix_module_content_module_id ON module_content(module_id);

ALTER TABLE module_content
  DROP FOREIGN KEY IF EXISTS module_content_ibfk_1;
ALTER TABLE module_content
  ADD CONSTRAINT module_content_ibfk_1
  FOREIGN KEY (module_id) REFERENCES modules(module_id) ON DELETE CASCADE;

-- -----------------------------------------------
-- 3. MODULE_SUMMARIES — FK index + CASCADE
-- -----------------------------------------------
CREATE INDEX IF NOT EXISTS ix_module_summaries_module_id ON module_summaries(module_id);

ALTER TABLE module_summaries
  DROP FOREIGN KEY IF EXISTS module_summaries_ibfk_1;
ALTER TABLE module_summaries
  ADD CONSTRAINT module_summaries_ibfk_1
  FOREIGN KEY (module_id) REFERENCES modules(module_id) ON DELETE CASCADE;

-- -----------------------------------------------
-- 4. MODULE_KEYWORDS — FK index + CASCADE
-- -----------------------------------------------
CREATE INDEX IF NOT EXISTS ix_module_keywords_module_id ON module_keywords(module_id);

ALTER TABLE module_keywords
  DROP FOREIGN KEY IF EXISTS module_keywords_ibfk_1;
ALTER TABLE module_keywords
  ADD CONSTRAINT module_keywords_ibfk_1
  FOREIGN KEY (module_id) REFERENCES modules(module_id) ON DELETE CASCADE;

-- -----------------------------------------------
-- 5. MODULE_TOPICS — FK index + CASCADE
-- -----------------------------------------------
CREATE INDEX IF NOT EXISTS ix_module_topics_module_id ON module_topics(module_id);

ALTER TABLE module_topics
  DROP FOREIGN KEY IF EXISTS module_topics_ibfk_1;
ALTER TABLE module_topics
  ADD CONSTRAINT module_topics_ibfk_1
  FOREIGN KEY (module_id) REFERENCES modules(module_id) ON DELETE CASCADE;

-- -----------------------------------------------
-- 6. MODULE_ENTITIES — FK index + CASCADE
-- -----------------------------------------------
CREATE INDEX IF NOT EXISTS ix_module_entities_module_id   ON module_entities(module_id);
CREATE INDEX IF NOT EXISTS ix_module_entities_entity_type ON module_entities(entity_type);

ALTER TABLE module_entities
  DROP FOREIGN KEY IF EXISTS module_entities_ibfk_1;
ALTER TABLE module_entities
  ADD CONSTRAINT module_entities_ibfk_1
  FOREIGN KEY (module_id) REFERENCES modules(module_id) ON DELETE CASCADE;

-- -----------------------------------------------
-- 7. MODULE_IMAGES — FK index + CASCADE
-- -----------------------------------------------
CREATE INDEX IF NOT EXISTS ix_module_images_module_id ON module_images(module_id);

ALTER TABLE module_images
  DROP FOREIGN KEY IF EXISTS module_images_ibfk_1;
ALTER TABLE module_images
  ADD CONSTRAINT module_images_ibfk_1
  FOREIGN KEY (module_id) REFERENCES modules(module_id) ON DELETE CASCADE;

-- -----------------------------------------------
-- 8. MODULE_QUESTIONS — FK indexes + CASCADE (module), SET NULL (image)
-- -----------------------------------------------
CREATE INDEX IF NOT EXISTS ix_module_questions_module_id      ON module_questions(module_id);
CREATE INDEX IF NOT EXISTS ix_module_questions_question_type  ON module_questions(question_type);
CREATE INDEX IF NOT EXISTS ix_module_questions_difficulty     ON module_questions(difficulty_level);
CREATE INDEX IF NOT EXISTS ix_module_questions_image_id       ON module_questions(image_id);

ALTER TABLE module_questions
  DROP FOREIGN KEY IF EXISTS module_questions_ibfk_1;
ALTER TABLE module_questions
  ADD CONSTRAINT module_questions_ibfk_1
  FOREIGN KEY (module_id) REFERENCES modules(module_id) ON DELETE CASCADE;

-- image_id: SET NULL when image is deleted (question text still valid)
ALTER TABLE module_questions
  DROP FOREIGN KEY IF EXISTS module_questions_ibfk_2;
ALTER TABLE module_questions
  ADD CONSTRAINT module_questions_ibfk_2
  FOREIGN KEY (image_id) REFERENCES module_images(image_id) ON DELETE SET NULL;

-- -----------------------------------------------
-- 9. EXAMS — indexes on FKs + filter columns
-- -----------------------------------------------
CREATE INDEX IF NOT EXISTS ix_exams_module_id       ON exams(module_id);
CREATE INDEX IF NOT EXISTS ix_exams_teacher_id      ON exams(teacher_id);
CREATE INDEX IF NOT EXISTS ix_exams_category_id     ON exams(category_id);
CREATE INDEX IF NOT EXISTS ix_exams_department_id   ON exams(department_id);
CREATE INDEX IF NOT EXISTS ix_exams_admin_status    ON exams(admin_status);
CREATE INDEX IF NOT EXISTS ix_exams_is_published    ON exams(is_published);
CREATE INDEX IF NOT EXISTS ix_exams_reviewed_by     ON exams(reviewed_by);
CREATE INDEX IF NOT EXISTS ix_exams_teacher_status  ON exams(teacher_id, admin_status);

-- -----------------------------------------------
-- 10. EXAM_QUESTIONS — FK indexes + CASCADE from exam
-- -----------------------------------------------
CREATE INDEX IF NOT EXISTS ix_exam_questions_exam_id            ON exam_questions(exam_id);
CREATE INDEX IF NOT EXISTS ix_exam_questions_module_question_id ON exam_questions(module_question_id);
CREATE INDEX IF NOT EXISTS ix_exam_questions_question_type      ON exam_questions(question_type);
CREATE INDEX IF NOT EXISTS ix_exam_questions_difficulty         ON exam_questions(difficulty_level);
CREATE INDEX IF NOT EXISTS ix_exam_questions_image_id           ON exam_questions(image_id);

ALTER TABLE exam_questions
  DROP FOREIGN KEY IF EXISTS exam_questions_ibfk_1;
ALTER TABLE exam_questions
  ADD CONSTRAINT exam_questions_ibfk_1
  FOREIGN KEY (exam_id) REFERENCES exams(exam_id) ON DELETE CASCADE;

ALTER TABLE exam_questions
  DROP FOREIGN KEY IF EXISTS exam_questions_ibfk_2;
ALTER TABLE exam_questions
  ADD CONSTRAINT exam_questions_ibfk_2
  FOREIGN KEY (module_question_id) REFERENCES module_questions(question_id) ON DELETE SET NULL;

ALTER TABLE exam_questions
  DROP FOREIGN KEY IF EXISTS exam_questions_ibfk_3;
ALTER TABLE exam_questions
  ADD CONSTRAINT exam_questions_ibfk_3
  FOREIGN KEY (image_id) REFERENCES module_images(image_id) ON DELETE SET NULL;

-- -----------------------------------------------
-- 11. EXAM_SUBMISSIONS — indexes (NO CASCADE — audit data)
-- -----------------------------------------------
CREATE INDEX IF NOT EXISTS ix_exam_submissions_exam_id   ON exam_submissions(exam_id);
CREATE INDEX IF NOT EXISTS ix_exam_submissions_user_id   ON exam_submissions(user_id);
CREATE INDEX IF NOT EXISTS ix_exam_submissions_completed ON exam_submissions(is_completed);

-- -----------------------------------------------
-- 12. EXAM_ANSWERS — FK index + CASCADE from submission
-- -----------------------------------------------
CREATE INDEX IF NOT EXISTS ix_exam_answers_submission_id ON exam_answers(submission_id);
CREATE INDEX IF NOT EXISTS ix_exam_answers_question_id   ON exam_answers(question_id);

ALTER TABLE exam_answers
  DROP FOREIGN KEY IF EXISTS exam_answers_ibfk_1;
ALTER TABLE exam_answers
  ADD CONSTRAINT exam_answers_ibfk_1
  FOREIGN KEY (submission_id) REFERENCES exam_submissions(submission_id) ON DELETE CASCADE;

-- -----------------------------------------------
-- 13. EXAM_MODULES — FK indexes + CASCADE from exam
-- -----------------------------------------------
CREATE INDEX IF NOT EXISTS ix_exam_modules_exam_id   ON exam_modules(exam_id);
CREATE INDEX IF NOT EXISTS ix_exam_modules_module_id ON exam_modules(module_id);

ALTER TABLE exam_modules
  DROP FOREIGN KEY IF EXISTS exam_modules_ibfk_1;
ALTER TABLE exam_modules
  ADD CONSTRAINT exam_modules_ibfk_1
  FOREIGN KEY (exam_id) REFERENCES exams(exam_id) ON DELETE CASCADE;

-- -----------------------------------------------
-- 14. USERS — indexes on FK + filter columns
-- -----------------------------------------------
CREATE INDEX IF NOT EXISTS ix_users_role          ON users(role);
CREATE INDEX IF NOT EXISTS ix_users_role_id       ON users(role_id);
CREATE INDEX IF NOT EXISTS ix_users_department_id ON users(department_id);
CREATE INDEX IF NOT EXISTS ix_users_school_id     ON users(school_id_number);
CREATE INDEX IF NOT EXISTS ix_users_is_active     ON users(is_active);
CREATE INDEX IF NOT EXISTS ix_users_is_approved   ON users(is_approved);

-- -----------------------------------------------
-- 15. REFRESH_TOKENS — FK index + CASCADE from user
-- -----------------------------------------------
CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id ON refresh_tokens(user_id);

ALTER TABLE refresh_tokens
  DROP FOREIGN KEY IF EXISTS refresh_tokens_ibfk_1;
ALTER TABLE refresh_tokens
  ADD CONSTRAINT refresh_tokens_ibfk_1
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;

-- -----------------------------------------------
-- 16. OTP_VERIFICATIONS — FK index + CASCADE from user
-- -----------------------------------------------
CREATE INDEX IF NOT EXISTS ix_otp_verifications_user_id ON otp_verifications(user_id);
CREATE INDEX IF NOT EXISTS ix_otp_verifications_email   ON otp_verifications(email);

ALTER TABLE otp_verifications
  DROP FOREIGN KEY IF EXISTS otp_verifications_ibfk_1;
ALTER TABLE otp_verifications
  ADD CONSTRAINT otp_verifications_ibfk_1
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;

-- -----------------------------------------------
-- 17. NOTIFICATIONS — CASCADE from user
-- -----------------------------------------------
ALTER TABLE notifications
  DROP FOREIGN KEY IF EXISTS notifications_ibfk_1;
ALTER TABLE notifications
  ADD CONSTRAINT notifications_ibfk_1
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;

-- -----------------------------------------------
-- 18. TEACHER_APPROVALS — indexes (NO CASCADE — audit)
-- -----------------------------------------------
CREATE INDEX IF NOT EXISTS ix_teacher_approvals_user_id     ON teacher_approvals(user_id);
CREATE INDEX IF NOT EXISTS ix_teacher_approvals_approved_by ON teacher_approvals(approved_by);
CREATE INDEX IF NOT EXISTS ix_teacher_approvals_status      ON teacher_approvals(status);

-- -----------------------------------------------
-- 19. DEPARTMENTS + SUBJECTS — FK indexes
-- -----------------------------------------------
CREATE INDEX IF NOT EXISTS ix_departments_school_id    ON departments(school_id_number);
CREATE INDEX IF NOT EXISTS ix_subjects_department_id   ON subjects(department_id);

-- ============================================================
-- Done. All indexes and CASCADE rules applied.
-- ============================================================
