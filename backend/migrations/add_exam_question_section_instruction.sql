-- Migration: add_exam_question_section_instruction.sql
-- Purpose: preserve exam section instructions without embedding them in question_text.

SET @database_name = DATABASE();
SET @column_exists = (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = @database_name
    AND TABLE_NAME = 'exam_questions'
    AND COLUMN_NAME = 'section_instruction'
);

SET @migration_sql = IF(
  @column_exists = 0,
  'ALTER TABLE exam_questions ADD COLUMN section_instruction TEXT NULL AFTER question_text',
  'SELECT ''section_instruction column already exists'' AS message'
);

PREPARE stmt FROM @migration_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
