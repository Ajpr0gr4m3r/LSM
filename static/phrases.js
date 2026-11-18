'use strict';
// Convierte una secuencia de señas confirmadas (orden LSM) en una oración en español.
// No es una traducción completa de LSM: aplica reglas de frases conocidas,
// conjugación de pronombre + verbo, preguntas al inicio y une el deletreo.
// Las reglas vienen del servidor (vocabulary_catalog.py → profile.phrasebook).

class SenaPhrasebook {
  constructor(book = {}) {
    this.book = book || {};
    this.rules = (this.book.rules || [])
      .map((rule) => ({ keys: rule.signs.map((s) => SenaPhrasebook.key(s)), text: rule.text }))
      .sort((a, b) => b.keys.length - a.keys.length);
    const keyed = (object = {}) =>
      Object.fromEntries(Object.entries(object).map(([k, v]) => [SenaPhrasebook.key(k), v]));
    this.pronouns = keyed(this.book.pronouns);
    this.conjugations = keyed(this.book.conjugations);
    this.personIndex = this.book.person_index || {};
    this.questions = new Set((this.book.question_words || []).map((w) => SenaPhrasebook.key(w)));
    this.greetings = new Set((this.book.greetings || []).map((w) => SenaPhrasebook.key(w)));
    this.copulas = {};
    for (const copula of Object.values(this.book.copulas || {}))
      for (const word of copula.words) this.copulas[SenaPhrasebook.key(word)] = copula.forms;
    this.articles = keyed(this.book.articles);
    this.places = new Set((this.book.places || []).map((w) => SenaPhrasebook.key(w)));
    this.prepositions = keyed(this.book.verb_prepositions);
    this.articleVerbs = new Set((this.book.article_verbs || []).map((w) => SenaPhrasebook.key(w)));
  }

  // «a» + «el hospital» → «al hospital»; «de» + «el baño» → «del baño».
  static withPreposition(preposition, noun) {
    if (preposition === 'a' && noun.startsWith('el ')) return 'al ' + noun.slice(3);
    if (preposition === 'de' && noun.startsWith('el ')) return 'del ' + noun.slice(3);
    return `${preposition} ${noun}`;
  }

