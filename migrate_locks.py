import asyncio
from app.database import db
from os import getenv
from dotenv import load_dotenv

load_dotenv()

async def migrate():
    print("Connecting to database...")
    await db.connect()
    
    print("Checking for 'locked_by' column in 'applications' table...")
    try:
        # Проверяем, есть ли колонка
        await db.execute("SELECT locked_by FROM applications LIMIT 1")
        print("Column 'locked_by' already exists.")
    except Exception:
        print("Column 'locked_by' not found. Adding columns...")
        try:
            await db.execute("ALTER TABLE applications ADD COLUMN locked_by INTEGER REFERENCES users(id) ON DELETE SET NULL")
            await db.execute("ALTER TABLE applications ADD COLUMN locked_at TIMESTAMP")
            print("Columns 'locked_by' and 'locked_at' added successfully.")
        except Exception as e:
            print(f"Error adding columns: {e}")

    await db.close()

if __name__ == "__main__":
    asyncio.run(migrate())
