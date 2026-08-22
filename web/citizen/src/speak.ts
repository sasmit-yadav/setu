/** Read the signed alert copy with the OS voice. Not an LLM — the same
 * headline + body already on screen. Some browsers (Chrome) only start
 * speaking after a tap, which is why the PWA exposes a button. */

export function speechSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

function langTag(raw: string | undefined): string {
  const lang = (raw ?? "en").trim().toLowerCase();
  if (lang.startsWith("ml")) return "ml-IN";
  if (lang.startsWith("hi")) return "hi-IN";
  if (lang.startsWith("mr")) return "mr-IN";
  if (lang.startsWith("en")) return "en-IN";
  return lang;
}

function pickVoice(tag: string): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis.getVoices();
  const exact = voices.find((v) => v.lang.toLowerCase() === tag.toLowerCase());
  if (exact) return exact;
  const prefix = tag.slice(0, 2).toLowerCase();
  return voices.find((v) => v.lang.toLowerCase().startsWith(prefix)) ?? null;
}

export function stopSpeaking(): void {
  if (!speechSupported()) return;
  window.speechSynthesis.cancel();
}

export function speakAlert(opts: {
  severity: string;
  headline: string;
  body: string;
  lang?: string;
  onend?: () => void;
}): boolean {
  if (!speechSupported()) return false;
  stopSpeaking();
  const tag = langTag(opts.lang);
  const text = [opts.severity, opts.headline, opts.body]
    .map((part) => part.trim())
    .filter(Boolean)
    .join(". ");
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = tag;
  const voice = pickVoice(tag);
  if (voice) utterance.voice = voice;
  utterance.onend = () => opts.onend?.();
  utterance.onerror = () => opts.onend?.();
  // Some browsers populate voices only after the first query / voiceschanged.
  if (!voice && window.speechSynthesis.getVoices().length === 0) {
    window.speechSynthesis.addEventListener(
      "voiceschanged",
      () => {
        const later = pickVoice(tag);
        if (later) utterance.voice = later;
      },
      { once: true },
    );
  }
  window.speechSynthesis.speak(utterance);
  return true;
}
