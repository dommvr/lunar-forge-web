import type { Metadata } from "next";

import { SandboxApp } from "./SandboxApp";

export const metadata: Metadata = {
  title: "Sandbox",
  description:
    "A disposable, time-boxed LunarForge session in the browser. Commands run inside the container and still pause for your approval.",
};

export default function SandboxPage() {
  return <SandboxApp />;
}
