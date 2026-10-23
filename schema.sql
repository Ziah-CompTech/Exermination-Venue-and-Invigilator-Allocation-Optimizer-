-- Create databases and application user for the exam optimiser.
-- Run once as MySQL root:
--     mysql -u root -p < schema.sql

CREATE DATABASE IF NOT EXISTS exam_optimizer
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE DATABASE IF NOT EXISTS exam_optimizer_test
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'exam_user'@'localhost'
  IDENTIFIED BY 'exam_pass';

GRANT ALL PRIVILEGES ON exam_optimizer.* TO 'exam_user'@'localhost';
GRANT ALL PRIVILEGES ON exam_optimizer_test.* TO 'exam_user'@'localhost';

FLUSH PRIVILEGES;