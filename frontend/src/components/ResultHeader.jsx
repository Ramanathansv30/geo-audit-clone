import { labelTone } from "../labels.js";
import Pill from "./Pill.jsx";
import ScoreRing from "./ScoreRing.jsx";

export default function ResultHeader({ report, onReset }) {
  const { title, final_url: finalUrl, summary, overall_score: score, label, geo_ready: geoReady } = report;

  return (
    <section className="card result-header">
      <ScoreRing score={score} label={label} />
      <div className="result-summary">
        <div className="result-badges">
          <span className={`label-text ${labelTone(label)}`}>{label}</span>
          {geoReady && <Pill tone="ready">GEO-Ready</Pill>}
        </div>
        <h1 className="result-title">{title || finalUrl}</h1>
        <a className="result-url" href={finalUrl} target="_blank" rel="noreferrer">
          {finalUrl}
        </a>
        <p className="result-text">{summary}</p>
      </div>
      <button type="button" className="button button-secondary" onClick={onReset}>
        New Analysis
      </button>
    </section>
  );
}
