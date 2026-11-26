const STEPS = [
  { title: "Enter your URL", text: "Paste the address of any public page. No account needed." },
  { title: "We crawl & analyze", text: "We read the page, its structured data and robots.txt, then run 6 groups of checks." },
  { title: "Get your GEO score", text: "See a score out of 100, how each dimension performs and which AI bots can read the page." },
  { title: "Fix what matters", text: "Start with the top fixes, ranked by impact versus effort." },
];

export default function HowItWorks() {
  return (
    <section className="section">
      <h2 className="section-heading">How it works</h2>
      <ol className="how-grid">
        {STEPS.map(({ title, text }, index) => (
          <li key={title} className="card how-step">
            <span className="how-number">{String(index + 1).padStart(2, "0")}</span>
            <h3 className="how-title">{title}</h3>
            <p className="muted">{text}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
