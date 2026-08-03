import { requireUser } from "@/lib/auth/session";

export default async function SandboxLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  await requireUser("/sandbox");
  return children;
}
