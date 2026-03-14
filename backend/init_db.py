import mysql.connector
from mysql.connector import errorcode
from config import settings

# 从配置中提取数据库连接信息
db_config = {
    'user': 'root',
    'password': 'password',
    'host': 'localhost',
    'port': '3306'
}

database_name = 'news_platform'

try:
    # 连接到MySQL服务器
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    # 创建数据库
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    print(f"Database '{database_name}' created successfully!")
    
    # 关闭连接
    cursor.close()
    conn.close()
    
except mysql.connector.Error as err:
    if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
        print("Error: Access denied. Please check your username and password.")
    elif err.errno == errorcode.ER_BAD_DB_ERROR:
        print("Error: Database does not exist.")
    else:
        print(f"Error: {err}")
