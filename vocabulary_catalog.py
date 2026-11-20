"""Catálogo de palabras y frases de LSM para grabar ejemplos y armar oraciones.

Igual que ``alphabets.py``: las entradas son **etiquetas para grabar**, no
contienen gestos ni pesos. Una seña solo se reconoce después de grabar al
menos 30 ejemplos variados y reentrenar el modelo.

Hay dos maneras de que Seña produzca una frase completa:

1. **Frase grabada como una sola seña** (``kind='frase'``). Sirve para frases
   cortas que caben en la ventana de 30 fotogramas (≈3 s a 10 fps), por ejemplo
   «¿Cómo estás?».
2. **Frase compuesta** a partir de palabras confirmadas en orden
   (``PHRASE_RULES``). LSM tiene su propio orden (la pregunta suele ir al final:
   TÚ NOMBRE QUÉ), así que el compositor de la conversación convierte esa
   secuencia en español escrito: «¿Cómo te llamas?».

Las reglas usan el **texto** de las etiquetas, sin distinguir mayúsculas ni
acentos. Si en tu equipo una seña se registra con otro nombre, agrega la
variante a la regla.
"""
from sign_languages import language_info, labels_for, register_label

# ── Palabras y frases por categoría ─────────────────────────────────────────
# Cada categoría: id estable, título visible y entradas (texto de salida).
CATEGORIES = [
    {'id': 'saludos', 'title': 'Saludos y cortesía', 'kind': 'palabra', 'entries': [
        'Hola', 'Adiós', 'Buenos días', 'Buenas tardes', 'Buenas noches', 'Gracias', 'De nada',
        'Por favor', 'Perdón', 'Con permiso', 'Mucho gusto', 'Bienvenido', 'Hasta luego', 'Hasta mañana']},
    {'id': 'personas', 'title': 'Personas y pronombres', 'kind': 'palabra', 'entries': [
        'Yo', 'Tú', 'Él', 'Ella', 'Nosotros', 'Ustedes', 'Ellos', 'Nombre', 'Persona', 'Amigo',
        'Sordo', 'Oyente', 'Intérprete', 'Maestro', 'Alumno', 'Doctor']},
    {'id': 'familia', 'title': 'Familia', 'kind': 'palabra', 'entries': [
        'Familia', 'Mamá', 'Papá', 'Hermano', 'Hermana', 'Hijo', 'Hija', 'Abuelo', 'Abuela',
        'Esposo', 'Esposa', 'Bebé']},
    {'id': 'preguntas', 'title': 'Preguntas', 'kind': 'palabra', 'entries': [
        'Qué', 'Quién', 'Cómo', 'Dónde', 'Cuándo', 'Por qué', 'Cuánto', 'Cuál']},
    {'id': 'verbos', 'title': 'Acciones (verbos)', 'kind': 'palabra', 'entries': [
        'Querer', 'Necesitar', 'Tener', 'Ir', 'Venir', 'Comer', 'Beber', 'Dormir', 'Trabajar',
        'Estudiar', 'Aprender', 'Entender', 'Saber', 'Conocer', 'Ayudar', 'Hablar', 'Ver',
        'Esperar', 'Llamar', 'Vivir', 'Gustar', 'Poder', 'Hacer', 'Jugar', 'Pagar', 'Comprar']},
    {'id': 'estados', 'title': 'Sentimientos y estados', 'kind': 'palabra', 'entries': [
        'Bien', 'Mal', 'Feliz', 'Triste', 'Enojado', 'Cansado', 'Enfermo', 'Preocupado',
        'Nervioso', 'Tranquilo', 'Hambre', 'Sed', 'Dolor', 'Miedo']},
    {'id': 'tiempo', 'title': 'Tiempo', 'kind': 'palabra', 'entries': [
        'Hoy', 'Mañana', 'Ayer', 'Ahora', 'Después', 'Antes', 'Siempre', 'Nunca', 'Día', 'Noche',
        'Semana', 'Mes', 'Año', 'Hora', 'Edad']},
    {'id': 'lugares', 'title': 'Lugares', 'kind': 'palabra', 'entries': [
        'Casa', 'Escuela', 'Trabajo', 'Hospital', 'Baño', 'Tienda', 'Restaurante', 'Parque',
        'Banco', 'Farmacia', 'Mercado']},
    {'id': 'cosas', 'title': 'Cosas y necesidades', 'kind': 'palabra', 'entries': [
        'Agua', 'Comida', 'Dinero', 'Teléfono', 'Medicina', 'Ropa', 'Libro', 'Computadora',
        'Coche', 'Camión']},
    {'id': 'respuestas', 'title': 'Respuestas y conectores', 'kind': 'palabra', 'entries': [
        'Sí', 'No', 'Tal vez', 'No sé', 'Más', 'Menos', 'Mucho', 'Poco', 'Otra vez', 'También',
        'Pero', 'Con', 'Sin', 'Igual', 'Diferente', 'Listo']},
    {'id': 'numeros', 'title': 'Números', 'kind': 'palabra', 'entries': [
        'Uno', 'Dos', 'Tres', 'Cuatro', 'Cinco', 'Seis', 'Siete', 'Ocho', 'Nueve', 'Diez']},
    {'id': 'emergencias', 'title': 'Emergencias', 'kind': 'palabra', 'entries': [
        'Ayuda', 'Emergencia', 'Policía', 'Ambulancia', 'Incendio', 'Peligro', 'Accidente']},
    {'id': 'frases', 'title': 'Frases completas', 'kind': 'frase', 'entries': [
        '¿Cómo estás?', 'Estoy bien', '¿Cómo te llamas?', 'Me llamo', '¿Cuántos años tienes?',
        '¿Dónde está el baño?', 'No entiendo', '¿Puedes repetir?', 'Más despacio, por favor',
        'Soy sordo', 'Necesito ayuda', 'Necesito un intérprete', 'Llama a una ambulancia',
        'Me duele', 'Tengo hambre', 'Tengo sed', '¿Qué hora es?', '¿Cuánto cuesta?',
        'Nos vemos mañana', 'Que tengas buen día', '¿Me ayudas?', 'Lo siento',
        'Escríbelo, por favor', 'Feliz cumpleaños', 'Buen provecho', 'Te quiero', 'Te amo']},
]

