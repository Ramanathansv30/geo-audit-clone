import { labelTone } from "../labels.js";
import IssueItem from "./IssueItem.jsx";
import ScoreRing from "./ScoreRing.jsx";

export default function DimensionCard({ dimension }) {
  const { name, score, label, sub_scores: subScores, issues } = dimension;

  return (
    <article className="card dimension">
      <header className="dimension-head">
        <div>
          <h3 className="dimension-name">{name}</h3>
          <span className={`label-text ${labelTone(label)}`}>{label}</span>
        </div>
        <ScoreRing score={score} label={label} size={64} />
      </header>

      <table className="sub-scores">
        <tbody>
          {subScores.map((sub) => (
            <tr key={sub.key}>
              <th scope="row">{sub.name}</th>
              <td className="sub-score-value">{sub.score ?? "—"}</td>
              <td className="sub-score-detail">{sub.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {issues.length === 0 ? (
        <p className="muted">No issues found.</p>
      ) : (
        <div className="issue-list">
          {issues.map((issue) => (
            <IssueItem key={issue.title} issue={issue} showExplanation />
          ))}
        </div>
      )}
    </article>
  );
}
