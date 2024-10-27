import pymssql
import json
import time
import os
from dotenv import load_dotenv

load_dotenv()

SERVER = os.getenv('DB_SERVER')
DATABASE = os.getenv('DB_NAME')
USERNAME = os.getenv('DB_USERNAME')
PASSWORD = os.getenv('DB_PASSWORD')

def get_db_connection(retries=5, delay=5):
    for attempt in range(retries):
        try:
            conn = pymssql.connect(server=SERVER, user=USERNAME, password=PASSWORD, database=DATABASE)
            print("Connection successful")
            return conn
        except pymssql.OperationalError as e:
            print(f"OperationalError: {e}. Retrying in {delay} seconds...")
            time.sleep(delay)
        except Exception as e:
            print("Unexpected error:", e)
            raise
    raise Exception("Failed to connect to the database after several attempts.")

def create_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='file_cache' AND xtype='U')
    CREATE TABLE file_cache (
        file_hash VARCHAR(32) PRIMARY KEY,
        file_name NVARCHAR(255),
        result NVARCHAR(MAX),
        created_at DATETIME DEFAULT GETDATE()
    )
    ''')
    conn.commit()
    conn.close()

def get_cached_result(file_hash):
    conn = get_db_connection()
    cursor = conn.cursor(as_dict=True)
    cursor.execute("SELECT file_name, result FROM file_cache WHERE file_hash = %s", (file_hash,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {
            'file_name': result['file_name'],
            'result': json.loads(result['result'])
        }
    return None

def cache_result(file_hash, file_name, data):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "MERGE INTO file_cache AS target "
        "USING (VALUES (%s, %s, %s, GETDATE())) AS source (file_hash, file_name, result, created_at) "
        "ON target.file_hash = source.file_hash "
        "WHEN MATCHED THEN "
        "    UPDATE SET file_name = source.file_name, result = source.result, created_at = source.created_at "
        "WHEN NOT MATCHED THEN "
        "    INSERT (file_hash, file_name, result, created_at) VALUES (source.file_hash, source.file_name, source.result, source.created_at);",
        (file_hash, file_name, json.dumps(data))
    )
    conn.commit()
    conn.close()

def initialize_database():
    create_table()