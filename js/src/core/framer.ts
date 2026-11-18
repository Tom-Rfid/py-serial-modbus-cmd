/**
 * core/framer.ts — Découpage des octets reçus en trames.
 *
 * Le port série livre les octets par morceaux de taille quelconque. On les
 * accumule, et une trame est considérée comme terminée quand rien n'est
 * arrivé pendant `gapMs` millisecondes. Même règle que la version Python
 * (SerialLink._reader).
 *
 *   octets : AA 55 01 ......(silence > gapMs)...... AA 55 02
 *   trames : [AA 55 01]                             [AA 55 02]
 *
 * Fonctionnement : chaque morceau reçu relance un minuteur de `gapMs` ;
 * quand le minuteur arrive au bout, la trame accumulée est publiée.
 */
export class FrameAssembler {
  private buf: number[] = [];          // octets de la trame en cours
  private timer: ReturnType<typeof setTimeout> | null = null;   // minuteur de fin de trame

  constructor(
    private readonly onFrame: (frame: Uint8Array) => void,
    public gapMs = 20,
  ) {}

  /** Ajoute des octets reçus et relance le minuteur de fin de trame. */
  push(chunk: Uint8Array): void {
    if (!chunk.length) return;
    this.buf.push(...chunk);
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => this.flush(), this.gapMs);
  }

  /** Publie immédiatement la trame en cours (si non vide). */
  flush(): void {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    if (this.buf.length) {
      const frame = Uint8Array.from(this.buf);
      this.buf = [];
      this.onFrame(frame);
    }
  }

  /** Oublie la trame en cours sans la publier (nouvelle connexion). */
  reset(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    this.buf = [];
  }
}
