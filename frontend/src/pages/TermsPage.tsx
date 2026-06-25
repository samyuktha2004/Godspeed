import { Link } from '@tanstack/react-router'

export default function TermsPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <Link to="/" className="mb-8 inline-flex items-center gap-1.5 text-sm text-brand hover:underline">
        ← Back to Godspeed
      </Link>

      <h1 className="mt-4 text-3xl font-semibold">Terms of Service</h1>
      <p className="mt-1 text-sm text-stone-400">
        Effective date: [DATE] &nbsp;·&nbsp; Version 1.0
      </p>
      <p className="mt-2 text-sm text-stone-500">
        These Terms govern your access to and use of the Godspeed platform. By registering or using the
        Service you agree to be bound by them. If you are accepting on behalf of a company you represent
        that you have authority to do so.
      </p>

      <div className="mt-8 space-y-8 text-sm text-stone-700 dark:text-stone-300">

        {/* 1 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">1. Parties</h2>
          <p>
            "<strong>Godspeed</strong>" means [Company legal name], a company incorporated in India.
            "<strong>Customer</strong>" or "<strong>you</strong>" means the organisation or individual who
            has registered for the Service. Together, "Parties".
          </p>
        </section>

        {/* 2 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">2. The Service</h2>
          <p>
            Godspeed provides a B2B AI-powered knowledge-management platform that ingests content from
            third-party sources (Jira, Confluence, GitHub, Slack, Notion, and others) and makes it
            searchable through a natural-language interface. The specific features available depend on
            your subscription tier.
          </p>
        </section>

        {/* 3 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">3. Licence & Permitted Use</h2>
          <p>
            Subject to these Terms and timely payment of fees, we grant you a limited, non-exclusive,
            non-transferable, revocable licence to access and use the Service for your internal business
            purposes. You may not:
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>Resell, sublicence, or otherwise commercialise the Service to third parties.</li>
            <li>Reverse-engineer, decompile, or attempt to extract source code.</li>
            <li>Use the Service to store or process data in violation of applicable law.</li>
            <li>Upload malware, spam, or content that infringes third-party intellectual property rights.</li>
            <li>Attempt to gain unauthorised access to other customers' workspaces.</li>
          </ul>
        </section>

        {/* 4 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">4. Customer Data</h2>
          <p>
            You retain full ownership of all data, documents, and content you upload or that Godspeed
            ingests from your authorised third-party integrations ("<strong>Customer Data</strong>").
            You grant Godspeed a limited, worldwide licence to process Customer Data solely to provide
            and improve the Service as described in our{' '}
            <Link to="/privacy" className="text-brand hover:underline">Privacy Policy</Link>.
            You are responsible for ensuring you have the right to connect third-party sources and share
            the resulting content with Godspeed.
          </p>
        </section>

        {/* 5 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">5. Intellectual Property</h2>
          <p>
            Godspeed and its licensors own all intellectual property rights in the Service, including
            the software, models, algorithms, UI, and documentation. Nothing in these Terms transfers
            any IP to you. Feedback you provide may be used by us without restriction or compensation.
            AI-generated responses produced by the Service are provided as informational output; we
            make no representation that they are free of third-party IP claims.
          </p>
        </section>

        {/* 6 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">6. Confidentiality</h2>
          <p>
            Each party will protect the other's confidential information with at least the same care
            it uses for its own confidential information, but no less than reasonable care. Godspeed
            treats your Customer Data as confidential. This obligation does not apply to information
            that is or becomes publicly available, was already known, or is independently developed
            without reference to the confidential information.
          </p>
        </section>

        {/* 7 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">7. Fees & Payment</h2>
          <p>
            Subscription fees are as set out in the applicable order form or pricing page. Fees are
            invoiced in advance on a monthly or annual basis and are non-refundable except as required
            by law or as expressly stated herein. Unpaid amounts accrue interest at 1.5% per month or
            the maximum permitted by law, whichever is lower. We may suspend access if payment is
            overdue by more than 15 days after written notice.
          </p>
        </section>

        {/* 8 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">8. Warranties & Disclaimers</h2>
          <p>
            We warrant that the Service will perform materially in accordance with its documentation
            under normal use. <strong>Except as expressly stated, the Service is provided "as is"
            and we disclaim all other warranties, express or implied, including merchantability,
            fitness for a particular purpose, and non-infringement.</strong> AI-generated outputs
            may be inaccurate; you are responsible for independently verifying any output before
            relying on it for decisions.
          </p>
        </section>

        {/* 9 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">9. Limitation of Liability</h2>
          <p>
            To the maximum extent permitted by applicable law:
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>
              Neither party will be liable for indirect, incidental, consequential, special, or
              exemplary damages, loss of profits, or loss of data, even if advised of the possibility.
            </li>
            <li>
              Godspeed's total aggregate liability arising out of or relating to these Terms will not
              exceed the fees paid by you in the 12 months immediately preceding the claim.
            </li>
          </ul>
        </section>

        {/* 10 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">10. Indemnification</h2>
          <p>
            You will indemnify, defend, and hold harmless Godspeed and its officers, directors, and
            employees from any third-party claims, losses, or expenses (including reasonable legal fees)
            arising from: (a) your breach of these Terms; (b) your violation of applicable law;
            (c) your Customer Data infringing a third party's rights.
          </p>
        </section>

        {/* 11 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">11. Term & Termination</h2>
          <p>
            These Terms commence on your registration date and continue until terminated. Either party
            may terminate for convenience with 30 days' written notice. Either party may terminate
            immediately for material breach not cured within 15 days of notice, or upon the other's
            insolvency. Upon termination, your access ceases and we will delete Customer Data within
            30 days (except where retention is required by law). You may export your data before
            termination using the tools in the Admin panel.
          </p>
        </section>

        {/* 12 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">12. Data Protection</h2>
          <p>
            Each party will comply with applicable data protection law including the DPDPA.
            Our <Link to="/privacy" className="text-brand hover:underline">Privacy Policy</Link> forms
            part of these Terms and governs the processing of personal data. Where Godspeed processes
            personal data on your behalf as a Data Processor, we will act only on your documented
            instructions.
          </p>
        </section>

        {/* 13 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">13. Governing Law & Dispute Resolution</h2>
          <p>
            These Terms are governed by the laws of India. The parties will attempt to resolve disputes
            informally for 30 days before initiating formal proceedings. Unresolved disputes will be
            settled by binding arbitration under the Arbitration and Conciliation Act, 1996, seated in
            [City], India, conducted in English before a sole arbitrator. Notwithstanding this, either
            party may seek interim injunctive relief from a competent court.
          </p>
        </section>

        {/* 14 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">14. Changes to Terms</h2>
          <p>
            We may update these Terms from time to time. For material changes we will give at least
            30 days' notice by email. Continued use of the Service after the effective date constitutes
            acceptance. If you do not agree, you may terminate as described in §11.
          </p>
        </section>

        {/* 15 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">15. General</h2>
          <ul className="list-disc space-y-1 pl-5">
            <li><strong>Entire agreement:</strong> these Terms and the Privacy Policy constitute the entire agreement between the parties on this subject matter.</li>
            <li><strong>Severability:</strong> if any provision is unenforceable, it will be modified to the minimum extent necessary; the rest of the Terms remain in effect.</li>
            <li><strong>Waiver:</strong> failure to enforce any right is not a waiver of future enforcement.</li>
            <li><strong>Assignment:</strong> you may not assign these Terms without our prior written consent. We may assign in connection with a merger, acquisition, or sale of assets.</li>
            <li><strong>Force majeure:</strong> neither party is liable for delays caused by circumstances beyond their reasonable control.</li>
          </ul>
        </section>

        {/* 16 */}
        <section>
          <h2 className="mb-2 text-base font-semibold">16. Contact</h2>
          <p>
            Legal notices: <a href="mailto:legal@[domain]" className="text-brand hover:underline">legal@[domain]</a><br />
            Registered address: [Company legal name, full address]
          </p>
        </section>

      </div>
    </div>
  )
}
