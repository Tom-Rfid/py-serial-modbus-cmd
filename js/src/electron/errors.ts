import type { PortCheck } from '../link/types';

/** Traduit une erreur d'ouverture serialport en état lisible. */
export function classifyOpenError(err: unknown): PortCheck {
  const text = err instanceof Error ? err.message : String(err);
  const low = text.toLowerCase();
  if (/access denied|access is denied|accès refusé|cannot lock port|resource temporarily unavailable|resource busy/.test(low)) {
    return { status: 'busy', message: 'déjà utilisé par un autre programme' };
  }
  if (/file not found|no such file|cannot find|introuvable/.test(low)) {
    return { status: 'missing', message: 'introuvable (débranché ?)' };
  }
  if (/permission denied/.test(low)) {
    return { status: 'error', message: "accès refusé (droits : groupe 'dialout' sous Linux)" };
  }
  return { status: 'error', message: text };
}
