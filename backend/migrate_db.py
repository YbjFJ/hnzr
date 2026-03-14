from sqlalchemy import create_engine, text
from config import settings
from database import engine
from models import Base

# 连接到数据库
print("连接到数据库...")

# 删除所有表
print("开始删除旧表...")
Base.metadata.drop_all(bind=engine)
print("旧表删除完成!")

# 重新创建表
print("开始创建新表...")
Base.metadata.create_all(bind=engine)
print("新表创建完成!")

print("数据库迁移成功!")
