import * as ed from "@noble/ed25519";

let cachedKey: Uint8Array | null = null;

function b64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i);
  return out;
}

export function setVerifyKey(publicKeyB64: string) {
  cachedKey = b64ToBytes(publicKeyB64);
}

export async function verifyAlertSignature(
  payload: Record<string, unknown>,
  signatureB64: string | undefined,
): Promise<boolean> {
  if (!signatureB64 || !cachedKey) return false;
  const body = JSON.stringify(payload, Object.keys(payload).sort());
  const message = new TextEncoder().encode(body);
  const signature = b64ToBytes(signatureB64);
  return ed.verify(signature, message, cachedKey);
}
