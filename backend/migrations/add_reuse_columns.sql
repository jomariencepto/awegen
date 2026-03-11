-- Migration: Add exam re-use tracking columns
-- Run this once against your awegen_db database in phpMyAdmin or MySQL CLI

ALTER TABLE `exams`
  ADD COLUMN `reused_from_exam_id` INT(11) NULL DEFAULT NULL COMMENT 'ID of the original approved exam this was re-used from',
  ADD COLUMN `reused_at` DATETIME NULL DEFAULT NULL COMMENT 'When this exam was created as a re-use';