# ── Perfil «LSM · Frases»: oraciones completas grabadas como una sola toma ───
# Cada toma dura ≈6 s, suficiente para una oración básica. Incluye respuestas
# cortas (Sí, No, Gracias) porque en una conversación se alternan con las frases.
PHRASE_CATEGORIES = [
    {'id': 'saludos', 'title': 'Saludos', 'kind': 'frase', 'entries': [
        'Hola, ¿cómo estás?', 'Hola', 'Buenos días', 'Buenas tardes', 'Buenas noches',
        'Mucho gusto', 'Bienvenido']},
    {'id': 'presentacion', 'title': 'Presentarse', 'kind': 'frase', 'entries': [
        '¿Cómo te llamas?', 'Me llamo', '¿Cuántos años tienes?', '¿Dónde vives?', 'Soy sordo',
        'Soy oyente', 'Estoy aprendiendo lengua de señas']},
    {'id': 'respuestas', 'title': 'Responder', 'kind': 'frase', 'entries': [
        'Estoy bien', 'Estoy mal', 'Más o menos', '¿Y tú?', 'Sí', 'No', 'No sé', 'Gracias',
        'De nada', 'Por favor']},
    {'id': 'comprension', 'title': 'Entender la conversación', 'kind': 'frase', 'entries': [
        'No entiendo', '¿Puedes repetir?', 'Más despacio, por favor', 'Escríbelo, por favor',
        '¿Qué significa?']},
    {'id': 'necesidades', 'title': 'Necesidades', 'kind': 'frase', 'entries': [
        'Necesito ayuda', '¿Dónde está el baño?', 'Tengo hambre', 'Tengo sed', 'Me duele',
        'Llama a una ambulancia', '¿Qué hora es?', '¿Cuánto cuesta?']},
    {'id': 'despedidas', 'title': 'Despedidas', 'kind': 'frase', 'entries': [
        'Adiós', 'Hasta luego', 'Nos vemos mañana', 'Que tengas buen día', 'Cuídate']},
]

