"""
Ciclo de vida de una incapacidad dentro del proceso.

Los cuatro estados de la sección 5.4 (Transcrita, Cobrada, Rechazada, Pagada)
son los de la relación con la entidad; los demás cubren las etapas internas.
"""

RECIBIDA = "Recibida"
INCOMPLETA = "Documentación incompleta"
VERIFICADA = "Verificada"
TRANSCRITA = "Transcrita"
COBRADA = "Cobrada"
RECHAZADA = "Rechazada"
PAGADA = "Pagada"
EN_CARTERA = "En cartera"
EN_JURIDICO = "En jurídico"
DADA_DE_BAJA = "Dada de baja"
ARCHIVADA = "Archivada"

TODOS = [RECIBIDA, INCOMPLETA, VERIFICADA, TRANSCRITA, COBRADA, RECHAZADA,
         PAGADA, EN_CARTERA, EN_JURIDICO, DADA_DE_BAJA, ARCHIVADA]

# Transiciones permitidas: estado actual -> estados a los que puede pasar
TRANSICIONES = {
    RECIBIDA: {INCOMPLETA, VERIFICADA},
    INCOMPLETA: {VERIFICADA},
    VERIFICADA: {TRANSCRITA},
    TRANSCRITA: {COBRADA, RECHAZADA},
    RECHAZADA: {TRANSCRITA, EN_JURIDICO},          # nueva transcripción o cobro jurídico (5.4.2)
    COBRADA: {PAGADA, EN_CARTERA, EN_JURIDICO},    # EN_JURIDICO: incumplimiento del tiempo de pago
    EN_CARTERA: {PAGADA, EN_JURIDICO},
    EN_JURIDICO: {PAGADA, DADA_DE_BAJA},           # "se recupera o se da de baja"
    PAGADA: {ARCHIVADA},
    DADA_DE_BAJA: set(),
    ARCHIVADA: set(),
}

# Estados desde los cuales ya hay que reportar novedad de nómina (5.2)
ESTADOS_CON_NOVEDAD_NOMINA = {TRANSCRITA, COBRADA, RECHAZADA, PAGADA,
                              EN_CARTERA, EN_JURIDICO, DADA_DE_BAJA, ARCHIVADA}

# Estados en los que todavía hay dinero por cobrar a la entidad
ESTADOS_POR_COBRAR = {TRANSCRITA, COBRADA, EN_CARTERA, EN_JURIDICO}


def puede_pasar(actual: str, nuevo: str) -> bool:
    return nuevo in TRANSICIONES.get(actual, set())
