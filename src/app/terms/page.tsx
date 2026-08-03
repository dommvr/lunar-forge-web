import type { Metadata } from "next";

import { PolicyPage } from "@/components/PolicyPage";

export const metadata: Metadata = { title: "Terms" };

export default function TermsPage() {
  return (
    <PolicyPage title="Terms of use" updated="August 2, 2026">
      <section>
        <h2>Draft status</h2>
        <p>
          These are concise placeholder terms for owner review, not final launch
          terms. Access to private surfaces is limited to individually invited
          accounts and may be suspended or revoked by the owner.
        </p>
      </section>
      <section>
        <h2>Acceptable use</h2>
        <p>
          Do not attempt unauthorized access, interfere with the service, evade
          limits, introduce malicious content, or use another person’s account.
          Keep account credentials private and report suspected compromise.
        </p>
      </section>
      <section>
        <h2>No hosted-agent promise yet</h2>
        <p>
          Hosted execution is unfinished. Availability, support, warranties,
          liability, governing law, deletion, and service-provider terms must be
          reviewed and completed by the owner before launch.
        </p>
      </section>
    </PolicyPage>
  );
}
