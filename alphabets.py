"""Catálogos escritos para recolectar dactilología, independientes por lengua.
Las entradas son etiquetas para grabar: no contienen gestos ni pesos entrenados.
"""
from sign_languages import language_info, labels_for, register_label, LANGUAGES

CATALOGS = {
    'lsm': {'title': 'Abecedario español', 'symbols': list('ABCDEFGHIJKLMNÑOPQRSTUVWXYZ'),
            'extras': list('ÁÉÍÓÚÜ'), 'note': '27 letras, incluida Ñ. Las tildes son variantes escritas opcionales; registra su representación según la convención que uses en LSM.',
            'source': 'https://nuevaescuelamexicana.sep.gob.mx/contenido/recurso/40967/'},
}


# Obtiene los símbolos y notas del abecedario correspondiente al perfil validado.
def alphabet_for(language):
    language_info(language)
    return {**CATALOGS[language], 'symbols': list(CATALOGS[language]['symbols']), 'extras': list(CATALOGS[language]['extras'])}


# Busca si un símbolo ya tiene una etiqueta equivalente para evitar duplicarlo.
def find_symbol_label(labels, symbol):
    # lower conserva ß distinto de SS y mantiene los diacríticos.
    return next((row for row in labels if row['text'].lower() == symbol.lower()), None)


# Combina símbolos, ejemplos y vocabulario aprendido para mostrar el progreso del abecedario.
def alphabet_status(language, rows, model):
    catalog = alphabet_for(language)
    trained = {label['id'] for label in (model or {}).get('labels', [])}
    # Construye las filas de símbolos con su etiqueta, cantidad de ejemplos y estado entrenado.
    def entries(symbols):
        result = []
        for symbol in symbols:
            row = find_symbol_label(rows, symbol)
            result.append({'symbol': symbol, 'label_id': row['id'] if row else None,
                           'samples': row['samples'] if row else 0, 'trained': bool(row and row['id'] in trained)})
        return result
    return {**catalog, 'symbols': entries(catalog['symbols']), 'extras': entries(catalog['extras'])}


# Registra los símbolos de un perfil sin inventar ejemplos ni modificar sus modelos.
def add_alphabet(language, extras=False):
    if not isinstance(extras, bool):
        raise ValueError('La opción de variantes debe ser verdadera o falsa.')
    catalog = alphabet_for(language)
    symbols = catalog['extras'] if extras else catalog['symbols']
    before = {row['id'] for row in labels_for(language)}
    labels = [register_label(language, symbol) for symbol in symbols]
    return {'language': language, 'added': sum(label['id'] not in before for label in labels), 'total': len(labels)}


# Registra los símbolos del perfil español sin crear ejemplos de entrenamiento.
def add_all_alphabets():
    return [add_alphabet(language['id']) for language in LANGUAGES]
