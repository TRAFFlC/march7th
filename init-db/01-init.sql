-- Initialize database with proper character set
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- Ensure database exists
CREATE DATABASE IF NOT EXISTS `march7th_chat`
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE `march7th_chat`;

-- Grant privileges to application user
-- Note: Password should match MYSQL_PASSWORD in .env
GRANT ALL PRIVILEGES ON `march7th_chat`.* TO 'march7th'@'%';
FLUSH PRIVILEGES;
