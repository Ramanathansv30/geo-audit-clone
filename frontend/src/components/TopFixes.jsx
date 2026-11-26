import IssueItem from "./IssueItem.jsx";

export default function TopFixes({ issues }) {
  return (
    <section className="card">
      <h2 className="section-title">Fix these first</h2>
      {issues.length === 0 ? (
        <p className="muted">No major issues found.</p>
      ) : (
        <ol className="fix-list">
          {issues.map((issue, index) => (
            <li key={issue.title} className="fix">
              <span className="fix-number">{index + 1}</span>
              <IssueItem issue={issue} />
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
