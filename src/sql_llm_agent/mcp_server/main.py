#!/usr/bin/env python3
"""
Servidor MCP para consultas SQL usando stdio transport
"""

import asyncio
import sys
import structlog
from mcp.server.fastmcp import FastMCP
from .database import DatabaseManager
from .models import SQLQueryRequest

# CORREGIR LOGGING: Configurar structlog para que vaya a stderr, NO stdout
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Configurar logging básico para stderr
import logging
logging.basicConfig(
    level=logging.ERROR,  # Solo errores críticos
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr  # IMPORTANTE: usar stderr, no stdout
)

# Inicializar componentes
db_manager = DatabaseManager()
app = FastMCP("SQL LLM Agent")

@app.tool()
def ejecutar_consulta_sql(query: str, limit: int = 100) -> str:
    """
    Ejecuta una consulta SQL SELECT de forma segura.
    Incluye contexto de negocio relevante basado en el glosario.
    
    Args:
        query: La consulta SQL a ejecutar (solo SELECT permitido)
        limit: Límite máximo de filas a retornar (default: 100)
    
    Returns:
        Resultados de la consulta con contexto de negocio adicional
    """
    try:
        # Ejecutar la consulta
        result = db_manager.execute_query(query, limit)
        
        # Obtener contexto del glosario
        contexto_negocio = _obtener_contexto_glosario(query)
        
        # Combinar resultado con contexto
        respuesta = result.to_text()
        
        if contexto_negocio:
            respuesta += f"\n\n💡 **Contexto de Negocio:**\n{contexto_negocio}"
        
        return respuesta
        
    except Exception as e:
        return f"❌ Error inesperado: {str(e)}"

@app.tool()
def obtener_esquema_bd() -> str:
    """
    Obtiene el esquema completo de la base de datos.
    """
    try:
        result = db_manager.get_schema()
        if result.success:
            schema_text = "📊 **Esquema de Base de Datos**\n\n"
            
            if result.data:
                current_table = None
                for row in result.data:
                    table_name = row['TABLE_NAME']
                    if table_name != current_table:
                        current_table = table_name
                        schema_text += f"\n🗂️ **Tabla: {table_name}**\n"
                    
                    nullable = "NULL" if row['IS_NULLABLE'] == 'YES' else "NOT NULL"
                    default = f" DEFAULT {row['COLUMN_DEFAULT']}" if row['COLUMN_DEFAULT'] else ""
                    
                    schema_text += f"  - {row['COLUMN_NAME']} ({row['DATA_TYPE']}) {nullable}{default}\n"
            
            return schema_text
        else:
            return f"❌ Error obteniendo esquema: {result.error}"
    except Exception as e:
        return f"❌ Error inesperado: {str(e)}"

@app.tool()
def probar_conexion() -> str:
    """
    Prueba la conexión a la base de datos.
    """
    try:
        if db_manager.test_connection():
            return "✅ Conexión a base de datos exitosa"
        else:
            return "❌ No se pudo conectar a la base de datos"
    except Exception as e:
        return f"❌ Error probando conexión: {str(e)}"

@app.tool()
def obtener_info_tabla(nombre_tabla: str) -> str:
    """
    Obtiene información detallada sobre una tabla específica.
    """
    try:
        info_query = f"""
        SELECT 
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE,
            COLUMN_DEFAULT,
            CHARACTER_MAXIMUM_LENGTH
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = '{nombre_tabla}' AND TABLE_CATALOG = DB_NAME()
        ORDER BY ORDINAL_POSITION
        """
        
        result = db_manager.execute_query(info_query)
        
        if not result.success:
            return f"❌ Error: {result.error}"
        
        if not result.data:
            return f"❌ Tabla '{nombre_tabla}' no encontrada"
        
        count_query = f"SELECT COUNT(*) as total_filas FROM {nombre_tabla}"
        count_result = db_manager.execute_query(count_query)
        
        total_filas = 0
        if count_result.success and count_result.data:
            total_filas = count_result.data[0]['total_filas']
        
        info_text = f"🗂️ **Tabla: {nombre_tabla}**\n"
        info_text += f"📊 **Total de filas:** {total_filas}\n\n"
        info_text += "📋 **Columnas:**\n"
        
        for col in result.data:
            col_name = col['COLUMN_NAME']
            data_type = col['DATA_TYPE']
            nullable = "NULL" if col['IS_NULLABLE'] == 'YES' else "NOT NULL"
            max_length = f"({col['CHARACTER_MAXIMUM_LENGTH']})" if col['CHARACTER_MAXIMUM_LENGTH'] else ""
            default = f" DEFAULT {col['COLUMN_DEFAULT']}" if col['COLUMN_DEFAULT'] else ""
            
            info_text += f"  - **{col_name}**: {data_type}{max_length} {nullable}{default}\n"
        
        return info_text
        
    except Exception as e:
        return f"❌ Error inesperado: {str(e)}"


