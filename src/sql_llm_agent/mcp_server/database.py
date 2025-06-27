import pyodbc
import os
import structlog
from typing import List, Dict, Any, Tuple
from dotenv import load_dotenv
from .models import SQLQueryResult

# Configurar logging para stderr (MCP requirement)
logger = structlog.get_logger()

class DatabaseManager:
    def __init__(self):
        """Inicializa la conexión a la base de datos para MCP"""
        load_dotenv()
        self.connection_string = self._build_connection_string()
        
    def _build_connection_string(self) -> str:
        """Construye la cadena de conexión ODBC"""
        driver = os.getenv('DB_DRIVER')
        server = os.getenv('DB_SERVER') 
        database = os.getenv('DB_DATABASE')
        user = os.getenv('DB_USERNAME')
        pwd = os.getenv('DB_PASSWORD')
        
        return (
            f"DRIVER={{{driver}}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"UID={user};PWD={pwd};"
            "Encrypt=no;"
        )
    
    def test_connection(self) -> bool:
        """Prueba si podemos conectarnos a la BD"""
        try:
            conn = pyodbc.connect(self.connection_string)
            conn.close()
            return True
        except Exception as e:
            logger.error("Error de conexión", error=str(e))
            return False
    
    def _validate_query(self, query: str) -> Tuple[bool, str]:
        """Valida que la consulta sea segura (solo SELECT)"""
        query_clean = query.strip().upper()
        
        # Solo permitir SELECT
        if not query_clean.startswith('SELECT'):
            return False, "Solo se permiten consultas SELECT"
        
        # Palabras prohibidas
        forbidden_words = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']
        for word in forbidden_words:
            if word in query_clean:
                return False, f"Palabra prohibida detectada: {word}"
        
        return True, "Consulta válida"
    
    def execute_query(self, query: str, limit: int = 100) -> SQLQueryResult:
        """Ejecuta una consulta SQL de forma segura para MCP"""
        # Validar consulta
        is_valid, validation_message = self._validate_query(query)
        if not is_valid:
            # logger.warning("Consulta rechazada", query=query, reason=validation_message)
            return SQLQueryResult(
                success=False,
                error=validation_message
            )
        
        # Añadir TOP para SQL Server (no LIMIT)
        query_upper = query.strip().upper()
        if "TOP" not in query_upper and "LIMIT" not in query_upper:
            # Para SQL Server, insertar TOP después de SELECT
            if query_upper.startswith('SELECT'):
                query = query.replace('SELECT', f'SELECT TOP {limit}', 1)
        
        try:
            # Conectar y ejecutar
            conn = pyodbc.connect(self.connection_string)
            cursor = conn.cursor()
            
            # logger.info("Ejecutando consulta", query=query)
            cursor.execute(query)
            
            # Obtener resultados
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
            
            # Convertir a lista de diccionarios
            data = []
            for row in rows:
                data.append(dict(zip(columns, row)))
            
            conn.close()
            
            # logger.info("Consulta ejecutada exitosamente", rows_count=len(data))
            return SQLQueryResult(
                success=True,
                data=data,
                rows_affected=len(data)
            )
            
        except Exception as e:
            # logger.error("Error ejecutando consulta", query=query, error=str(e))
            return SQLQueryResult(
                success=False,
                error=f"Error de base de datos: {str(e)}"
            )
    
    def get_schema(self) -> SQLQueryResult:
        """Obtiene el esquema de la base de datos"""
        schema_query = """
        SELECT 
            TABLE_NAME,
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE,
            COLUMN_DEFAULT
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_CATALOG = DB_NAME()
        ORDER BY TABLE_NAME, ORDINAL_POSITION
        """
        return self.execute_query(schema_query)