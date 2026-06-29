import { Link } from '@tanstack/react-router'

export default function PrivacyPolicyPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <Link to="/" className="mb-8 inline-flex items-center gap-1.5 text-sm text-brand hover:underline">
        ← Back to Godspeed
      </Link>

      <h1 className="mt-4 text-3xl font-semibold">Privacy Policy</h1>
      <p className="mt-1 text-sm text-stone-400">
        Effective date: [DATE] &nbsp;·&nbsp; Version 1.0
      </p>
      <p className="mt-2 text-sm text-stone-500">
        This policy describes how Godspeed ("<strong>we</strong>", "<strong>us</strong>", "<strong>our</strong>")
        collects, uses, and protects personal data when you use our knowledge-management platform
        ("<strong>Service</strong>"). It is issued under India's{' '}
        <strong>Digital Personal Data Protection Act, 2023 (DPDPA)</strong> and its associated Rules.
      </p>

      <div className="mt-8 space-y-8 text-sm text-stone-700 dark:text-stone-300">

        {/* 1 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">1. Data Fiduciary</h2>
          <p>
            [Company legal name], a company incorporated under the Companies Act, 2013, with registered
            office at [address], India ("<strong>Godspeed</strong>" / "<strong>Data Fiduciary</strong>").
            CIN: [CIN]. Contact: <a href="mailto:privacy@[domain]" className="text-brand hover:underline">privacy@[domain]</a>.
          </p>
        </section>

        {/* 2 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">2. Personal Data We Collect</h2>
          <div className="overflow-x-auto rounded-lg border border-surface-subtle">
            <table className="w-full text-xs">
              <thead className="bg-stone-50 dark:bg-stone-800">
                <tr>
                  <th className="px-4 py-2 text-left font-medium text-stone-600 dark:text-stone-300">Category</th>
                  <th className="px-4 py-2 text-left font-medium text-stone-600 dark:text-stone-300">Data elements</th>
                  <th className="px-4 py-2 text-left font-medium text-stone-600 dark:text-stone-300">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-subtle">
                {[
                  ['Account data', 'Full name, work email, company name, password hash, role', 'Provided by you at registration'],
                  ['Usage data', 'Search queries, pages visited, session timestamps, feature interactions', 'Automatically collected'],
                  ['Device & log data', 'IP address, browser type, OS, referring URL, error logs', 'Automatically collected'],
                  ['Integrated source content', 'Documents, tickets, and metadata from Jira, Confluence, GitHub, Slack, Notion (as configured by your workspace admin)', 'Third-party integrations you authorise'],
                  ['Communication data', 'Support emails, feedback submissions', 'Provided by you'],
                ].map(([cat, elems, src]) => (
                  <tr key={cat} className="align-top">
                    <td className="px-4 py-2 font-medium">{cat}</td>
                    <td className="px-4 py-2 text-stone-500 dark:text-stone-400">{elems}</td>
                    <td className="px-4 py-2 text-stone-500 dark:text-stone-400">{src}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-stone-500">
            We practise <strong>data minimisation</strong>: we collect only what is necessary for the stated purpose.
          </p>
        </section>

        {/* 3 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">3. How We Use Your Data</h2>
          <ul className="list-disc space-y-1.5 pl-5">
            <li><strong>Service provision:</strong> create and manage your workspace, authenticate you, and fulfil queries you submit.</li>
            <li><strong>Knowledge indexing:</strong> ingest and index content from authorised third-party sources so you can search it.</li>
            <li><strong>Security & integrity:</strong> detect abuse, investigate incidents, enforce our Terms of Service, and comply with applicable law.</li>
            <li><strong>Communications:</strong> send transactional emails (invite links, password resets, data export links) and — with your separate consent — product updates.</li>
            <li><strong>Product improvement:</strong> aggregated, anonymised analytics to understand feature usage and improve the Service.</li>
          </ul>
          <p className="mt-2 text-xs text-stone-500">
            Lawful basis (DPDPA §4): processing is pursuant to your consent given at registration or is necessary
            to fulfil the contract for the Service.
          </p>
        </section>

        {/* 4 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">4. Sharing & Third-Party Processors</h2>
          <p className="mb-2">
            We do not sell your personal data. We share it only as described below:
          </p>
          <ul className="list-disc space-y-1.5 pl-5">
            <li><strong>Anthropic (Claude API):</strong> your query text is sent to generate answers. Queries are not used to train third-party models.</li>
            <li><strong>Supabase (PostgreSQL, Auth &amp; Storage):</strong> stores user accounts, workspace and document metadata, and ingestion job records.</li>
            <li><strong>Neo4j:</strong> stores the knowledge graph (entities and relationships extracted from your ingested documents).</li>
            <li><strong>Qdrant:</strong> stores vector embeddings of document chunks to power semantic search.</li>
            <li><strong>Redis:</strong> stores session tokens, recent query history, and transient cache.</li>
            <li><strong>Hosting:</strong> the application runs on Hugging Face Spaces (or your deployment's cloud host). Data may be processed in regions outside India; we rely on Standard Contractual Clauses or equivalent safeguards.</li>
            <li><strong>Email delivery:</strong> transactional emails (invites, data exports, notifications) are sent via the operator-configured SMTP provider.</li>
            <li><strong>Legal &amp; safety:</strong> if required by a court order, government authority, or to protect rights and safety.</li>
          </ul>
          <p className="mt-2 text-xs text-stone-500">
            Document embedding (BGE-M3) and entity extraction (GLiNER) run locally within our own
            infrastructure and are not shared with any third party. All sub-processors are contractually
            bound to process data only on our instructions and to implement reasonable security measures.
          </p>
        </section>

        {/* 5 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">5. Data Retention</h2>
          <ul className="list-disc space-y-1.5 pl-5">
            <li><strong>Account data:</strong> retained for the duration of your subscription plus 90 days after termination to allow for disputes, then deleted.</li>
            <li><strong>Search query logs:</strong> retained for 12 months for audit and security purposes, then purged.</li>
            <li><strong>Indexed source content:</strong> retained while the integration is active; deleted within 30 days of disconnecting a source or deleting your workspace.</li>
            <li><strong>Billing records:</strong> retained for 8 years as required under Indian accounting law.</li>
          </ul>
        </section>

        {/* 6 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">6. Your Rights under DPDPA</h2>
          <p className="mb-3">
            As a Data Principal you have the following rights, exercisable at any time from{' '}
            <Link to="/settings" className="text-brand hover:underline">Settings → Privacy & Data</Link>
            {' '}or by emailing <a href="mailto:privacy@[domain]" className="text-brand hover:underline">privacy@[domain]</a>:
          </p>
          <div className="space-y-3 rounded-lg border border-surface-subtle p-4">
            {[
              ['Right to Information (§11)', 'Request a summary of the personal data we hold about you and the processing purposes.'],
              ['Right to Correction & Erasure (§12)', 'Request correction of inaccurate data or erasure of data no longer necessary for the original purpose. We will fulfil within 30 days.'],
              ['Right to Grievance Redressal (§13)', 'Raise a grievance with our DPO; we will acknowledge within 48 hours and resolve within 30 days.'],
              ['Right to Nominate (§14)', 'Nominate another individual to exercise these rights on your behalf in the event of death or incapacity.'],
              ['Right to Withdraw Consent', 'Withdraw consent at any time; withdrawal does not affect the lawfulness of prior processing. Withdrawal may limit your ability to use the Service.'],
            ].map(([right, desc]) => (
              <div key={right as string}>
                <p className="font-medium">{right}</p>
                <p className="mt-0.5 text-xs text-stone-500">{desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* 7 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">7. Security</h2>
          <p>
            We implement industry-standard safeguards including AES-256 encryption at rest, TLS 1.2+ in transit,
            role-based access controls, continuous monitoring, and annual penetration testing. In the event of a
            personal data breach, we will notify the Data Protection Board of India (DPBI) within 72 hours and
            affected Data Principals without undue delay, as required by DPDPA §8(6).
          </p>
        </section>

        {/* 8 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">8. Children's Data</h2>
          <p>
            The Service is intended for business use and is not directed at individuals under 18 years of age.
            We do not knowingly process personal data of minors. If you believe we have inadvertently done so,
            please contact us immediately.
          </p>
        </section>

        {/* 9 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">9. Cookies & Tracking</h2>
          <p>
            We use strictly necessary session cookies to maintain authentication. We do not use third-party
            advertising cookies. Our self-hosted analytics use a first-party cookie that does not track you
            across other websites. You may clear cookies at any time via your browser settings.
          </p>
        </section>

        {/* 10 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">10. Data Protection Officer</h2>
          <p>
            [DPO Name], [Title]<br />
            Email: <a href="mailto:dpo@[domain]" className="text-brand hover:underline">dpo@[domain]</a><br />
            Address: [Registered address]
          </p>
          <p className="mt-2 text-xs text-stone-500">
            If your grievance is not resolved within 30 days, you may file a complaint with the{' '}
            <strong>Data Protection Board of India (DPBI)</strong> via the portal designated by MeitY.
          </p>
        </section>

        {/* 11 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">11. Changes to This Policy</h2>
          <p>
            We will notify you of material changes by email and by updating the effective date above. Continued
            use of the Service after the updated policy takes effect constitutes acceptance. For changes that
            require fresh consent under DPDPA, we will present an explicit notice before you continue using the Service.
          </p>
        </section>

        {/* 12 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">12. Contact</h2>
          <p>
            For any privacy queries: <a href="mailto:privacy@[domain]" className="text-brand hover:underline">privacy@[domain]</a><br />
            For data rights requests: <Link to="/settings" className="text-brand hover:underline">Settings → Privacy & Data</Link>
          </p>
        </section>

      </div>
    </div>
  )
}
