import psycopg2
import os

DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    """Lit le fichier schema.sql et crée les tables si elles n'existent pas."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        with open('schema.sql', 'r') as f:
            cursor.execute(f.read())
        conn.commit()
        print("✅ Base de données initialisée avec succès.")
    except Exception as e:
        print(f"❌ Erreur initialisation DB: {e}")
    finally:
        cursor.close()
        conn.close()
