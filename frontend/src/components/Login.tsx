import { useState } from "react";
import { login } from "../api/auth";

const COMPTES_DEMO = [
  { email: "admin@akiem.com", mdp: "admin", role: "ADMIN", nom: "Admin Akiem" },
  { email: "direction@akiem.com", mdp: "direction", role: "DIRECTION", nom: "Direction" },
  { email: "head@akiem.com", mdp: "pricing", role: "PRICING", nom: "Head of Pricing" },
  { email: "kam1@akiem.com", mdp: "kam", role: "KAM", nom: "KAM France" },
  { email: "kam2@akiem.com", mdp: "kam", role: "KAM", nom: "KAM Allemagne" },
  { email: "kam3@akiem.com", mdp: "kam", role: "KAM", nom: "KAM Pologne" },
];

interface Props {
  onConnecte: () => void;
}

export function Login({ onConnecte }: Props) {
  const [email, setEmail] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  async function soumettre(e: React.FormEvent) {
    e.preventDefault();
    setEnCours(true);
    setErreur(null);
    try {
      await login(email, motDePasse);
      onConnecte();
    } catch (err) {
      setErreur(err instanceof Error ? err.message : "Échec de connexion");
    } finally {
      setEnCours(false);
    }
  }

  function utiliserCompteDemo(compte: typeof COMPTES_DEMO[0]) {
    setEmail(compte.email);
    setMotDePasse(compte.mdp);
  }

  return (
    <div className="login-page">
      <div className="login-carte">
        <h1>Plateforme Pricing Akiem</h1>
        <p className="login-sous-titre">Connecte-toi pour accéder au configurateur.</p>

        <form className="login-form" onSubmit={soumettre}>
          <label>
            E-mail
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoFocus
              required
              placeholder="vous@akiem.com"
            />
          </label>
          <label>
            Mot de passe
            <input
              type="password"
              value={motDePasse}
              onChange={(e) => setMotDePasse(e.target.value)}
              required
            />
          </label>
          {erreur && <div className="erreur">{erreur}</div>}
          <button type="submit" className="bouton-principal" disabled={enCours || !email || !motDePasse}>
            {enCours ? "Connexion…" : "Se connecter"}
          </button>
        </form>

        <details className="login-demo">
          <summary>Comptes de démonstration</summary>
          <p className="registre-sous-titre" style={{ marginTop: 8 }}>
            Clique sur un compte pour remplir le formulaire. Chaque rôle a son niveau d'accès.
          </p>
          <ul className="login-demo-liste">
            {COMPTES_DEMO.map((c) => (
              <li key={c.email}>
                <button type="button" className="login-demo-bouton" onClick={() => utiliserCompteDemo(c)}>
                  <strong>{c.nom}</strong>
                  <span className={`badge-role badge-role-${c.role}`}>{c.role}</span>
                  <span className="login-demo-email">{c.email}</span>
                  <code>mdp : {c.mdp}</code>
                </button>
              </li>
            ))}
          </ul>
        </details>
      </div>
    </div>
  );
}
