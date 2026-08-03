import type { Metadata } from "next";

import { PolicyPage } from "@/components/PolicyPage";

export const metadata: Metadata = { title: "Privacy" };

export default function PrivacyPage() {
  return (
    <PolicyPage title="Privacy notice" updated="August 2, 2026">
      <section>
        <h2>Current scope</h2>
        <p>
          This is a pre-launch placeholder for owner review. The public site
          serves product and documentation pages. Invited accounts use Supabase
          Auth for identity and session cookies when authentication is configured.
        </p>
      </section>
      <section>
        <h2>Sandbox data</h2>
        <p>
          The browser sandbox is still a deterministic frontend preview. Hosted
          execution, project persistence, model-provider handling, analytics, and
          production retention are not connected in this phase.
        </p>
      </section>
      <section>
        <h2>Before launch</h2>
        <p>
          The owner must replace this draft with jurisdiction-appropriate terms
          covering deployed providers, retention, deletion, logs, cookies, and a
          working privacy contact.
        </p>
      </section>
    </PolicyPage>
  );
}
