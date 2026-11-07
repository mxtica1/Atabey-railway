#!/usr/bin/env python3
"""
Script para limpiar datos de prueba de PostgreSQL en Render.
Elimina todas las lecturas (readings) para dejar la BD lista para Vantroi.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

# DATABASE_URL de Render (de los comentarios anteriores)
DATABASE_URL = "postgresql://atabey_db_irdy_user:UFLDPWuLM1F7m8KZL5NNkpR8a3ujwHHZ@dpg-dbl3h44ipgvc73ennl10-a/atabey_db_irdy?sslmode=require"

def cleanup_readings():
    """Elimina todas las lecturas de la BD."""
    try:
        # Conectar a PostgreSQL
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        print("🔗 Conectado a PostgreSQL (Render)")
        print("")
        
        # Contar lecturas actuales
        cursor.execute("SELECT COUNT(*) as count FROM readings;")
        count_before = cursor.fetchone()['count']
        print(f"📊 Lecturas antes de limpieza: {count_before}")
        
        # Contar buffers
        cursor.execute("SELECT COUNT(*) as count FROM ingest_buffers;")
        buffers_before = cursor.fetchone()['count']
        print(f"📦 Buffers antes de limpieza: {buffers_before}")
        print("")
        
        # Eliminar lecturas
        print("🗑️  Eliminando todas las lecturas...")
        cursor.execute("TRUNCATE TABLE readings CASCADE;")
        print("✓ Tabla readings limpiada")
        
        # Eliminar buffers
        cursor.execute("TRUNCATE TABLE ingest_buffers CASCADE;")
        print("✓ Tabla ingest_buffers limpiada")
        
        # Confirmar cambios
        conn.commit()
        print("")
        
        # Verificar
        cursor.execute("SELECT COUNT(*) as count FROM readings;")
        count_after = cursor.fetchone()['count']
        print(f"✓ Lecturas después: {count_after}")
        
        cursor.execute("SELECT COUNT(*) as count FROM ingest_buffers;")
        buffers_after = cursor.fetchone()['count']
        print(f"✓ Buffers después: {buffers_after}")
        print("")
        
        print("✅ BD limpiada exitosamente")
        print("🚀 Lista para datos de Vantroi")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    cleanup_readings()
