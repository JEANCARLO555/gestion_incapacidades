import sys
import json
import smtplib
import os
import re
from dotenv import load_dotenv
from email.mime.text import MIMEText
from openai import OpenAI

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

# Credenciales y servidor SMTP
SMTP_SERVER = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
REMITENTE_SISTEMA = os.getenv("SMTP_USER") or os.getenv("SMTP_FROM")
PASSWORD_RAW = os.getenv("SMTP_PASSWORD", "")
PASSWORD_SISTEMA = PASSWORD_RAW.replace(" ", "").strip()

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"
)

def enviar_correo_smtp(destinatario: str, asunto: str, cuerpo: str):
    if not REMITENTE_SISTEMA or not PASSWORD_SISTEMA:
        return False, "Error: No hay credenciales SMTP en el archivo .env"

    msg = MIMEText(cuerpo, 'plain', 'utf-8')
    msg['Subject'] = asunto
    msg['From'] = REMITENTE_SISTEMA
    msg['To'] = destinatario

    try:
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(REMITENTE_SISTEMA, PASSWORD_SISTEMA)
                server.sendmail(REMITENTE_SISTEMA, destinatario, msg.as_string())
        else:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(REMITENTE_SISTEMA, PASSWORD_SISTEMA)
                server.sendmail(REMITENTE_SISTEMA, destinatario, msg.as_string())
                
        return True, f"Correo enviado exitosamente a {destinatario}"
    except Exception as e:
        return False, f"Error al enviar correo: {e}"

def procesar_orden(instruccion: str, contexto_datos: str = ""):
    inst_lower = instruccion.lower()

    # --- ACCESO RÁPIDO VÍA REGEX (SUB-SEGUNDO) PARA CUALQUIER USUARIO ---
    match_dias = re.search(r"(\d+)\s*días", inst_lower) or re.search(r"(\d+)\s*dias", inst_lower)
    es_registro = any(w in inst_lower for w in ["reporto", "reportó", "genero", "generó", "incapacidad", "radica", "ingreso", "ingresó"])
    
    if es_registro and match_dias:
        dias = int(match_dias.group(1))
        # Extraer cualquier nombre introducido en la instrucción
        palabras_ignorar = {"reporto", "reportó", "genero", "generó", "incapacidad", "por", "dias", "días", "de", "en", "para", "dolor", "cabeza", "fiebre", "salud", "total", "sura", "eps"}
        palabras = [p.capitalize() for p in instruccion.split() if p.lower() not in palabras_ignorar and not p.isdigit()]
        nombre = " ".join(palabras[:2]) if palabras else "Usuario Desconocido"
        
        return {
            "accion": "registrar_incapacidad",
            "colaborador": nombre,
            "dias": dias,
            "tipo": "Enfermedad general",
            "entidad": "SURA EPS"
        }

    # --- MODO IA COMPLETO PARA ANÁLISIS Y CORREOS ---
    necesita_analisis = any(w in inst_lower for w in ["analiza", "analisis", "análisis", "informe", "reporte", "por que", "por qué", "revisa", "quien", "quién"])
    contexto_prompt = f"\nDATOS ACTUALES EN BD:\n{contexto_datos[:600]}\n" if necesita_analisis else ""

    system_prompt = (
        "Responde EXCLUSIVAMENTE en JSON plano sin bloques markdown.\n"
        f"{contexto_prompt}"
        "Estructuras válidas:\n"
        '1. {"accion": "registrar_incapacidad", "colaborador": "Nombre Cualquiera", "dias": N, "tipo": "Enfermedad general", "entidad": "EPS"}\n'
        '2. {"accion": "crear_colaboradores", "cantidad": N}\n'
        '3. {"accion": "eliminar_colaborador", "target": "Nombre"}\n'
        '4. {"accion": "correo", "destinatario": "email", "asunto": "...", "mensaje": "..."}\n'
        '5. {"accion": "analisis", "titulo": "...", "conclusion": "...", "puntos_clave": ["..."], "recomendacion": "..."}\n'
        '6. {"accion": "consulta", "respuesta": "..."}'
    )

    try:
        response = client.chat.completions.create(
            model="qwen2.5:1.5b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": instruccion}
            ],
            temperature=0.1,
            max_tokens=200,
            response_format={"type": "json_object"}
        )

        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        return {"accion": "error", "mensaje": f"Error procesando la orden: {e}"}