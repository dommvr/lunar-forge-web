import type { Metadata } from "next";

import { PolicyPage } from "@/components/PolicyPage";

export const metadata: Metadata = { title: "Security" };

export default function SecurityPage() {
  return (
    <PolicyPage title="Security overview" updated="August 2, 2026">
      <section>
        <h2>Authentication baseline</h2>
        <p>
          Sandbox and administration routes require a server-verified Supabase
          session. Administrator access additionally requires a server-controlled
          role assignment and a verified TOTP factor.
        </p>
      </section>
      <section>
        <h2>Current limitations</h2>
        <p>
          This phase does not run agent workloads or provide a hosted isolation
          boundary. The sandbox interface remains a scripted preview; backend,
          runtime, and preview-gateway security controls are not deployed yet.
        </p>
      </section>
      <section>
        <h2>Reporting</h2>
        <p>
          <strong>Owner review required:</strong> add a monitored security contact
          and disclosure process before public launch. Do not include secrets or
          sensitive project data in a report sent through an unverified channel.
        </p>
      </section>
    </PolicyPage>
  );
}
