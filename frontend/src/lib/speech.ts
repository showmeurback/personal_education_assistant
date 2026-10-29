import { useCallback, useEffect, useRef, useState } from "react";

/* Голосовой ввод через Web Speech API браузера (Chrome, Edge, Safari).
   Распознавание выполняет сервис браузера, сервер приложения звук не получает. */

interface RecognitionAlternative { transcript: string }
interface RecognitionResult { isFinal: boolean; 0: RecognitionAlternative }
interface RecognitionEvent { resultIndex: number; results: ArrayLike<RecognitionResult> }
interface RecognitionErrorEvent { error: string }
interface Recognition {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((e: RecognitionEvent) => void) | null;
  onerror: ((e: RecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
type RecognitionCtor = new () => Recognition;

function recognitionCtor(): RecognitionCtor | null {
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

const ERRORS: Record<string, string> = {
  "not-allowed": "Нет доступа к микрофону. Разрешите его в настройках сайта (значок замка в адресной строке).",
  "service-not-allowed": "Браузер запретил распознавание речи на этой странице.",
  "audio-capture": "Микрофон не найден. Проверьте, что он подключён.",
  network: "Сервис распознавания речи браузера недоступен. Проверьте подключение к интернету.",
};

/**
 * Диктовка текста. onText получает распознанный текст: с final=false — промежуточный вариант
 * (пока человек говорит), с final=true — окончательную фразу.
 */
export function useSpeechInput(onText: (text: string, final: boolean) => void, onError: (message: string) => void) {
  const supported = recognitionCtor() !== null;
  const [listening, setListening] = useState(false);
  const recRef = useRef<Recognition | null>(null);
  const handlers = useRef({ onText, onError });
  useEffect(() => { handlers.current = { onText, onError }; });
  useEffect(() => () => { recRef.current?.abort(); }, []);

  /** Закончить запись: фраза, которую браузер ещё распознаёт, придёт в onText. */
  const stop = useCallback(() => { recRef.current?.stop(); }, []);
  /** Прервать запись без результата (текст уже забран, например при отправке сообщения). */
  const cancel = useCallback(() => {
    const rec = recRef.current;
    if (!rec) return;
    rec.onresult = null;
    rec.abort();
  }, []);

  const start = useCallback(() => {
    const Ctor = recognitionCtor();
    if (!Ctor || recRef.current) return;
    const rec = new Ctor();
    rec.lang = "ru-RU";
    rec.continuous = true;
    rec.interimResults = true;
    rec.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) handlers.current.onText(r[0].transcript.trim(), true);
        else interim += r[0].transcript;
      }
      handlers.current.onText(interim.trim(), false);
    };
    rec.onerror = (e) => {
      if (e.error === "no-speech" || e.error === "aborted") return;
      handlers.current.onError(ERRORS[e.error] ?? `Ошибка распознавания речи: ${e.error}`);
    };
    rec.onend = () => {
      recRef.current = null;
      setListening(false);
      handlers.current.onText("", false);
    };
    recRef.current = rec;
    try {
      rec.start();
    } catch {
      // браузер не дал начать запись (например, запись уже идёт в другой вкладке)
      recRef.current = null;
      handlers.current.onError("Не удалось включить микрофон. Закройте другие вкладки, где идёт запись, и попробуйте снова.");
      return;
    }
    setListening(true);
  }, []);

  return { supported, listening, start, stop, cancel };
}