def _obtener_contexto_glosario(query: str) -> str:
    """
    Obtiene contexto relevante del glosario basado en la consulta SQL.
    """
    try:
        import json
        import os
        
        # Cargar glosario
        glosario_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'context', 'glosario.json')
        
        if not os.path.exists(glosario_path):
            return ""
            
        with open(glosario_path, 'r', encoding='utf-8') as f:
            glosario = json.load(f)
        
        query_lower = query.lower()
        contextos = []
        
        # 🔍 BUSCAR EN SINÓNIMOS PRIMERO
        sinonimos = glosario.get("sinonimos", {})
        
        # Detectar qué conceptos están en la consulta
        conceptos_detectados = []
        
        for concepto, palabras_clave in sinonimos.items():
            # Buscar tanto el concepto como sus sinónimos
            todas_palabras = [concepto] + palabras_clave
            
            for palabra in todas_palabras:
                if palabra.lower() in query_lower:
                    conceptos_detectados.append(concepto)
                    break  # Ya encontró este concepto
        
        # 📝 GENERAR CONTEXTO BASADO EN LO DETECTADO
        conceptos_negocio = glosario.get("conceptos_negocio", {})
        
        for concepto in conceptos_detectados:
            if concepto == "ventas":
                facturacion = conceptos_negocio.get("facturacion", {})
                desc = facturacion.get("descripcion", "Sistema de ventas")
                contextos.append(f"📊 **Ventas**: {desc}")
                
            elif concepto == "canciones":
                catalogo = conceptos_negocio.get("catalogo_musical", {})
                desc = catalogo.get("descripcion", "Biblioteca de música organizada jerárquicamente")
                contextos.append(f"🎵 **Música**: {desc}")
                
            elif concepto == "artistas":
                catalogo = conceptos_negocio.get("catalogo_musical", {})
                jerarquia = catalogo.get("jerarquia", "Artist > Album > Track")
                contextos.append(f"🎤 **Artistas**: {jerarquia}")
                
            elif concepto == "clientes":
                ventas_cliente = conceptos_negocio.get("ventas_por_cliente", {})
                desc = ventas_cliente.get("descripcion", "Análisis de comportamiento de compra")
                contextos.append(f"👥 **Clientes**: {desc}")
                
            elif concepto == "empleados":
                empleados = conceptos_negocio.get("empleados", {})
                desc = empleados.get("descripcion", "Personal de la tienda musical")
                jerarquia = empleados.get("jerarquia", "Manager -> Employee")
                contextos.append(f"💼 **Empleados**: {desc} - {jerarquia}")
        
        # 🧮 DETECTAR FUNCIONES SQL Y AÑADIR CONTEXTO DE CÁLCULOS
        calculos_comunes = glosario.get("calculos_comunes", {})
        
        if 'sum(' in query_lower and 'total' in query_lower:
            if "ingresos_totales" in calculos_comunes:
                contextos.append(f"💰 **Métrica**: {calculos_comunes['ingresos_totales']}")
                
        if 'count(' in query_lower:
            contextos.append("📈 **Conteo**: Análisis de frecuencia/volumen de datos.")
            
        if 'avg(' in query_lower:
            if "precio_promedio_track" in calculos_comunes:
                contextos.append(f"📊 **Promedio**: {calculos_comunes['precio_promedio_track']}")
        
        return "\n".join(contextos) if contextos else ""
        
    except Exception:
        return ""
def main():
    """Punto de entrada principal del servidor MCP"""
    try:
        # Verificar conexión al iniciar (solo a stderr)
        if not db_manager.test_connection():
            print("❌ Error: No se puede conectar a la base de datos", file=sys.stderr)
            sys.exit(1)
        
        print("🚀 Servidor MCP SQL Agent iniciado", file=sys.stderr)
        print("📡 Transporte: stdio", file=sys.stderr)
        print("🔒 Modo seguro: Solo SELECT", file=sys.stderr)
        
        # Ejecutar servidor MCP con transporte stdio
        app.run(transport="stdio")
        
    except KeyboardInterrupt:
        print("🛑 Servidor detenido", file=sys.stderr)
    except Exception as e:
        print(f"💥 Error crítico: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()