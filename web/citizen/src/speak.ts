/** Read the signed alert copy with the OS voice. Not an LLM — the same
 * headline + body already on screen. Auto-starts when the alert opens;
 * the button re-reads if the browser blocked autoplay or the villager
 * wants it again. Chrome only unlocks speech after a tap, so login
 * submits call unlockSpeech() while that gesture is still live. */

let speakGen = 0;

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
  speakGen += 1;
  if (!speechSupported()) return;
  window.speechSynthesis.cancel();
}

/** Spend the current tap so a later auto-read is more likely to start. */
export function unlockSpeech(): void {
  if (!speechSupported()) return;
  const priming = new SpeechSynthesisUtterance(" ");
  priming.volume = 0;
  priming.rate = 10;
  window.speechSynthesis.speak(priming);
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
  const gen = (speakGen += 1);
  window.speechSynthesis.cancel();
  window.speechSynthesis.resume();
  const tag = langTag(opts.lang);
  const text = [opts.severity, opts.headline, opts.body]
    .map((part) => part.trim())
    .filter(Boolean)
    .join(". ");
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = tag;
  const voice = pickVoice(tag);
  if (voice) utterance.voice = voice;
  const done = () => {
    if (gen !== speakGen) return;
    opts.onend?.();
  };
  utterance.onend = done;
  utterance.onerror = done;
  if (!voice && window.speechSynthesis.getVoices().length === 0) {
    window.speechSynthesis.addEventListener(
      "voiceschanged",
      () => {
        if (gen !== speakGen) return;
        const later = pickVoice(tag);
        if (later) utterance.voice = later;
      },
      { once: true },
    );
  }
  window.speechSynthesis.speak(utterance);
  window.setTimeout(() => {
    if (gen !== speakGen) return;
    if (!window.speechSynthesis.speaking && !window.speechSynthesis.pending) {
      done();
    }
  }, 400);
  return true;
}