  // Sin mayúsculas, signos ni acentos (la ñ se conserva).
  static key(text) {
    return String(text ?? '')
      .toLocaleLowerCase('es-MX')
      .replaceAll('ñ', '\u0000')
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replaceAll('\u0000', 'ñ')
      .replace(/[¿?¡!.,;:]/g, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  static isLetter(text) {
    return /^[a-zñáéíóúü]$/i.test(String(text ?? '').trim());
  }

  // Une letras consecutivas en una palabra; «Espacio» separa palabras deletreadas.
  joinSpelling(signs) {
    const tokens = [];
    let letters = '';
    const flush = () => {
      if (letters) tokens.push({ text: letters[0].toLocaleUpperCase('es-MX') + letters.slice(1).toLocaleLowerCase('es-MX'), spelled: true });
      letters = '';
    };
    for (const sign of signs) {
      const text = String(sign?.text ?? sign ?? '').trim();
      if (!text) continue;
      if (SenaPhrasebook.key(text) === 'espacio' || sign?.id === 'espacio') { flush(); continue; }
      if (SenaPhrasebook.isLetter(text)) { letters += text; continue; }
      flush();
      tokens.push({ text });
    }
    flush();
    return tokens;
  }

  compose(signs) {
    const tokens = this.joinSpelling(signs);
    const keys = tokens.map((t) => (t.spelled ? null : SenaPhrasebook.key(t.text)));
    const parts = [];
    let question = false;
    let pendingQuestion = null;
    let verb = null; // último verbo, para su complemento de lugar u objeto
    for (let i = 0; i < tokens.length;) {
      // 1. Frases conocidas (la secuencia más larga primero).
      const rule = this.rules.find((r) => r.keys.every((k, j) => keys[i + j] === k));
      if (rule) {
        parts.push({ text: rule.text, phrase: true });
        i += rule.keys.length;
        verb = null;
        continue;
      }
      const token = tokens[i];
      const key = keys[i];
      const person = this.pronouns[key];
      if (person) {
        const index = this.personIndex[person];
        // Él, ella, ellos y ustedes se conservan; yo, tú y nosotros van implícitos en el verbo.
        const subject = index === 2 || index === 4 ? token.text.toLocaleLowerCase('es-MX') + ' ' : '';
        const conjugated = this.conjugations[keys[i + 1]];
        const copula = this.copulas[keys[i + 1]];
        if (conjugated || copula) {
          const negated = keys[i + 2] === 'no';
          let complement = tokens[i + 1].text.toLocaleLowerCase('es-MX');
          // LSM no marca género; con «ella» se usa la forma femenina (cansada, doctora).
          if (copula && key === 'ella' && /o$/.test(complement)) complement = complement.slice(0, -1) + 'a';
          if (copula && key === 'ella' && /or$/.test(complement)) complement += 'a';
          const form = conjugated ? conjugated[index] : `${copula[index]} ${complement}`;
          parts.push({ text: subject + (negated ? 'no ' : '') + form });
          verb = conjugated ? keys[i + 1] : null;
          i += negated ? 3 : 2;
          continue;
        }
      }
      // 2. Verbo seguido de «no» (orden LSM) → «no» antes del verbo.
      if (this.conjugations[key]) {
        const negated = keys[i + 1] === 'no';
        parts.push({ text: (negated ? 'no ' : '') + token.text.toLocaleLowerCase('es-MX') });
        verb = key;
        i += negated ? 2 : 1;
        continue;
      }
      // 3. Palabra interrogativa: en LSM suele ir al final; en español va al inicio.
      if (this.questions.has(key)) {
        question = true;
        pendingQuestion = token.text;
        i += 1;
        continue;
      }
      // 4. Complemento del verbo: «voy a la escuela», «me gusta la comida».
      const noun = this.articles[key];
      if (noun && verb) {
        const preposition = this.places.has(key) ? this.prepositions[verb] : null;
        if (preposition) parts.push({ text: SenaPhrasebook.withPreposition(preposition, noun) });
        else parts.push({ text: this.articleVerbs.has(verb) ? noun : token.text });
        verb = null;
        i += 1;
        continue;
      }
      parts.push(token);
      i += 1;
    }
    if (pendingQuestion) parts.unshift({ text: pendingQuestion, questionWord: true });
    return this.punctuate(parts, question);
  }

  punctuate(parts, question) {
    if (!parts.length) return '';
    const words = parts.map((part, index) => {
      let text = part.text;
      if (!part.spelled && !/^LSM$/.test(text)) {
        // Minúsculas dentro de la oración, salvo nombres deletreados y frases con «¿».
        const at = /^[¿¡]/.test(text) ? 1 : 0;
        if (index > 0 || !at) text = text.slice(0, at) + text.charAt(at).toLocaleLowerCase('es-MX') + text.slice(at + 1);
      }
      const nextExists = index < parts.length - 1;
      if (nextExists && this.greetings.has(SenaPhrasebook.key(part.text)) && !/[,.?!]$/.test(text)) text += ',';
      return text;
    });
    let sentence = words.join(' ').replace(/\s+/g, ' ').trim();
    // Si una frase interior ya trae «¿…?», no envolver toda la oración otra vez.
    const innerQuestion = /[¿?]/.test(sentence);
    if (question && !innerQuestion) sentence = `¿${sentence}?`;
    const first = sentence.search(/[^¿¡\s]/);
    if (first >= 0) sentence = sentence.slice(0, first) + sentence[first].toLocaleUpperCase('es-MX') + sentence.slice(first + 1);
    if (!/[.?!]$/.test(sentence)) sentence += '.';
    return sentence;
  }
}

if (typeof module !== 'undefined') module.exports = { SenaPhrasebook };
