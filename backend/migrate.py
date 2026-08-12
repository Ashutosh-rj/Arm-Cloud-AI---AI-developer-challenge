import asyncio
import os
import asyncpg
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def run_migrations():
    print("Starting InferaV22 database migrations...")
    database_url = os.getenv("DATABASE_URL", "postgresql://inferav22:inferav22@localhost:5432/inferav22")
    
    try:
        conn = await asyncpg.connect(database_url)
    except Exception as e:
        print(f"Failed to connect to DB for migrations: {e}")
        return

    try:
        # Run init.sql
        init_sql_path = os.path.join(os.path.dirname(__file__), "migrations", "init.sql")
        with open(init_sql_path, "r") as f:
            sql = f.read()
            
        print("Executing init.sql...")
        await conn.execute(sql)
        
        # Seed default admin user
        admin_email = "admin@inferav22.local"
        admin_password = "admin" # The user should change this
        
        exists = await conn.fetchval("SELECT id FROM users WHERE email = $1", admin_email)
        if not exists:
            print(f"Seeding default admin user: {admin_email}")
            hashed = pwd_context.hash(admin_password)
            await conn.execute(
                "INSERT INTO users (email, hashed_password, role) VALUES ($1, $2, 'admin')",
                admin_email, hashed
            )
        else:
            print("Admin user already exists.")
            
        print("Migrations completed successfully.")
        
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(run_migrations())
