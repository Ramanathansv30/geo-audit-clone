export default function Hero({ url, onUrlChange, onSubmit, loading, error }) {
  function handleSubmit(event) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <section className="hero">
      <h1 className="hero-title">Free GEO Audit</h1>
      <p className="hero-subtitle">Analyze your website's readiness for AI search engines.</p>
      <form className="audit-form" onSubmit={handleSubmit} noValidate>
        <label htmlFor="audit-url" className="visually-hidden">
          Page URL
        </label>
        <input
          id="audit-url"
          className="audit-input"
          type="text"
          inputMode="url"
          autoComplete="url"
          placeholder="https://example.com/your-page"
          value={url}
          onChange={(event) => onUrlChange(event.target.value)}
          disabled={loading}
        />
        <button type="submit" className="button" disabled={loading}>
          {loading ? "Analyzing..." : "Analyze"}
        </button>
      </form>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
