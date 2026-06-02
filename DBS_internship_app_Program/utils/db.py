import mysql.connector
from mysql.connector import pooling
from dotenv import load_dotenv
import os

load_dotenv()

# Centralized database credentials
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Pooja@1998")
DB_NAME = os.getenv("DB_NAME", "student_internship_db")

# Initialize connection pool
try:
    db_pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_name="mypool",
        pool_size=5,
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=True
    )
    print("Database connection pool initialized successfully.")
except mysql.connector.Error as err:
    print(f"Error initializing connection pool: {err}")
    db_pool = None

def get_connection():
    """Gets a connection from the pool, or creates a standalone one if pool failed."""
    if db_pool:
        return db_pool.get_connection()
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=True
    )

def execute_query(query, params=None, fetch="all"):
    """Executes a standard SELECT or read-only query and returns results."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(query, params or ())
        if fetch == "all":
            result = cursor.fetchall()
        elif fetch == "one":
            result = cursor.fetchone()
        else:
            result = None
        return result
    finally:
        cursor.close()
        conn.close()

def execute_dml(query, params=None):
    """Executes a DML query (INSERT, UPDATE, DELETE) and returns lastrowid or rowcount."""
    conn = get_connection()
    cursor = conn.cursor()
    # Ensure auto_commit is handled or commit explicitly
    try:
        cursor.execute(query, params or ())
        # Explicit commit for safety
        conn.commit()
        last_id = cursor.lastrowid
        row_count = cursor.rowcount
        return {"lastrowid": last_id, "rowcount": row_count}
    except mysql.connector.Error as err:
        # Rollback in case of error
        try:
            conn.rollback()
        except:
            pass
        raise err
    finally:
        cursor.close()
        conn.close()

def call_procedure(proc_name, params=None):
    """Calls a stored procedure (e.g. apply_for_role, accept_offer, reject_offer)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.callproc(proc_name, params or [])
        conn.commit()
    except mysql.connector.Error as err:
        try:
            conn.rollback()
        except:
            pass
        raise err
    finally:
        cursor.close()
        conn.close()
