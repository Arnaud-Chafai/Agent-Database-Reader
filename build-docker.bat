@echo off
echo 🐳 Construyendo imagen Docker del SQL LLM Agent...

docker build -t sql-llm-agent:latest .

if %ERRORLEVEL% EQU 0 (
    echo ✅ Imagen construida exitosamente
    echo 🚀 Para ejecutar: docker-compose up -d
) else (
    echo ❌ Error construyendo la imagen
)

pause