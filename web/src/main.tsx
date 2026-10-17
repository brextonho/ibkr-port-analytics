import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./chartSetup";
import "gridjs/dist/theme/mermaid.css";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
