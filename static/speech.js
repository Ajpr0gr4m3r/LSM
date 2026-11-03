'use strict';

// Keep the active utterance alive and finish it before speaking the next sign.
// Gestiona la voz con una cola breve y sin cortar el mensaje que ya está sonando.
class SenaSpeechQueue {
  // Conserva el sintetizador y prepara la consulta de voces instaladas.
  constructor(synthesis, Utterance, onError = () => {}) {
    this.synthesis = synthesis;
    this.Utterance = Utterance;
    this.onError = onError;
    this.pending = [];
    this.current = null;
    this.waiting = false;
    // Some browsers load installed voices asynchronously. Query them early,
    // then again at playback time rather than caching an empty first result.
    synthesis?.getVoices();
  }

  // Añade un texto no repetido y limita la cola para no acumular retraso de anuncios.
  enqueue(text, locale) {
    if (!text || !this.synthesis || !this.Utterance) return;
    if (this.current?.text === text && this.current.lang === locale) return;
    if (this.pending.some(item => item.text === text && item.locale === locale)) return;
    // Keep announcements near the live gesture instead of building a long lag.
    if (this.pending.length >= 4) this.pending.shift();
    this.pending.push({text, locale});
    this.playNext();
  }

  // Selecciona voz e idioma y reproduce el siguiente mensaje al terminar el anterior.
  playNext() {
    if (this.current || this.waiting || !this.pending.length) return;
    const {text, locale} = this.pending.shift();
    const utterance = new this.Utterance(text);
    const normalize = lang => String(lang || '').replaceAll('_', '-').toLowerCase();
    const desired = normalize(locale);
    const base = desired.split('-')[0];
    const voices = this.synthesis.getVoices();
    const voice = voices.find(v => v.localService && normalize(v.lang) === desired)
      || voices.find(v => v.localService && normalize(v.lang).split('-')[0] === base)
      || voices.find(v => normalize(v.lang) === desired)
      || voices.find(v => normalize(v.lang).split('-')[0] === base);
    utterance.lang = locale;
    utterance.rate = 1;
    utterance.pitch = 1;
    if (voice) utterance.voice = voice;
    this.current = utterance;
    const finish = error => {
      if (this.current !== utterance) return;
      this.current = null;
      this.waiting = true;
      if (error && !['canceled', 'interrupted'].includes(error)) this.onError(error);
      // Starting synchronously inside onend can stall speech in WebKit.
      setTimeout(() => { this.waiting = false; this.playNext(); }, 60);
    };
    utterance.onend = () => finish();
    utterance.onerror = event => finish(event.error || 'unknown');
    try {
      if (this.synthesis.paused) this.synthesis.resume();
      this.synthesis.speak(utterance);
    } catch (error) {
      finish(error.message || 'unknown');
    }
  }
}
