import Pill from "./Pill.jsx";

const PLATFORMS = ["ChatGPT", "Perplexity", "Claude", "Gemini", "Google AI"];

export default function PlatformStrip() {
  return (
    <section className="platform-strip">
      <p className="eyebrow">Checks readiness across</p>
      <div className="pill-row">
        {PLATFORMS.map((platform) => (
          <Pill key={platform}>{platform}</Pill>
        ))}
      </div>
    </section>
  );
}
