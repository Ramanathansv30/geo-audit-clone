import { useState } from "react";

const ITEMS = [
  {
    question: "What is GEO?",
    answer:
      "Generative Engine Optimization (GEO) is the practice of making your pages easy for AI assistants such as ChatGPT, Claude, Perplexity and Gemini to find, understand and cite in their answers.",
  },
  {
    question: "What does this audit check?",
    answer:
      "Six dimensions: answer-first content, technical optimization, citation authority, AI comprehension, content freshness and content depth. It also checks whether robots.txt lets the main AI crawlers in.",
  },
  {
    question: "How is the score calculated?",
    answer:
      "Each dimension is the weighted average of its sub-scores, which come from fixed rules (no AI is used). The overall score is the weighted average of the six dimensions, from 0 to 100.",
  },
  {
    question: "How can I improve my score?",
    answer:
      "Work through the top fixes first. They are sorted by impact versus effort, so the quickest wins with the biggest effect are at the top.",
  },
];

export default function Faq() {
  const [openIndex, setOpenIndex] = useState(null);

  return (
    <section className="section">
      <h2 className="section-heading">Frequently asked questions</h2>
      <div className="faq-list">
        {ITEMS.map(({ question, answer }, index) => {
          const isOpen = openIndex === index;
          const panelId = `faq-panel-${index}`;
          return (
            <div key={question} className="card faq-item">
              <button
                type="button"
                className="faq-question"
                aria-expanded={isOpen}
                aria-controls={panelId}
                onClick={() => setOpenIndex(isOpen ? null : index)}
              >
                {question}
                <span className="faq-icon" aria-hidden="true" />
              </button>
              <p id={panelId} className="faq-answer muted" hidden={!isOpen}>
                {answer}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