# ── Frases compuestas: secuencia de señas (orden LSM) → español escrito ──────
# Se prueba primero la secuencia más larga. Pon variantes de orden habituales.
PHRASE_RULES = [
    {'signs': ['Tú', 'Nombre', 'Qué'], 'text': '¿Cómo te llamas?'},
    {'signs': ['Nombre', 'Tú', 'Qué'], 'text': '¿Cómo te llamas?'},
    {'signs': ['Tú', 'Nombre', 'Cómo'], 'text': '¿Cómo te llamas?'},
    {'signs': ['Nombre', 'Tú', 'Cuál'], 'text': '¿Cómo te llamas?'},
    {'signs': ['Yo', 'Nombre'], 'text': 'me llamo'},
    {'signs': ['Nombre', 'Yo'], 'text': 'me llamo'},
    {'signs': ['Tú', 'Cómo'], 'text': '¿Cómo estás?'},
    {'signs': ['Cómo', 'Tú'], 'text': '¿Cómo estás?'},
    {'signs': ['Tú', 'Bien'], 'text': '¿Estás bien?'},
    {'signs': ['Tú', 'Edad', 'Cuánto'], 'text': '¿Cuántos años tienes?'},
    {'signs': ['Edad', 'Tú', 'Cuánto'], 'text': '¿Cuántos años tienes?'},
    {'signs': ['Tú', 'Edad', 'Qué'], 'text': '¿Cuántos años tienes?'},
    {'signs': ['Baño', 'Dónde'], 'text': '¿Dónde está el baño?'},
    {'signs': ['Dónde', 'Baño'], 'text': '¿Dónde está el baño?'},
    {'signs': ['Yo', 'Entender', 'No'], 'text': 'no entiendo'},
    {'signs': ['Yo', 'No', 'Entender'], 'text': 'no entiendo'},
    {'signs': ['Entender', 'No'], 'text': 'no entiendo'},
    {'signs': ['No', 'Entender'], 'text': 'no entiendo'},
    {'signs': ['Otra vez', 'Por favor'], 'text': '¿Puedes repetir, por favor?'},
    {'signs': ['Yo', 'Necesitar', 'Ayuda'], 'text': 'necesito ayuda'},
    {'signs': ['Ayuda', 'Necesitar'], 'text': 'necesito ayuda'},
    {'signs': ['Yo', 'Necesitar', 'Intérprete'], 'text': 'necesito un intérprete'},
    {'signs': ['Llamar', 'Ambulancia'], 'text': 'llama a una ambulancia'},
    {'signs': ['Ambulancia', 'Llamar'], 'text': 'llama a una ambulancia'},
    {'signs': ['Yo', 'Dolor'], 'text': 'me duele'},
    {'signs': ['Hora', 'Qué'], 'text': '¿Qué hora es?'},
    {'signs': ['Qué', 'Hora'], 'text': '¿Qué hora es?'},
    {'signs': ['Dinero', 'Cuánto'], 'text': '¿Cuánto cuesta?'},
    {'signs': ['Cuánto', 'Dinero'], 'text': '¿Cuánto cuesta?'},
    {'signs': ['Ver', 'Mañana'], 'text': 'nos vemos mañana'},
    {'signs': ['Mañana', 'Ver'], 'text': 'nos vemos mañana'},
    {'signs': ['Tú', 'Ayudar', 'Yo'], 'text': '¿Me ayudas?'},
    {'signs': ['Ayudar', 'Yo', 'Tú'], 'text': '¿Me ayudas?'},
    {'signs': ['Tú', 'Vivir', 'Dónde'], 'text': '¿Dónde vives?'},
    {'signs': ['Tú', 'Trabajar', 'Dónde'], 'text': '¿Dónde trabajas?'},
    {'signs': ['Gracias', 'Mucho'], 'text': 'muchas gracias'},
    {'signs': ['Quién', 'Tú'], 'text': '¿Quién eres?'},
    {'signs': ['Tú', 'Quién'], 'text': '¿Quién eres?'},
]

