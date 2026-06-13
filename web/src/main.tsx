import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router";
import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import "@xyflow/react/dist/style.css";
import "./index.css";
import { App } from "./App";

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root element #root not found");
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
