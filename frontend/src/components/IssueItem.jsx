import Pill from "./Pill.jsx";

/** One issue: title, severity and effort pills, optional explanation, and how to fix it. */
export default function IssueItem({ issue, showExplanation = false }) {
  return (
    <div className="issue">
      <div className="issue-head">
        <h4 className="issue-title">{issue.title}</h4>
        <div className="pill-row">
          <Pill tone={`severity-${issue.severity.toLowerCase()}`}>{issue.severity} severity</Pill>
          <Pill>{issue.effort} effort</Pill>
        </div>
      </div>
      {showExplanation && <p className="issue-text">{issue.explanation}</p>}
      <p className="issue-text">
        <strong>How to fix:</strong> {issue.how_to_fix}
      </p>
    </div>
  );
}