# ── Conjugación en presente para pronombre + verbo (orden LSM: YO QUERER) ────
PRONOUNS = {'Yo': 'yo', 'Tú': 'tu', 'Él': 'el', 'Ella': 'el', 'Nosotros': 'nosotros',
            'Ustedes': 'ellos', 'Ellos': 'ellos'}
# yo, tú, él/ella, nosotros, ellos/ustedes
CONJUGATIONS = {
    'Querer': ['quiero', 'quieres', 'quiere', 'queremos', 'quieren'],
    'Necesitar': ['necesito', 'necesitas', 'necesita', 'necesitamos', 'necesitan'],
    'Tener': ['tengo', 'tienes', 'tiene', 'tenemos', 'tienen'],
    'Ir': ['voy', 'vas', 'va', 'vamos', 'van'],
    'Venir': ['vengo', 'vienes', 'viene', 'venimos', 'vienen'],
    'Comer': ['como', 'comes', 'come', 'comemos', 'comen'],
    'Beber': ['bebo', 'bebes', 'bebe', 'bebemos', 'beben'],
    'Dormir': ['duermo', 'duermes', 'duerme', 'dormimos', 'duermen'],
    'Trabajar': ['trabajo', 'trabajas', 'trabaja', 'trabajamos', 'trabajan'],
    'Estudiar': ['estudio', 'estudias', 'estudia', 'estudiamos', 'estudian'],
    'Aprender': ['aprendo', 'aprendes', 'aprende', 'aprendemos', 'aprenden'],
    'Entender': ['entiendo', 'entiendes', 'entiende', 'entendemos', 'entienden'],
    'Saber': ['sé', 'sabes', 'sabe', 'sabemos', 'saben'],
    'Conocer': ['conozco', 'conoces', 'conoce', 'conocemos', 'conocen'],
    'Ayudar': ['ayudo', 'ayudas', 'ayuda', 'ayudamos', 'ayudan'],
    'Hablar': ['hablo', 'hablas', 'habla', 'hablamos', 'hablan'],
    'Ver': ['veo', 'ves', 've', 'vemos', 'ven'],
    'Esperar': ['espero', 'esperas', 'espera', 'esperamos', 'esperan'],
    'Llamar': ['llamo', 'llamas', 'llama', 'llamamos', 'llaman'],
    'Vivir': ['vivo', 'vives', 'vive', 'vivimos', 'viven'],
    'Gustar': ['me gusta', 'te gusta', 'le gusta', 'nos gusta', 'les gusta'],
    'Poder': ['puedo', 'puedes', 'puede', 'podemos', 'pueden'],
    'Hacer': ['hago', 'haces', 'hace', 'hacemos', 'hacen'],
    'Jugar': ['juego', 'juegas', 'juega', 'jugamos', 'juegan'],
    'Pagar': ['pago', 'pagas', 'paga', 'pagamos', 'pagan'],
    'Comprar': ['compro', 'compras', 'compra', 'compramos', 'compran'],
}
PERSON_INDEX = {'yo': 0, 'tu': 1, 'el': 2, 'nosotros': 3, 'ellos': 4}
# Pronombre + estado/profesión/sensación: el verbo se omite en LSM y se agrega en español.
COPULAS = {
    'estar': {'forms': ['estoy', 'estás', 'está', 'estamos', 'están'],
              'words': ['Bien', 'Mal', 'Feliz', 'Triste', 'Enojado', 'Cansado', 'Enfermo',
                        'Preocupado', 'Nervioso', 'Tranquilo', 'Listo']},
    'ser': {'forms': ['soy', 'eres', 'es', 'somos', 'son'],
            'words': ['Sordo', 'Oyente', 'Intérprete', 'Maestro', 'Alumno', 'Doctor', 'Amigo', 'Persona']},
    'tener': {'forms': ['tengo', 'tienes', 'tiene', 'tenemos', 'tienen'],
              'words': ['Hambre', 'Sed', 'Miedo', 'Dolor']},
}
# Sustantivos con artículo para armar «voy a la escuela», «trabajo en el hospital».
ARTICLES = {
    'Casa': 'casa', 'Escuela': 'la escuela', 'Trabajo': 'el trabajo', 'Hospital': 'el hospital',
    'Baño': 'el baño', 'Tienda': 'la tienda', 'Restaurante': 'el restaurante', 'Parque': 'el parque',
    'Banco': 'el banco', 'Farmacia': 'la farmacia', 'Mercado': 'el mercado', 'Comida': 'la comida',
    'Agua': 'el agua', 'Dinero': 'el dinero', 'Teléfono': 'el teléfono', 'Medicina': 'la medicina',
    'Ropa': 'la ropa', 'Libro': 'el libro', 'Computadora': 'la computadora', 'Coche': 'el coche',
    'Camión': 'el camión', 'Familia': 'la familia',
}
PLACES = ['Casa', 'Escuela', 'Trabajo', 'Hospital', 'Baño', 'Tienda', 'Restaurante', 'Parque',
          'Banco', 'Farmacia', 'Mercado']
