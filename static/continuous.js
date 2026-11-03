'use strict';
// Control de una tanda: un resultado repetido nunca cuenta como otra toma.
// Mantiene el contador y la identidad de una tanda, incluyendo pausa y descarte de respuestas repetidas.
class ContinuousCapture {
  // Inicializa una tanda inactiva con contador, límite y conjunto de tomas recibidas.
  constructor() { this.active = false; this.paused = false; this.count = 0; this.limit = 0; this.serial = 0; this.ids = new Set(); }
  // Valida entre 5 y 60 tomas e inicia una identidad nueva de tanda.
  start(limit) {
    if (!Number.isInteger(limit) || limit < 5 || limit > 60) throw new Error('Elige entre 5 y 60 tomas.');
    if (this.active) throw new Error('Ya hay una tanda en curso.');
    this.active = true; this.paused = false; this.count = 0; this.limit = limit; this.ids.clear();
    return ++this.serial;
  }
  // Cuenta una toma completa solo una vez y termina al alcanzar el objetivo.
  complete(id, serial) {
    if (!this.active || serial !== this.serial || this.ids.has(id)) return null;
    this.ids.add(id); this.count++;
    const done = this.count >= this.limit;
    if (done) this.active = false;
    return {count: this.count, limit: this.limit, done};
  }
  // Suspende la tanda e invalida su cuenta atrás anterior sin borrar tomas completas.
  pause() { if (this.active && !this.paused) { this.paused = true; this.serial++; } }
  // Reactiva la programación de tomas conservando contador y objetivo.
  resume() { if (this.active) this.paused = false; return this.serial; }
  // Cancela la tanda e invalida respuestas antiguas conservando el número de tomas completas.
  stop() { this.active = false; this.paused = false; this.serial++; }
  // Comprueba si una operación pertenece a la tanda activa y no pausada.
  current(serial) { return this.active && !this.paused && serial === this.serial; }
}
if (typeof module !== 'undefined') module.exports = ContinuousCapture;
