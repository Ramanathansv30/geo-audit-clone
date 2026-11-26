const DATE_FORMAT = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });
const PLACEHOLDER = "—";

function footnote({ status, data }) {
  if (status === "loading") return "*Loading comparison values...";
  if (status === "error") return "*Comparison values are unavailable right now";
  if (data.is_sample) return "*Sample values";
  return `*Average of ${data.sample_size} reference sites, updated ${DATE_FORMAT.format(new Date(data.updated_at))}`;
}

/** benchmarks is { status: "loading" | "ready" | "error", data: Benchmarks | null }. */
export default function ComparisonStrip({ score, benchmarks }) {
  const { data } = benchmarks;
  const stats = [
    { label: "Your score", value: score },
    { label: "Reference average*", value: data?.industry_average ?? PLACEHOLDER },
    { label: "Top reference sites*", value: data?.top_sites ?? PLACEHOLDER },
  ];

  return (
    <section className="comparison">
      <div className="comparison-grid">
        {stats.map(({ label, value }) => (
          <div key={label} className="card stat">
            <span className="stat-value">{value}</span>
            <span className="stat-label">{label}</span>
          </div>
        ))}
      </div>
      <p className="footnote">{footnote(benchmarks)}</p>
    </section>
  );
}
