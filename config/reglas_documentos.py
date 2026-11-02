"""
Documentos que se deben recibir según el tipo de incapacidad (5.1.2)
y plazos de la verificación documental.
"""

TIPO_ENFERMEDAD_GENERAL = "Enfermedad general"
TIPO_ACCIDENTE_TRANSITO = "Accidente de tránsito"
TIPO_ACCIDENTE_LABORAL = "Accidente laboral"
TIPO_LICENCIA_MATERNIDAD = "Licencia de maternidad"
TIPO_LICENCIA_PATERNIDAD = "Licencia de paternidad"

TIPOS_INCAPACIDAD = [
    TIPO_ENFERMEDAD_GENERAL,
    TIPO_ACCIDENTE_TRANSITO,
    TIPO_ACCIDENTE_LABORAL,
    TIPO_LICENCIA_MATERNIDAD,
    TIPO_LICENCIA_PATERNIDAD,
]

# La epicrisis solo es obligatoria en enfermedad general si supera estos días (sección 3)
DIAS_EPICRISIS_ENFERMEDAD_GENERAL = 2

# Plazos
DIAS_HABILES_PARA_COMPLETAR_DOCUMENTACION = 3   # 5.1.2
DIAS_MAXIMOS_ENVIO_COLABORADOR = 2              # paso 3 del desarrollo

DOC_CERTIFICADO = "Certificado de incapacidad (original)"
DOC_EPICRISIS = "Epicrisis o documento que soporte la incapacidad"
DOC_EPICRISIS_SEMANAS = "Epicrisis o documento con semanas de gestación al momento del parto"
DOC_FURIPS = "FURIPS"
DOC_NACIDO_VIVO = "Certificado de nacido vivo"
DOC_REGISTRO_CIVIL = "Registro civil"
DOC_IDENTIDAD = "Fotocopia del documento de identidad"
DOC_IDENTIDAD_MADRE = "Fotocopia del documento de identidad de la madre"

# Documentos clínicos: el paso 16 indica que NO reposan en el archivo (se destruyen)
DOCUMENTOS_CLINICOS = {DOC_EPICRISIS, DOC_EPICRISIS_SEMANAS}


def documentos_requeridos(tipo: str, dias: int) -> list[str]:
    """Devuelve los documentos que se deben recibir según el tipo (5.1.2)."""
    if tipo == TIPO_ENFERMEDAD_GENERAL:
        docs = [DOC_CERTIFICADO]
        if dias > DIAS_EPICRISIS_ENFERMEDAD_GENERAL:
            docs.append(DOC_EPICRISIS)
        return docs
    if tipo == TIPO_ACCIDENTE_TRANSITO:
        return [DOC_CERTIFICADO, DOC_EPICRISIS, DOC_FURIPS]
    if tipo == TIPO_ACCIDENTE_LABORAL:
        return [DOC_CERTIFICADO, DOC_EPICRISIS]
    if tipo == TIPO_LICENCIA_MATERNIDAD:
        return [DOC_CERTIFICADO, DOC_EPICRISIS_SEMANAS, DOC_NACIDO_VIVO,
                DOC_REGISTRO_CIVIL, DOC_IDENTIDAD]
    if tipo == TIPO_LICENCIA_PATERNIDAD:
        return [DOC_EPICRISIS_SEMANAS, DOC_NACIDO_VIVO, DOC_REGISTRO_CIVIL,
                DOC_IDENTIDAD_MADRE]
    raise ValueError(f"Tipo de incapacidad desconocido: {tipo}")


# Documentos que se pueden subir al archivo digital (además de los requeridos)
OTROS_DOCUMENTOS = ["Soporte de liquidación", "Otro"]
