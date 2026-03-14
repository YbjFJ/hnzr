-- 为「官方解读」功能添加字段：解读文章归属的新闻 ID
-- 若使用 SQLite/MySQL，执行以下语句（按数据库类型二选一）。

-- SQLite:
ALTER TABLE articles ADD COLUMN news_id INTEGER REFERENCES articles(id);

-- MySQL:
-- ALTER TABLE articles ADD COLUMN news_id INT NULL, ADD INDEX idx_articles_news_id (news_id), ADD FOREIGN KEY (news_id) REFERENCES articles(id);
