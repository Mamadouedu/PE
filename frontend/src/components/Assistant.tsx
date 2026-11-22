import { useEffect, useRef, useState } from "react";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

const QUESTIONS_RAPIDES = [
  "Comment chiffrer une offre ?",
  "Explique-moi le niveau de validation",
  "Quels sont les 8 contrôles avant envoi ?",
  "Comment demander une dérogation ?",
  "Comment publier une nouvelle version du référentiel ?",
];

export function Assistant() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Bonjour ! Je suis l'assistant du configurateur Akiem. Je peux t'expliquer le chiffrage, le niveau de validation, les contrôles, les dérogations ou le référentiel. Par quoi veux-tu commencer ?",
    },
  ]);
  const [brouillon, setBrouillon] = useState("");
  const [enCours, setEnCours] = useState(false);
  const [moteur, setMoteur] = useState<string | null>(null);
  const finRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, enCours]);

  async function envoyer(texte: string) {
    const t = texte.trim();
    if (!t || enCours) return;

    const nouvelHistorique: Message[] = [...messages, { role: "user", content: t }];
    setMessages(nouvelHistorique);
    setBrouillon("");
    setEnCours(true);

    try {
      const reponse = await fetch(`${BASE_URL}/api/v1/assistant/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: nouvelHistorique.filter((m) => m.role === "user" || m.role === "assistant"),
        }),
      });
      if (!reponse.ok) throw new Error(`HTTP ${reponse.status}`);
      const data = (await reponse.json()) as { message: string; moteur: string };
      setMoteur(data.moteur);
      setMessages((h) => [...h, { role: "assistant", content: data.message }]);
    } catch (e) {
      setMessages((h) => [
        ...h,
        { role: "assistant", content: "Impossible de joindre l'assistant. Vérifie que l'API tourne." },
      ]);
    } finally {
      setEnCours(false);
    }
  }

  return (
    <section className="registre assistant">
      <header className="registre-entete">
        <div>
          <h2>Assistant du KAM</h2>
          <p className="registre-sous-titre">
            M3-08 : pose tes questions sur le chiffrage, les contrôles, les dérogations, le référentiel.
            {moteur && <> Moteur : <code>{moteur}</code>.</>}
          </p>
        </div>
      </header>

      <div className="assistant-chat">
        <div className="assistant-messages">
          {messages.map((m, i) => (
            <div key={i} className={`assistant-msg assistant-msg-${m.role}`}>
              <div className="assistant-msg-bulle">{m.content}</div>
            </div>
          ))}
          {enCours && (
            <div className="assistant-msg assistant-msg-assistant">
              <div className="assistant-msg-bulle assistant-msg-ecrit">L'assistant écrit…</div>
            </div>
          )}
          <div ref={finRef} />
        </div>

        <div className="assistant-suggestions">
          {QUESTIONS_RAPIDES.map((q) => (
            <button key={q} type="button" className="suggestion" onClick={() => envoyer(q)} disabled={enCours}>
              {q}
            </button>
          ))}
        </div>

        <form
          className="assistant-input"
          onSubmit={(e) => {
            e.preventDefault();
            envoyer(brouillon);
          }}
        >
          <input
            type="text"
            value={brouillon}
            onChange={(e) => setBrouillon(e.target.value)}
            placeholder="Pose ta question…"
            disabled={enCours}
          />
          <button type="submit" className="bouton-principal" disabled={enCours || !brouillon.trim()}>
            Envoyer
          </button>
        </form>
      </div>
    </section>
  );
}
