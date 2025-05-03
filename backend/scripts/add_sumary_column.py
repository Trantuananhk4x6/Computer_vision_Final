# Lưu file này dưới dạng scripts/add_summary_column.py
import os
import sys
import sqlite3

# Thiết lập đường dẫn
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BACKEND_DIR)

from config import Config
from app import create_app

def add_summary_column():
    print("Starting database migration: Adding 'summary' column to tracking_sessions...")
    
    # Tạo Flask app để lấy đường dẫn database từ config
    app = create_app()
    
    # Extract database path from SQLAlchemy URI
    db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        return False
    
    print(f"Found database at: {db_path}")
    
    try:
        # Kết nối với database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Kiểm tra xem cột đã tồn tại chưa
        cursor.execute("PRAGMA table_info(tracking_sessions)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'summary' in column_names:
            print("Column 'summary' already exists in tracking_sessions table.")
        else:
            # Thêm cột summary nếu chưa tồn tại
            cursor.execute("ALTER TABLE tracking_sessions ADD COLUMN summary JSON")
            conn.commit()
            print("Column 'summary' successfully added to tracking_sessions table.")
        
        conn.close()
        return True
    
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        return False

if __name__ == "__main__":
    success = add_summary_column()
    if success:
        print("Migration completed successfully.")
    else:
        print("Migration failed.")