# Preposición que pide cada verbo antes de un lugar.
VERB_PREPOSITIONS = {'Ir': 'a', 'Venir': 'de', 'Llamar': 'a', 'Trabajar': 'en', 'Estudiar': 'en',
                     'Vivir': 'en', 'Esperar': 'en', 'Comer': 'en', 'Dormir': 'en', 'Jugar': 'en',
                     'Comprar': 'en', 'Pagar': 'en'}
# Verbos cuyo complemento lleva artículo: «me gusta la comida».
ARTICLE_VERBS = ['Gustar']
QUESTION_WORDS = ['Qué', 'Quién', 'Cómo', 'Dónde', 'Cuándo', 'Por qué', 'Cuánto', 'Cuál']
# Saludos que llevan coma cuando les sigue más texto: «Hola, me llamo Ana.»
GREETINGS = ['Hola', 'Buenos días', 'Buenas tardes', 'Buenas noches', 'Gracias', 'Perdón', 'Adiós']


def catalog_for(language):
    source = PHRASE_CATEGORIES if language_info(language).get('kind') == 'frases' else CATEGORIES
    return [{**category, 'entries': list(category['entries'])} for category in source]


def phrasebook(language):
    """Datos que usa el compositor de conversación del navegador."""
    language_info(language)
    return {'rules': PHRASE_RULES, 'pronouns': PRONOUNS, 'conjugations': CONJUGATIONS,
            'person_index': PERSON_INDEX, 'question_words': QUESTION_WORDS, 'greetings': GREETINGS,
            'copulas': COPULAS, 'articles': ARTICLES, 'places': PLACES,
            'verb_prepositions': VERB_PREPOSITIONS, 'article_verbs': ARTICLE_VERBS}


def _key(text):
    return ' '.join(str(text).split()).casefold()


def catalog_status(language, rows, model):
    """Igual que el abecedario: muestra qué entradas ya existen, sus ejemplos y si están entrenadas."""
    trained = {label['id'] for label in (model or {}).get('labels', [])}
    by_text = {}
    for row in rows:
        for value in (row.get('text'), row.get('meaning')):
            if value:
                by_text.setdefault(_key(value), row)
    result = []
    for category in catalog_for(language):
        entries = []
        for text in category['entries']:
            row = by_text.get(_key(text))
            entries.append({'text': text, 'label_id': row['id'] if row else None,
                            'samples': row['samples'] if row else 0,
                            'trained': bool(row and row['id'] in trained)})
        result.append({'id': category['id'], 'title': category['title'], 'kind': category['kind'],
                       'entries': entries})
    return result


def add_category(language, category_id):
    """Registra en el vocabulario todas las entradas de una categoría (sin crear ejemplos)."""
    category = next((c for c in catalog_for(language) if c['id'] == category_id), None)
    if category is None:
        raise ValueError('Categoría de vocabulario desconocida.')
    before = {row['id'] for row in labels_for(language)}
    labels = [register_label(language, text) for text in category['entries']]
    return {'language': language, 'category': category_id,
            'added': sum(label['id'] not in before for label in labels), 'total': len(labels)}
