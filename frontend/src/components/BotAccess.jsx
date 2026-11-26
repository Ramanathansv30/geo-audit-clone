import Pill from "./Pill.jsx";

export default function BotAccess({ bots }) {
  return (
    <section className="card">
      <h2 className="section-title">AI bot access</h2>
      <ul className="bot-list">
        {bots.map(({ bot, allowed }) => (
          <li key={bot} className="bot">
            <span className="bot-name">{bot}</span>
            <Pill tone={allowed ? "allowed" : "blocked"}>{allowed ? "Allowed" : "Blocked"}</Pill>
          </li>
        ))}
      </ul>
    </section>
  );
}
