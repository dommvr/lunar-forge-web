import React from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

function App() {
  return <main><h1>Ready to forge.</h1></main>;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>,
);
