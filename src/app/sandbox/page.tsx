import type { Metadata } from "next";

import { SandboxApp } from "./SandboxApp";

export const metadata: Metadata = {
  title: "Sandbox",
  description:
    "The LunarForge browser sandbox connected to deterministic FastAPI services and schema-v1 events.",
};

export default function SandboxPage() {
  return <SandboxApp />;
}
